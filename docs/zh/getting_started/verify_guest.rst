.. SPDX-License-Identifier: Apache-2.0

.. _gs-verify-guest:

验证客户机
==========

本页在客户机内确认 amdgpu 驱动与 ROCm 栈已就绪，并运行第一个 HIP 程序。
驱动参数与手动恢复的完整说明见第 4 章，本页只走默认路径。

自动初始化
----------

客户机启动后，``cosim-gpu-initialize.service`` 自动执行以下步骤：

1. 把 ``/root/roms/mi300.rom`` 写入物理地址 ``0xC0000`` 的 VGA ROM 区域；
2. 把 ``mi300_discovery`` 链接为 ``ip_discovery.bin``；
3. 移除 cmdline 的运行时 modprobe blacklist，然后用固定参数加载 amdgpu；
4. 检查每个 AMD PCI 设备都有对应的 DRM card，否则以非零状态退出。

服务通常约 40 秒完成。检查状态：

.. code-block:: bash

   systemctl status cosim-gpu-initialize.service
   journalctl -u cosim-gpu-initialize.service -b | tail -20

检查 GPU 与 ROCm
----------------

.. code-block:: bash

   dmesg | grep -i amdgpu | tail -20
   lspci -d 1002:
   rocm-smi
   rocminfo | head -40

预期结果：``lspci`` 显示 AMD 设备，``rocm-smi`` 显示设备号 ``0x74a0``，
``rocminfo`` 的代理名称是 ``gfx942``。加载过程中出现若干 fence fallback
timer 警告属于正常现象，是 DRM 探测 ring buffer 时的超时回退。

第一个 HIP 程序
---------------

在客户机内创建向量加法程序：

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

把内容保存为 ``/tmp/vec_add.cpp`` 后编译并运行：

.. code-block:: bash

   /opt/rocm/bin/hipcc --offload-arch=gfx942 -o /tmp/vec_add /tmp/vec_add.cpp
   /tmp/vec_add

预期输出：

.. code-block:: text

   Result: 11 22 33 44
   PASSED!

.. warning::

   ``--offload-arch`` 必须是 ``gfx942``；报错找不到 ROCm device library 时，
   先确认 ``/opt/rocm/lib`` 存在。

手动恢复驱动
------------

只有自动服务未执行或需要重新加载驱动时才使用手动步骤。按顺序执行：

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128
   ln -sf /usr/lib/firmware/amdgpu/mi300_discovery \
       /usr/lib/firmware/amdgpu/ip_discovery.bin
   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 \
       ras_enable=0 discovery=2

.. warning::

   ``dd`` 必须在 ``modprobe`` 之前执行，否则驱动的 BIOS 发现链失败，会在
   ``amdgpu_atom_parse_data_header`` 处发生空指针崩溃。``ip_block_mask``
   必须使用 ``0x67``，同时禁用未建模的 PSP 与 SMU；``0x6f`` 会导致内核
   panic。

参数含义、ROM 写入细节与更多已知问题见 :ref:`客户机驱动要求 <sim-guest-driver>`
与 :ref:`客户机参数 <ref-guest-parameters>`，以及
:ref:`已知问题 <ref-known-issues>`。

相关页面
--------

- :doc:`first_session`
- :doc:`next_steps`
- :ref:`客户机驱动要求 <sim-guest-driver>`
- :ref:`客户机参数 <ref-guest-parameters>`
- :ref:`已知问题 <ref-known-issues>`
