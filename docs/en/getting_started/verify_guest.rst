.. SPDX-License-Identifier: Apache-2.0

.. _gs-verify-guest:

Verify the guest
================

This page confirms that the amdgpu driver and the ROCm stack are ready
inside the guest, then runs the first HIP program. Canonical driver
parameters and manual recovery live in chapter 4; this page follows the
default path.

Automatic setup
---------------

After the guest boots, ``cosim-gpu-initialize.service`` runs these steps:

1. Write ``/root/roms/mi300.rom`` to the VGA ROM area at physical address
   ``0xC0000``.
2. Link ``mi300_discovery`` as ``ip_discovery.bin``.
3. Remove the runtime modprobe blacklist from the cmdline and load amdgpu
   with fixed parameters.
4. Check that every AMD PCI device has a DRM card and exit non-zero
   otherwise.

The service usually takes about 40 seconds. Check its state:

.. code-block:: bash

   systemctl status cosim-gpu-initialize.service
   journalctl -u cosim-gpu-initialize.service -b | tail -20

Check the GPU and ROCm
----------------------

.. code-block:: bash

   dmesg | grep -i amdgpu | tail -20
   lspci -d 1002:
   rocm-smi
   rocminfo | head -40

Expected results: ``lspci`` lists the AMD device, ``rocm-smi`` reports
device ``0x74a0`` and ``rocminfo`` names the agent ``gfx942``. A number of
fence fallback timer warnings during load are normal: they are the DRM
timeout fallback used while probing ring buffers.

First HIP program
-----------------

Create a vector addition program inside the guest:

.. code-block:: cpp

   #include <hip/hip_runtime.h>
   #include <cstdio>

   __global__ void vec_add(int *a, int *b, int *c, int n) {
       int i = blockIdx.x * blockDim.x + threadIdx.x;
       if (i < n) c[i] = a[i] + b[i];
   }

   int main() {
       const int N = 4;
       int ha[N] = {1, 2, 3, 4};
       int hb[N] = {10, 20, 30, 40};
       int hc[N] = {0};

       int *da, *db, *dc;
       hipMalloc(&da, N * sizeof(int));
       hipMalloc(&db, N * sizeof(int));
       hipMalloc(&dc, N * sizeof(int));
       hipMemcpy(da, ha, N * sizeof(int), hipMemcpyHostToDevice);
       hipMemcpy(db, hb, N * sizeof(int), hipMemcpyHostToDevice);

       vec_add<<<1, N>>>(da, db, dc, N);

       hipMemcpy(hc, dc, N * sizeof(int), hipMemcpyDeviceToHost);
       printf("Result: %d %d %d %d\n", hc[0], hc[1], hc[2], hc[3]);

       bool pass = (hc[0] == 11 && hc[1] == 22 && hc[2] == 33 && hc[3] == 44);
       printf("%s\n", pass ? "PASSED!" : "FAILED!");
       hipFree(da); hipFree(db); hipFree(dc);
       return pass ? 0 : 1;
   }

Save it as ``/tmp/vec_add.cpp``, then compile and run:

.. code-block:: bash

   /opt/rocm/bin/hipcc --offload-arch=gfx942 -o /tmp/vec_add /tmp/vec_add.cpp
   /tmp/vec_add

Expected output:

.. code-block:: text

   Result: 11 22 33 44
   PASSED!

.. warning::

   ``--offload-arch`` must be ``gfx942``. If the compiler reports a missing
   ROCm device library, check that ``/opt/rocm/lib`` exists first.

Manual driver recovery
----------------------

Only use the manual steps when the automatic service did not run or the
driver must be reloaded. Run them in order:

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128
   ln -sf /usr/lib/firmware/amdgpu/mi300_discovery \
       /usr/lib/firmware/amdgpu/ip_discovery.bin
   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 \
       ras_enable=0 discovery=2

.. warning::

   The ``dd`` step must run before ``modprobe``; otherwise the driver BIOS
   discovery chain fails and crashes with a NULL dereference in
   ``amdgpu_atom_parse_data_header``. ``ip_block_mask`` must be ``0x67`` to
   disable the unmodeled PSP and SMU; ``0x6f`` causes a kernel panic.

Parameter meanings, ROM details and more known issues are documented in
:ref:`Guest driver requirements <sim-guest-driver>`,
:ref:`Guest parameters <ref-guest-parameters>` and
:ref:`Known issues <ref-known-issues>`.

Related pages
-------------

- :doc:`first_session`
- :doc:`next_steps`
- :ref:`Guest driver requirements <sim-guest-driver>`
- :ref:`Guest parameters <ref-guest-parameters>`
- :ref:`Known issues <ref-known-issues>`
