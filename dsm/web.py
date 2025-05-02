"""
This is the web app, allowing the user to check the status of the servers and to interact with
them, and the configs.
"""
import logging
import os
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, cli, request
from flask_basicauth import BasicAuth
from werkzeug.utils import secure_filename

from dsm import config, jobs, dcs, srs, logs


# web app singleton, we won't need more than one
app = Flask("dcs_server_manager")
logger = logging.getLogger(__name__)

SERVERS = {"dcs": dcs, "srs": srs}


def launch():
    """
    Configure the web app and launch it.
    """
    debug = os.environ.get("DEBUG", False)

    if not debug:
        # disable all kinds of console output that I don't want to show to the user
        app.logger.disabled = True
        logging.getLogger("werkzeug").disabled = True
        logging.getLogger("apscheduler").disabled = True
        logging.getLogger("apscheduler.scheduler").disabled = True
        logging.getLogger("apscheduler.executors.default").disabled = True
        cli.show_server_banner = lambda *args: None

    if config.current["DSM_WEB_UI_PASSWORD"]:
        app.config["BASIC_AUTH_USERNAME"] = "admin"
        app.config["BASIC_AUTH_PASSWORD"] = config.current["DSM_WEB_UI_PASSWORD"]
        app.config["BASIC_AUTH_FORCE"] = True
        BasicAuth(app)

    jobs.launch()

    logger.info("Running DCS Server Manager")
    logger.info("Web UI: http://localhost:%s", config.current["DSM_WEB_UI_PORT"])

    app.run(
        host=config.current["DSM_WEB_UI_HOST"],
        port=config.current["DSM_WEB_UI_PORT"],
        debug=debug,
    )


@app.route("/")
def home():
    """
    Home page.
    """
    return render_template("home.html")


GOOD_ICON = "🟢"
WARNING_ICON = "🟡"
BAD_ICON = "🔴"

STATUS_ICONS = {
    dcs.DCSServerStatus.RUNNING: GOOD_ICON,
    dcs.DCSServerStatus.NON_RESPONSIVE: BAD_ICON,
    dcs.DCSServerStatus.NOT_RUNNING: BAD_ICON,
    dcs.DCSServerStatus.PROBABLY_BOOTING: WARNING_ICON,
    srs.SRSServerStatus.RUNNING: GOOD_ICON,
    srs.SRSServerStatus.NOT_RUNNING: BAD_ICON,
}


@app.route("/<server_name>/status")
def server_status(server_name):
    try:
        status = SERVERS[server_name].current_status()
        icon = STATUS_ICONS[status]
        text = status.name.replace("_", " ").lower()
        return f"<span>{icon} {text}</span>"
    except Exception as err:
        return f'<span title="{err}">{WARNING_ICON} failed to get status</span>'


@app.route("/<server_name>/status/icon")
def server_status_icon(server_name):
    try:
        icon = STATUS_ICONS[SERVERS[server_name].current_status()]
    except Exception as err:
        icon = WARNING_ICON
    return icon


@app.route("/<server_name>/resources")
def server_resources(server_name):
    try:
        resources = SERVERS[server_name].current_resources()
        return render_template("server_resources.html", resources=resources)
    except Exception as err:
        return render_template("messages.html", errors=[f"Error querying server resources: {err}"])


@app.route("/<server_name>/start", methods=["POST"])
def server_start(server_name):
    try:
        SERVERS[server_name].start()
        return '<span class="good-message">Server started</span>'
    except Exception as err:
        return f'<span class="error-message" title="{err}">Failed to start server</span>'


@app.route("/<server_name>/restart", methods=["POST"])
def server_restart(server_name):
    try:
        SERVERS[server_name].restart()
        return '<span class="good-message">Server restarted</span>'
    except Exception as err:
        return f'<span class="error-message" title="{err}">Failed to restart server</span>'


@app.route("/<server_name>/kill", methods=["POST"])
def server_kill(server_name):
    try:
        SERVERS[server_name].kill()
        return '<span class="good-message">Server killed</span>'
    except Exception as err:
        return f'<span class="error-message" title="{err}">Failed to kill server</span>'


@app.route("/<server_name>/manager_config_form", methods=["GET", "POST"])
def server_manager_config_form(server_name):
    prefix = f"{server_name.upper()}_SERVER_"
    relevant_config_names = [
        config_name for config_name in config.current
        if config_name.startswith(prefix)
    ]
    broken_fields = set()
    errors = []
    warnings = []
    messages = []

    if request.method == "POST":
        new_configs = {}
        for config_name in relevant_config_names:
            try:
                if config.SPEC[config_name].type is bool:
                    value = config_name in request.form
                else:
                    value = request.form.get(config_name, "").strip()
                    if config.SPEC[config_name].type is int:
                        if value:
                            value = int(value)
                        else:
                            value = None

                new_configs[config_name] = value

                if config.SPEC[config_name].type is Path and value:
                    try:
                        value_path = Path(value).absolute()
                        if not value_path.exists():
                            warnings.append(f"Warning: path {value_path} does not exist")
                    except Exception as err:
                        # not important to show errors in this check to the user
                        logger.debug("Failed to run path check for %s: %s", config_name, err)
            except ValueError:
                broken_fields.add(config_name)

        if broken_fields:
            errors.append("Settings not saved: some fields are not valid")
        else:
            try:
                config.current.update(new_configs)
                config.save(config.current_path)
                # reload jobs if configs have changed
                jobs.schedule_jobs()

                messages.append("Settings saved")
            except Exception as err:
                errors.append(f"Error while applying the settings: {err}")

    relevant_configs = {
        config_name: config.current[config_name]
        for config_name in relevant_config_names
    }

    return render_template(
        "server_manager_config_form.html",
        server_name=server_name,
        prefix=prefix,
        configs=relevant_configs,
        configs_spec=config.SPEC,
        broken_fields=broken_fields,
        errors=errors,
        warnings=warnings,
        messages=messages,
    )


@app.route("/<server_name>/config_form", methods=["GET", "POST"])
@app.route("/<server_name>/config_form/restart", methods=["POST"], defaults={"restart": True})
def server_config_form(server_name, restart=False):
    config_path = SERVERS[server_name].get_config_path()
    config_contents = ""
    errors = []
    warnings = []
    messages = []

    if request.method == "POST":
        config_contents = request.form.get("config_contents", "").strip()
        try:
            if server_name == "dcs" and not config_path:
                errors.append("Config not saved: you must configure the location of the DCS "
                              "Server Saved Games folder in order to edit the config file.")
            elif not config_path.exists():
                errors.append(f"Config not saved: no config file found at {config_path}")
            else:
                if config_contents:
                    config_path.write_text(config_contents)
                    messages.append("Config saved")

                    if restart:
                        restarted, reason = SERVERS[server_name].restart()
                        if restarted:
                            messages.append("Server restarted")
                        else:
                            warnings.append(f"Failed to restart server: {reason}")
                else:
                    errors.append("Config not saved: empty config contents")
        except Exception as err:
            errors.append(f"Error trying to save the config: {err}")
    else:
        if server_name == "dcs" and not config_path:
            errors.append("Can't read config: you must configure the location of the DCS Server "
                          "Saved Games folder in order to edit the config file.")
        elif not config_path.exists():
            errors.append(f"Can't read config: no config file found at {config_path}")
        else:
            config_contents = config_path.read_text()

    return render_template(
        "server_config_form.html",
        server_name=server_name,
        config_contents=config_contents,
        errors=errors,
        warnings=warnings,
        messages=messages,
    )


def list_files_in_folder(folder_path, extension, errors=None, warnings=None, messages=None):
    """
    List files in the specified folder, with the specified extension.
    """
    if errors is None:
        errors = []
    if warnings is None:
        warnings = []
    if messages is None:
        messages = []

    if folder_path.exists():
        files = [
            file_path
            for file_path in folder_path.glob("*." + extension)
            if file_path.is_file()
        ]
    else:
        files = []
        warnings.append(f"Folder {folder_path} does not exist")

    return render_template(
        "files_list.html",
        files=files,
        errors=errors,
        warnings=warnings,
        messages=messages,
    )


@app.route("/dcs/missions", methods=["GET", "POST"])
def dcs_missions():
    errors = []
    messages = []

    missions_path = dcs.get_missions_path()

    if request.method == "POST":
        file = request.files["mission_file"]
        # If the user does not select a file, the browser submits an empty file without a filename.
        if file.filename == "":
            errors.append("No mission file selected")
        elif not missions_path.exists():
            errors.append("Mission not uploaded: folder does not exist")
        else:
            filename = secure_filename(file.filename)
            file.save(missions_path / filename)
            messages.append(f"Mission {filename} uploaded")

    return list_files_in_folder(
        folder_path=missions_path,
        extension=dcs.MISSION_FILE_EXTENSION,
        errors=errors,
        messages=messages,
    )


@app.route("/dcs/tracks")
def dcs_tracks():
    return list_files_in_folder(
        folder_path=dcs.get_tracks_path(),
        extension=dcs.TRACK_FILE_EXTENSION,
    )


@app.route("/dcs/tacviews")
def dcs_tacviews():
    return list_files_in_folder(
        folder_path=dcs.get_tacviews_path(),
        extension=dcs.TACVIEW_FILE_EXTENSION,
    )


@app.route("/dcs/mission_status", methods=["GET", "POST"])
def dcs_mission_status():
    if request.method == "POST":
        data = request.get_json()
        dcs.set_mission_status(
            mission=data.get("mission", "Unknown"),
            players=data.get("players", []),
        )

    return render_template("dcs_mission_status.html", mission_status=dcs.current_mission_status())


@app.route("/dcs/hook/install", methods=["POST"])
def dcs_install_hook():
    try:
        dcs.install_hook()
        args = dict(messages=["Hook installed (restart the DCS Server to apply changes)"])
    except Exception as err:
        args = dict(errors=[f"Failed to install hook: {err}"])

    return render_template("messages.html", **args)


@app.route("/dcs/hook/uninstall", methods=["POST"])
def dcs_uninstall_hook():
    try:
        dcs.uninstall_hook()
        args = dict(messages=["Hook uninstalled (restart the DCS Server to apply changes)"])
    except Exception as err:
        args = dict(errors=[f"Failed to uninstall hook: {err}"])

    return render_template("messages.html", **args)


@app.route("/dcs/pretense/check_persistence")
def dcs_pretense_check_persistence():
    try:
        is_persistent = dcs.pretense_is_persistent()
        if is_persistent:
            args = dict(messages=["Pretense persistence is Enabled"])
        else:
            args = dict(messages=["Pretense persistence is Disabled"])
    except Exception as err:
        args = dict(errors=[f"Failed to check Pretense persistence: {err}"])

    return render_template("messages.html", **args)


@app.route("/dcs/pretense/enable_persistence", methods=["POST"])
def dcs_pretense_enable_persistence():
    try:
        dcs.pretense_enable_persistence()
        args = dict(messages=["Pretense persistence enabled"])
    except Exception as err:
        args = dict(errors=[f"Failed to enable Pretense persistence: {err}"])

    return render_template("messages.html", **args)


@app.route("/dcs/pretense/disable_persistence", methods=["POST"])
def dcs_pretense_disable_persistence():
    try:
        dcs.pretense_disable_persistence()
        args = dict(messages=["Pretense persistence disabled"])
    except Exception as err:
        args = dict(errors=[f"Failed to disable Pretense persistence: {err}"])

    return render_template("messages.html", **args)


@app.route("/logs")
def log_contents():
    log_path = logs.get_path()
    if log_path.exists():
        log_contents = log_path.read_text(encoding="utf-8")
    else:
        log_contents = "No log file found"

    return log_contents


@app.route("/logs/delete", methods=["POST"])
def log_delete():
    log_path = logs.get_path()
    if log_path.exists():
        log_path.write_text("")

    return "Logs emptied"


@app.route("/logs/size")
def log_size():
    log_path = logs.get_path()
    if log_path.exists():
        size_mb = log_path.stat().st_size / (1024 * 1024)
        return f"{size_mb:.2f} MB"
    else:
        return "no file found"


@app.errorhandler(Exception)
def handle_exception(e):
    """
    Generic error handler for when actions fail.
    """
    return render_template("messages.html", warnings=[str(e)])
