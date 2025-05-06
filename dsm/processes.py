"""
Utilities for managing processes: starting, killing, querying status, etc.
"""
import logging
import os
import platform
import signal
import subprocess
import sys
from collections import namedtuple
from pathlib import Path
from time import sleep
from threading import Thread

import psutil

from dsm import config
from dsm import dcs


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


def restart_self(delay):
    """
    Restart the current DCS Server Manager process itself, after some delay in seconds.
    """
    logger.info("Restarting DCS Server Manager...")

    if ON_WINDOWS:
        # on windows, launch the app again but in mode "wait until this pid exits"
        def _restart():
            self_pid = os.getpid()
            sleep(delay)

            exe_path = sys.argv[0]
            start(exe_path, arguments=f"--wait-pid {self_pid}")

            # Sys.exit isn't enough to kill us because of how threads are used in flask/waitress
            self_process = psutil.Process(self_pid)
            self_process.terminate()
    else:
        # on linux, a very simple solution: just execv the current process
        def _restart():
            sleep(delay)
            os.execv(sys.executable, [sys.executable] + sys.argv)

    Thread(target=_restart, daemon=True).start()
