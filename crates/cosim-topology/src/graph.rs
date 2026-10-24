// SPDX-License-Identifier: Apache-2.0

//! Mermaid rendering of machines and their device connections.

use crate::model::Topology;

/// Renders machines and their vfio-user connections as a Mermaid flowchart.
pub fn graph(topology: &Topology) -> String {
    let mut text = String::from("flowchart TD\n");
    for (machine_index, machine) in topology.machines.iter().enumerate() {
        let vhost = format!("h{machine_index}");
        text.push_str(&format!(
            "    subgraph m{machine_index}[\"{}\"]\n        {vhost}[\"QEMU vHost\"]\n",
            machine.id
        ));
        for (device_index, device) in machine.devices.iter().enumerate() {
            let node = format!("d{machine_index}_{device_index}");
            text.push_str(&format!(
                "        {node}[\"{} ({})\"]\n        {vhost} -->|vfio-user| {node}\n",
                device.id, device.kind
            ));
        }
        text.push_str("    end\n");
    }
    text
}
