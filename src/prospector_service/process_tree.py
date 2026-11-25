import asyncio
import ctypes
import os
import signal
import sys
from pathlib import Path


def enable_subreaper():
    if sys.platform != "linux":
        raise RuntimeError("verified process supervision requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot supervise orphaned browser processes")


def process_table():
    table = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            values = path.read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        table[int(path.parent.name)] = (int(values[1]), values[0])
    return table


def descendants(root: int, table):
    children = {root}
    while True:
        expanded = children | {pid for pid, (parent, _) in table.items() if parent in children}
        if expanded == children:
            return children - {root}
        children = expanded


def reap_orphans():
    while True:
        try:
            child, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return True
        if child == 0:
            return False


async def terminate_tree(process, deadline: float) -> bool:
    """Freeze and enumerate the live subreaper's descendants before killing it."""
    if sys.platform != "linux" or process.returncode is not None:
        return False
    descriptors = {}
    loop = asyncio.get_running_loop()
    try:
        root = process.pid
        descriptors[root] = os.pidfd_open(root)
        signal.pidfd_send_signal(descriptors[root], signal.SIGSTOP)
        while loop.time() < deadline:
            table = process_table()
            if root not in table or table[root][1] == "Z":
                return False
            pids = descendants(root, table) | {root}
            for pid in pids - descriptors.keys():
                try:
                    handle = os.pidfd_open(pid)
                except ProcessLookupError:
                    continue
                descriptors[pid] = handle
                try:
                    signal.pidfd_send_signal(handle, signal.SIGSTOP)
                except ProcessLookupError:
                    pass
            if pids <= descriptors.keys() and all(table[pid][1] in {"T", "t", "Z"} for pid in pids):
                for pid in [*sorted(pids - {root}), root]:
                    try:
                        signal.pidfd_send_signal(descriptors[pid], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                while loop.time() < deadline:
                    if process.returncode is not None and pids.isdisjoint(process_table()):
                        return True
                    await asyncio.sleep(0.05)
                return False
            await asyncio.sleep(0.025)
        return False
    except OSError:
        return False
    finally:
        for descriptor in descriptors.values():
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            except OSError:
                pass
            os.close(descriptor)
