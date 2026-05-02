import os
import sys
import time
import subprocess
import argparse
import configparser
import signal
import atexit
import typing

from dataclasses import dataclass

DEFAULT_CONFIG_FILE_NAME = "config.txt"

def system_is_macos():
    return sys.platform == "darwin"

def betaloop_log(msg: str):
    print(f"[BETALOOP] {msg}")

@dataclass
class BetaloopConfig:
    """Config class used to store all of the Betaloop arguments
       after being parsed by BetaloopConfigParser"""
    
    # core paths
    aeroloop_path: str
    world_path: str
    betaflight_elf_path: str

    # auxiliary paths
    msp_virtual_radio_path: str
    
    # launch settings
    show_gazebo: typing.Optional[bool]
    disable_msp_virtual_radio: typing.Optional[bool]

class ConfigField:
    """Configuration Field to hold information regarding each of the simulators
       arguments. Also used to enforce required arguments that are non-negotiable
       paths / values that are needed to setup the simulation environment"""
    
    def __init__(self, name: str, required: bool, file_key: str, cli_key: str):
        self.name = name
        self.required = required
        self.file_key = file_key
        self.cli_key = cli_key

    def validate(self, value) -> bool: raise NotImplementedError()
    def cli_value_invalid_error(self, value): raise NotImplementedError()
    def file_required_value_missing_error(self, filename: str): raise NotImplementedError()
    def file_value_invalid_error(self, value): raise NotImplementedError()
    def get_from_section(self, section: configparser.SectionProxy): raise NotImplementedError()
    def register_cli_argument(self, argparser: argparse.ArgumentParser): raise NotImplementedError()

    def _get_cli_cmd_str(self) -> str:
        return "--" + self.cli_key.replace("_", "-")

class PathConfigField(ConfigField):
    """Configuration Field for defining a path to some resource"""

    def validate(self, value) -> bool:
        if value is None:
            return False
        if not isinstance(value, str):
            return False
        return os.path.exists(value)
    
    def cli_value_invalid_error(self, value):
        err = f"provided value for {self.cli_key} invalid\n" \
              f"-> path: {value} does not exist"
        return err
    
    def file_required_value_missing_error(self, filename: str):
        err = f"required field {self.file_key} missing from ({filename})\n" \
              f"-> please add the missing field as {self.file_key}=/path/to/{self.name}"
        return err
    
    def file_value_invalid_error(self, value):
        err = f"provided value for {self.file_key} invalid\n" \
              f"-> path {value} does not exist"
        return err
    
    def get_from_section(self, section: configparser.SectionProxy):
        return section.get(self.file_key)

    def register_cli_argument(self, argparser: argparse.ArgumentParser):
        argparser.add_argument(self._get_cli_cmd_str(), type=str)
        
class BoolConfigField(ConfigField):
    """Configuation Field for enabling disabling specific behaviors
        i.e. if Gazebo UI runs headless"""
    
    def validate(self, value):
        if value is None:
            return False
        return isinstance(value, bool)
    
    def cli_value_invalid_error(self, value):
        err = f"provided value for {self.cli_key} invalid, value must be a boolean"
        return err
    
    def file_required_value_missing_error(self, filename: str):
        err = f"required field {self.file_key} missing from {filename}\n" \
              f"-> please add the missing field as:\n" \
              f"   {self.file_key}=True or {self.file_key}=False depending on desired behavior"
        return err
    
    def file_value_invalid_error(self, value):
        err = f"provided value for {self.file_key} invalid\n" \
                "-> value must be a boolean (true or false)"
        return err
    
    def get_from_section(self, section: configparser.SectionProxy):
        try:
            return section.getboolean(self.file_key)
        except ValueError as e:
            # getboolean may return a value error if the provided value is not
            # within the list of acceptable "boolean" values
            return None
    
    def register_cli_argument(self, argparser: argparse.ArgumentParser):
        argparser.add_argument(self._get_cli_cmd_str(), action="store_true", default=None)

class BetaloopConfigParser:
    """Configuration Parser class used for coalescing config input from both config file
       (if it exists) and/or from the cli arguments passed when running the python script
       additionally in the case of misconfigurations it provides user with hints 
       to help them resolve the issue"""
    
    def __init__(self, fpath: str):
        # store list of configuration fields

        self._fields: typing.List[ConfigField]  = [
            # required fields
            PathConfigField("aeroloop_path", True, "AeroloopGazeboHome", "gazebo_assets"),
            PathConfigField("world_file", True, "World", "world"),
            PathConfigField("betaflight_elf", True, "BetaflightElf", "elf"),

            # optional path fields
            PathConfigField("transmitter", False, "MspVirtualRadioHome", "transmitter"),

            # optional boolean fields
            BoolConfigField("show_gazebo", False, "ShowGazebo", "gazebo"),
            BoolConfigField("disable_transmitter", False, "DisableTransmitter", "disable_transmitter")
        ]

        self._config_file_name = os.path.basename(fpath)
        self._config_file_exists = os.path.exists(fpath)

        if self._config_file_exists:
            self._config_file_parser = configparser.ConfigParser()
            self._config_file_parser.read(fpath)

        # setup CLI 

        self._config_cli_parser = argparse.ArgumentParser("Betaloop")

        for field in self._fields:
            field.register_cli_argument(self._config_cli_parser)

        self._config_cli_args = self._config_cli_parser.parse_args()

    def parse(self):
        config_values = {}
    
        if self._config_file_exists:
            if "Betaloop" not in self._config_file_parser:
                err = "section missing from config.txt\n" \
                        "-> format of config.txt is expected to be\n" \
                        "[Betaloop]\n..."
                betaloop_log(err)
                return None
            
            config_section = self._config_file_parser["Betaloop"]
        else:
            config_section = None

        # config validation
        for field in self._fields:
            value_from_cli = False
            value = getattr(self._config_cli_args, field.cli_key)

            if value is not None:
                # value sourced from CLI
                value_from_cli = True

            elif config_section is not None:
                # try to source value from config file
                value = field.get_from_section(config_section)
                if field.required:
                    if value is None:
                        # log error that the value could not be found in the file
                        err_msg = field.file_required_value_missing_error(self._config_file_name)
                        betaloop_log(err_msg)
                        return None
                
            elif field.required:
                # required field that wasn't found in CLI or the config file
                betaloop_log(f"required field {field.name} missing")
                return None
            
            # world value is the only field that is specfically a filename and is dependent on
            # gazebo_assets

            # note: don't want to break existing configs so this functionality is here
            
            if field.name == "world_file":
                value = os.path.join(config_values["aeroloop_path"], "worlds", value)
            
            if value is not None:
                if not field.validate(value):
                    if value_from_cli:
                        betaloop_log(field.cli_value_invalid_error(value))
                    else:
                        betaloop_log(field.file_value_invalid_error(value))
                    return None
            
            config_values[field.name] = value
                    
        return BetaloopConfig(
            config_values["aeroloop_path"],
            config_values["world_file"],
            config_values["betaflight_elf"],
            config_values["transmitter"],
            config_values["show_gazebo"],
            config_values["disable_transmitter"]
        )

class Betaloop:
    """Core Betaloop launcher class which starts the simulated environment"""

    def __init__(self, config: BetaloopConfig):
        self.config = config
        self.process_handles: typing.List[subprocess.Popen] = []
        self.shutdown_started = False

        atexit.register(self._kill_subprocesses)
        signal.signal(signal.SIGTERM, self._kill_subprocesses)
        signal.signal(signal.SIGINT, self._kill_subprocesses)

    def _append_to_env(self, env_key: str, value: str):
        env = os.environ.get(env_key, "")
        if not env:
            os.environ[env_key] = value
        else:
            os.environ[env_key] += os.pathsep + value

    def _setup_env(self): 
        models_dir = os.path.join(self.config.aeroloop_path, "models")
        worlds_dir = os.path.join(self.config.aeroloop_path, "worlds")
        plugins_dir = os.path.join(self.config.aeroloop_path, "plugins", "build")

        self._append_to_env("SDF_PATH", models_dir)
        self._append_to_env("GZ_SIM_RESOURCE_PATH", worlds_dir)
        self._append_to_env("GZ_SIM_SYSTEM_PLUGIN_PATH", plugins_dir)

    # subprocess management

    def _start_subprocess(self, arguments, cwd=None):
        """spawns subprocess and adds its handle to the list"""
        proc = subprocess.Popen(
            arguments,
            shell=False,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            start_new_session=True
        )
        self.process_handles.append(proc)

    def _kill_subprocesses(self, sig=None, frame=None):
        if not self.shutdown_started:
            self.shutdown_started = True
            
            for proc in self.process_handles:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass  # already dead

            deadline = time.time() + 5
            alive = list(self.process_handles)
            while alive and time.time() < deadline:
                alive = [p for p in alive if p.poll() is None]
                time.sleep(0.1)

            for proc in alive:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # already dead

            if sig is not None:
                sys.exit(0)
            
    
    # Betaloop subprocess startup

    def _start_gazebo(self):
        args_base = ["gz", "sim"]

        # start the server (default behavior)
        if system_is_macos():
            # run the gazebo server
            args_server = args_base + ["-s", "-r", "-v", "4", self.config.world_path]
            self._start_subprocess(args_server)

            if self.config.show_gazebo:
                # start viewport
                args_gui = args_base + ["-g"]
                self._start_subprocess(args_gui)
        else:
            args_gz = args_base.copy()

            if not self.config.show_gazebo:
                args_gz.append("-s")

            args_gz += ["-r", "-v", "4", self.config.world_path]
            self._start_subprocess(args_gz)

        time.sleep(5)

    def _start_betaflight(self):
        dir_path = os.path.dirname(self.config.betaflight_elf_path)
        self._start_subprocess([self.config.betaflight_elf_path], cwd=dir_path)
        time.sleep(3)

    def _start_msp_virtual_radio(self):
        self._start_subprocess(["node", self.config.msp_virtual_radio_path])

    def _start_websockify(self):
        """websockify is used to proxy in between the betaflight configurator
        websocket and the TCP socket from betaflight SITL"""

        self._start_subprocess(["websockify", "localhost:6761", "localhost:5761"])
    
    def _verify_gazebo_plugin(self):
        # ensure that the aeroloop gazebo plugin is built
        plugin_dir = os.path.join(self.config.aeroloop_path, "plugins")
        build_dir = os.path.join(plugin_dir, "build")

        if not os.path.exists(build_dir):
            betaloop_log("startup failed, aeroloop_gazebo not built")
            return False
        
        
        return True
    
    def _verify_msp_virtual_radio(self):
        # check that path to mspvirtualradio is correct
        virtual_radio_path = self.config.msp_virtual_radio_path
        emu_radio_filename = "emu-dx6-msp.js"

        if not virtual_radio_path.endswith(emu_radio_filename):
            betaloop_log(f"startup failed, ensure path provided for MspVirtualRadioHome leads to {emu_radio_filename}")
            return False
        
        return True

    def start(self):
        if not self._verify_gazebo_plugin():
            sys.exit(1)
        # verify virtual radio
        disable_transmitter = self.config.disable_msp_virtual_radio or \
                            self.config.msp_virtual_radio_path is None
        if not disable_transmitter:
            if not self._verify_msp_virtual_radio():
                sys.exit(1)

        self._setup_env()
               
        try:
            # Block until connected
            betaloop_log("starting gazebo")
            self._start_gazebo()

            # start websockify
            betaloop_log("starting websockify proxy")
            self._start_websockify()

            # starting betaflight SITL
            betaloop_log(f"starting Betaflight SITL at {self.config.betaflight_elf_path}")
            self._start_betaflight()

            if not disable_transmitter:
                # startup MSP virtual radio
                betaloop_log("starting msp_virtual_radio")
                self._start_msp_virtual_radio()
        except Exception as e:
            betaloop_log(f"startup failed with {e}")
            self._kill_subprocesses()
            sys.exit(1)

        # Keep it up so we can kill with ctrl + c
        while True:
            time.sleep(1)

def start_betaloop():
    betaloop_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(betaloop_dir, DEFAULT_CONFIG_FILE_NAME)

    config_parser = BetaloopConfigParser(config_file_path)
    result = config_parser.parse()

    if result is None:
        betaloop_log("config failed, one or more required fields missing or invalid")
        sys.exit(1)

    betaloop_log("config success, starting")

    betaloop_config = result
    betaloop = Betaloop(betaloop_config)

    betaloop.start()

if __name__ == "__main__":
    start_betaloop()
