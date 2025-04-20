import logging
from collections import namedtuple
from pathlib import Path
from os import system

import psutil

from dsm import config


logger = logging.getLogger(__name__)


ProcessInfo = namedtuple("ProcessInfo", "pid name memory cpu threads child_processes")


def get_exe_name(exe_path):
    """
    Get the name of the exe from a path, to be used to find the process.
    """
    return Path(exe_path).name


def find_process(exe_name):
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


def kill_process(exe_name):
    """
    Kill a process by its executable name.
    """
    proc = find_process(exe_name)

    if proc:
        try:
            p = psutil.Process(proc.pid)
            p.terminate()
            logger.info("Process %s killed successfully", exe_name)
            return True
        except Exception as err:
            logger.warning("Failed to kill process %s: %s", exe_name, err)
            return False
    else:
        logger.warning("Process %s not found", exe_name)
        return False


def start_process(exe_path, arguments=None):
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
        logger.info("Process %s started successfully", exe_path)
        return True
    except Exception as err:
        logger.warning("Failed to start process %s: %s", exe_path, err)
        return False


def check_server_up(server_configs_prefix):
    """
    Check if a server is running. Optionally, restart it if it's not running.
    """
    title = server_configs_prefix
    exe_path = config.current[f"{server_configs_prefix}_SERVER_EXE_PATH"]
    arguments = config.current[f"{server_configs_prefix}_SERVER_EXE_ARGUMENTS"]
    restart_if_not_running = config.current[f"{server_configs_prefix}_SERVER_START_IF_NOT_RUNNING"]

    logger.info("Checking %s server status...", title)

    exe_name = get_exe_name(exe_path)
    process = find_process(exe_name)

    if process:
        logger.info("%s server running", title)
    elif restart_if_not_running:
        logger.info("%s server not running, attempting to start it...", title)

        started = start_process(exe_path, arguments)
        if started:
            logger.info("%s server started successfully", title)
        else:
            logger.warning("Failed to start %s server", title)
    else:
        logger.warning("%s server not running, and not set to restart", title)


def restart_server(server_configs_prefix):
    """
    If a server is running, terminate it. In any case, start it again.
    """
    title = server_configs_prefix
    exe_path = config.current[f"{server_configs_prefix}_SERVER_EXE_PATH"]
    arguments = config.current[f"{server_configs_prefix}_SERVER_EXE_ARGUMENTS"]

    logger.info("About to restart %s server...", title)

    exe_name = get_exe_name(exe_path)
    process = find_process(exe_name)

    if process:
        logger.info("%s server running, stopping it...", title)
        kill_process(exe_name)
    else:
        logger.info("%s server not running", title)

    logger.info("Starting %s server...", title)
    start_process(exe_path, arguments)
