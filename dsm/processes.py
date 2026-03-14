"""
Utilities for managing processes: starting, killing, querying status, etc.
"""
import logging
import os
import platform
import subprocess
import time
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


def stop(exe_name, kill=False):
    """
    Stop a process by its executable name, by default allowing it to gracefully shut down.
    If kill is True, it will forcefully kill the process instead.
    """
    proc = find(exe_name)

    if proc:
        p = psutil.Process(proc.pid)
        if kill:
            p.kill()
        else:
            if ON_WINDOWS:
                # on windows, p.terminate() is synonymous with kill(), so not a soft kill
                # instead we use taskkill then
                subprocess.run(f"taskkill /PID {exe_name} /T", shell=True, check=False)
            else:
                p.terminate()
    else:
        # technically still a success, wasn't running anyway
        logger.debug("Process %s not found", exe_name)


def wait_until_stopped(exe_name, timeout=30):
    """
    Wait until a process is stopped, with a timeout in seconds.
    Return True if the process is stopped, False if the timeout is reached and the process
    is still running.
    """
    wait_start = time.monotonic()

    while True:
        if find(exe_name):
            if time.monotonic() - wait_start > timeout:
                return False
        else:
            return True

        time.sleep(1)


def ensure_stopped(exe_name, stop_timeout=30, kill_timeout=5):
    """
    Stops a process and then makes sure it was stopped, waiting until it's no longer running.
    Returns True if the process was successfully restarted, False otherwise.

    If we reach the stop_timeout after the soft stop, we then try to kill it and wait kill_timeout.
    If reach kill_timeout too, we just return False and let the caller decide what to do.
    """
    logger.info("Soft stopping process %s...", exe_name)
    stop(exe_name, kill=False)

    stopped = wait_until_stopped(exe_name, timeout=stop_timeout)
    if not stopped:
        logger.info("Process %s still running after soft stop, trying a force kill...", exe_name)
        stop(exe_name, kill=True)

        stopped = wait_until_stopped(exe_name, timeout=kill_timeout)
        if not stopped:
            logger.info("Process %s still running after a force kill!", exe_name)
            return False

    return True


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
