.. SPDX-License-Identifier: Apache-2.0

.. _contrib-rust-guidelines:

Rust guidelines
===============

The Rust crates under ``crates/`` follow these rules. The simulator submodules keep
their own development rules; the applicable general principles come from the
Asterinas Coding Guidelines, with the configuration and lifecycle contracts
below defined for this project.

Module boundaries
-----------------

- ``cosim-topology`` decodes YAML, resolves imports and templates, validates
  declarations and renders launch arguments from caller-supplied contexts. It
  reads only topology documents: no environment variables, no other filesystem
  state and no operating-system interfaces.
- ``cosim-runtime`` owns everything that depends on the executing system: host
  facts (``ExecEnv``), session paths (``SessionLayout``), plans, processes,
  files, locks and cleanup.
- ``cosim-cli`` owns argument parsing, signals, the standard-input lifeline and
  terminal output.
- A module groups one coherent concept and exposes only the operations its callers
  need.
- Shared dependencies, including internal path dependencies, use workspace
  inheritance.
- Imported free functions and statics are qualified through their parent module;
  types and traits may be imported directly.
- Use explicit exports and the narrowest visibility needed by existing consumers.
  Read-only data types use public fields with ``#[non_exhaustive]``.

Types and configuration boundaries
----------------------------------

Decoded input types (``raw``) are separate from validated types (``model``).
Parse values once at the boundary: sizes become ``ByteSize``, formats and buses
become enums, names become ``Identifier``, and combinations of fields become
types such as ``DiskMode`` or ``Option<DirectBoot>``. Validated types
contain no optional field that later code must unwrap.

- Closed choices are enums that carry their data, for example ``Adapter``,
  ``CommandTemplate``, ``Probe`` and ``DiskMode``; ``match`` must
  stay exhaustive.
- Use checked arithmetic for byte counts, alignment, offsets and deadlines.
- Replace behavior-selecting boolean parameters with named operations or enums;
  meaningful configuration booleans remain ordinary data.
- YAML syntax is parsed by ``serde_yaml_ng`` and Serde; Schemars generates the
  document schema; MiniJinja renders adapter templates; JSON command arrays and
  persisted records use Serde JSON.
- Use established libraries to parse mature formats; application code implements
  import, template, identity and resource rules over parsed values. Relative
  paths are resolved in the document that defines them; ``..`` components stay
  for the filesystem, which resolves symbolic links first.

External host parameters
------------------------

Host executable, machine, accelerator, CPU, memory, boot, storage, display,
monitoring and additional QEMU arguments come from YAML or imported templates;
keep sample defaults in ``resources/vhosts/``.

- Select ``qemu-system-aarch64`` for ARM64 hosts and
  ``qemu-system-x86_64`` for x86_64 hosts. Keep CPU, machine, boot images and
  guest physical memory ranges consistent with that profile; keep gem5 object
  files from different host architectures in separate build directories.
- Rust derives session paths, memory offsets, prepared disk paths and device
  endpoints; the host adapter defines how these values become arguments and
  declares how many devices its PCIe layout can attach.
- An adapter provides an argument list or a MiniJinja command template that
  renders a JSON string array. Each element becomes one process argument;
  execution uses no shell interpretation.
- The host adapter must bind the generated memory pool and expose the declared
  QMP and serial endpoints. ``cosim run --dry-run`` contains the exact executable,
  arguments, environment and resources that ``run`` consumes.
- Every device process runs natively in the execution environment, which is the
  Linux host or the development container. Every process an adapter starts runs
  in the foreground, keeps all resource users in its process group and keeps
  inherited file descriptors open, so the session lock and image leases reach its
  descendants.

Errors and resource ownership
-----------------------------

Return configuration, filesystem and process failures through ``Result`` and
``?``. Attach the relevant path, field, node or operation to each error.
User-controlled failures must not become panics; internal invariants must be
established by construction or explicitly checked; ``debug_assert!`` is for
internal correctness assertions that are unnecessary for input validation.

Every file, socket, lock and child process has exactly one owner value. The
session owns these values in a tree. Register a created resource before the next
fallible operation.

- Graceful shutdown is an explicit consuming
  ``async fn shutdown(self)``: SIGTERM, a bounded wait, then SIGKILL. Dropping
  a process group sends ``killpg(SIGKILL)`` without waiting; dropping a lock
  releases it.
- Files, sockets and directories that processes use are removed only by an
  explicit consuming ``remove`` after their users have stopped. Dropping their
  owners leaves them for ``cosim clean``, because termination is not confirmed
  on that path. Directories created during initialization, before any process
  starts, are removed when initialization fails.
- Node futures stay inside the session task (``FuturesUnordered``); do not move
  resource owners into ``tokio::spawn``.
- Dependencies are leases: a ready node gives each dependent an
  ``mpsc::Sender`` clone and stops after all of them are dropped. Readiness is a
  type state; only a ready node can hand out leases.
- Cancellation reaches owners through ``CancellationToken``. The library reports
  progress through events and never installs signal handlers or prints.
- Children start through ``setpriv --pdeathsig KILL`` from the launcher thread,
  so the kernel stops them when the launcher dies. Lock descriptors are
  close-on-exec; a session passes its session lock to every process it starts and
  an image lease to each host or helper that uses the image.
- Remove shared files and overlays only after their users have stopped. When
  termination cannot be confirmed, keep the resources and record it in the
  verdict.
- A directory that another session may also create appears only in its complete
  state: prepare it under a session-specific name and rename it without replacing
  an existing directory.
- The persisted manifest serves ``cosim clean`` after the launcher was killed or
  exited abnormally; ``clean`` takes the session lock that every session process
  holds, validates paths against their owned directories and removes them through
  the same owner types.
- QEMU commands must omit ``-daemonize`` and ``--daemonize``; planning
  rejects them.

Rust source conventions
-----------------------

- Use conventional Rust names and identify units with types such as
  ``Duration`` or explicit field names.
- Give variables containing closures or function pointers an ``_fn`` suffix.
- Alphabetize ordinary outer attributes and place ``derive`` last among them.
  Alphabetize the derived traits. Derive helper attributes, including Serde,
  Schemars and Clap attributes, follow their derive declaration.
- Keep public flow readable before implementation helpers; use early returns and
  named intermediate values to avoid deeply nested branches.
- Write concise rustdoc for public contracts and module responsibilities;
  document errors, side effects and ownership where they matter.
- Keep comments factual, necessary and in English; complete comment sentences use
  punctuation.
- Bridge-owned Rust code uses safe APIs; workspace lints forbid local unsafe code.
  Dependencies may implement the platform interfaces behind those APIs.

Verification and documentation
------------------------------

Use the top-level ``justfile`` for builds, tests and checks; recipes run on the
host or in the development container according to ``COSIM_ENV``.

.. code-block:: bash

   just check-cosim                # rustfmt check, Clippy and regression tests
   just test-cosim-integration     # real QEMU processes, disk images and signals
   just test-cosim-vfio-user       # vfio-user device after build-qemu
   just check-gem5-style           # gem5 style check
   just check-maintainers          # file ownership
   just check-patch-file <patch>   # draft patch

Retained tests must exercise meaningful behavior, be reusable, and detect
plausible regressions. Use actual libraries, files and processes; report the
observed outcomes; document unavailable execution environments separately from
completed validation; preserve commands, source identities, complete logs and
verdicts for runtime evidence.

Keep user-facing documentation consistent with the supported interfaces. Update
both ``docs/en/`` and ``docs/zh/``, and no longer add a language link on the
first line; see :doc:`documentation` for the documentation rules. Use Mermaid for
architecture diagrams. Commit and review requirements are in :doc:`workflow`.

Related pages
-------------

- :doc:`workflow`
- :doc:`documentation`
- :ref:`ref-device-adapters`
- :ref:`launcher-rust-workspace`
