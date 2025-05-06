"""
This is the web app, allowing the user to check the status of the servers and to interact with
them, and the configs.
"""
import logging
import os
import sys
import shutil
from enum import Enum
from uuid import uuid4
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, cli, request, after_this_request
from flask_basicauth import BasicAuth
from werkzeug.utils import secure_filename
import waitress

from dsm import config, jobs, dcs, srs, logs, processes


class MessageKind(Enum):
    """
    Kinds of messages to show in the UI.
    """
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message:
    """
    A message to show in the ui, with style based on the message kind and optional timeout.
    When created, it automatically adds itself to request.messages.
    """
    def __init__(self, text, kind, timeout=None):
        self.id_ = str(uuid4())
        self.text = text
        self.kind = kind
        self.timeout = timeout

        if not hasattr(request, "messages"):
            request.messages = []

        request.messages.append(self)

    def render(self, as_tag="p"):
        """
        Render this message to html.
        """
        return render_template("messages.html", messages=[self], as_tag=as_tag)


# helpers to build messages with very short code:

def error(text, timeout=None):
    """
    Build an error message.
    """
    return Message(text, MessageKind.ERROR, timeout)


def warn(text, timeout=None):
    """
    Build a warning message.
    """
    return Message(text, MessageKind.WARNING, timeout)


def info(text, timeout=None):
    """
    Build an info message.
    """
    return Message(text, MessageKind.INFO, timeout)


# web app singleton, we won't need more than one
app = Flask(
    "dcs_server_manager",
    template_folder=config.get_data_path() / "templates",
    static_folder=config.get_data_path() / "static",
)
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
        logging.getLogger('waitress').disabled = True
        logging.getLogger('waitress.queue').disabled = True
        cli.show_server_banner = lambda *args: None

    if config.current["DSM_PASSWORD"]:
        app.config["BASIC_AUTH_USERNAME"] = "admin"
        app.config["BASIC_AUTH_PASSWORD"] = config.current["DSM_PASSWORD"]
        app.config["BASIC_AUTH_FORCE"] = True
        BasicAuth(app)

    jobs.launch()

    logger.info("Running DCS Server Manager")
    logger.info("Web UI: http://localhost:%s", config.current["DSM_PORT"])
    logger.info("If you don't remember the password, you can edit it in the config file")

    host = config.current["DSM_HOST"]
    port = config.current["DSM_PORT"]
    if debug:
        # in debug mode we run the server directly with flask, so we can debug on errors
        app.run(host=host, port=port, debug=True)
    else:
        # in prod we use waitress
        waitress.serve(app, host=host, port=port, threads=2, _quiet=True)


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
@app.route("/<server_name>/status/short", defaults={"short": True})
def server_status(server_name, short=False):
    try:
        status = SERVERS[server_name].current_status()
        icon = STATUS_ICONS[status]
        text = status.name.replace("_", " ").lower()
        title = ""
    except Exception as err:
        icon = WARNING_ICON
        text = "failed to get status"
        title = str(err)

    if short:
        return f'<span title="{text} {title}">{icon}</span>'
    else:
        return f'<span title="{title}">{icon} {text}</span>'


@app.route("/<server_name>/resources")
def server_resources(server_name):
    try:
        resources = SERVERS[server_name].current_resources()
        return render_template("server_resources.html", resources=resources)
    except Exception as err:
        return error(f"Error querying server resources: {err}").render()


@app.route("/<server_name>/start", methods=["POST"])
def server_start(server_name):
    try:
        SERVERS[server_name].start()
        return info("Server started").render("span")
    except Exception as err:
        return error(f"Failed to start server: {err}").render("span")


@app.route("/<server_name>/restart", methods=["POST"])
def server_restart(server_name):
    try:
        SERVERS[server_name].restart()
        return info("Server restarted").render("span")
    except Exception as err:
        return error(f"Failed to restart server: {err}").render("span")


@app.route("/<server_name>/kill", methods=["POST"])
def server_kill(server_name):
    try:
        SERVERS[server_name].kill()
        return info("Server killed").render("span")
    except Exception as err:
        return error(f"Failed to kill server: {err}").render("span")


@app.route("/<server_name>/manager_config_form", methods=["GET", "POST"])
def server_manager_config_form(server_name):
    prefix = f"{server_name.upper()}_"
    relevant_config_names = [
        config_name for config_name in config.current
        if config_name.startswith(prefix)
    ]
    broken_fields = set()

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
                            warn(f"Warning: path {value_path} does not exist")
                    except Exception as err:
                        # not important to show errors in this check to the user
                        logger.debug("Failed to run path check for %s: %s", config_name, err)
            except ValueError:
                broken_fields.add(config_name)

        if broken_fields:
            error("Settings not saved: some fields are not valid")
        else:
            try:
                config.current.update(new_configs)
                config.save(config.current_path)
                # reload jobs if configs have changed
                jobs.schedule_jobs()

                info("Settings saved", 6)
                if server_name == "dsm":
                    info("Restarting the DCS Server Manager so the changes take effect...", 10)
                    processes.restart_self(delay=2)
            except Exception as err:
                error(f"Error while applying the settings: {err}")

    relevant_configs = {
        config_name: config.current[config_name]
        for config_name in relevant_config_names
    }

    if server_name == "dsm" and relevant_configs["DSM_PASSWORD"] == "":
        warn("Warning: password is empty, the web UI is not protected! "
             "It's recommended to set a password.")

    return render_template(
        "server_manager_config_form.html",
        server_name=server_name,
        prefix=prefix,
        configs=relevant_configs,
        configs_spec=config.SPEC,
        broken_fields=broken_fields,
    )


@app.route("/<server_name>/config_form", methods=["GET", "POST"])
@app.route("/<server_name>/config_form/restart", methods=["POST"], defaults={"restart": True})
def server_config_form(server_name, restart=False):
    config_path = SERVERS[server_name].get_config_path()
    config_contents = ""

    if server_name == "dcs" and not config_path:
        error("Can't edit config: you must configure the location of the DCS Server "
              "Saved Games folder in order to edit the config file.")
    elif not config_path.exists():
        error(f"No config file found at {config_path}")
    elif request.method == "POST":
        config_contents = request.form.get("config_contents", "").strip()
        try:
            if config_contents:
                config_path.write_text(config_contents)
                info("Config saved", 6)

                if restart:
                    try:
                        SERVERS[server_name].restart()
                        info("Server restarted", 6)
                    except Exception as err:
                        error(f"Failed to restart server: {err}")
            else:
                error("Config not saved: empty config contents")
        except Exception as err:
            error(f"Error trying to save the config: {err}")
    else:
        config_contents = config_path.read_text()

    return render_template(
        "server_config_form.html",
        server_name=server_name,
        config_path=config_path,
        config_contents=config_contents,
    )


def list_files_in_folder(folder_path, extension):
    """
    List files in the specified folder, with the specified extension.
    """
    if folder_path.exists():
        files = [
            file_path
            for file_path in folder_path.glob("*." + extension)
            if file_path.is_file()
        ]
    else:
        files = []
        warn(f"Folder {folder_path} does not exist")

    return render_template("files_list.html", files=files)


@app.route("/dcs/missions", methods=["GET", "POST"])
def dcs_missions():
    missions_path = dcs.get_missions_path()

    if request.method == "POST":
        if "mission_file" not in request.files:
            warn("No mission file selected")
        else:
            file = request.files["mission_file"]
            # If the user does not select a file, the browser submits an empty file without a filename.
            if file.filename == "":
                error("No mission file selected")
            else:
                filename = secure_filename(file.filename)
                file.save(missions_path / filename)
                info(f"Mission {filename} uploaded", 6)

    return list_files_in_folder(folder_path=missions_path, extension=dcs.MISSION_FILE_EXTENSION)


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
        return info("Hook installed (restart the DCS Server to apply changes)", 10).render()
    except Exception as err:
        return error(f"Failed to install hook: {err}").render()


@app.route("/dcs/hook/uninstall", methods=["POST"])
def dcs_uninstall_hook():
    try:
        dcs.uninstall_hook()
        return info("Hook uninstalled (restart the DCS Server to apply changes)", 10).render()
    except Exception as err:
        return error(f"Failed to uninstall hook: {err}").render()


@app.route("/dcs/pretense/check_persistence")
def dcs_pretense_check_persistence():
    try:
        is_persistent = dcs.pretense_is_persistent()
        if is_persistent:
            return info("Pretense persistence is Enabled", 6).render()
        else:
            return info("Pretense persistence is Disabled", 6).render()
    except Exception as err:
        return error(f"Failed to check Pretense persistence: {err}").render()


@app.route("/dcs/pretense/enable_persistence", methods=["POST"])
def dcs_pretense_enable_persistence():
    try:
        dcs.pretense_enable_persistence()
        return info("Pretense persistence enabled", 6).render()
    except Exception as err:
        return error(f"Failed to enable Pretense persistence: {err}").render()


@app.route("/dcs/pretense/disable_persistence", methods=["POST"])
def dcs_pretense_disable_persistence():
    try:
        dcs.pretense_disable_persistence()
        return info("Pretense persistence disabled", 6).render()
    except Exception as err:
        return error(f"Failed to disable Pretense persistence: {err}").render()


@app.route("/logs")
def log_contents():
    log_path = logs.get_path()
    if log_path.exists():
        contents = log_path.read_text(encoding="utf-8")
    else:
        contents = "No log file found"
    return contents


@app.route("/logs/delete", methods=["POST"])
def log_delete():
    log_path = logs.get_path()
    if log_path.exists():
        log_path.write_text("")
    return info("Logs emptied").render("span")


@app.route("/logs/archive", methods=["POST"])
def log_archive():
    log_path = logs.get_path()
    if log_path.exists():
        while True:
            # create a new archive name, but make sure it doesn't exist
            archive_date = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = log_path.parent / f"{log_path.name}.archive_{archive_date}"

            if not archive_path.exists():
                break

        # can't just move the current file because that breaks the logging handles, so we must
        # copy to a new file and clean the current one instead
        shutil.copy(log_path, archive_path)
        log_path.write_text("")

    return info(f"Logs archived to {archive_path}").render("span")


@app.route("/logs/size")
def log_size():
    log_path = logs.get_path()
    if log_path.exists():
        size_mb = log_path.stat().st_size / (1024 * 1024)
        return f"{size_mb:.2f} MB in {log_path}"
    else:
        return warn("no file found").render("span")


@app.errorhandler(Exception)
def handle_exception(e):
    """
    Generic error handler for when actions fail.
    """
    return warn(str(e)).render()
