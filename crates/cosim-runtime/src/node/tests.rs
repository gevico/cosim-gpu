// SPDX-License-Identifier: Apache-2.0

use std::path::Path;
use std::time::Instant;

use cosim_topology::Probe;
use nix::sys::wait::{Id, WaitPidFlag, WaitStatus, waitid};
use nix::unistd::Pid;

use super::*;
use crate::env::ExecEnv;

fn directory() -> tempfile::TempDir {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../build/tests/runtime");
    fs::create_dir_all(&root).unwrap();
    tempfile::Builder::new()
        .prefix("node")
        .tempdir_in(root)
        .unwrap()
}

fn process_plan(root: &Path, role: NodeRole, argv: Vec<String>) -> ProcessPlan {
    let env = ExecEnv::local().unwrap();
    ProcessPlan {
        id: "completed".to_owned(),
        machine: 0,
        role,
        program: "/bin/sh".into(),
        argv,
        env: [("PATH".to_owned(), env.search_path)].into(),
        directory: root.join("process"),
        output_log: root.join("output.log"),
        endpoints: Vec::new(),
        probes: vec![Probe::Log {
            path: root.join("output.log"),
            marker: "READY".to_owned(),
            timeout: None,
        }],
        dependencies: Vec::new(),
    }
}

fn child_pid(path: &Path) -> Pid {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        if let Ok(bytes) = fs::read(path)
            && let Ok(pid) = serde_json::from_slice(&bytes)
        {
            return Pid::from_raw(pid);
        }
        assert!(Instant::now() < deadline, "child did not record its PID");
        std::thread::sleep(Duration::from_millis(1));
    }
}

/// Observes a real exit without reaping it or polling the Tokio reactor.
fn observe_exit(pid: Pid) -> WaitStatus {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let status = waitid(
            Id::Pid(pid),
            WaitPidFlag::WEXITED | WaitPidFlag::WNOWAIT | WaitPidFlag::WNOHANG,
        )
        .unwrap();
        if status != WaitStatus::StillAlive {
            return status;
        }
        assert!(Instant::now() < deadline, "child did not exit");
        std::thread::sleep(Duration::from_millis(1));
    }
}

#[tokio::test(flavor = "current_thread")]
async fn completed_exits_take_precedence_over_simultaneous_stop_requests() {
    for (role, code, released) in [
        (NodeRole::Vhost, 17, false),
        (NodeRole::Device, 0, true),
        (NodeRole::Vhost, 0, false),
    ] {
        let directory = directory();
        let release = directory.path().join("exit");
        let pid_file = directory.path().join("pid.json");
        let plan = process_plan(
            directory.path(),
            role,
            vec![
                "-c".into(),
                concat!(
                    r#"printf '%s' "$$" > "$3"; printf 'READY\n'; "#,
                    r#"while ! test -e "$1"; do sleep 0.01; done; exit "$2""#
                )
                .into(),
                "node-exit".into(),
                release.display().to_string(),
                code.to_string(),
                pid_file.display().to_string(),
            ],
        );
        let lifeline = Lifeline::locate(&plan.env["PATH"]).unwrap();
        let cancel = CancellationToken::new();
        let force = CancellationToken::new();
        let (events, mut observed) = mpsc::unbounded_channel();
        let (ready, _) = mpsc::unbounded_channel();
        let context = NodeContext {
            lifeline: &lifeline,
            ready_timeout: Duration::from_secs(5),
            cancel: &cancel,
            force: &force,
            events: &events,
            ready: &ready,
        };
        let spawned = Spawned::start(&plan, &lifeline, &[]).unwrap();
        let ready = match spawned.probe(&context).await {
            Ok(ready) => ready,
            Err(end) => panic!("process did not become ready: {:?}", end.result),
        };
        let pid = child_pid(&pid_file);
        fs::write(&release, []).unwrap();
        assert_eq!(observe_exit(pid), WaitStatus::Exited(pid, code));
        let running = if released {
            let (sender, receiver) = oneshot::channel();
            let running = ready.publish(vec![sender]);
            drop(receiver.await.unwrap());
            running
        } else {
            cancel.cancel();
            ready.publish(Vec::new())
        };
        let end = running.supervise(&context).await;
        assert!(end.stopped);
        assert_eq!(end.result.is_ok(), role == NodeRole::Vhost && code == 0);
        assert!(matches!(observed.try_recv().unwrap(), Event::Exited { .. }));
    }
}

#[tokio::test(flavor = "current_thread")]
async fn completed_startup_failure_precedes_readiness_and_cancellation() {
    let directory = directory();
    let pid_file = directory.path().join("pid.json");
    let plan = process_plan(
        directory.path(),
        NodeRole::Device,
        vec![
            "-c".into(),
            r#"printf '%s' "$$" > "$1"; printf 'READY\n'; exit 17"#.into(),
            "node-exit".into(),
            pid_file.display().to_string(),
        ],
    );
    let lifeline = Lifeline::locate(&plan.env["PATH"]).unwrap();
    let cancel = CancellationToken::new();
    let force = CancellationToken::new();
    let (events, _) = mpsc::unbounded_channel();
    let (ready, _) = mpsc::unbounded_channel();
    let context = NodeContext {
        lifeline: &lifeline,
        ready_timeout: Duration::from_secs(5),
        cancel: &cancel,
        force: &force,
        events: &events,
        ready: &ready,
    };
    let spawned = Spawned::start(&plan, &lifeline, &[]).unwrap();
    let pid = child_pid(&pid_file);
    assert_eq!(observe_exit(pid), WaitStatus::Exited(pid, 17));
    assert_eq!(fs::read_to_string(&plan.output_log).unwrap(), "READY\n");
    cancel.cancel();
    let end = match spawned.probe(&context).await {
        Err(end) => end,
        Ok(_) => panic!("an exited process became ready"),
    };
    assert!(end.stopped);
    let error = format!("{:#}", end.result.unwrap_err());
    assert!(error.contains("before it was ready"), "{error}");
}
