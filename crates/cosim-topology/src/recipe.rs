// SPDX-License-Identifier: Apache-2.0

//! Device recipes compose device identity, backend defaults and simulator inputs.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Component, Path, PathBuf};

use anyhow::{Context, Result, ensure};
use schemars::JsonSchema;
use serde::Deserialize;
use serde_json::{Map, Value, json};

use crate::loader::merge;
use crate::raw;
use crate::size::ByteSize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Identity {
    schema: u32,
    pci: Map<String, Value>,
}

#[derive(Debug, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub(crate) struct Backend {
    simulator: String,
    kind: String,
    model: String,
    ready_log: String,
    runtime: BackendRuntime,
    defaults: Value,
    requirements: Requirements,
    parameters: BTreeMap<String, Parameter>,
}

#[derive(Debug, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
struct BackendRuntime {
    command: String,
}

#[derive(Debug, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
struct Requirements {
    memory_map: bool,
    regions: BTreeMap<String, Region>,
}

#[derive(Debug, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
struct Region {
    power_of_two: bool,
}

#[derive(Debug, Deserialize, JsonSchema)]
#[serde(tag = "type", rename_all = "kebab-case", deny_unknown_fields)]
enum Parameter {
    Integer { default: u64, min: u64, max: u64 },
    StringList { default: Vec<String> },
}

impl Parameter {
    fn default_value(&self) -> Value {
        match self {
            Self::Integer { default, .. } => json!(default),
            Self::StringList { default } => json!(default),
        }
    }

    fn check(&self, value: &Value, name: &str) -> Result<()> {
        let valid = match self {
            Self::Integer { min, max, .. } => {
                value.as_u64().is_some_and(|n| (*min..=*max).contains(&n))
            }
            Self::StringList { .. } => value
                .as_array()
                .is_some_and(|items| items.iter().all(Value::is_string)),
        };
        ensure!(valid, "invalid recipe parameter {name}: {value}");
        Ok(())
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Simulator {
    schema: u32,
    source: Source,
    build: Build,
    runtime: Runtime,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Source {
    path: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Build {
    config: String,
    binary: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Runtime {
    entry: String,
}

/// Loads one backend and validates the final instance after template expansion.
/// The returned kind uses the existing generic command renderer.
pub(crate) fn expand(
    value: &mut Value,
    resources: &Path,
    workspace: &Path,
    memory_map: bool,
) -> Result<Option<(String, raw::Kind)>> {
    let Some(identifier) = value
        .get("recipe")
        .and_then(Value::as_str)
        .map(str::to_owned)
    else {
        return Ok(None);
    };
    let recipe_path = relative(&identifier, 3).context("device recipe")?;
    let root = resources.join("devices");
    let config = contained(&root, &root.join(recipe_path).with_extension("yaml"))?;
    let directory = config.parent().context("device recipe directory")?;
    let document = crate::loader::read_document(&config)?;
    let backend = document.recipe.context("device YAML requires recipe")?;
    let identity: Identity = read(&root, &directory.join("device.toml"))?;
    ensure!(identity.schema == 1, "unsupported device identity schema");
    ensure!(
        !backend.requirements.memory_map || memory_map,
        "device recipe {identifier} requires vhost.memory_map"
    );
    let simulator_path = relative(&backend.simulator, 1).context("simulator recipe")?;
    let simulator_root = resources.join("device_simulators");
    let simulator_dir = contained(&simulator_root, &simulator_root.join(simulator_path))?;
    let simulator: Simulator = read(&simulator_dir, &simulator_dir.join("recipe.toml"))?;
    ensure!(simulator.schema == 1, "unsupported simulator recipe schema");
    relative(&simulator.source.path, 2).context("simulator source")?;
    relative(&simulator.build.config, 1).context("simulator build config")?;
    relative(&simulator.build.binary, 1).context("simulator binary")?;
    let entry = contained(
        &simulator_dir,
        &simulator_dir.join(relative(&simulator.runtime.entry, 1).context("simulator entry")?),
    )?;
    contained(
        directory,
        &directory.join(relative(&backend.model, 1).context("device model")?),
    )?;
    let host_arch = value
        .get("host_arch")
        .and_then(Value::as_str)
        .unwrap_or(std::env::consts::ARCH);
    ensure!(
        matches!(host_arch, "x86_64" | "aarch64"),
        "host_arch must be x86_64 or aarch64"
    );
    let binary = workspace
        .join("build")
        .join(&backend.simulator)
        .join(host_arch)
        .join(&simulator.build.config)
        .join(&simulator.build.binary);
    let expected_pci = backend.defaults.get("pci").cloned();
    for (name, parameter) in &backend.parameters {
        parameter.check(&parameter.default_value(), name)?;
    }
    let defaults = backend
        .parameters
        .iter()
        .map(|(name, parameter)| (name.clone(), parameter.default_value()))
        .collect::<Map<_, _>>();
    let mut base = json!({"kind": backend.kind, "entry": entry, "config": config, "ready_log": backend.ready_log,
        "runtime": {"binary": binary}, "args": defaults, "pci": identity.pci});
    merge(&mut base, backend.defaults);
    merge(&mut base, value.take());
    ensure!(
        base.get("entry") == Some(&json!(entry)) && base.get("config") == Some(&json!(config)),
        "recipe entry and model configuration cannot be replaced"
    );
    let args = base
        .get("args")
        .and_then(Value::as_object)
        .context("recipe args must be a mapping")?;
    for (name, value) in args {
        backend
            .parameters
            .get(name)
            .with_context(|| format!("unknown recipe parameter {name}"))?
            .check(value, name)?;
    }
    for name in backend.parameters.keys() {
        ensure!(args.contains_key(name), "missing recipe parameter {name}");
    }
    let pci = base
        .get("pci")
        .and_then(Value::as_object)
        .context("recipe pci must be a mapping")?;
    for (name, expected) in identity
        .pci
        .iter()
        .filter(|(name, _)| name.as_str() != "rom")
    {
        ensure!(
            pci.get(name) == Some(expected),
            "device PCI {name} cannot differ from device.toml"
        );
    }
    // Backend-specific PCI fields have the same fixed-identity semantics.
    if let Some(expected) = expected_pci.as_ref().and_then(Value::as_object) {
        for (name, expected) in expected {
            ensure!(
                pci.get(name) == Some(expected),
                "device PCI {name} cannot differ from backend recipe"
            );
        }
    }
    let regions = base
        .get("memory_regions")
        .cloned()
        .context("recipe requires memory_regions")?;
    let regions: Vec<raw::MemoryRegion> =
        serde_json::from_value(regions).context("recipe memory_regions")?;
    ensure!(
        regions.len() == backend.requirements.regions.len(),
        "recipe requires exactly the declared memory regions"
    );
    for region in regions {
        let rule = backend
            .requirements
            .regions
            .get(&region.name)
            .with_context(|| {
                format!(
                    "recipe requires memory regions {:?}",
                    backend.requirements.regions.keys().collect::<Vec<_>>()
                )
            })?;
        let size: ByteSize = region.size;
        ensure!(
            !rule.power_of_two || size.is_power_of_two(),
            "{} size must be a power of two",
            region.name
        );
    }
    ensure!(
        base.get("kind").and_then(Value::as_str) == Some(backend.kind.as_str()),
        "recipe kind cannot be replaced"
    );
    let command = backend.runtime.command;
    let model = serde_json::from_value(json!(backend.simulator)).context("simulator model")?;
    let kind = raw::Kind {
        role: crate::model::Role::Device,
        model,
        argv: Vec::new(),
        command: Some(command),
        max_devices: None,
    };
    *value = base;
    Ok(Some((backend.kind, kind)))
}

fn read<T: serde::de::DeserializeOwned>(root: &Path, path: &Path) -> Result<T> {
    let path = contained(root, path)?;
    let text =
        fs::read_to_string(&path).with_context(|| format!("read recipe {}", path.display()))?;
    toml::from_str(&text).with_context(|| format!("recipe {}", path.display()))
}

fn relative(value: &str, levels: usize) -> Result<PathBuf> {
    let path = Path::new(value);
    ensure!(
        !value.is_empty()
            && !value.contains('\\')
            && !path.is_absolute()
            && value
                .split('/')
                .all(|part| !matches!(part, "" | "." | ".."))
            && path.components().count() == levels
            && path.components().all(|c| matches!(c, Component::Normal(_))),
        "expected a {levels}-level relative recipe path: {value}"
    );
    Ok(path.to_path_buf())
}

fn contained(root: &Path, path: &Path) -> Result<PathBuf> {
    let root = fs::canonicalize(root).with_context(|| format!("recipe root {}", root.display()))?;
    let path = fs::canonicalize(path).with_context(|| format!("recipe path {}", path.display()))?;
    ensure!(
        path.starts_with(&root),
        "recipe path escapes {}",
        root.display()
    );
    Ok(path)
}
