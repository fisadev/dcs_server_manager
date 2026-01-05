"""
This is the web app, allowing the user to check the status of the servers and to interact with
them, and the configs.
"""
import logging
import os
from enum import Enum
from uuid import uuid4
from pathlib import Path

from flask import Flask, render_template, cli, request, send_file
from flask_basicauth import BasicAuth
from werkzeug.utils import secure_filename
import waitress

from dsm import config, jobs, dcs, srs, logs, VERSION


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

    logger.info("Running DCS Server Manager %s", VERSION)
    logger.info("Web UI: http://localhost:%s", config.current["DSM_PORT"])
    logger.info("If you don't remember the password, you can edit it in the config file")

    host = config.current["DSM_HOST"]
    port = config.current["DSM_PORT"]
    if debug:
        # in debug mode we run the server directly with flask, so we can debug on errors
        app.run(host=host, port=port, debug=True)
    else:
        # in prod we use waitress, and we need many threads to support the UI asking for
        # status while the server is posting updates, etc
        waitress.serve(app, host=host, port=port, threads=10, _quiet=True)


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
    dcs.DCSServerStatus.PLAYING: GOOD_ICON,
    dcs.DCSServerStatus.PAUSED: GOOD_ICON,
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


@app.route("/<server_name>/stop", methods=["POST"])
@app.route("/<server_name>/kill", methods=["POST"], defaults={"kill": True})
def server_stop(server_name, kill=False):
    try:
        SERVERS[server_name].stop(kill=kill)
        return info(f"Server stopped").render("span")
    except Exception as err:
        return error(f"Failed to stop server: {err}").render("span")


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
                    info("You need to restart DCS Server Manager for the changes to take effect")
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


def files_in_folder(folder_path, glob_filter, files_form_id):
    """
    View that lists files in the specified folder, with the specified glob filter, and allows for
    some basic interactions with them.

    If "file" is in the request args, it will download that file instead.
    If it's a POST and "upload_file" is in request.files, it will upload the file to the folder.
    If it's a POST and there are "delete-..." keys in request.form, it will delete those files.

    For anything except the file download case, the list of current files is returned as html at
    the end.
    """
    if request.method == "POST":
        if "upload_file" in request.files:
            # uploading a file case
            file = request.files["upload_file"]
            # If the user does not select a file, the browser submits an empty file without a
            # filename
            if file.filename == "":
                error("No file selected to be uploaded")
            else:
                filename = secure_filename(file.filename)
                file.save(folder_path / filename)
                info(f"{filename} uploaded", 6)
        elif any(key.startswith("delete-") for key in request.form):
            # deleting files case
            deleted_count = 0
            for key in request.form:
                if key.startswith("delete-"):
                    file_name = key.replace("delete-", "")
                    file_path = folder_path / file_name
                    if file_path.exists():
                        file_path.unlink()
                        deleted_count += 1
                    else:
                        warn(f"Can't delete {file_name}, no longer exist")

            if deleted_count:
                info(f"{deleted_count} files deleted", 6)

    if "download_file" in request.args:
        # downloading a file case
        file_name = request.args["download_file"]
        file_path = folder_path / file_name
        if file_path.exists():
            return send_file(file_path, as_attachment=True)
        else:
            return warn(f"Can't download {file_name}, no longer exists").render(), 404

    if folder_path.exists():
        files = [
            file_path
            for file_path in folder_path.glob(glob_filter)
            if file_path.is_file()
        ]
    else:
        files = []
        warn(f"Folder {folder_path} does not exist")

    return render_template(
        "files_list.html",
        files=files,
        files_form_id=files_form_id,
    )


@app.route("/dcs/missions", methods=["GET", "POST"])
def dcs_missions():
    return files_in_folder(
        folder_path=dcs.get_missions_path(),
        glob_filter="*." + dcs.MISSION_FILE_EXTENSION,
        files_form_id="dcs-missions-form",
    )


@app.route("/dcs/tracks", methods=["GET", "POST"])
def dcs_tracks():
    return files_in_folder(
        folder_path=dcs.get_tracks_path(),
        glob_filter="*." + dcs.TRACK_FILE_EXTENSION,
        files_form_id="dcs-tracks-form",
    )


@app.route("/dcs/tacviews", methods=["GET", "POST"])
def dcs_tacviews():
    return files_in_folder(
        folder_path=dcs.get_tacviews_path(),
        glob_filter="*." + dcs.TACVIEW_FILE_EXTENSION,
        files_form_id="dcs-tacviews-form",
    )


@app.route("/dcs/mission_status", methods=["GET", "POST"])
def dcs_mission_status():
    if request.method == "POST":
        # POSTs to this endpoint are meant to be used by the DCS server hook to update the
        # current mission status, while also consuming the pending actions. So we both update the
        # mission status, and consume+return the pending actions.
        data = request.get_json()
        dcs.set_mission_status(
            mission=data.get("mission", "Unknown"),
            players=data.get("players", []),
            paused=data.get("paused", "Unknown"),
        )

        return {"actions": dcs.consume_pending_actions()}
    else:
        # GETs just return the current mission status, usually for the UI
        return render_template("dcs_mission_status.html", mission_status=dcs.current_mission_status())


@app.route("/dcs/pause_buttons")
def dcs_pause_buttons():
    return render_template("dcs_pause_buttons.html", mission_status=dcs.current_mission_status())


@app.route("/dcs/pause", methods=["POST"], defaults={"action": "pause"})
@app.route("/dcs/unpause", methods=["POST"], defaults={"action": "unpause"})
def dcs_queue_pending_action(action):
    dcs.add_pending_action(action)
    return info(f"{action.capitalize()} requested").render("span")


@app.route("/dcs/hook/install", methods=["POST"])
def dcs_install_hook():
    try:
        dcs.install_hook()
        return info("Hook installed, restart the DCS Server to apply changes", 10).render()
    except Exception as err:
        return error(f"Failed to install hook: {err}").render()


@app.route("/dcs/hook/uninstall", methods=["POST"])
def dcs_uninstall_hook():
    try:
        dcs.uninstall_hook()
        return info("Hook uninstalled, restart the DCS Server to apply changes", 10).render()
    except Exception as err:
        return error(f"Failed to uninstall hook: {err}").render()


@app.route("/dcs/hook/check")
def dcs_check_hook():
    try:
        installed, up_to_date, version = dcs.hook_check()
        if installed:
            if up_to_date:
                return info(f"Hook is installed and up to date (version: {version})", 6).render()
            else:
                return warn(f"Hook is installed but not up to date (version: {version})", 6).render()
        else:
            return warn("Hook is not installed", 6).render()
    except Exception as err:
        return error(f"Failed to check hook: {err}").render()


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


@app.route("/jobs/status")
@app.route("/jobs/status/short", defaults={"short": True})
def jobs_status(short=False):
    if jobs.enabled:
        icon = GOOD_ICON
        text = "enabled"
    else:
        icon = WARNING_ICON
        text = "disabled"

    if short:
        return f'<span title="automations {text}">{icon}</span>'
    else:
        return f'<span>{icon} {text}</span>'


@app.route("/jobs/enable", methods=["POST"])
def jobs_enable():
    try:
        jobs.enable()
        return info("Jobs enabled").render("span")
    except Exception as err:
        return error(f"Failed to enable jobs: {err}").render("span")


@app.route("/jobs/disable", methods=["POST"])
def jobs_disable():
    try:
        jobs.disable()
        return info("Jobs disabled").render("span")
    except Exception as err:
        return error(f"Failed to disable jobs: {err}").render("span")


@app.route("/logs")
def log_contents():
    try:
        contents = logs.read_contents()
        if contents is None:
            return warn("No log file found").render("span")
        else:
            return contents
    except Exception as err:
        return error(f"Failed to read logs: {err}").render("span")


@app.route("/log/clear", methods=["POST"])
def log_clear():
    try:
        logs.clear()
        return info("Logs emptied").render("span")
    except Exception as err:
        return error(f"Failed to empty logs: {err}").render("span")


@app.route("/log/archive", methods=["POST"])
def log_archive():
    try:
        archive_path = logs.archive()
        if archive_path is None:
            return warn("No log file found").render("span")
        else:
            return info(f"Logs archived to {archive_path}").render("span")
    except Exception as err:
        return error(f"Failed to archive logs: {err}").render("span")


@app.route("/log/size")
def log_size():
    try:
        size_bytes = logs.current_size()
        if size_bytes is None:
            return warn("no file found").render("span")
        else:
            size_mb = size_bytes / (1024 * 1024)
            return f"{size_mb:.2f} MB in {logs.get_path()}"
    except Exception as err:
        return error(f"failed to get logs size: {err}").render("span")


@app.route("/log/files", methods=["GET", "POST"])
def log_files():
    return files_in_folder(
        folder_path=logs.get_path().parent,
        glob_filter="*.log",
        files_form_id="log-files-form",
    )


@app.route("/version")
def version():
    """
    Show the version of the app.
    """
    return VERSION


@app.errorhandler(Exception)
def handle_exception(e):
    """
    Generic error handler for when actions fail.
    """
    return warn(str(e)).render()
