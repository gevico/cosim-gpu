// SPDX-License-Identifier: Apache-2.0

//! Reads documents, follows imports and expands templates.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail, ensure};
use serde_json::Value;

use crate::adapter::{Gem5Mi300x, QemuDevice};
use crate::model::Topology;
use crate::raw::{self, Document};
use crate::resolve::{self, Kinds, MachineSpec};

const MAX_DEPTH: usize = 64;

/// Loads a topology document with its imports and validates the result.
///
/// Imports resolve against the importing file, then against `resources`.
/// Relative resource paths resolve against the configured workspace root.
/// Only the top-level document contributes runnable machines.
pub fn load(path: &Path, resources: &Path) -> Result<Topology> {
    let workspace = workspace_root()?;
    load_with_workspace(path, resources, &workspace)
}

fn workspace_root() -> Result<PathBuf> {
    match std::env::var_os("COSIM_WORKSPACE") {
        Some(workspace) if !workspace.is_empty() => {
            fs::canonicalize(PathBuf::from(workspace)).context("resolve COSIM_WORKSPACE")
        }
        Some(_) => bail!("COSIM_WORKSPACE must not be empty"),
        None => std::env::current_dir().context("read the current workspace directory"),
    }
}

/// Loads a topology with an explicit workspace root for path-valued fields.
/// Relative resource paths resolve from this directory.
pub fn load_with_workspace(path: &Path, resources: &Path, workspace: &Path) -> Result<Topology> {
    let workspace = fs::canonicalize(workspace)
        .with_context(|| format!("resolve workspace {}", workspace.display()))?;
    let source = fs::canonicalize(path).with_context(|| format!("open {}", path.display()))?;
    let mut loader = Loader {
        resources: std::path::absolute(resources)?,
        workspace,
        active: Vec::new(),
        loaded: BTreeSet::new(),
        templates: BTreeMap::new(),
        kinds: BTreeMap::new(),
    };
    let mut decode = || -> Result<Topology> {
        let document = loader.read(&source)?;
        let kinds = Kinds::new(std::mem::take(&mut loader.kinds))?;
        let specs = document
            .machines
            .into_iter()
            .enumerate()
            .map(|(index, machine)| {
                loader
                    .machine(machine)
                    .with_context(|| format!("machines[{index}]"))
            })
            .collect::<Result<Vec<_>>>()?;
        resolve::topology(source.clone(), specs, &kinds)
    };
    decode().with_context(|| source.display().to_string())
}

/// A template value and the file that defines it.
struct Definition {
    value: Value,
    source: PathBuf,
}

struct Loader {
    resources: PathBuf,
    workspace: PathBuf,
    active: Vec<PathBuf>,
    loaded: BTreeSet<PathBuf>,
    templates: BTreeMap<String, Definition>,
    kinds: BTreeMap<String, raw::Kind>,
}

impl Loader {
    /// Reads one document and registers the definitions it imports or declares.
    fn read(&mut self, path: &Path) -> Result<Document> {
        ensure!(
            path.to_str().is_some(),
            "configuration paths must be valid UTF-8: {}",
            path.display()
        );
        if self.active.iter().any(|active| active == path) {
            let chain = self
                .active
                .iter()
                .chain(std::iter::once(&path.to_path_buf()))
                .map(|path| path.display().to_string())
                .collect::<Vec<_>>()
                .join(" -> ");
            bail!("import cycle: {chain}");
        }
        ensure!(
            self.active.len() < MAX_DEPTH,
            "import depth exceeds {MAX_DEPTH} at {}",
            path.display()
        );
        let text = fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
        let mut yaml: serde_yaml_ng::Value =
            serde_yaml_ng::from_str(&text).with_context(|| path.display().to_string())?;
        yaml.apply_merge()
            .with_context(|| format!("{}: YAML merge", path.display()))?;
        let mut document: Document =
            serde_yaml_ng::from_value(yaml).with_context(|| path.display().to_string())?;
        ensure!(
            document.version == 1,
            "{}: unsupported version {}",
            path.display(),
            document.version
        );
        let directory = path
            .parent()
            .context("document has no parent directory")?
            .to_path_buf();
        for machine in &mut document.machines {
            resolve_paths(machine, &self.workspace)?;
        }
        if !self.loaded.insert(path.to_path_buf()) {
            return Ok(document);
        }
        self.active.push(path.to_path_buf());
        for name in std::mem::take(&mut document.imports) {
            let imported = self.locate(path, &directory, &name)?;
            self.read(&imported)
                .with_context(|| format!("{} imports {name}", path.display()))?;
        }
        for (name, mut value) in std::mem::take(&mut document.templates) {
            resolve_paths(&mut value, &self.workspace)?;
            if let Some(previous) = self.templates.get(&name) {
                bail!(
                    "duplicate template {name}: {} and {}",
                    previous.source.display(),
                    path.display()
                );
            }
            let definition = Definition {
                value,
                source: path.to_path_buf(),
            };
            self.templates.insert(name, definition);
        }
        for (name, kind) in std::mem::take(&mut document.kinds) {
            ensure!(
                !matches!(name.as_str(), Gem5Mi300x::KIND | QemuDevice::KIND),
                "cannot replace built-in kind {name}"
            );
            ensure!(
                !self.kinds.contains_key(&name),
                "duplicate kind {name} in {}",
                path.display()
            );
            self.kinds.insert(name, kind);
        }
        self.active.pop();
        Ok(document)
    }

    /// Finds an import and checks the resource directory layering.
    fn locate(&self, importer: &Path, directory: &Path, name: &str) -> Result<PathBuf> {
        let relative = name.strip_suffix("#templates").unwrap_or(name);
        ensure!(
            !relative.contains('#'),
            "unsupported import selector: {name}"
        );
        let candidate = directory.join(relative);
        let candidate = if candidate.exists() {
            candidate
        } else {
            self.resources.join(relative)
        };
        let imported = fs::canonicalize(&candidate)
            .with_context(|| format!("{} imports {name}", importer.display()))?;
        let root = fs::canonicalize(&self.resources).unwrap_or_else(|_| self.resources.clone());
        let layer = |path: &Path| -> Option<String> {
            let first = path.strip_prefix(&root).ok()?.components().next()?;
            Some(first.as_os_str().to_string_lossy().into_owned())
        };
        let allowed = match layer(importer).as_deref() {
            Some("vhosts" | "devices") => false,
            Some("machines") => matches!(layer(&imported).as_deref(), Some("vhosts" | "devices")),
            Some("clusters") => matches!(layer(&imported).as_deref(), Some("machines")),
            _ => true,
        };
        ensure!(
            allowed,
            "invalid import direction: {} -> {}",
            importer.display(),
            imported.display()
        );
        Ok(imported)
    }

    /// Expands a machine, then its vHost and devices, recording each device
    /// reference name.
    ///
    /// The machine-level merge completes before the vHost's own `use` chain is
    /// expanded, so a machine can replace the vHost template of its template.
    fn machine(&self, value: Value) -> Result<MachineSpec> {
        let mut value = self.expand(value, &mut Vec::new())?;
        if let Some(vhost) = value.get_mut("vhost") {
            *vhost = self
                .expand(vhost.take(), &mut Vec::new())
                .context("vhost")?;
        }
        let mut device_names = Vec::new();
        if let Some(devices) = value.get_mut("devices") {
            let devices = devices.as_array_mut().context("devices must be a list")?;
            for device in devices {
                let name = device
                    .get("id")
                    .or_else(|| device.get("use"))
                    .and_then(Value::as_str)
                    .map(str::to_owned);
                device_names.push(name);
                *device = self.expand(device.take(), &mut Vec::new())?;
            }
        }
        let machine = serde_json::from_value(value).context("machine definition")?;
        Ok(MachineSpec {
            machine,
            device_names,
        })
    }

    /// Replaces the `use` reference of `value` with the merged template chain.
    ///
    /// Nested definitions such as `vhost` keep their own references.
    fn expand(&self, mut value: Value, active: &mut Vec<String>) -> Result<Value> {
        let object = value
            .as_object_mut()
            .context("definitions must be mappings")?;
        if let Some(reference) = object.remove("use") {
            let name = reference
                .as_str()
                .context("use must name a template")?
                .to_owned();
            ensure!(
                !active.contains(&name),
                "template cycle: {} -> {name}",
                active.join(" -> ")
            );
            ensure!(
                active.len() < MAX_DEPTH,
                "template depth exceeds {MAX_DEPTH}"
            );
            let definition = self
                .templates
                .get(&name)
                .with_context(|| format!("unknown template {name}"))?;
            active.push(name.clone());
            let mut base = self
                .expand(definition.value.clone(), active)
                .with_context(|| format!("template {name} in {}", definition.source.display()))?;
            active.pop();
            merge(&mut base, value);
            value = base;
        }
        Ok(value)
    }
}

/// Merges mappings recursively; other overlay values replace the base.
fn merge(base: &mut Value, overlay: Value) {
    match (base, overlay) {
        (Value::Object(base), Value::Object(overlay)) => {
            for (key, value) in overlay {
                match base.get_mut(&key) {
                    Some(previous) => merge(previous, value),
                    None => {
                        base.insert(key, value);
                    }
                }
            }
        }
        (base, overlay) => *base = overlay,
    }
}

/// Resolves relative resource paths from the workspace root.
///
/// Executables are resolved only when they contain a path separator; bare
/// names are searched in `PATH` at execution.
fn resolve_paths(value: &mut Value, workspace: &Path) -> Result<()> {
    if let Some(vhost) = value.get_mut("vhost") {
        resolve_paths(vhost, workspace)?;
    }
    if let Some(devices) = value.get_mut("devices").and_then(Value::as_array_mut) {
        for device in devices {
            resolve_paths(device, workspace)?;
        }
    }
    if let Some(binary) = value.pointer_mut("/runtime/binary")
        && binary.as_str().is_some_and(|binary| binary.contains('/'))
    {
        absolute(binary, workspace)?;
    }
    for pointer in ["/config", "/pci/rom", "/kernel", "/initrd"] {
        if let Some(path) = value.pointer_mut(pointer) {
            absolute(path, workspace)?;
        }
    }
    if let Some(disks) = value.get_mut("disks").and_then(Value::as_array_mut) {
        for disk in disks {
            for key in ["path", "backing"] {
                if let Some(path) = disk.get_mut(key) {
                    absolute(path, workspace)?;
                }
            }
        }
    }
    Ok(())
}

/// Resolves a resource path against the workspace or preserves an absolute path.
/// Relative paths reject parent-directory traversal.
fn absolute(value: &mut Value, workspace: &Path) -> Result<()> {
    let path = value.as_str().context("path values must be strings")?;
    ensure!(!path.is_empty(), "path values must not be empty");
    ensure!(
        !path.contains("${COSIM_WORKSPACE}"),
        "resource paths must be workspace-relative without COSIM_WORKSPACE interpolation: {path}"
    );
    let source = Path::new(path);
    let joined = if source.is_absolute() {
        source.to_path_buf()
    } else {
        ensure!(
            !source
                .components()
                .any(|component| component == std::path::Component::ParentDir),
            "workspace-relative paths must not contain parent-directory traversal: {path}"
        );
        workspace.join(source)
    };
    let normalized = joined.components().collect::<PathBuf>();
    *value = Value::String(normalized.to_string_lossy().into_owned());
    Ok(())
}
