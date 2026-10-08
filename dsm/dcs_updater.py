"""
This module handles the DCS updater: updating DCS to its latest version, and installing or
uninstalling modules (maps, etc).
It uses the DCS_updater.exe that comes with DCS, in its "--quiet" mode, so nobody needs to click
on its windows.

While doing any of these things, the DCS server is in maintenance (see dcs.current_maintenance),
so the automatic jobs and the UI buttons don't try to start or stop it in the middle.
"""
import gzip
import json
import subprocess
from collections import namedtuple
from datetime import datetime
from logging import getLogger

import requests

from dsm import dcs


logger = getLogger(__name__)


LATEST_VERSION_URL = "https://api.digitalcombatsimulator.com/gameapi/updater/branch/{branch}/"

# modules that we know can be installed in a server. This list needs to be updated when ED releases
# new maps. Installed modules that aren't in this list are still shown, and can be uninstalled.
KNOWN_MODULES = (
    "CAUCASUS_terrain",
    "NEVADA_terrain",
    "NORMANDY_terrain",
    "PERSIANGULF_terrain",
    "THECHANNEL_terrain",
    "SYRIA_terrain",
    "MARIANAISLANDS_terrain",
    "MARIANAISLANDSWWII_terrain",
    "FALKLANDS_terrain",
    "SINAIMAP_terrain",
    "KOLA_terrain",
    "AFGHANISTAN_terrain",
    "IRAQ_terrain",
    "GERMANYCW_terrain",
    "WWII-ARMOUR",
    "SUPERCARRIER",
)

# modules that are part of DCS itself, they can't be uninstalled
REQUIRED_MODULES = ("WORLD",)

LatestVersion = namedtuple("LatestVersion", "version changelog_url checked_at")

# message about the result of the last maintenance task, to show in the UI
last_result = None
# the latest version we know of, from the last time we asked ED's servers
known_latest_version = None


def get_updater_path():
    """
    Get the path to the DCS updater exe.
    """
    return dcs.get_install_path() / "bin" / dcs.UPDATER_EXE_NAME


def read_autoupdate_config():
    """
    Read the autoupdate.cfg file from the DCS install folder. The updater keeps it updated with the
    installed version, branch and modules.
    """
    autoupdate_config_path = dcs.get_install_path() / "autoupdate.cfg"
    return json.loads(autoupdate_config_path.read_text("utf-8"))


def get_installed_version():
    """
    Get the version of DCS currently installed.
    """
    return read_autoupdate_config()["version"]


def get_branch():
    """
    Get the branch of DCS currently installed (usually "release").
    """
    return read_autoupdate_config()["branch"]


def get_installed_modules():
    """
    Get the list of modules currently installed.
    """
    return read_autoupdate_config()["modules"]


def check_latest_version():
    """
    Ask ED's servers which is the latest DCS version for the installed branch.
    It's also remembered in known_latest_version, so other parts of DSM can use it without asking
    ED's servers again.
    """
    global known_latest_version

    url = LATEST_VERSION_URL.format(branch=get_branch())
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    # the response is a gzipped json, but the headers don't say so, so requests doesn't
    # decompress it by itself
    data = json.loads(gzip.decompress(response.content))

    # versions are sorted from oldest to newest
    newest = data["versions2"][-1]

    known_latest_version = LatestVersion(
        version=newest["version"],
        changelog_url=newest.get("changelog_url"),
        checked_at=datetime.now(),
    )
    return known_latest_version


def update_available():
    """
    Check if there is an update available, comparing the installed version with the latest version
    we know of (without asking ED's servers again).
    Returns None if we don't know the latest version yet.
    """
    if known_latest_version is None:
        return None

    # we compare inside the same branch, and ED's latest is always the newest, so any difference
    # means there's an update
    return get_installed_version() != known_latest_version.version


def set_maintenance_task(task):
    """
    Put the DCS server in maintenance, with a description of the task being done.
    """
    logger.info("DCS maintenance: %s", task)
    dcs.current_maintenance = dcs.Maintenance(task=task, started_at=datetime.now())


def end_maintenance():
    """
    Take the DCS server out of maintenance.
    """
    logger.info("DCS maintenance finished")
    dcs.current_maintenance = None


def run_updater(arguments):
    """
    Run the DCS updater in quiet mode with the given arguments, and wait for it to finish.
    """
    updater_path = get_updater_path()
    command = [str(updater_path), "--quiet"] + arguments

    logger.info("Running the DCS updater: %s", " ".join(command))
    result = subprocess.run(command, cwd=updater_path.parent, check=False)
    # we don't know what the exit codes mean, so we just log it. The callers check if the
    # changes were applied by reading autoupdate.cfg instead
    logger.info("The DCS updater finished with exit code %s", result.returncode)


def update():
    """
    Update DCS to the latest version, if there is a new one.
    If an update is needed, DCS is stopped during the update and started again at the end (if it
    was running before).
    This can take a long time, so it's meant to be run in the background.
    """
    global last_result

    try:
        # this must be checked before entering maintenance, because in maintenance the status is
        # always MAINTENANCE
        was_running = dcs.current_status() != dcs.DCSServerStatus.NOT_RUNNING

        set_maintenance_task("Checking for DCS updates")
        branch = get_branch()
        installed_version = get_installed_version()
        latest_version = check_latest_version().version

        if installed_version == latest_version:
            last_result = f"No update needed, DCS is already at the latest version ({installed_version})"
        else:
            set_maintenance_task("Stopping DCS to update it")
            dcs.ensure_stopped(ignore_maintenance=True)

            try:
                set_maintenance_task(f"Updating DCS from {installed_version} to {latest_version}")
                run_updater(["update", f"{latest_version}@{branch}"])
            finally:
                # even if the update failed, we don't want to leave the server down
                if was_running:
                    set_maintenance_task("Starting DCS after the update")
                    dcs.start(ignore_maintenance=True)

            new_version = get_installed_version()
            if new_version == latest_version:
                last_result = f"DCS updated from {installed_version} to {latest_version}"
            else:
                last_result = (f"DCS update failed, the installed version is still {new_version}. "
                               "Check the DSM logs for more info.")
    except Exception as err:
        last_result = f"DCS update failed: {err}"
    finally:
        logger.info(last_result)
        end_maintenance()


def change_modules(to_install, to_uninstall):
    """
    Install and uninstall DCS modules (maps, etc).
    DCS is stopped while doing it, and started again at the end (if it was running before).
    This can take a long time, so it's meant to be run in the background.
    """
    global last_result

    total = len(to_install) + len(to_uninstall)
    done = 0

    try:
        # this must be checked before entering maintenance, because in maintenance the status is
        # always MAINTENANCE
        was_running = dcs.current_status() != dcs.DCSServerStatus.NOT_RUNNING

        set_maintenance_task("Stopping DCS to change modules")
        dcs.ensure_stopped(ignore_maintenance=True)

        try:
            for module in to_install:
                done += 1
                set_maintenance_task(f"Installing {module} ({done}/{total})")
                try:
                    run_updater(["install", module])
                except Exception as err:
                    # we keep going with the rest, at the end we check what was installed
                    logger.error("Failed to install %s: %s", module, err)

            for module in to_uninstall:
                done += 1
                set_maintenance_task(f"Uninstalling {module} ({done}/{total})")
                try:
                    run_updater(["uninstall", module])
                except Exception as err:
                    # we keep going with the rest, at the end we check what was uninstalled
                    logger.error("Failed to uninstall %s: %s", module, err)
        finally:
            # even if something failed, we don't want to leave the server down
            if was_running:
                set_maintenance_task("Starting DCS after changing modules")
                dcs.start(ignore_maintenance=True)

        installed_modules = get_installed_modules()
        results = []
        for module in to_install:
            if module in installed_modules:
                results.append(f"{module} installed")
            else:
                results.append(f"{module} FAILED to install")
        for module in to_uninstall:
            if module not in installed_modules:
                results.append(f"{module} uninstalled")
            else:
                results.append(f"{module} FAILED to uninstall")

        last_result = "Modules changed: " + ", ".join(results)
    except Exception as err:
        last_result = f"Failed to change modules: {err}"
    finally:
        logger.info(last_result)
        end_maintenance()
