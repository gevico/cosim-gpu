<div align="center">
  <h1 align="center">Cosim-GPU</h1>
  <p><strong>使用 QEMU 和 gem5 进行 YAML 配置的 AMD MI300X GPU 联合仿真</strong></p>
</div>

<p align="center">
  <img alt="Linux x86_64 与 ARM64" src="https://img.shields.io/badge/Linux-x86%5F64%20%7C%20ARM64-FCC624?logo=linux&amp;logoColor=black">
  <img alt="Rust 1.95+" src="https://img.shields.io/badge/Rust-1.95%2B-orange?logo=rust&amp;logoColor=white">
  <img alt="QEMU Device Model" src="https://img.shields.io/badge/QEMU-vfio--user-FF6600">
  <img alt="gem5 MI300X" src="https://img.shields.io/badge/gem5-MI300X-6f42c1">
  <img alt="ROCm HIP" src="https://img.shields.io/badge/ROCm-HIP-ED1C24">
  <img alt="Apache 2.0 许可证" src="https://img.shields.io/badge/license-Apache--2.0-34a853">
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <strong>简体中文</strong>
</p>

<p align="center">
  <a href="https://gevico.github.io/cosim-gpu/zh/getting_started/">快速入门</a> ·
  <a href="https://gevico.github.io/cosim-gpu/zh/topology/">拓扑与硬件支持</a> ·
  <a href="https://gevico.github.io/cosim-gpu/zh/architecture/">整体架构</a>
</p>

使用 YAML 描述 QEMU 和 Device Model 配置，再用 Rust <code>cosim</code> 启动会话。
Host 运行 Host-side QEMU 和独立的 gem5 或 QEMU Device Model 进程。QEMU 使用 KVM
或 TCG 启动 vHost 操作系统，并通过 libvfio-user 支持的 **vfio-user** 接口向
vHost 提供 vGPU/vGPGPU。

## 架构

~~~mermaid
flowchart LR
    YAML[拓扑 YAML] --> CLI[Rust cosim 启动器]

    subgraph Host 操作系统
        CLI --> H[Host-side QEMU]
        CLI --> G[gem5 MI300X Device Model]
        CLI --> Q[QEMU Device Model]
        H <-->|vfio-user / libvfio-user| G
        H <-->|vfio-user| Q
        H --- P[机器内存池]
        G --- P
        Q --- P
    end
    H -->|KVM 或 TCG| V[vHost 操作系统 · Linux · ROCm/HIP]
~~~

启动器准备共享内存和磁盘覆盖层，先启动 Device Model，再启动 Host-side QEMU，
并在会话结束时清理资源。Device Model 负责模拟 vGPU/vGPGPU 的行为和时序。

## 快速入门

~~~bash
just dev-submodules
just dev-image        # 非 Linux Host，或设置 COSIM_ENV=container

# 在带 KVM 的 x86_64 Host 上构建工具链和 vHost 镜像
just build-all
just run-topology resources/machines/single-gpu.yaml
~~~

首次构建镜像时会使用 `resources/images/` 中选定的配方，并将验证后的磁盘与内核
保存在 `build/images/`。可以先检查解析后的配方和启动命令，不构建镜像或启动进程：

~~~bash
just run-topology resources/machines/single-gpu.yaml --dry-run
~~~

### 拓扑示例

- <code>resources/machines/single-gpu.yaml</code>：启动单 GPU vHost。
- <code>resources/machines/mixed-models.yaml</code>：组合 gem5 和 QEMU Device Model。
- <code>resources/machines/gpu-8.yaml</code>：查看八 GPU 机器及其 96 GiB 内存池。
- <code>resources/machines/host-only-aarch64.yaml</code>：在 ARM64 上检查不含 Device Model 的 vHost。

<details>
<summary>示例：一台机器组合 gem5 和 QEMU 设备</summary>

~~~yaml
version: 1
imports:
  - vhosts/qemu.yaml
  - devices/gpu/mi300x.yaml
  - devices/pci/qemu-edu.yaml
machines:
  - id: m0
    vhost: {use: vhost-x86-rocm, memory: 32G}
    devices:
      - {use: mi300x, count: 2}
      - {use: qemu-edu}
~~~

所选 vHost 配置已经包含镜像配方和启动输入。构建产物统一保存在仓库顶层的
`build/` 目录中。

QEMU Device Model 示例使用 <code>just build-qemu</code> 构建的 QEMU，通过
<code>x-vfio-user-server</code> 提供真实的 <code>edu</code> PCI 模型。

</details>

## Host 与构建环境

### 启动器和配置工具

启动器需要 Rust 1.95+、Cargo 和 just。QEMU、gem5 构建，拓扑运行和 Rust 检查
通过 <code>scripts/host/dev.sh</code> 执行。非 Linux Host 或设置
<code>COSIM_ENV=container</code> 时，命令使用基于
<code>scripts/host/Dockerfile.dev</code> 的临时容器。vHost 镜像、HIP 应用以及
<code>just run-launch</code> 和 <code>just test-gpu</code> 使用各自的 Docker 流程。

### Linux Host 运行会话

- 需要 glibc 和 util-linux 提供的 <code>setpriv</code>。
- 需要匹配 Host 架构的 QEMU 和 <code>qemu-img</code>。
- x86_64 Host 使用 <code>qemu-system-x86_64</code>；ARM64 Host 使用
  <code>qemu-system-aarch64</code>。
- <code>COSIM_HOST_ARCH</code> 用于选择构建架构，默认使用当前 Host 架构。
  gem5 在 x86_64 Host 上构建到 <code>build/gem5/x86_64/VEGA_X86</code>，在 ARM64 Host 上构建到
  <code>build/gem5/aarch64/VEGA_X86</code>。

### MI300X 和 QEMU Device Model

- MI300X 联合仿真需要 gem5 VEGA_X86、支持 vfio-user 的 QEMU、vHost 镜像输入，
  以及 Ubuntu vHost 所需的 KVM。
- QEMU 设备服务端需要使用 <code>--enable-vfio-user-server</code> 构建。
- 提供的 Ubuntu/ROCm vHost 镜像构建流程面向 x86_64。
- vHost 镜像和模拟器产物需要足够的磁盘空间。内存池所在文件系统必须容纳完整的机器布局。

## 仓库目录

- **Rust 工作区：** <code>crates/cosim-topology/</code>、
  <code>crates/cosim-runtime/</code> 和 <code>crates/cosim-cli/</code>。
- **模拟器模型：** <code>third_party/gem5/</code>、
  <code>third_party/qemu/</code> 和 <code>configs/sst/</code>。
- **GPU 工作负载和 vHost 固件输入：** <code>third_party/gem5-resources/</code>。
- **机器配置：** <code>resources/vhosts/</code>、<code>resources/devices/</code>、
  <code>resources/machines/</code> 和 <code>resources/clusters/</code>。
- **示例程序：** <code>samples/</code> 留给 vHost 启动后运行的程序。
- **项目工具：** <code>scripts/</code>、
  <code>justfile</code> 和 <code>.agents/</code>。
- **vHost 镜像配方：** <code>resources/images/recipes/</code> 中按操作系统组织的
  Packer/QEMU 配置、Ansible playbook 和镜像文件。
- **vHost 通用脚本：** 多个 vHost 镜像配方共用的脚本放在 <code>resources/scripts/</code>。
- **Host 与 CI 脚本：** Host 上由 just 调用的工具放在 <code>scripts/host/</code>；
  workflow 专用辅助程序和测试放在 <code>scripts/ci/</code>。

## 更多文档

- [文档首页](https://gevico.github.io/cosim-gpu/zh/)
- [参考手册](https://gevico.github.io/cosim-gpu/zh/reference/)
- [贡献指南](https://gevico.github.io/cosim-gpu/zh/contributing/)

顶层项目使用 [Apache 2.0 许可证](LICENSE)。子模块保留各自的许可证。
