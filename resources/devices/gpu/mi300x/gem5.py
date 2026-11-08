# Copyright (c) 2024 The gem5 Contributors
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

"""MI300X model assembly for the generic gem5 device runner.

Builds a minimal gem5 system with MI300X GPU model(s) (no x86 kernel,
no CPU execution).  QEMU handles all host-side simulation (CPU, kernel
boot, PCI enumeration, ROCm driver); gem5 provides the GPU compute
back-end via Unix domain socket bridges.

Multi-GPU support (--num-gpus N):
  Each GPU gets its own AMDGPUDevice, Shader, vfio-user bridge, and
  VRAM shared memory region.  The Ruby GPU cache hierarchy is shared
  across all GPUs in a single gem5 process (single-process model).

Only the vfio-user backend supports multi-GPU.

Architecture (single GPU):
    QEMU (guest Linux + amdgpu driver)
        |  Unix domain socket
        v
    MI300XVfioUser (this config, in gem5)
        |  forward via AMDGPUDevice read/write
        v
    AMDGPUDevice + Shader + Ruby GPU hierarchy

Architecture (multi-GPU, N=2 example)::

    QEMU (guest Linux + amdgpu driver)
        |              |
        | socket-0     | socket-1
        v              v
    VfioUser-0      VfioUser-1
        |              |
        v              v
    GPU-0            GPU-1
    (Shader-0)       (Shader-1)
         \\            /
         Ruby GPU hierarchy (shared)

Shared memory:
    /dev/shm/cosim-guest-ram     - guest physical memory (QEMU + gem5 DMA)
    /dev/shm/mi300x-vram         - GPU VRAM (single-GPU)
    /dev/shm/mi300x-vram-{0..N}  - per-GPU VRAM (multi-GPU)
"""

from __future__ import annotations

import json
import math
import os

import m5
from m5.objects import *
from m5.util import convert

from amd import AmdGPUOptions
from common import (
    GPUTLBConfig,
    GPUTLBOptions,
    ObjectList,
    Options,
)
from example.gpufs.Disjoint_VIPER import *
from ruby import Ruby
from system.amdgpu import (
    connectGPU,
    createGPU,
)


def addCosimOptions(parser):
    parser.add_argument(
        "--shared-pool",
        default="",
        help="Existing pool file containing guest RAM and this GPU's VRAM",
    )
    parser.add_argument(
        "--pool-vram-offset", type=int, default=0, help="VRAM byte offset"
    )
    parser.add_argument(
        "--host-memory-ranges",
        type=json.loads,
        help="JSON array of guest RAM start, size and pool offset values",
    )
    parser.add_argument(
        "--socket-path",
        type=str,
        default="/tmp/gem5-mi300x.sock",
        help="Unix domain socket path for QEMU connection "
        "(multi-GPU: base path, e.g. /tmp/gem5-mi300x for "
        "/tmp/gem5-mi300x-0.sock, /tmp/gem5-mi300x-1.sock, ...)",
    )
    parser.add_argument(
        "--shmem-path",
        type=str,
        default="/mi300x-vram",
        help="POSIX shared memory name for VRAM "
        "(multi-GPU: base path, e.g. /mi300x-vram for "
        "/mi300x-vram-0, /mi300x-vram-1, ...)",
    )
    parser.add_argument(
        "--shmem-host-path",
        type=str,
        default="/cosim-guest-ram",
        help="POSIX shared memory name for host (guest) RAM",
    )
    parser.add_argument(
        "--num-gpus",
        type=int,
        default=1,
        help="Number of MI300X GPU instances (default: 1)",
    )
    parser.add_argument(
        "--xgmi-topology",
        type=str,
        choices=["mesh", "ring"],
        default=None,
        help="xGMI interconnect topology (requires --num-gpus >= 2)",
    )
    parser.add_argument(
        "--xgmi-bandwidth",
        type=str,
        default="128GB/s",
        help="xGMI per-link bandwidth (default: 128GB/s)",
    )
    parser.add_argument(
        "--xgmi-latency",
        type=str,
        default="100ns",
        help="xGMI per-hop latency (default: 100ns)",
    )


def _gpu_socket_path(base_path, gpu_id, num_gpus):
    """Per-GPU socket path. Single-GPU preserves original path."""
    if num_gpus == 1:
        return base_path
    stem, ext = os.path.splitext(base_path)
    if not ext:
        ext = ".sock"
    return f"{stem}-{gpu_id}{ext}"


def _gpu_shmem_path(base_path, gpu_id, num_gpus):
    """Per-GPU VRAM shared memory name. Single-GPU preserves original path."""
    if num_gpus == 1:
        return base_path
    return f"{base_path}-{gpu_id}"


def _create_per_gpu_components(system, args, gpu_id, num_gpus):
    """Create all per-GPU components: device, shader, SDMA, PM4, HSA, IH.

    Returns (gpu_device, shader, dma_ports) where dma_ports is the list
    of DMA-capable ports that need Ruby DMA controllers.
    """
    # GPU device (PCI)
    gpu = connectGPU(system, args, gpu_id)
    if gpu_id > 0:
        setattr(system, f"gpu{gpu_id}", gpu)
    gpu.upstream = system.pc.pci_host
    gpu.BAR4 = PciMemBar(size="8KiB")
    gpu.vram_shared_backstore = _gpu_shmem_path(
        args.shmem_path, gpu_id, num_gpus
    )
    if args.shared_pool:
        gpu.vram_shared_backstore = args.shared_pool
        gpu.vram_shared_backstore_is_file = True
        gpu.vram_shared_backstore_offset = args.pool_vram_offset
        gpu.vram_shared_backstore_limit = args.dgpu_mem_size

    # Shader (CU array)
    shader = createGPU(system, args, gpu_id)

    # HSA Packet Processor
    hsapp_gpu_map_paddr = 0xE0000000 + gpu_id * 0x01000000
    hsapp_pt_walker = VegaPagetableWalker()
    gpu_hsapp = HSAPacketProcessor(
        pioAddr=hsapp_gpu_map_paddr,
        numHWQueues=args.num_hw_queues,
        walker=hsapp_pt_walker,
    )
    dispatcher = GPUDispatcher()
    cp_pt_walker = VegaPagetableWalker()
    gpu_cmd_proc = GPUCommandProcessor(
        hsapp=gpu_hsapp,
        dispatcher=dispatcher,
        walker=cp_pt_walker,
    )
    shader.dispatcher = dispatcher
    shader.gpu_cmd_proc = gpu_cmd_proc
    gpu.cp = gpu_cmd_proc

    # GPU Interrupt Handler
    device_ih = AMDGPUInterruptHandler()
    gpu.device_ih = device_ih

    # SDMA engines (MI300X: 16)
    sdma_bases = [
        0x4980,
        0x6180,
        0x65000,
        0x66000,
        0x84980,
        0x86180,
        0xE5000,
        0xE6000,
        0x104980,
        0x106180,
        0x165000,
        0x166000,
        0x184980,
        0x186180,
        0x1E5000,
        0x1E6000,
    ]
    num_sdmas = 16
    sdma_sizes = [0x1000] * num_sdmas
    sdma_pt_walkers = []
    sdma_engines = []
    for idx in range(num_sdmas):
        w = VegaPagetableWalker()
        e = SDMAEngine(
            walker=w,
            mmio_base=sdma_bases[idx],
            mmio_size=sdma_sizes[idx],
        )
        sdma_pt_walkers.append(w)
        sdma_engines.append(e)
    gpu.sdmas = sdma_engines

    # PM4 packet processors (8)
    pm4_procs = []
    pm4_ranges = [
        (0xC000, 0xD000),
        (0x4C000, 0x4D000),
        (0x8C000, 0x8D000),
        (0xCC000, 0xCD000),
        (0x10C000, 0x10D000),
        (0x14C000, 0x14D000),
        (0x18C000, 0x18D000),
        (0x1CC000, 0x1CD000),
    ]
    for ip_id, (start, end) in enumerate(pm4_ranges):
        pm4_procs.append(
            PM4PacketProcessor(
                ip_id=ip_id,
                mmio_range=AddrRange(start=start, end=end),
            )
        )
    gpu.pm4_pkt_procs = pm4_procs

    # GPU memory manager and system hub
    gpu_mem_mgr = AMDGPUMemoryManager(cache_line_size=args.cacheline_size)
    gpu.memory_manager = gpu_mem_mgr
    system_hub = AMDGPUSystemHub()
    shader.system_hub = system_hub

    # Attach GPU to PCI bus
    system.pc.attachPciDevice(gpu)

    # Collect DMA ports for Ruby
    dma_ports = []
    dma_ports.append(gpu_hsapp)
    dma_ports.append(gpu_cmd_proc)
    for sdma in sdma_engines:
        dma_ports.append(sdma)
    dma_ports.append(device_ih)
    for pm4 in pm4_procs:
        dma_ports.append(pm4)
    dma_ports.append(system_hub)
    dma_ports.append(gpu_mem_mgr)
    dma_ports.append(hsapp_pt_walker)
    dma_ports.append(cp_pt_walker)
    for w in sdma_pt_walkers:
        dma_ports.append(w)

    # PIO ports
    gpu_hsapp.pio = system.iobus.mem_side_ports
    gpu_cmd_proc.pio = system.iobus.mem_side_ports
    for sdma in sdma_engines:
        sdma.pio = system.iobus.mem_side_ports
    device_ih.pio = system.iobus.mem_side_ports
    for pm4 in pm4_procs:
        pm4.pio = system.iobus.mem_side_ports
    system_hub.pio = system.iobus.mem_side_ports

    return gpu, shader, dma_ports


def _host_memory_ranges(ranges: object, total_size: int) -> tuple[list, int]:
    page_size = os.sysconf("SC_PAGE_SIZE")
    if ranges is None:
        low_limit = 0x80000000 if total_size >= 0xB0000000 else 0xB0000000
        low_size = min(total_size, low_limit)
        ranges = [{"start": 0, "size": low_size, "offset": 0}]
        if total_size > low_size:
            ranges.append(
                {
                    "start": 0x100000000,
                    "size": total_size - low_size,
                    "offset": low_size,
                }
            )
    if not isinstance(ranges, list) or not 1 <= len(ranges) <= 64:
        raise ValueError("host memory map requires 1..64 ranges")
    result = []
    base_offset = None
    expected_offset = 0
    previous_end = 0
    for entry in ranges:
        if not isinstance(entry, dict) or set(entry) != {
            "start",
            "size",
            "offset",
        }:
            raise ValueError("host memory range requires start, size, offset")
        start, size, offset = (entry["start"], entry["size"], entry["offset"])
        if any(type(value) is not int for value in (start, size, offset)):
            raise ValueError("host memory range values must be integers")
        if base_offset is None:
            base_offset = expected_offset = offset
        if offset < 0 or offset + size > (1 << 63) - 1:
            raise ValueError("host memory backing offset overflows")
        if start < previous_end or size <= 0 or start + size >= 1 << 64:
            raise ValueError("host memory range overlaps or overflows")
        if (
            start % page_size
            or size % page_size
            or offset % page_size
            or offset != expected_offset
        ):
            raise ValueError(
                "host memory range alignment or offset is invalid"
            )
        result.append(AddrRange(start, size=size))
        previous_end = start + size
        expected_offset += size
    if expected_offset - base_offset != total_size:
        raise ValueError("host memory map size must equal --mem-size")
    return result, base_offset


def buildCosimSystem(args):
    """Build a minimal gem5 GPU-only system for cosimulation with QEMU.

    Supports multiple GPU instances (--num-gpus N).  Each GPU gets its
    own AMDGPUDevice, Shader, and vfio-user bridge.  The Ruby GPU cache
    hierarchy is shared across all GPUs in the single gem5 process.
    """
    num_gpus = getattr(args, "num_gpus", 1)
    if num_gpus < 1:
        m5.util.panic("--num-gpus must be >= 1")
    if args.shared_pool:
        if num_gpus != 1:
            m5.util.panic("--shared-pool requires one GPU per process")

    per_gpu_cus = args.num_compute_units

    # Scale derived cache counts to cover ALL CUs across ALL GPUs
    total_cus = per_gpu_cus * num_gpus
    n_cu = total_cus
    args.num_sqc = int(math.ceil(float(n_cu) / args.cu_per_sqc))
    args.num_scalar_cache = int(
        math.ceil(float(n_cu) / args.cu_per_scalar_cache)
    )

    # Minimal system — StubWorkload by default, no kernel needed
    system = System()
    system.mem_mode = "atomic_noncaching"
    system.m5ops_base = 0xFFFF0000

    total_mem = convert.toMemorySize(args.mem_size)
    ranges, ram_offset = _host_memory_ranges(
        args.host_memory_ranges, total_mem
    )
    system.mem_ranges = ranges
    if ram_offset and not args.shared_pool:
        m5.util.panic("Nonzero host RAM offsets require --shared-pool")

    # Share host memory with QEMU via POSIX shared memory
    system.shared_backstore = args.shmem_host_path
    system.auto_unlink_shared_backstore = True
    if args.shared_pool:
        vram_end = args.pool_vram_offset + convert.toMemorySize(
            args.dgpu_mem_size
        )
        if (
            args.pool_vram_offset < ram_offset + total_mem
            and ram_offset < vram_end
        ):
            m5.util.panic("Pool VRAM overlaps guest RAM")
        system.shared_backstore = args.shared_pool
        system.shared_backstore_is_file = True
        system.shared_backstore_offset = ram_offset
        system.shared_backstore_limit = args.mem_size
        system.auto_unlink_shared_backstore = False

    # PCI infrastructure
    system.pc = Pc()
    system.pc.south_bridge.cmos.disable_rtc_events = True
    system.pc.south_bridge.pit.disable_timer_events = True

    # Clock domains
    system.voltage_domain = VoltageDomain(voltage=args.sys_voltage)
    system.clk_domain = SrcClockDomain(
        clock=args.sys_clock, voltage_domain=system.voltage_domain
    )
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(
        clock=args.cpu_clock, voltage_domain=system.cpu_voltage_domain
    )

    # Bus setup
    system.iobus = IOXBar()
    system._dma_ports = [system.pc.pci_host.up_request_port()]
    system.pc.attachIO(system.iobus, system._dma_ports)

    # Minimal dummy CPU
    system.cpu = [AtomicSimpleCPU(clk_domain=system.cpu_clk_domain, cpu_id=0)]

    # ----------------------------------------------------------------
    # Create N GPU instances
    # ----------------------------------------------------------------
    gpu_devices = []
    shader_list = []
    shader_indices = []

    for gpu_id in range(num_gpus):
        gpu, shader, dma_ports = _create_per_gpu_components(
            system, args, gpu_id, num_gpus
        )
        gpu_devices.append(gpu)
        shader_list.append(shader)

        # Append shader as "CPU" (needed by GPUTLBConfig and Ruby wiring)
        shader_idx = len(system.cpu)
        system.cpu.append(shader)
        shader_indices.append(shader_idx)

        # Accumulate DMA ports
        system._dma_ports.extend(dma_ports)

    # ----------------------------------------------------------------
    # TLB hierarchy (per GPU)
    # ----------------------------------------------------------------
    args.full_system = True
    # Configure each GPU's local translation hierarchy.
    saved_cus = args.num_compute_units
    args.num_compute_units = per_gpu_cus
    args.num_sqc = int(math.ceil(float(per_gpu_cus) / args.cu_per_sqc))
    args.num_scalar_cache = int(
        math.ceil(float(per_gpu_cus) / args.cu_per_scalar_cache)
    )
    for gpu_id in range(num_gpus):
        GPUTLBConfig.config_tlb_hierarchy(
            args,
            system,
            shader_indices[gpu_id],
            gpu_devices[gpu_id],
            True,
            tlb_owner=gpu_devices[gpu_id],
        )
    args.num_compute_units = saved_cus

    # ----------------------------------------------------------------
    # Ruby GPU memory hierarchy (disjoint VIPER)
    # ----------------------------------------------------------------
    # Use total CU count so Ruby creates enough cache controllers
    args.num_compute_units = total_cus
    args.num_sqc = int(math.ceil(float(total_cus) / args.cu_per_sqc))
    args.num_scalar_cache = int(
        math.ceil(float(total_cus) / args.cu_per_scalar_cache)
    )

    system.ruby = Disjoint_VIPER()
    system.ruby.create(
        args,
        system,
        system.iobus,
        system._dma_ports,
        gpu_devices=gpu_devices,
    )
    system.ruby.clk_domain = SrcClockDomain(
        clock=args.ruby_clock, voltage_domain=system.voltage_domain
    )

    # ----------------------------------------------------------------
    # Wire CPU ports
    # ----------------------------------------------------------------
    for i in range(args.num_cpus):
        cpu = system.cpu[i]
        cpu.clk_domain = system.cpu_clk_domain
        cpu.createThreads()
        cpu.createInterruptController()
        system.ruby._cpu_ports[i].connectCpuPorts(cpu)

    # ----------------------------------------------------------------
    # Wire GPU ports to Ruby (all GPUs' CUs)
    # ----------------------------------------------------------------
    gpu_port_idx = (
        len(system.ruby._cpu_ports)
        - total_cus
        - args.num_sqc
        - args.num_scalar_cache
    )
    gpu_port_idx -= args.num_cp * 2

    # Token ports
    token_port_idx = 0
    for i in range(len(system.ruby._cpu_ports)):
        if isinstance(system.ruby._cpu_ports[i], VIPERCoalescer):
            # Find which shader and local CU index this token belongs to
            shader_gpu_id = token_port_idx // per_gpu_cus
            local_cu = token_port_idx % per_gpu_cus
            if shader_gpu_id < num_gpus:
                system.cpu[shader_indices[shader_gpu_id]].CUs[
                    local_cu
                ].gmTokenPort = system.ruby._cpu_ports[i].gmTokenPort
            token_port_idx += 1

    # CU memory ports
    for gpu_id in range(num_gpus):
        s_idx = shader_indices[gpu_id]
        for i in range(per_gpu_cus):
            for j in range(args.wf_size):
                system.cpu[s_idx].CUs[i].memory_port[j] = (
                    system.ruby._cpu_ports[gpu_port_idx].in_ports[j]
                )
            gpu_port_idx += 1

    # SQC ports
    global_cu = 0
    for gpu_id in range(num_gpus):
        s_idx = shader_indices[gpu_id]
        for i in range(per_gpu_cus):
            if global_cu > 0 and not global_cu % args.cu_per_sqc:
                gpu_port_idx += 1
            system.cpu[s_idx].CUs[i].sqc_port = system.ruby._cpu_ports[
                gpu_port_idx
            ].in_ports
            global_cu += 1
    gpu_port_idx += 1

    # Scalar ports
    global_cu = 0
    for gpu_id in range(num_gpus):
        s_idx = shader_indices[gpu_id]
        for i in range(per_gpu_cus):
            if global_cu > 0 and not global_cu % args.cu_per_scalar_cache:
                gpu_port_idx += 1
            system.cpu[s_idx].CUs[i].scalar_port = system.ruby._cpu_ports[
                gpu_port_idx
            ].in_ports
            global_cu += 1

    # ----------------------------------------------------------------
    # Co-simulation bridges
    # ----------------------------------------------------------------
    cosim_bridges = []
    for gpu_id in range(num_gpus):
        sock = _gpu_socket_path(args.socket_path, gpu_id, num_gpus)
        bridge = MI300XVfioUser(
            gpu_device=gpu_devices[gpu_id],
            socket_path=sock,
        )
        cosim_bridges.append(bridge)

    # Assign bridges to system
    if num_gpus == 1:
        system.cosim = cosim_bridges[0]
    else:
        system.cosim_bridges = cosim_bridges

    # ----------------------------------------------------------------
    # xGMI interconnect bridges (Milestone 2)
    # ----------------------------------------------------------------
    xgmi_topo = getattr(args, "xgmi_topology", None)
    if xgmi_topo is not None:
        if num_gpus < 2:
            m5.util.panic("--xgmi-topology requires --num-gpus >= 2")

        xgmi_bw = getattr(args, "xgmi_bandwidth", "128GB/s")
        xgmi_lat = getattr(args, "xgmi_latency", "100ns")

        # Create bridge objects (peers assigned after all are created)
        xgmi_bridges = []
        for gpu_id in range(num_gpus):
            xb = XGMIBridge(
                gpu_device=gpu_devices[gpu_id],
                gpu_id=gpu_id,
                num_gpus=num_gpus,
                bandwidth=xgmi_bw,
                latency=xgmi_lat,
                vram_size_per_gpu=args.dgpu_mem_size,
            )
            xgmi_bridges.append(xb)

        # Assign peers based on topology via SimObject parameters
        if xgmi_topo == "mesh":
            for i in range(num_gpus):
                xgmi_bridges[i].peers = [
                    xgmi_bridges[j] for j in range(num_gpus) if j != i
                ]
        elif xgmi_topo == "ring":
            for i in range(num_gpus):
                ring_peers = []
                nxt = (i + 1) % num_gpus
                prv = (i - 1) % num_gpus
                ring_peers.append(xgmi_bridges[nxt])
                if prv != nxt:
                    ring_peers.append(xgmi_bridges[prv])
                xgmi_bridges[i].peers = ring_peers

        system.xgmi_bridges = xgmi_bridges

    # Restore per-GPU CU count
    args.num_compute_units = per_gpu_cus

    return system


def add_arguments(parser, recipe):
    Options.addCommonOptions(parser)
    AmdGPUOptions.addAmdGPUOptions(parser)
    Ruby.define_options(parser)
    GPUTLBOptions.tlb_options(parser)
    addCosimOptions(parser)

    from example.gpufs.runfs import addRunFSOptions

    addRunFSOptions(parser)
    parser.set_defaults(
        mem_size="8GiB",
        num_compute_units=recipe["parameters"]["num_compute_units"]["default"],
        dgpu_mem_size=recipe["defaults"]["memory_regions"][0]["size"],
    )


def build(args):
    if not hasattr(m5.objects, "MI300XVfioUser"):
        m5.util.fatal(
            "MI300XVfioUser is unavailable. Initialize ext/libvfio-user "
            "with 'git submodule update --init ext/libvfio-user' and "
            "rebuild gem5."
        )

    # Cosim defaults
    args.num_cpus = 1
    args.cpu_type = "AtomicSimpleCPU"
    if not hasattr(args, "gpu_topology") or args.gpu_topology is None:
        args.gpu_topology = "Crossbar"
    if not hasattr(args, "cpu_topology") or args.cpu_topology is None:
        args.cpu_topology = "Crossbar"
    args.gpu_device = "MI300X"

    num_gpus = getattr(args, "num_gpus", 1)

    # Validate xGMI parameters at parse time
    xgmi_topo = getattr(args, "xgmi_topology", None)
    if xgmi_topo is not None and num_gpus < 2:
        m5.util.panic("--xgmi-topology requires --num-gpus >= 2")
    xgmi_bw = getattr(args, "xgmi_bandwidth", "128GB/s")
    if convert.toMemoryBandwidth(xgmi_bw) <= 0:
        m5.util.panic("--xgmi-bandwidth must be > 0")
    xgmi_lat = getattr(args, "xgmi_latency", "100ns")
    if xgmi_lat == "0ns" or xgmi_lat == "0":
        m5.util.panic("--xgmi-latency must be > 0")

    system = buildCosimSystem(args)

    root = Root(full_system=True, system=system)

    print("=" * 60)
    print("gem5 MI300X co-simulation configuration")
    print("  Backend:    vfio-user")
    print(f"  Num GPUs:   {num_gpus}")
    for gpu_id in range(num_gpus):
        sock = _gpu_socket_path(args.socket_path, gpu_id, num_gpus)
        shmem = args.shared_pool or _gpu_shmem_path(
            args.shmem_path, gpu_id, num_gpus
        )
        print(f"  GPU {gpu_id}:")
        print(f"    Socket:   {sock}")
        print(f"    VRAM SHM: {shmem}")
    print(f"  Host SHM:   {args.shared_pool or args.shmem_host_path}")
    print(f"  VRAM size:  {args.dgpu_mem_size}")
    print(f"  Host RAM:   {args.mem_size}")
    print(f"  CUs/GPU:    {args.num_compute_units}")
    print("Starting vfio-user listeners...")
    print("=" * 60)
    return root
