.. SPDX-License-Identifier: Apache-2.0

.. _contrib-workflow:

Workflow
========

This page describes the path from preparing an environment to submitting a
patch. Patch formatting is covered in :doc:`patch_check` and file ownership in
:doc:`maintainers`.

Environment and prerequisites
-----------------------------

Build, launch, test and check tasks are defined in the top-level ``justfile``.
Run ``just`` in the repository root to list every task; recipes are grouped by
the ``dev-``, ``build-``, ``run-``, ``test-``, ``check-``,
``ci-`` and ``maint-`` prefixes.

QEMU, gem5, Rust and topology recipes run natively on a Linux host. On other
systems, or on Linux with ``COSIM_ENV=container``, they run in a temporary
development container by default. See :ref:`gs-requirements` for environment
requirements and :ref:`gs-platform-container` for container usage.

Submodules and repository boundaries
------------------------------------

``gem5``, ``qemu`` and ``gem5-resources`` are submodules. Changes
inside a submodule follow that repository's rules; the top-level checks apply
only to files in this repository.

- Initialize and update submodules with ``git submodule update --init --recursive``.
- Commit submodule pointer updates separately from top-level file changes.
- Have a submodule change reviewed in the submodule repository before updating
  the top-level pointer.

Branches and commits
--------------------

- Create a branch from ``main`` and keep it focused on one change.
- Keep commits focused; every non-merge commit must pass the patch check on its own.
- Write the subject in the imperative mood and explain the reason and impact in
  the body.
- Every commit carries a ``Signed-off-by:`` line in the exact form
  ``Signed-off-by: Name <email>``, taken from ``git config user.name`` and
  ``git config user.email``.
- Do not add AI attribution trailers, such as ``Co-authored-by:`` lines for AI
  tools, ``Assisted-by:``, ``Generated-by:`` or the ``🤖`` marker.
- New source files start with an ``SPDX-License-Identifier:`` line. The project
  license is ``Apache-2.0``; code derived from ``MIT``,
  ``BSD-2-Clause`` or ``BSD-3-Clause`` sources may use those licenses, and
  the commit message explains the choice.

Checks before submitting
------------------------

Run the following before committing or updating a pull request:

.. code-block:: bash

   just check

This runs ``just check-patch``, ShellCheck, ``just check-maintainers`` and
``just check-cosim``. Each can also be run on its own:

.. code-block:: bash

   just check-patch                     # commits not yet on origin/main
   just check-patch <base-commit>       # commits since a given base
   just check-patch-file <patch>        # inspect an uncommitted patch

For documentation changes also run ``just docs-check``, which builds both
languages and runs the bilingual and site checks; see :doc:`documentation`.

File ownership
--------------

Every tracked file must belong to an area in ``MAINTAINERS.yml``. When a commit
adds a file outside the existing areas, update ``MAINTAINERS.yml`` in the same
commit, otherwise ``just check-maintainers`` fails. See :doc:`maintainers` for
area lookup, checks and adding maintainers.

Related pages
-------------

- :doc:`patch_check`
- :doc:`maintainers`
- :doc:`documentation`
- :ref:`gs-requirements`
- :ref:`ref-version-matrix`
