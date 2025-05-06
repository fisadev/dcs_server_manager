"""
Utilities for managing processes: starting, killing, querying status, etc.
"""
import logging
import os
import platform
import signal
import subprocess
import sys
import tempfile
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
        def _restart():
            sleep(delay)
            # super hackish solution: create a .bat file that will restart us, fire it, and then
            # close us (more sane options like using multiprocessing have lots of issues, like
            # zombie processes not freeing ports and unable to be killed, etc).
            exe_path = sys.argv[0]

            bat = f'@echo off\ntimeout /t {delay} > NUL\nstart "" "{exe_path}"'

            with tempfile.NamedTemporaryFile('w', suffix='.bat', delete=False) as f:
                f.write(bat)
                bat_path = f.name

            # launch the .bat file and shut down
            os.system(f"cmd /c {bat_path}")
            # and kill us. Sys.exit isn't enough, sadly
            pid = os.getpid()
            os.kill(pid, signal.SIGKILL)
    else:
        # on linux, a very simple solution: just execv the current process
        def _restart():
            sleep(delay)
            os.execv(sys.executable, [sys.executable] + sys.argv)

    Thread(target=_restart, daemon=True).start()
