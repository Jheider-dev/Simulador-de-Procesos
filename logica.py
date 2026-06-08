from dataclasses import dataclass, field
from typing import Optional
import csv
import math

#  DATA CLASSES

@dataclass
class Process:
    pid: str
    arrival: int
    burst: int
    start: Optional[int] = None
    finish: Optional[int] = None

    @property
    def turnaround(self) -> Optional[int]:
        if self.finish is not None:
            return self.finish - self.arrival
        return None

    @property
    def waiting(self) -> Optional[int]:
        if self.turnaround is not None:
            return self.turnaround - self.burst
        return None

@dataclass
class GanttBlock:
    pid: str
    start: int
    end: int

@dataclass
class SchedulingResult:
    processes: list[Process]
    gantt: list[GanttBlock]

    @property
    def avg_turnaround(self) -> float:
        vals = [p.turnaround for p in self.processes if p.turnaround is not None]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_waiting(self) -> float:
        vals = [p.waiting for p in self.processes if p.waiting is not None]
        return sum(vals) / len(vals) if vals else 0.0

@dataclass
class MemoryBlock:
    name: str
    size: int
    is_free: bool
    address: int = 0

@dataclass
class BuddyNode:
    size: int
    address: int
    is_free: bool = True
    pid: Optional[str] = None
    left: Optional['BuddyNode'] = None
    right: Optional['BuddyNode'] = None

#  FILE LOADING

def load_processes_from_file(path: str) -> list[Process]:
    processes = []
    with open(path, newline='', encoding='utf-8') as f:
        sample = f.read(1024)
        f.seek(0)
        delimiter = ',' if ',' in sample else '\t' if '\t' in sample else ','
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            row = [c.strip() for c in row]
            if not row or row[0].upper().startswith('PID'):
                continue
            if len(row) >= 3:
                try:
                    processes.append(Process(
                        pid=row[0],
                        arrival=int(row[1]),
                        burst=int(row[2])
                    ))
                except ValueError:
                    continue
    return processes

#  CPU SCHEDULING ALGORITHMS

def _copy_processes(procs: list[Process]) -> list[Process]:
    return [Process(p.pid, p.arrival, p.burst) for p in procs]


def fcfs(processes: list[Process]) -> SchedulingResult:
    procs = sorted(_copy_processes(processes), key=lambda p: (p.arrival, p.pid))
    gantt: list[GanttBlock] = []
    time = 0
    for p in procs:
        time = max(time, p.arrival)
        p.start = time
        p.finish = time + p.burst
        gantt.append(GanttBlock(p.pid, p.start, p.finish))
        time = p.finish
    return SchedulingResult(procs, gantt)


def spn(processes: list[Process]) -> SchedulingResult:
    procs = _copy_processes(processes)
    gantt: list[GanttBlock] = []
    time = 0
    done = []
    remaining = list(procs)

    while remaining:
        available = [p for p in remaining if p.arrival <= time]
        if not available:
            time = min(p.arrival for p in remaining)
            available = [p for p in remaining if p.arrival <= time]
        chosen = min(available, key=lambda p: (p.burst, p.pid))
        remaining.remove(chosen)
        chosen.start = time
        chosen.finish = time + chosen.burst
        gantt.append(GanttBlock(chosen.pid, chosen.start, chosen.finish))
        time = chosen.finish
        done.append(chosen)

    return SchedulingResult(done, gantt)


def srt(processes: list[Process]) -> SchedulingResult:
    procs = _copy_processes(processes)
    gantt: list[GanttBlock] = []
    remaining_burst = {p.pid: p.burst for p in procs}
    started = {}
    finished = []
    time = 0
    current_pid = None
    block_start = 0
    total = sum(p.burst for p in procs)
    events = sorted(set(p.arrival for p in procs))

    def get_ready(t):
        return [p for p in procs if p.arrival <= t and p.pid not in {fp.pid for fp in finished} and remaining_burst[p.pid] > 0]

    tick = 0
    limit = total + max(p.arrival for p in procs) + 10

    while len(finished) < len(procs) and tick < limit:
        ready = get_ready(tick)
        if not ready:
            tick += 1
            current_pid = None
            continue
        chosen = min(ready, key=lambda p: (remaining_burst[p.pid], p.pid))
        if chosen.pid != current_pid:
            if current_pid is not None:
                gantt.append(GanttBlock(current_pid, block_start, tick))
            block_start = tick
            current_pid = chosen.pid
        if chosen.pid not in started:
            chosen.start = tick
            started[chosen.pid] = tick
        remaining_burst[chosen.pid] -= 1
        tick += 1
        if remaining_burst[chosen.pid] == 0:
            chosen.finish = tick
            gantt.append(GanttBlock(chosen.pid, block_start, tick))
            current_pid = None
            finished.append(chosen)

    for p in procs:
        if p.pid in started and p.start is None:
            p.start = started[p.pid]

    return SchedulingResult(procs, gantt)


def round_robin(processes: list[Process], quantum: int) -> SchedulingResult:
    procs = _copy_processes(processes)
    gantt: list[GanttBlock] = []
    remaining = {p.pid: p.burst for p in procs}
    started: dict[str, int] = {}
    finished: dict[str, int] = {}
    queue: list[Process] = []
    time = 0
    arrived = set()
    proc_map = {p.pid: p for p in sorted(procs, key=lambda p: p.arrival)}
    sorted_procs = sorted(procs, key=lambda p: p.arrival)

    def enqueue_new(t):
        for p in sorted_procs:
            if p.arrival <= t and p.pid not in arrived and remaining[p.pid] > 0:
                arrived.add(p.pid)
                queue.append(p)

    enqueue_new(time)
    limit = sum(p.burst for p in procs) * 3 + 100

    while queue and time < limit:
        p = queue.pop(0)
        if p.pid not in started:
            started[p.pid] = time
        run = min(quantum, remaining[p.pid])
        gantt.append(GanttBlock(p.pid, time, time + run))
        time += run
        remaining[p.pid] -= run
        enqueue_new(time)
        if remaining[p.pid] == 0:
            finished[p.pid] = time
        else:
            queue.append(p)

    result_procs = []
    for p in procs:
        p.start = started.get(p.pid)
        p.finish = finished.get(p.pid)
        result_procs.append(p)

    return SchedulingResult(result_procs, gantt)


#  MEMORY MANAGEMENT: DYNAMIC PARTITIONS

OS_SIZE_KB = 64

def _build_initial_memory(total_kb: int) -> list[MemoryBlock]:
    os_block = MemoryBlock("S.O.", OS_SIZE_KB, False, 0)
    free_block = MemoryBlock("Libre", total_kb - OS_SIZE_KB, True, OS_SIZE_KB)
    return [os_block, free_block]

def _assign_addresses(blocks: list[MemoryBlock]) -> list[MemoryBlock]:
    addr = 0
    for b in blocks:
        b.address = addr
        addr += b.size
    return blocks

def first_fit(total_kb: int, process_list: list[tuple[str, int]]) -> tuple[list[MemoryBlock], list[str]]:
    blocks = _build_initial_memory(total_kb)
    log = []
    for pid, size in process_list:
        placed = False
        for i, b in enumerate(blocks):
            if b.is_free and b.size >= size:
                remainder = b.size - size
                blocks[i] = MemoryBlock(pid, size, False, b.address)
                if remainder > 0:
                    blocks.insert(i + 1, MemoryBlock("Libre", remainder, True, b.address + size))
                log.append(f"{pid} ({size}KB) → bloque en {b.address}KB [First Fit]")
                placed = True
                break
        if not placed:
            log.append(f"{pid} ({size}KB) → NO CABE en memoria")
    return _assign_addresses(blocks), log

def best_fit(total_kb: int, process_list: list[tuple[str, int]]) -> tuple[list[MemoryBlock], list[str]]:
    blocks = _build_initial_memory(total_kb)
    log = []
    for pid, size in process_list:
        candidates = [(i, b) for i, b in enumerate(blocks) if b.is_free and b.size >= size]
        if not candidates:
            log.append(f"{pid} ({size}KB) → NO CABE en memoria")
            continue
        best_i, best_b = min(candidates, key=lambda x: x[1].size)
        remainder = best_b.size - size
        blocks[best_i] = MemoryBlock(pid, size, False, best_b.address)
        if remainder > 0:
            blocks.insert(best_i + 1, MemoryBlock("Libre", remainder, True, best_b.address + size))
        log.append(f"{pid} ({size}KB) → bloque en {best_b.address}KB [Best Fit]")
    return _assign_addresses(blocks), log

def worst_fit(total_kb: int, process_list: list[tuple[str, int]]) -> tuple[list[MemoryBlock], list[str]]:
    blocks = _build_initial_memory(total_kb)
    log = []
    for pid, size in process_list:
        candidates = [(i, b) for i, b in enumerate(blocks) if b.is_free and b.size >= size]
        if not candidates:
            log.append(f"{pid} ({size}KB) → NO CABE en memoria")
            continue
        worst_i, worst_b = max(candidates, key=lambda x: x[1].size)
        remainder = worst_b.size - size
        blocks[worst_i] = MemoryBlock(pid, size, False, worst_b.address)
        if remainder > 0:
            blocks.insert(worst_i + 1, MemoryBlock("Libre", remainder, True, worst_b.address + size))
        log.append(f"{pid} ({size}KB) → bloque en {worst_b.address}KB [Worst Fit]")
    return _assign_addresses(blocks), log

#  MEMORY MANAGEMENT: BUDDY SYSTEM

def _next_power_of_two(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))

def _buddy_allocate(node: BuddyNode, size: int, pid: str) -> bool:
    if node.size < size:
        return False
    if node.left is None and node.right is None:
        if not node.is_free:
            return False
        if node.size == size or node.size < size * 2:
            node.is_free = False
            node.pid = pid
            return True
        half = node.size // 2
        node.left = BuddyNode(half, node.address)
        node.right = BuddyNode(half, node.address + half)
        return _buddy_allocate(node.left, size, pid)
    if node.left and _buddy_allocate(node.left, size, pid):
        return True
    if node.right and _buddy_allocate(node.right, size, pid):
        return True
    return False

def _buddy_flatten(node: BuddyNode) -> list[MemoryBlock]:
    if node.left is None and node.right is None:
        name = node.pid if not node.is_free else "Libre"
        return [MemoryBlock(name, node.size, node.is_free, node.address)]
    result = []
    if node.left:
        result.extend(_buddy_flatten(node.left))
    if node.right:
        result.extend(_buddy_flatten(node.right))
    return result

def buddy_system(total_kb: int, process_list: list[tuple[str, int]]) -> tuple[list[MemoryBlock], list[str]]:
    rounded_total = _next_power_of_two(total_kb)
    root = BuddyNode(rounded_total, 0)
    log = []

    os_needed = _next_power_of_two(OS_SIZE_KB)
    _buddy_allocate(root, os_needed, "S.O.")

    for pid, size in process_list:
        needed = _next_power_of_two(size)
        if _buddy_allocate(root, needed, pid):
            log.append(f"{pid} ({size}KB → {needed}KB pot²) → asignado [Buddy]")
        else:
            log.append(f"{pid} ({size}KB → {needed}KB pot²) → NO CABE")

    blocks = _buddy_flatten(root)
    for b in blocks:
        if b.name == "S.O.":
            b.is_free = False
    return blocks, log

#  MEMORY MANAGEMENT: FIXED PARTITIONS

@dataclass
class FixedPartitionInfo:
    partition_id: int
    size: int
    assigned_pid: Optional[str] = None
    allocated_size: int = 0
    
    @property
    def internal_fragmentation(self) -> int:
        """Espacio sin usar en la partición asignada"""
        if self.assigned_pid is None:
            return 0
        return self.size - self.allocated_size

def _build_fixed_partitions_equal(total_kb: int, num_partitions: int) -> list[FixedPartitionInfo]:
    """Crea particiones de igual tamaño"""
    os_size = OS_SIZE_KB
    available = total_kb - os_size
    partition_size = available // num_partitions
    
    partitions = []
    partitions.append(FixedPartitionInfo(0, os_size, "S.O.", os_size))
    
    for i in range(num_partitions):
        partitions.append(FixedPartitionInfo(i + 1, partition_size))
    
    return partitions

def _build_fixed_partitions_unequal(total_kb: int, sizes_str: str) -> list[FixedPartitionInfo]:
    """Crea particiones con tamaños desiguales. sizes_str: '100, 200, 150'"""
    partitions = []
    sizes = []
    
    try:
        for s in sizes_str.split(','):
            sizes.append(int(s.strip()))
    except ValueError:
        raise ValueError("Formato inválido. Usa: 100, 200, 150")
    
    os_size = OS_SIZE_KB
    partitions.append(FixedPartitionInfo(0, os_size, "S.O.", os_size))
    
    total_user = sum(sizes)
    if total_user + os_size > total_kb:
        raise ValueError(f"Suma ({total_user}KB) + S.O. ({os_size}KB) > RAM ({total_kb}KB)")
    
    for i, size in enumerate(sizes):
        partitions.append(FixedPartitionInfo(i + 1, size))
    
    return partitions

def first_fit_fixed(total_kb: int, partitions: list[FixedPartitionInfo],
                    process_list: list[tuple[str, int]]) -> tuple[list[FixedPartitionInfo], list[str]]:
    """Asigna procesos a la primera partición disponible que quepa"""
    log = []
    
    for pid, size in process_list:
        placed = False
        for part in partitions:
            if part.assigned_pid is None and part.size >= size:
                part.assigned_pid = pid
                part.allocated_size = size
                frag = part.internal_fragmentation
                log.append(f"{pid} ({size}KB) → Partición #{part.partition_id} ({part.size}KB) [Frag: {frag}KB]")
                placed = True
                break
        
        if not placed:
            log.append(f"{pid} ({size}KB) → NO CABE en ninguna partición libre")
    
    return partitions, log

def best_fit_fixed(total_kb: int, partitions: list[FixedPartitionInfo],
                   process_list: list[tuple[str, int]]) -> tuple[list[FixedPartitionInfo], list[str]]:
    """Asigna procesos a la partición con mínima fragmentación interna"""
    log = []
    
    for pid, size in process_list:
        candidates = [p for p in partitions if p.assigned_pid is None and p.size >= size]
        
        if not candidates:
            log.append(f"{pid} ({size}KB) → NO CABE en ninguna partición libre")
            continue
        
        best_part = min(candidates, key=lambda p: p.size - size)
        best_part.assigned_pid = pid
        best_part.allocated_size = size
        frag = best_part.internal_fragmentation
        log.append(f"{pid} ({size}KB) → Partición #{best_part.partition_id} ({best_part.size}KB) [Frag: {frag}KB]")
    
    return partitions, log

def worst_fit_fixed(total_kb: int, partitions: list[FixedPartitionInfo],
                    process_list: list[tuple[str, int]]) -> tuple[list[FixedPartitionInfo], list[str]]:
    """Asigna procesos a la partición con máximo espacio libre"""
    log = []
    
    for pid, size in process_list:
        candidates = [p for p in partitions if p.assigned_pid is None and p.size >= size]
        
        if not candidates:
            log.append(f"{pid} ({size}KB) → NO CABE en ninguna partición libre")
            continue
        
        worst_part = max(candidates, key=lambda p: p.size)
        worst_part.assigned_pid = pid
        worst_part.allocated_size = size
        frag = worst_part.internal_fragmentation
        log.append(f"{pid} ({size}KB) → Partición #{worst_part.partition_id} ({worst_part.size}KB) [Frag: {frag}KB]")
    
    return partitions, log

def total_internal_fragmentation(partitions: list[FixedPartitionInfo]) -> int:
    """Calcula la fragmentación interna total"""
    return sum(p.internal_fragmentation for p in partitions)

def memory_usage_percent_fixed(partitions: list[FixedPartitionInfo], total_kb: int) -> float:
    """Porcentaje de memoria utilizada (sin contar fragmentación)"""
    used = sum(p.allocated_size for p in partitions if p.assigned_pid is not None and p.assigned_pid != "S.O.")
    return (used / total_kb * 100) if total_kb > 0 else 0.0

#  UTILITY

def parse_manual_processes(text: str) -> list[tuple[str, int]]:
    result = []
    for item in text.split(','):
        item = item.strip()
        if ':' in item:
            parts = item.split(':')
            if len(parts) == 2:
                try:
                    result.append((parts[0].strip(), int(parts[1].strip())))
                except ValueError:
                    pass
    return result

def memory_usage_percent(blocks: list[MemoryBlock], total_kb: int) -> float:
    used = sum(b.size for b in blocks if not b.is_free)
    return (used / total_kb * 100) if total_kb > 0 else 0.0
