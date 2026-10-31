.. SPDX-License-Identifier: Apache-2.0

.. _contrib-ci:

CI 与回归
=========

本页说明仓库的 GitHub Actions 工作流、快速检查、构建缓存，以及 ROCm 回归流程。

工作流总览
----------

.. list-table::
   :header-rows: 1

   * - 工作流
     - 触发
     - 作用
   * - ``docs.yml``
     - 修改 ``docs/**``、``justfile`` 或 README 的 push/PR
     - 构建中英文文档，执行双语与站点检查；``main`` 上部署 GitHub Pages
   * - ``ci.yml``
     - push/PR 到 ``main``
     - 不超过 5 分钟的主机侧检查，不需要子模块
   * - ``build.yml``
     - push/PR 到 ``main``，或手动触发
     - 按变更选择镜像配方检查，必要时构建 gem5 并调用完整回归
   * - ``image.yml``
     - 由 ``build.yml`` 以 ``workflow_call`` 调用
     - 独立验证、构建或复用一个指定配方的镜像并发布产物
   * - ``integration.yml``
     - 由 ``build.yml`` 以 ``workflow_call`` 调用
     - 在 KVM runner 上执行完整的 ROCm 客户机回归
   * - ``assigner.yml``
     - ``pull_request_target`` 与 issue 标签事件
     - 按 ``MAINTAINERS.yml`` 添加标签、请求审查并分配负责人

快速检查
--------

``ci.yml`` 中的任务在每次 push 和拉取请求上运行：

- ``Rust Topology and Runtime``：运行 ``just check-cosim``、
  ``just test-cosim-integration`` 与 ``just test-cosim-memory``。
- ``ROCm regression runner tests``：运行 ``python3 -m unittest discover
  -s scripts/ci -p 'test_*.py' -v``。
- ``Checkpatch``：对拉取请求使用基准提交、对 push 使用推送前提交运行
  ``just check-patch``；没有可用的前置提交时回退到 ``HEAD^``。
- ``Maintainers``：安装 ``scripts/ci/requirements.txt`` 后运行
  ``just check-maintainers``。
- ``ShellCheck``：运行 ``just check-shell``。
- ``Modprobe Params (Regression #9)``：运行 ``just check-modprobe-params``。
- ``GPU Kernel Compile``：运行 ``just build-gpu-tests``。

``Checkpatch`` 任务失败会阻止拉取请求合并。修正报告中的行，修改或变基相关提交，
然后强制推送分支。文档工作流先运行 ``docs/scripts/build.sh``，再运行
``docs/scripts/check_i18n.py`` 与 ``docs/scripts/verify_build.py``；
``main`` 分支的构建产物发布到 GitHub Pages。

配方检查的选择
--------------

``build.yml`` 先比较 PR 与目标分支，或 push 前后的完整变更列表：

- 仅修改 ``docs/`` 或中英文 README：跳过重型构建与回归。
- 仅修改已有配方目录及文档：每个受影响配方单独运行 ``image.yml``，跳过 gem5
  和完整 ROCm 回归。
- 公共文件、工作流、无法归类的路径、删除或移动配方：检查所有现有配方并保留
  完整回归。Ubuntu 基线镜像由完整回归的生产任务提供，不再重复构建。

配方列表使用现有目录中的 ``recipe.toml``；完整回归的基线取自 ``justfile`` 的
``rocm_recipe``。首次 push 没有可比较的前置提交时运行完整流程；比较失败则检查失败。
手动触发时，填写 ``recipe`` 只检查该配方，留空则运行完整流程。

镜像任务不依赖 gem5。它验证真实的 Packer/Ansible 配置，构建或校验镜像，并验证
产物完整性和复用隔离。Packer 构建时会启动临时 QEMU 并安装软件；这不等于验证
产物按仿真拓扑再次启动或完成 GPU 工作负载。任务当前在 Ubuntu x86_64 runner 上运行，
配方仍需具备匹配的 QEMU、固件及加速条件；新平台的环境准备随平台支持补充。

构建缓存与产物
--------------

完整回归复用 ``image.yml`` 中的镜像生产流程：

- ``Build gem5 (VEGA_X86)`` 只编译一次 gem5。缓存键由 ``just ci-gem5-key``
  计算，覆盖 gem5 输入、相关 just 配方与配置、构建任务、辅助脚本和 Dockerfile。
  just 变量只收集明确列出的 gem5 与开发容器构建设置；vHost recipe、镜像输出
  路径及其他 vHost 配置不参与 gem5 缓存键。
  命中缓存时保留原始的 ``build_source`` 与 ``build_run``，本轮任务的源码
  版本与运行标识单独记录。修改 ``COSIM_GEM5_CACHE_EPOCH`` 可以重新构建工具
  环境。产物包含二进制、模型测试需要的 ``libvfio-user.a``、开发容器镜像和
  SHA-256 清单，通过 ``just ci-reuse-gem5`` 发布为本轮工作流的固定 artifact，
  并由 ``just test-runtime-artifact`` 校验完整性与来源。
- ``Image`` 任务校验所选配方的真实 Packer 构建器与 provisioner，然后查找
  同一源分支下经过验证的保留镜像。镜像键覆盖源码版本、配方内容、QEMU 版本、镜像
  构建程序与磁盘格式；复用时校验输入标识和全部产物
  摘要。把 ``COSIM_ROCM_IMAGE_EPOCH`` 从默认值 ``1`` 改为新值，可以重新解析
  软件包依赖。完成的镜像记录配方声明的软件版本信息，以及
  ``manifest.json`` 中的 SHA-256。
- ``ROCm regression`` 调用 ``integration.yml``，传入 gem5 产物 ID、
  客户机镜像产物 ID 和镜像输入键。
- ``ROCm regression gate`` 始终运行，任一任务失败或取消都不能通过；按选择条件
  跳过的任务不阻塞检查。在分支保护中将它设置为必需检查。

``gem5-runtime-*`` 与 ``rocm-guest-*`` 产物保留两天；
``rocm-image-logs-*`` 与回归证据保留十四天。手动触发 ``build.yml`` 可以
再次运行完整流程，或通过 ``recipe`` 输入只验证一个配方。镜像 artifact 名称含
配方标识的摘要，以便同一轮运行保存多个配方的产物。

ROCm 回归
---------

``integration.yml`` 使用 ``build.yml`` 返回的固定 artifact ID，而不是重新
构建：

1. 检查 runner 为 x86_64 且 ``/dev/kvm`` 可用，初始化子模块。
2. 下载 gem5 产物，通过 ``just ci-restore-gem5`` 恢复经过验证的 gem5 与开发
   容器镜像。
3. 运行 ``just test-cosim-memory`` 验证并发会话的内存预留，再运行
   ``just test-gem5-mi300x`` 测试恢复后的 MI300X 模型。
4. 下载客户机镜像产物，通过 ``just ci-adopt-rocm-artifact`` 核对镜像输入键并
   接管磁盘、内核与软件包清单。
5. 构建 QEMU 与 Rust launcher，运行 ``just test-cosim-vfio-user`` 验证
   vfio-user 的 option ROM 暴露，再运行
   ``just test-rocm-regression`` 执行回归程序。

``just test-rocm-regression <output> <assets>`` 使用 Rust launcher 和示例
host/device 模板，并为每个用例创建独立的磁盘 overlay。默认使用 4 GiB Linux 内存、
4 GiB VRAM 和两个虚拟 CPU；8 GiB 共享内存池能够放入托管 runner 的共享内存容量，
并为模拟器保留内存。通过 ``--memory``、``--vram`` 和 ``--cpus`` 参数
可以修改这些设置。

回归程序为 ``vector_add``、``gemm``、``reduction``、
``transpose``、``prefix_scan`` 和 ``histogram``。每个客户机检查初始化
服务、amdgpu、KFD、render 设备以及 ``rocminfo`` 报告的 gfx942 agent，然后在
``HSA_ENABLE_INTERRUPT=0`` 环境下编译并执行指定的 HIP 程序。通过条件包括数值
校验输出 PASS、程序以零状态退出、launcher 成功清理资源；程序打印 PASS 后发生超时
仍然判定失败。执行在首个失败处停止，只有全部指定程序通过时整体结果才为 PASS。

``rocm-regression-*`` 产物保留完整串口和模型日志、拓扑与命令清单、源码版本、
二进制摘要、各程序结果以及 ``matrix.tsv``。

本地复现
--------

.. code-block:: bash

   python3 -m unittest discover -s scripts/ci -p 'test_*.py' -v  # CI 辅助脚本单元测试
   just test-legacy-build-image    # 遗留构建入口使用主机 Docker
   just test-cosim-memory          # 并发会话的内存预留与释放
   just test-cosim-integration     # 会话、取消与日志保留
   just test-runtime-artifact <source> <output>  # 运行时缓存完整性与来源
   just test-rocm-artifact <key> <output>        # 镜像选择与隔离

   # ROCm 镜像与回归
   just build-rocm-assets
   just test-rocm-assets
   just test-rocm-regression <output> <assets>

相关页面
--------

- :doc:`workflow`
- :doc:`patch_check`
- :ref:`gs-guest-image`
- :ref:`ref-version-matrix`
