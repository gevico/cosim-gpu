// SPDX-License-Identifier: Apache-2.0

//! Commands rendered from YAML argument lists or command templates.

use std::path::PathBuf;

use anyhow::{Context, Result, bail, ensure};
use minijinja::{Environment, UndefinedBehavior};
use serde::Serialize;
use serde_json::{Map, Value, json};

use super::{DeviceContext, Launch, Probe};
use crate::model::Device;

/// A MiniJinja argument template.
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum CommandTemplate {
    /// Each element renders to one argument.
    Argv(Vec<String>),
    /// The template renders a JSON array of arguments.
    Command(String),
}

impl CommandTemplate {
    /// Accepts at most one of an argument list and a command template, and
    /// checks the template syntax.
    pub(crate) fn from_parts(argv: Vec<String>, command: Option<String>) -> Result<Option<Self>> {
        let template = match (argv.is_empty(), command) {
            (true, None) => return Ok(None),
            (false, None) => Self::Argv(argv),
            (true, Some(command)) => Self::Command(command),
            (false, Some(_)) => bail!("argv and command are mutually exclusive"),
        };
        let environment = Environment::new();
        match &template {
            Self::Command(source) => {
                environment
                    .template_from_str(source)
                    .context("command template")?;
            }
            Self::Argv(arguments) => {
                for (index, argument) in arguments.iter().enumerate() {
                    environment
                        .template_from_str(argument)
                        .with_context(|| format!("argv[{index}] template"))?;
                }
            }
        }
        Ok(Some(template))
    }

    /// Renders arguments with strict handling of undefined values.
    pub(crate) fn render(&self, context: &Value) -> Result<Vec<String>> {
        let mut environment = Environment::new();
        environment.set_undefined_behavior(UndefinedBehavior::Strict);
        let argv: Vec<String> = match self {
            Self::Command(source) => {
                let rendered = environment
                    .render_str(source, context)
                    .context("render command template")?;
                serde_json::from_str(&rendered)
                    .context("command template must render a JSON string array")?
            }
            Self::Argv(template) => template
                .iter()
                .map(|argument| {
                    environment
                        .render_str(argument, context)
                        .context("render argument template")
                })
                .collect::<Result<_>>()?,
        };
        ensure!(
            !argv.is_empty(),
            "the command template produced no arguments"
        );
        Ok(argv)
    }
}

/// A device launched from a declared kind or a runtime command override.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct TemplateDevice {
    /// Argument template.
    pub command: CommandTemplate,
    /// Output text the device prints after it starts listening.
    pub ready_log: String,
    /// Model configuration file.
    pub config: Option<PathBuf>,
    /// Simulator configuration entry point.
    pub entry: Option<PathBuf>,
    /// Adapter-specific arguments passed to the template.
    pub args: Map<String, Value>,
}

impl TemplateDevice {
    pub(super) fn launch(&self, device: &Device, context: &DeviceContext<'_>) -> Result<Launch> {
        let regions = context
            .layout
            .regions_of(&device.id)
            .iter()
            .map(|region| (region.name.clone(), json!(region)))
            .collect::<Map<_, _>>();
        let template_context = json!({"id": device.id, "machine": context.machine.id,
            "socket": context.socket, "pool": context.pool, "ram": context.layout.ram,
            "regions": regions, "guest_ranges": context.layout.guest_ranges,
            "args": self.args, "config": self.config, "entry": self.entry, "model": device.model,
            "run_dir": context.run_dir, "node_dir": context.node_dir});
        Ok(Launch {
            argv: self.command.render(&template_context)?,
            probes: vec![
                Probe::Log {
                    path: context.output_log.to_path_buf(),
                    marker: {
                        let mut env = Environment::new();
                        env.set_undefined_behavior(UndefinedBehavior::Strict);
                        let marker = env
                            .render_str(&self.ready_log, &template_context)
                            .context("render ready_log")?;
                        ensure!(
                            !marker.is_empty() && !marker.contains('\0'),
                            "rendered ready_log must be nonempty text without NUL"
                        );
                        marker
                    },
                    timeout: None,
                },
                Probe::Socket {
                    path: context.socket.to_path_buf(),
                },
            ],
        })
    }
}
