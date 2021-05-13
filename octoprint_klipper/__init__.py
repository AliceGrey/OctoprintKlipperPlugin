# <Octoprint Klipper Plugin>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, unicode_literals
import datetime
import logging
import octoprint.plugin
import octoprint.plugin.core
import glob
import os
import sys
from octoprint.util.comm import parse_firmware_line
from octoprint.access.permissions import Permissions, ADMIN_GROUP, USER_GROUP
from .modules import KlipperLogAnalyzer
import flask
from flask_babel import gettext

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

if sys.version_info[0] < 3:
    import StringIO

class KlipperPlugin(
        octoprint.plugin.StartupPlugin,
        octoprint.plugin.TemplatePlugin,
        octoprint.plugin.SettingsPlugin,
        octoprint.plugin.AssetPlugin,
        octoprint.plugin.SimpleApiPlugin,
        octoprint.plugin.EventHandlerPlugin):

    _parsing_response = False
    _parsing_check_response = True
    _message = ""

    def __init__(self):
        self._logger = logging.getLogger("octoprint.plugins.klipper")
        self._octoklipper_logger = logging.getLogger("octoprint.plugins.klipper.debug")

    # -- Startup Plugin
    def on_startup(self, host, port):
        from octoprint.logging.handlers import CleaningTimedRotatingFileHandler
        octoklipper_logging_handler = CleaningTimedRotatingFileHandler(
            self._settings.get_plugin_logfile_path(postfix="debug"), when="D", backupCount=3)
        octoklipper_logging_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        octoklipper_logging_handler.setLevel(logging.DEBUG)

        self._octoklipper_logger.addHandler(octoklipper_logging_handler)
        self._octoklipper_logger.setLevel(
            logging.DEBUG if self._settings.get_boolean(["debug_logging"]) else logging.INFO)
        self._octoklipper_logger.propagate = False

    def on_after_startup(self):
        klipper_port = self._settings.get(["connection", "port"])
        additional_ports = self._settings.global_get(
            ["serial", "additionalPorts"])

        if klipper_port not in additional_ports:
            additional_ports.append(klipper_port)
            self._settings.global_set(
                ["serial", "additionalPorts"], additional_ports)
            self._settings.save()
            self.log_info(
                "Added klipper serial port {} to list of additional ports.".format(klipper_port))

    # -- Settings Plugin

    def get_additional_permissions(self, *args, **kwargs):
        return [
            {
                "key": "CONFIG",
                "name": "Config Klipper",
                "description": gettext("Allows to config klipper"),
                "default_groups": [ADMIN_GROUP],
                "dangerous": True,
                "roles": ["admin"]
            },
            {
                "key": "MACRO",
                "name": "Use Klipper Macros",
                "description": gettext("Allows to use klipper macros"),
                "default_groups": [ADMIN_GROUP],
                "dangerous": True,
                "roles": ["admin"]
            },
        ]

    def get_settings_defaults(self):
        return dict(
            connection=dict(
                port="/tmp/printer",
                replace_connection_panel=True
            ),
            macros=[dict(
                name="E-Stop",
                macro="M112",
                sidebar=True,
                tab=True
            )],
            probe=dict(
                height=0,
                lift=5,
                speed_xy=1500,
                speed_z=500,
                points=[dict(
                    name="point-1",
                    x=0,
                    y=0
                )]
            ),
            configuration=dict(
                debug_logging=False,
                configpath="~/printer.cfg",
                old_config="",
                logpath="/tmp/klippy.log",
                reload_command="RESTART",
                shortStatus_navbar=True,
                shortStatus_sidebar=True,
                parse_check=False,
                fontsize=9
            )
        )

    def on_settings_load(self):
        data = octoprint.plugin.SettingsPlugin.on_settings_load(self)

        configpath = os.path.expanduser(
            self._settings.get(["configuration", "configpath"])
        )

        try:
            f = open(configpath, "r")
            data["config"] = f.read()
            f.close()
        except IOError:
            self.log_error(
                "Error: Klipper config file not found at: {}".format(
                    configpath)
            )
        else:
            self.send_message("reload", "config", "", data["config"])
            # send the configdata to frontend to update ace editor
        return data

    def on_settings_save(self, data):

        self.log_debug(
            "Save klipper configs"
        )

        if "config" in data:
            if self.key_exist(data, "configuration", "parse_check"):
                check_parse = data["configuration"]["parse_check"]
            else:
                check_parse = self._settings.get(["configuration", "parse_check"])

            if sys.version_info[0] < 3:
                data["config"] = data["config"].encode('utf-8')

            # check for configpath if it was changed during changing of the configfile
            if self.key_exist(data, "configuration", "configpath"):
                configpath = os.path.expanduser(
                    data["configuration"]["configpath"]
                )
            else:
                # if the configpath was not changed during changing the printer.cfg. Then the configpath would not be in data[]
                configpath = os.path.expanduser(
                    self._settings.get(["configuration", "configpath"])
                )
            if self.file_exist(configpath) and (self._parsing_check_response or not check_parse):
                try:
                    f = open(configpath, "w")
                    f.write(data["config"])
                    f.close()


                    self.log_debug("Writing Klipper config to {}".format(configpath))
                except IOError:
                    self.log_error("Error: Couldn't write Klipper config file: {}".format(configpath))
                else:
                    #load the reload command from changed data if it is not existing load the saved setting
                    if self.key_exist(data, "configuration", "reload_command"):
                        reload_command = os.path.expanduser(
                            data["configuration"]["reload_command"]
                        )
                    else:
                        reload_command = self._settings.get(["configuration", "reload_command"])

                    if reload_command != "manually":
                        # Restart klippy to reload config
                        self._printer.commands(reload_command)
                        self.log_info("Restarting Klipper.")
                    # we dont want to write the klipper conf to the octoprint settings
                    data.pop("config", None)

        # save the rest of changed settings into config.yaml of octoprint
        old_debug_logging = self._settings.get_boolean(["configuration", "debug_logging"])

        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        new_debug_logging = self._settings.get_boolean(["configuration", "debug_logging"])
        if old_debug_logging != new_debug_logging:
            if new_debug_logging:
                self._octoklipper_logger.setLevel(logging.DEBUG)
            else:
                self._octoklipper_logger.setLevel(logging.INFO)

    def get_settings_restricted_paths(self):
        return dict(
            admin=[
                ["connection", "port"],
                ["configuration", "configpath"],
                ["configuration", "replace_connection_panel"]
            ],
            user=[
                ["macros"],
                ["probe"]
            ]
        )

    def get_settings_version(self):
        return 3

    def on_settings_migrate(self, target, current):
        if current is None:
            settings = self._settings

            if settings.has(["serialport"]):
                settings.set(["connection", "port"],
                             settings.get(["serialport"]))
                settings.remove(["serialport"])

            if settings.has(["replace_connection_panel"]):
                settings.set(
                    ["connection", "replace_connection_panel"],
                    settings.get(["replace_connection_panel"])
                )
                settings.remove(["replace_connection_panel"])

            if settings.has(["probeHeight"]):
                settings.set(["probe", "height"],
                             settings.get(["probeHeight"]))
                settings.remove(["probeHeight"])

            if settings.has(["probeLift"]):
                settings.set(["probe", "lift"], settings.get(["probeLift"]))
                settings.remove(["probeLift"])

            if settings.has(["probeSpeedXy"]):
                settings.set(["probe", "speed_xy"],
                             settings.get(["probeSpeedXy"]))
                settings.remove(["probeSpeedXy"])

            if settings.has(["probeSpeedZ"]):
                settings.set(["probe", "speed_z"],
                             settings.get(["probeSpeedZ"]))
                settings.remove(["probeSpeedZ"])

            if settings.has(["probePoints"]):
                points = settings.get(["probePoints"])
                points_new = []
                for p in points:
                    points_new.append(
                        dict(name="", x=int(p["x"]), y=int(p["y"]), z=0))
                settings.set(["probe", "points"], points_new)
                settings.remove(["probePoints"])

            if settings.has(["configPath"]):
                self.log_info("migrate setting for: configPath")
                settings.set(["config_path"], settings.get(["configPath"]))
                settings.remove(["configPath"])

        if target is 3 and current is 2:
            settings = self._settings
            if settings.has(["configuration", "navbar"]):
                self.log_info("migrate setting for: configuration/navbar")
                settings.set(["configuration", "shortStatus_navbar"], settings.get(["configuration", "navbar"]))
                settings.remove(["configuration", "navbar"])

    # -- Template Plugin

    def get_template_configs(self):
        return [
            dict(type="navbar", custom_bindings=True),
            dict(type="settings", custom_bindings=True),
            dict(
                type="generic",
                name="Assisted Bed Leveling",
                template="klipper_leveling_dialog.jinja2",
                custom_bindings=True
            ),
            dict(
                type="generic",
                name="PID Tuning",
                template="klipper_pid_tuning_dialog.jinja2",
                custom_bindings=True
            ),
            dict(
                type="generic",
                name="Coordinate Offset",
                template="klipper_offset_dialog.jinja2",
                custom_bindings=True
            ),
            dict(
                type="tab",
                name="Klipper",
                template="klipper_tab_main.jinja2",
                suffix="_main",
                custom_bindings=True
            ),
            dict(type="sidebar",
                 custom_bindings=True,
                 icon="rocket",
                 replaces="connection" if self._settings.get_boolean(
                     ["connection", "replace_connection_panel"]) else ""
                 ),
            dict(
                type="generic",
                name="Performance Graph",
                template="klipper_graph_dialog.jinja2",
                custom_bindings=True
            ),
            dict(
                type="generic",
                name="Config Editor",
                template="klipper_editor_dialog.jinja2",
                custom_bindings=True
            ),
            dict(
                type="generic",
                name="Macro Dialog",
                template="klipper_param_macro_dialog.jinja2",
                custom_bindings=True
            )
        ]

    # -- Asset Plugin

    def get_assets(self):
        return dict(
            js=["js/klipper.js",
                "js/klipper_settings.js",
                "js/klipper_leveling.js",
                "js/klipper_pid_tuning.js",
                "js/klipper_offset.js",
                "js/klipper_param_macro.js",
                "js/klipper_graph.js",
                "js/klipper_editor.js"
                ],
            css=["css/klipper.css"]
        )

    # -- Event Handler Plugin

    def on_event(self, event, payload):
        if "UserLoggedIn" == event:
            self.update_status("info", "Klipper: Standby")
        if "Connecting" == event:
            self.update_status("info", "Klipper: Connecting ...")
        elif "Connected" == event:
            self.update_status("info", "Klipper: Connected to host")
            self.log_info(
                "Connected to host via {} @{}bps".format(payload["port"], payload["baudrate"]))
        elif "Disconnected" == event:
            self.update_status("info", "Klipper: Disconnected from host")
        elif "Error" == event:
            self.update_status("error", "Klipper: Error")
            self.log_error(payload["error"])

    # -- GCODE Hook

    def on_parse_gcode(self, comm, line, *args, **kwargs):

        if "FIRMWARE_VERSION" in line:
            printerInfo = parse_firmware_line(line)
            if "FIRMWARE_VERSION" in printerInfo:
                self.log_info("Firmware version: {}".format(
                    printerInfo["FIRMWARE_VERSION"]))
        elif "// probe" in line or "// Failed to verify BLTouch" in line:
            msg = line.strip('/')
            self.log_info(msg)
            write_parsing_response_buffer()
        elif "//" in line:
            # add lines with // to a buffer
            self._message = self._message + line.strip('/')
            if not self._parsing_response:
                self.update_status("info", self._message)
            self._parsing_response = True
        elif "!!" in line:
            msg = line.strip('!')
            self.update_status("error", msg)
            self.log_error(msg)
            self.write_parsing_response_buffer()
        else:
            self.write_parsing_response_buffer()
        return line

    def write_parsing_response_buffer(self):
        # write buffer with // lines after a gcode response without //
        if self._parsing_response:
            self._parsing_response = False
            self.log_info(self._message)
            self._message = ""

    def get_api_commands(self):
        return dict(
            listLogFiles=[],
            getStats=["logFile"],
            reloadConfig=[],
            checkConfig=["config"]
        )

    def on_api_command(self, command, data):
        if command == "listLogFiles":
            files = []
            logpath = os.path.expanduser(
                self._settings.get(["configuration", "logpath"])
            )
            if self.file_exist(logpath):
                for f in glob.glob(self._settings.get(["configuration", "logpath"]) + "*"):
                    filesize = os.path.getsize(f)
                    files.append(dict(
                        name=os.path.basename(
                            f) + " ({:.1f} KB)".format(filesize / 1000.0),
                        file=f,
                        size=filesize
                    ))
                return flask.jsonify(data=files)
            else:
                return flask.jsonify(data=files)
        elif command == "getStats":
            if "logFile" in data:
                log_analyzer = KlipperLogAnalyzer.KlipperLogAnalyzer(
                    data["logFile"])
                return flask.jsonify(log_analyzer.analyze())
        elif command == "reloadConfig":
            data = octoprint.plugin.SettingsPlugin.on_settings_load(self)

            configpath = os.path.expanduser(
                self._settings.get(["configuration", "configpath"])
            )

            try:
                f = open(configpath, "r")
                data["config"] = f.read()
                f.close()
            except IOError:
                self.log_error(
                    "Error: Klipper config file not found at: {}".format(
                        configpath)
                )
            else:

                self._settings.set(["config"], data["config"])
                # self.send_message("reload", "config", "", data["config"])
                # send the configdata to frontend to update ace editor
                if sys.version_info[0] < 3:
                    data["config"] = data["config"].decode('utf-8')
                return flask.jsonify(data=data["config"])
        elif command == "checkConfig":
            if "config" in data:
                if not self.validate_configfile(data["config"]):
                    self.log_debug("validateConfig not ok")
                    self._settings.set(["configuration", "old_config"], data["config"])
                    return flask.jsonify(checkConfig="not OK")
                else:
                    self.log_debug("validateConfig ok")
                    self._settings.set(["configuration", "old_config"], "")
                    return flask.jsonify(checkConfig="OK")

    def get_update_information(self):
        return dict(
            klipper=dict(
                displayName=self._plugin_name,
                displayVersion=self._plugin_version,
                type="github_release",
                current=self._plugin_version,
                user="thelastWallE",
                repo="OctoprintKlipperPlugin",
                pip="https://github.com/thelastWallE/OctoprintKlipperPlugin/archive/{target_version}.zip",
                stable_branch=dict(
                    name="Stable",
                    branch="master",
                    comittish=["master"]
                ),
                prerelease_branches=[
                    dict(
                        name="Release Candidate",
                        branch="rc",
                        comittish=["rc", "master"]
                    )]
            )
        )

    #-- Helpers
    def send_message(self, type, subtype, title, payload):
        self._plugin_manager.send_plugin_message(
            self._identifier,
            dict(
                time=datetime.datetime.now().strftime("%H:%M:%S"),
                type=type,
                subtype=subtype,
                title=title,
                payload=payload
            )
        )

    def poll_status(self):
        self._printer.commands("STATUS")

    def update_status(self, type, status):
        self.send_message("status", type, status, status)

    def log_info(self, message):
        self._octoklipper_logger.info(message)
        self.send_message("log", "info", message, message)

    def log_debug(self, message):
        self._octoklipper_logger.debug(message)
        self._logger.info(message)
        # sends a message to frontend(in klipper.js -> self.onDataUpdaterPluginMessage) and write it to the console.
        # _mtype, subtype=debug/info, title of message, message)
        self.send_message("console", "debug", message, message)

    def log_error(self, error):
        self._octoklipper_logger.error(error)
        self._logger.info(error)
        self.send_message("log", "error", error, error)

    def file_exist(self, filepath):
        if not os.path.isfile(filepath):
            self.send_message("PopUp", "warning", "OctoKlipper Settings",
                              "Klipper " + filepath + " does not exist!")
            return False
        else:
            return True

    def key_exist(self, dict, key1, key2):
        try:
            dict[key1][key2]
        except KeyError:
            return False
        else:
            return True

    def validate_configfile(self, dataToBeValidated):
        """
        --->SyntaxCheck for a given data<----
        """

        try:
            dataToValidated = configparser.RawConfigParser(strict=False)
            #
            if sys.version_info[0] < 3:
                buf = StringIO.StringIO(dataToBeValidated)
                dataToValidated.readfp(buf)
            else:
                dataToValidated.read_string(dataToBeValidated)

            sections_search_list = ["bltouch",
                                    "probe"]
            value_search_list = [   "x_offset",
                                    "y_offset",
                                    "z_offset"]
            try:
                # cycle through sections and then values
                for y in sections_search_list:
                    for x in value_search_list:
                        if dataToValidated.has_option(y, x):
                            a_float = dataToValidated.getfloat(y, x)
            except ValueError as error:
                self.log_error(
                    "Error: Invalid Value for <b>"+x+"</b> in Section: <b>"+y+"</b>\n" +
                    "{}".format(str(error))
                )
                self.send_message("PopUp", "warning", "OctoKlipper: Invalid Config\n",
                            "Config got not saved!\n" +
                            "You can reload your last changes\n" +
                            "on the 'Klipper Configuration' tab.\n\n" +
                            "Invalid Value for <b>"+x+"</b> in Section: <b>"+y+"</b>\n" + "{}".format(str(error)))
                self._parsing_check_response = False
                return False
        except configparser.Error as error:
            if sys.version_info[0] < 3:
                error.message = error.message.replace("\\n","")
                error.message = error.message.replace("file: u","Klipper Configuration", 1)
                error.message = error.message.replace("'","", 2)
                error.message = error.message.replace("u'","'", 1)

            else:
                error.message = error.message.replace("\\n","")
                error.message = error.message.replace("file:","Klipper Configuration", 1)
                error.message = error.message.replace("'","", 2)
            self.log_error(
                "Error: Invalid Klipper config file:\n" +
                "{}".format(str(error))
            )
            self.send_message("PopUp", "warning", "OctoKlipper: Invalid Config data\n",
                            "Config got not saved!\n" +
                            "You can reload your last changes\n" +
                            "on the 'Klipper Configuration' tab.\n\n" + str(error))
            self._parsing_check_response = False
            return False
        else:
            self._parsing_check_response = True
            return True

__plugin_name__ = "OctoKlipper"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    global __plugin_hooks__
    __plugin_implementation__ = KlipperPlugin()
    __plugin_hooks__ = {
        "octoprint.access.permissions": __plugin_implementation__.get_additional_permissions,
        "octoprint.comm.protocol.gcode.received": __plugin_implementation__.on_parse_gcode,
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
