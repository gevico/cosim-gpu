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
     - 主机侧检查；会话与镜像工具测试构建锁定的 QEMU 子模块
   * - ``build.yml``
     - push/PR 到 ``main``，或手动触发
     - 按变更选择镜像配方检查，必要时构建 gem5 并调用完整回归
   * - ``image.yml``
     - 由 ``build.yml`` 以 ``workflow_call`` 调用
     - 验证、构建或复用指定配方并发布镜像；可选使用本地镜像执行 ROCm 回归
   * - ``assigner.yml``
     - ``pull_request_target`` 与 issue 标签事件
     - 按 ``MAINTAINERS.yml`` 添加标签、请求审查并分配负责人

快速检查
--------

``ci.yml`` 中的任务在每次 push 和拉取请求上运行：

会话与镜像工具测试先运行 ``just ci-build-qemu``，从锁定的子模块构建
``build/qemu/`` 下的 QEMU 和镜像工具。

镜像构建在 Packer 校验前执行 ``just ci-prepare-image-host <recipe>``。
配方加载器读取客户机架构并调用 ``just ci-build-qemu <architecture>``，因此 RISC-V
镜像会获得 ``build/qemu/qemu-system-riscv64`` 和同一源码构建的镜像工具。
此架构选择不改变编译 Host 架构。

- ``Rust Topology and Runtime``：运行 ``just check-cosim``、
  ``just test-cosim-integration`` 与 ``just test-cosim-memory``。
- ``CI helper tests``：运行 ``python3 -m unittest discover
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
- 仅修改已有配方目录及文档：选择受影响的配方，每个配方都准备镜像并执行 HIP 回归。
- 公共文件、工作流、无法归类的路径、删除或移动配方：选择全部现有配方，每个只运行一次。

配方列表来自现有目录中的 ``recipe.toml``。每个被选中的配方还必须提供
``regression.toml``；缺少配置时选择任务直接失败，不会静默跳过 GPU 测试。
首次 push 没有可比较的前置提交时检查所有配方；比较失败则检查失败。
手动触发时，填写 ``recipe`` 只准备和测试该配方，留空则测试全部配方。
两种路径都准备 gem5，并要求 HIP 工作负载通过。

每个配方 job 校验真实的 Packer/Ansible 配置，准备经过验证的镜像，检查产物完整性
和复用隔离，再执行 GPU 工作负载。Packer 构建时成功启动虚拟机，并不能证明
最终镜像能按仿真拓扑完成 GPU 测试。任务当前在 Ubuntu x86_64 runner 上运行，
配方仍需匹配的 QEMU、固件、加速条件和回归配置；新平台补充对应的环境准备与回归配方。

构建缓存与产物
--------------

Ubuntu 测试镜像配方在安装软件包前关闭周期性 APT 操作，停止并屏蔽更新定时器，
屏蔽对应服务，并等待已经启动的更新自然结束，不强制终止软件包操作。
生成的镜像保持关闭自动更新，软件包变更通过重新构建配方完成。最后的缓存清理
仍在出错时终止构建。

所有选中的配方都使用 ``image.yml`` 中的镜像准备与 GPU 回归流程：

- ``Build gem5 (VEGA_X86)`` 只编译一次 gem5。缓存键由 ``just ci-gem5-key``
  计算，覆盖 gem5 输入、相关 just 配方与配置、构建任务、辅助脚本和 Dockerfile。
  just 变量只收集明确列出的 gem5 与开发容器构建设置；vHost recipe、镜像输出
  路径及其他 vHost 配置不参与 gem5 缓存键。
  命中缓存时保留原始的 ``build_source`` 与 ``build_run``，本轮任务的源码
  版本与运行标识单独记录。修改 ``COSIM_GEM5_CACHE_EPOCH`` 可以重新构建工具
  环境。产物包含二进制、模型测试需要的 ``libvfio-user.a``、开发容器镜像和
  SHA-256 清单，通过 ``just ci-reuse-gem5`` 发布为本轮工作流的固定 artifact，
  并由 ``just test-runtime-artifact`` 校验完整性与来源。
- ``Image preparation and GPU regression`` 校验所选配方的真实 Packer 构建器与 provisioner，然后查找
  同一源分支下经过验证的保留镜像。镜像键覆盖相关文件摘要、配方内容、QEMU 工具链、
  镜像构建程序与磁盘格式；复用时校验输入标识和全部产物
  摘要。把 ``COSIM_ROCM_IMAGE_EPOCH`` 从默认值 ``1`` 改为新值，可以重新解析
  软件包依赖。完成的镜像记录配方声明的软件版本信息，以及
  ``manifest.json`` 中的 SHA-256。
- ``Recipe (<recipe>)`` 为每个选中的配方调用一次 ``image.yml``，与 gem5 并行准备
  镜像，并在 GPU 测试前同步。主机侧辅助脚本检查独立显示为 ``CI helper tests``。
- ``ROCm regression gate`` 始终运行，任一任务失败或取消都不能通过；按选择条件
  跳过的任务不阻塞检查。在分支保护中将它设置为必需检查。

``gem5-runtime-*`` 与 ``rocm-guest-*`` 产物保留两天；
``rocm-image-logs-*`` 与回归证据保留十四天。手动触发 ``build.yml`` 可以
再次运行完整流程，或通过 ``recipe`` 输入只验证一个配方。镜像 artifact 名称含
配方标识的摘要，以便同一轮运行保存多个配方的产物。

镜像也能跨同一源分支的多次 CI 运行复用。输入键不包含项目提交号和 CI run ID，
CModel 源码也不属于镜像输入；仅修改 CModel 时，可以复用前一次运行生成的匹配镜像。
新的 runner 仍需下载 bundle 并校验其输入标识与全部文件摘要。找不到产物、产物过期
或镜像输入变化时才重新构建，不会因此跳过 HIP 测试。当前镜像保留期仍为两天，
来源仍限制为同一分支。

ROCm 回归
---------

每个镜像与其回归在同一个 job 内运行，让校验后的磁盘和内核保留在 runner 本地。
GitHub-hosted 的每个 job 都使用独立环境，详见
`runner 选择说明 <https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job>`_。
相同的 ``runs-on`` 标签和 ``needs`` 依赖不保证两个 job 在同一台机器上运行。
自建持久 runner 可以通过唯一标签固定到一台机器，但文件保留和清理由项目自行管理。

镜像准备与独立的 gem5 job 并行。镜像 job 不设置对 gem5 的 ``needs`` 依赖，
而是在本地镜像准备完成后执行 ``just ci-wait-gem5``。它查询本次 workflow run 中截至当前 attempt 的最新 gem5 生产任务；
失败或取消则停止，最多等待两小时，确认成功后选择对应的固定 artifact，再下载和
恢复 gem5。仅重跑失败任务时，可复用同一 run 中此前已成功且未被重跑的生产任务。
GitHub 可能把它的成功记录复制到新 attempt，而不重新执行。开始与完成时间均相同的记录
对应原来的执行，产物名称保留原 attempt 编号。无需额外启动后台步骤，因为准备镜像时 gem5 已经在
并行运行。最终回归 gate 仍要求所有相关任务通过。

这样既保留并行准备，也省掉把系统盘传给第二台 runner 的开销。作为本次调整依据的
运行中，gem5 产物下载约一分钟，客户机镜像下载约五十分钟；这是实测耗时，不是传输
速度保证。镜像仍会发布，供后续 CI 运行复用；跨次复用仍校验准确的输入键和全部
产物摘要。每个配方 job 都为镜像准备和回归预留五小时。

配方通过 ``recipe.toml`` 旁的 ``regression.toml`` 接入完整 GPU 回归，引用
``resources/machines`` 下的 machine YAML 和本配方目录中的客户机准备脚本。
启动参数归 machine/vHost 模板管理；回归入口根据镜像配方架构选择 QEMU 并校验
对应产物，不再从 Ubuntu 或编译 Host 推断启动配置。Ubuntu 准备初始化服务和 ROM，
openRuyi 准备本地编译器环境并加载 amdgpu。两个配方均提供 root 串口访问。
通用的 ``tests/rocm_regression.sh`` 通过只读 9p 共享，统一执行 GPU 检查、编译和测试。

合并后的 job 按以下顺序运行：

1. 准备源码构建的 QEMU 和镜像工具；校验 Packer，构建镜像或接管保留镜像，并检查
   完整性、复用与来源隔离。
2. 发布镜像供后续运行使用，同时保留本地磁盘与内核。
3. 等待本轮 gem5 生产任务成功，下载对应的固定运行时产物，恢复经过验证的二进制
   和开发容器镜像。
4. 执行会话内存、MI300X 模型和 vfio-user ROM 检查，并构建 Rust launcher。
5. 将本地镜像目录与配方标识传给 ``just test-rocm-regression``；失败时也保留诊断，
   各配方使用独立的 artifact 名称。

``just test-rocm-regression <output> <assets> <recipe>`` 使用 Rust launcher 和配方
引用的 machine 配置，并为每个用例创建独立的磁盘 overlay。默认使用 4 GiB Linux 内存、
4 GiB VRAM 和两个虚拟 CPU；8 GiB 共享内存池能够放入托管 runner 的共享内存容量，
并为模拟器保留内存。通过 ``--memory``、``--vram`` 和 ``--cpus`` 参数
可以修改这些设置。

回归程序为 ``vector_add``、``gemm``、``reduction``、
``transpose``、``prefix_scan`` 和 ``histogram``。每个客户机执行配方准备脚本并检查
amdgpu、KFD、render 设备以及 ``rocminfo`` 报告的 gfx942 agent，然后在
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
   just test-rocm-regression <output> <assets> <recipe>

相关页面
--------

- :doc:`workflow`
- :doc:`patch_check`
- :ref:`gs-guest-image`
- :ref:`ref-version-matrix`
