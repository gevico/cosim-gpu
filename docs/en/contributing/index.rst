.. SPDX-License-Identifier: Apache-2.0

.. _contrib-index:

Contributing
============

This chapter is the entry point for contributing. Read it before submitting a
patch, and use the checklist at the end of this page to review the change.

In this chapter
---------------

.. toctree::
   :maxdepth: 1

   workflow
   add_vhost_recipe
   patch_check
   maintainers
   ci
   rust_guidelines
   documentation

Recommended path
----------------

- First contribution: read :doc:`workflow`, then :doc:`patch_check`
- New guest distribution or image variant: read :doc:`add_vhost_recipe`
- Rust changes: also read :doc:`rust_guidelines`
- Documentation changes: read :doc:`documentation` and run ``just docs-check``
- To find the reviewers: see :doc:`maintainers`

Before you submit
-----------------

- Every non-merge commit passes ``just check-patch``
- Each commit carries a ``Signed-off-by:`` line and no AI attribution trailers
- New files belong to an existing area in ``MAINTAINERS.yml``, or add one in the same commit
- When a change touches both languages, update the Chinese and English pages in the same commit

Related pages
-------------

- :doc:`workflow`
- :doc:`patch_check`
- :doc:`documentation`
- :ref:`gs-index`
