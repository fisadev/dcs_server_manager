"""
Utilities for managing processes: starting, killing, querying status, etc.
"""
import logging
import os
import platform
import subprocess
from collections import namedtuple
from pathlib import Path

import psutil



logger = logging.getLogger(__name__)


ProcessInfo = namedtuple("ProcessInfo", "pid name memory cpu threads child_processes")


ON_WINDOWS = platform.system() == "Windows"


def get_exe_name(exe_path):
    """
    Get the name of the exe from a path, to be used to find the process.
    """
    return Path(exe_path).name


def find(exe_name):
    """
    Find a process by its executable name, and return info about its current status.
    If the process is not found, return None.
    """
    for proc in psutil.process_iter():
        try:
            full_name = proc.name() + "".join(proc.cmdline())
            if exe_name.lower() in full_name.lower():
                return ProcessInfo(
                    pid=proc.pid,
                    name=full_name,
                    memory=round(proc.memory_info().rss / (1024 * 1024), 1),  # MB
                    cpu=round(proc.cpu_percent(), 1),
                    threads=proc.num_threads(),
                    child_processes=len(proc.children()),
                )
        except Exception:
            pass

    return None


def kill(exe_name):
    """
    Kill a process by its executable name.
    """
    proc = find(exe_name)

    if proc:
        p = psutil.Process(proc.pid)
        p.terminate()
    else:
        # technically still a success, wasn't running anyway
        logger.debug("Process %s not found", exe_name)


def start(exe_path, arguments=None):
    """
    Start a process with the given executable path and arguments.
    """
    if not Path(exe_path).exists():
        return False, f"Executable {exe_path} not found"

    parent_path = Path(exe_path).parent

    if ON_WINDOWS:
        launch_command = f'start "" /D "{parent_path}" "{exe_path}" {arguments or ""}'
        os.system(launch_command)
    else:
        # this is just useful for developing and testing on Linux, not really used in prod
        # (DCS and SRS are Windows centric)
        launch_command = f'{exe_path} {arguments}'
        subprocess.Popen(launch_command, cwd=parent_path, shell=True)
