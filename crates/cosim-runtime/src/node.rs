// SPDX-License-Identifier: Apache-2.0

//! Process nodes: dependency leases, readiness states and shutdown.
//!
//! A node starts after it holds a lease from every dependency. Only a ready
//! node hands out leases, and it stops only after all its leases are
//! dropped, so dependents always stop before their dependencies.

use std::fs;
use std::os::fd::BorrowedFd;
use std::process::ExitStatus;
use std::time::Duration;

use anyhow::{Context, Result, anyhow, ensure};
use futures_util::future;
use tokio::sync::{mpsc, oneshot};
use tokio::time::Instant;
use tokio_util::sync::CancellationToken;

use crate::plan::{NodeRole, ProcessPlan};
use crate::probe;
use crate::process::{Lifeline, ProcessGroup, Spawn};
use crate::resource::Endpoint;
use crate::session::Event;

/// Held by a dependent while it needs its dependency to keep running.
pub(crate) struct Lease {
    _holder: mpsc::Sender<()>,
}

/// The dependency edges of one node.
pub(crate) struct Links {
    dependencies: Vec<oneshot::Receiver<Lease>>,
    dependents: Vec<oneshot::Sender<Lease>>,
}

/// Creates one lease channel per dependency edge.
///
/// Every dependency must precede its dependent, which also rules out cycles.
pub(crate) fn links(processes: &[ProcessPlan]) -> Result<Vec<Links>> {
    let mut links = processes
        .iter()
        .map(|_| Links {
            dependencies: Vec::new(),
            dependents: Vec::new(),
        })
        .collect::<Vec<_>>();
    for (index, process) in processes.iter().enumerate() {
        for &dependency in &process.dependencies {
            ensure!(
                dependency < index,
                "process {} depends on a later or missing process",
                process.id
            );
            let (sender, receiver) = oneshot::channel();
            links[dependency].dependents.push(sender);
            links[index].dependencies.push(receiver);
        }
    }
    Ok(links)
}

/// Inputs shared by the nodes of a session.
pub(crate) struct NodeContext<'a> {
    pub(crate) lifeline: &'a Lifeline,
    pub(crate) ready_timeout: Duration,
    pub(crate) cancel: &'a CancellationToken,
    pub(crate) force: &'a CancellationToken,
    pub(crate) events: &'a mpsc::UnboundedSender<Event>,
    pub(crate) ready: &'a mpsc::UnboundedSender<()>,
}

/// How a node ended.
pub(crate) struct NodeEnd {
    /// The first failure of the node.
    pub(crate) result: Result<()>,
    /// Whether every process of the node is known to have exited.
    pub(crate) stopped: bool,
}

impl NodeEnd {
    fn idle(result: Result<()>) -> Self {
        Self {
            result,
            stopped: true,
        }
    }

    fn after(failure: Result<()>, (stopped, cleanup): (bool, Result<()>)) -> Self {
        Self {
            result: failure.and(cleanup),
            stopped,
        }
    }
}

/// Runs a node from dependency wait to shutdown.
///
/// The process keeps the lock descriptors in `inherit`.
pub(crate) async fn run(
    plan: &ProcessPlan,
    links: Links,
    inherit: &[BorrowedFd<'_>],
    context: &NodeContext<'_>,
) -> NodeEnd {
    let Links {
        dependencies,
        dependents,
    } = links;
    let leases = tokio::select! {
        biased;
        _ = context.cancel.cancelled() => return NodeEnd::idle(Ok(())),
        leases = future::try_join_all(dependencies) => match leases {
            Ok(leases) => leases,
            Err(_) => {
                let error = anyhow!("a dependency of {} stopped before it was ready", plan.id);
                return NodeEnd::idle(Err(error));
            }
        },
    };
    let spawned = match Spawned::start(plan, context.lifeline, inherit) {
        Ok(spawned) => spawned,
        Err(error) => return NodeEnd::idle(Err(error)),
    };
    context.emit(Event::Started {
        process: plan.id.clone(),
    });
    let end = match spawned.probe(context).await {
        Ok(ready) => {
            context.emit(Event::Ready {
                process: plan.id.clone(),
            });
            let _ = context.ready.send(());
            ready.publish(dependents).supervise(context).await
        }
        Err(end) => end,
    };
    if end.stopped {
        context.emit(Event::Stopped {
            process: plan.id.clone(),
        });
    }
    drop(leases);
    end
}

impl NodeContext<'_> {
    fn emit(&self, event: Event) {
        let _ = self.events.send(event);
    }
}

/// A running process and the sockets it creates.
///
/// Dropping a node sends SIGKILL to its process group and leaves the sockets
/// for `cosim clean`; [`Node::shutdown`] stops the group and removes them.
struct Node<'p> {
    plan: &'p ProcessPlan,
    process: ProcessGroup,
    endpoints: Vec<Endpoint>,
}

impl Node<'_> {
    /// Stops the process and removes its sockets once it has exited.
    ///
    /// Returns whether termination is confirmed and any cleanup failure.
    async fn shutdown(self, force: &CancellationToken) -> (bool, Result<()>) {
        let Self {
            plan,
            process,
            endpoints,
        } = self;
        if let Err(error) = process.shutdown(force).await {
            // The sockets stay for `cosim clean`.
            drop(endpoints);
            return (false, Err(error.context(format!("stop {}", plan.id))));
        }
        let mut result = Ok(());
        for endpoint in endpoints {
            result = result.and(endpoint.remove());
        }
        (true, result)
    }
}

/// A node whose process started but is not ready yet.
struct Spawned<'p> {
    node: Node<'p>,
    started: Instant,
}

impl<'p> Spawned<'p> {
    fn start(
        plan: &'p ProcessPlan,
        lifeline: &Lifeline,
        inherit: &[BorrowedFd<'_>],
    ) -> Result<Self> {
        fs::create_dir_all(&plan.directory)
            .with_context(|| format!("create {}", plan.directory.display()))?;
        let endpoints = plan
            .endpoints
            .iter()
            .cloned()
            .map(Endpoint::adopt)
            .collect();
        let process = ProcessGroup::spawn(
            lifeline,
            &Spawn {
                program: &plan.program,
                argv: &plan.argv,
                env: &plan.env,
                directory: &plan.directory,
                log: &plan.output_log,
                inherit,
            },
        )
        .with_context(|| format!("start {}", plan.id))?;
        Ok(Self {
            node: Node {
                plan,
                process,
                endpoints,
            },
            started: Instant::now(),
        })
    }

    /// Evaluates the readiness probes; failure or cancellation stops the node.
    async fn probe(self, context: &NodeContext<'_>) -> Result<Ready<'p>, NodeEnd> {
        let Self { mut node, started } = self;
        let plan = node.plan;
        // Observe a completed exit before readiness or cancellation.
        let outcome = tokio::select! {
            biased;
            status = node.process.wait() => Err(match status {
                Ok(status) => anyhow!("exited with {status} before it was ready"),
                Err(error) => error,
            }),
            result = probe::wait_all(&plan.probes, started, context.ready_timeout) => {
                result.map(Some)
            }
            _ = context.cancel.cancelled() => Ok(None),
        };
        let outcome = outcome.and_then(|ready| match node.process.try_wait()? {
            Some(status) => Err(anyhow!("exited with {status} before it was ready")),
            None => Ok(ready),
        });
        match outcome {
            Ok(Some(())) => Ok(Ready(node)),
            Ok(None) => Err(NodeEnd::after(Ok(()), node.shutdown(context.force).await)),
            Err(error) => {
                let failure = Err(error.context(format!(
                    "{} readiness; see {}",
                    plan.id,
                    plan.output_log.display()
                )));
                Err(NodeEnd::after(failure, node.shutdown(context.force).await))
            }
        }
    }
}

/// A node whose readiness probes passed.
struct Ready<'p>(Node<'p>);

impl<'p> Ready<'p> {
    /// Hands a lease to every dependent that still waits for this node.
    fn publish(self, dependents: Vec<oneshot::Sender<Lease>>) -> Running<'p> {
        let (holder, holders) = mpsc::channel(1);
        let mut leased = false;
        for dependent in dependents {
            let lease = Lease {
                _holder: holder.clone(),
            };
            leased |= dependent.send(lease).is_ok();
        }
        Running {
            node: self.0,
            holders,
            leased,
        }
    }
}

/// A ready node that serves its dependents.
struct Running<'p> {
    node: Node<'p>,
    holders: mpsc::Receiver<()>,
    leased: bool,
}

/// Why a running node stops.
enum Stop {
    Exited(Result<ExitStatus>),
    Released,
    Cancelled,
}

impl Running<'_> {
    /// Waits until the process exits, its dependents release it, or the
    /// session is cancelled, then stops it.
    ///
    /// A node with dependents ignores cancellation and waits for them, so
    /// shutdown follows reverse dependency order.
    /// Completed process status takes precedence over simultaneous stop requests.
    async fn supervise(self, context: &NodeContext<'_>) -> NodeEnd {
        let Self {
            mut node,
            mut holders,
            leased,
        } = self;
        let stop = tokio::select! {
            biased;
            status = node.process.wait() => Stop::Exited(status),
            _ = holders.recv(), if leased => Stop::Released,
            _ = context.cancel.cancelled(), if !leased => Stop::Cancelled,
        };
        let stop = match stop {
            Stop::Exited(status) => Stop::Exited(status),
            request => match node.process.try_wait() {
                Ok(Some(status)) => Stop::Exited(Ok(status)),
                Ok(None) => request,
                Err(error) => Stop::Exited(Err(error)),
            },
        };
        let plan = node.plan;
        let failure = match stop {
            Stop::Exited(Ok(status)) => {
                context.emit(Event::Exited {
                    process: plan.id.clone(),
                    status: status.to_string(),
                });
                if plan.role == NodeRole::Vhost && status.success() {
                    Ok(())
                } else {
                    Err(anyhow!(
                        "{} exited with {status}; see {}",
                        plan.id,
                        plan.output_log.display()
                    ))
                }
            }
            Stop::Exited(Err(error)) => Err(error),
            Stop::Released | Stop::Cancelled => Ok(()),
        };
        NodeEnd::after(failure, node.shutdown(context.force).await)
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests;
