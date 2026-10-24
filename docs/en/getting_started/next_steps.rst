.. SPDX-License-Identifier: Apache-2.0

.. _gs-next-steps:

Next steps
==========

After the first session works, pick the next chapter by goal. This page only
routes readers; it does not duplicate chapter content.

Understand how the system works
-------------------------------

Start with :ref:`Architecture overview <arch-index>`, read
:ref:`Components and responsibilities <arch-components>` to understand the
QEMU functional, gem5 performance and vfio-user split, then continue with
:ref:`Execution flow <arch-execution-flow>` and
:ref:`Memory and shared memory model <arch-memory-model>`.

Use and extend the launcher
---------------------------

Commands, the YAML-to-plan pipeline, session lifecycle and debugging are in
chapter 3:

- :ref:`Commands and options <launcher-cli>`
- :ref:`YAML loading, templates and plans <launcher-yaml-pipeline>`
- :ref:`Session lifecycle and resources <launcher-session-lifecycle>`
- :ref:`Debugging sessions <launcher-debugging-sessions>`

Go deeper into simulators and the driver
----------------------------------------

QEMU as vhost and device model, the gem5 MI300X performance model and guest
driver requirements are in chapter 4:

- :ref:`QEMU and gem5: functional and performance simulation <sim-index>`
- :ref:`MI300X performance model <sim-gem5-model>`
- :ref:`Guest driver requirements <sim-guest-driver>`

Write your own topology
-----------------------

Machine catalog, host and device configuration, vHost and how to write a
topology YAML are in chapter 5:

- :ref:`Topology and hardware support <topo-index>`
- :ref:`Machine catalog <topo-machines-index>`
- :ref:`How to write a topology YAML <topo-write-topology>`

Look up facts and troubleshoot
------------------------------

Schemas, parameters, versions, artifact paths and known issues are in
chapter 6:

- :ref:`Guest parameters <ref-guest-parameters>`
- :ref:`Version matrix <ref-version-matrix>`
- :ref:`Files, artifacts and source map <ref-files-and-artifacts>`
- :ref:`Known issues <ref-known-issues>`

Related pages
-------------

- :doc:`index`
- :doc:`verify_guest`
- :ref:`Architecture overview <arch-index>`
- :ref:`Cosim Launcher <launcher-index>`
- :ref:`Topology and hardware support <topo-index>`
