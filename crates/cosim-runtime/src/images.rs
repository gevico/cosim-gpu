// SPDX-License-Identifier: Apache-2.0

//! Resolves vHost image recipes through the shared Packer/Ansible builder.

use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result, ensure};
use cosim_topology::{DiskFormat, Topology};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ImageState {
    pub recipe: RecipeSummary,
    pub status: String,
    pub input_key: Option<String>,
    pub inputs: Option<serde_json::Value>,
    pub artifact_directory: PathBuf,
    pub disk: PathBuf,
    pub disk_format: String,
    pub kernel: Option<PathBuf>,
    pub reasons: Vec<String>,
    pub commands: Vec<Vec<String>>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RecipeSummary {
    pub id: String,
    pub distribution: String,
    pub release: String,
    pub architecture: String,
    pub software: String,
    pub software_release: String,
}

/// Inspects selected recipes and adds each result to its owning vHost.
pub fn prepare_image_recipes(
    topology: &mut Topology,
    workspace: &Path,
    build: bool,
) -> Result<Vec<ImageState>> {
    let mut states = Vec::new();
    for machine in &mut topology.machines {
        let Some(recipe) = machine
            .vhost
            .image
            .as_ref()
            .map(|image| image.recipe.clone())
        else {
            continue;
        };
        let mut state = inspect_recipe_with_policy(workspace, &recipe, build)?;
        if build && state.status != "ready" {
            run_builder(workspace, "build", &recipe, false)?;
            state = inspect_recipe_with_policy(workspace, &recipe, build)?;
        }
        if build {
            ensure!(
                state.status == "ready",
                "image recipe {} is not ready: {}",
                recipe,
                state.reasons.join("; ")
            );
        }
        let disk_format = serde_json::from_value::<DiskFormat>(serde_json::Value::String(
            state.disk_format.clone(),
        ))
        .context("decode image recipe disk format")?;
        cosim_topology::materialize_image_recipe(
            &mut machine.vhost,
            state.kernel.clone(),
            state.disk.clone(),
            disk_format,
        )?;
        states.push(state);
    }
    Ok(states)
}

/// Reads recipe and cache state without creating files or starting Packer.
pub fn inspect_recipe(workspace: &Path, recipe: &str) -> Result<ImageState> {
    inspect_recipe_with_policy(workspace, recipe, false)
}

fn inspect_recipe_with_policy(
    workspace: &Path,
    recipe: &str,
    write_verification_cache: bool,
) -> Result<ImageState> {
    let output = run_builder(workspace, "inspect", recipe, write_verification_cache)?;
    serde_json::from_slice(&output).context("decode image recipe inspection")
}

fn run_builder(
    workspace: &Path,
    operation: &str,
    recipe: &str,
    write_verification_cache: bool,
) -> Result<Vec<u8>> {
    let mut command = Command::new("python3");
    command
        .arg("-m")
        .arg("resources.images.cli")
        .arg("--workspace")
        .arg(workspace)
        .arg(operation)
        .arg(recipe)
        .current_dir(workspace)
        .env("PYTHONDONTWRITEBYTECODE", "1");
    if operation == "inspect" {
        command.arg("--json");
        if write_verification_cache {
            command.arg("--write-verification-cache");
        }
        let output = command
            .output()
            .context("start the guest image recipe inspector")?;
        ensure!(
            output.status.success(),
            "image recipe inspection failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        );
        Ok(output.stdout)
    } else {
        let status = command.status().context("start the guest image builder")?;
        ensure!(
            status.success(),
            "guest image {operation} failed for {recipe}"
        );
        Ok(Vec::new())
    }
}
