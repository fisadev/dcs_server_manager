"""
Utilities for managing processes: starting, killing, querying status, etc.
"""
import logging
from collections import namedtuple
from pathlib import Path
from os import system

import psutil

from dsm import config
from dsm import dcs


logger = logging.getLogger(__name__)


ProcessInfo = namedtuple("ProcessInfo", "pid name memory cpu threads child_processes")


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
            name = proc.name()
            if exe_name.lower() in name.lower():
                return ProcessInfo(
                    pid=proc.pid,
                    name=name,
                    memory=round(proc.memory_info().rss / (1024 * 1024 * 1024), 1),
                    cpu=round(proc.cpu_percent(), 1),
                    threads=proc.num_threads(),
                    child_processes=len(proc.children()),
                )
        except Exception as err:
            logger.warning("Something failed when checking for process %s: %s", exe_name, err)

    return None


def kill(exe_name):
    """
    Kill a process by its executable name.
    """
    proc = find(exe_name)

    if proc:
        try:
            p = psutil.Process(proc.pid)
            p.terminate()
            logger.debug("Process %s killed successfully", exe_name)
            return True
        except Exception as err:
            logger.warning("Failed to kill process %s: %s", exe_name, err)
            return False
    else:
        logger.debug("Process %s not found", exe_name)
        return False


def start(exe_path, arguments=None):
    """
    Start a process with the given executable path and arguments.
    """
    if not Path(exe_path).exists():
        logger.warning("Executable %s not found", exe_path)
        return False

    parent_path = Path(exe_path).parent

    launch_command = f'start "" /D "{parent_path}" "{exe_path}" {arguments or ""}'

    try:
        system(launch_command)
        logger.debug("Process %s started successfully", exe_path)
        return True
    except Exception as err:
        logger.warning("Failed to start process %s: %s", exe_path, err)
        return False
