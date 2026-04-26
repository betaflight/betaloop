import subprocess
import sys
import os
import configparser
import argparse
import logging
import signal
import time
import typing

DEFAULT_CONFIG_FILE_NAME = "config.txt"

# everything can be registered as a plugin and betaloop will decide the boot order of the plugins I suppose? 
# also remove the need to manually run websockify in a separate terminal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("betaloop")

def get_env_var(name):
    return os.environ[name] if name in os.environ else ""

# config class which is sent to betaloop on startup to actually configure the program

class BetaloopConfig:
    def __init__(
        self,
        aeroloop_path: str,
        world_path: str,
        betaflight_path: str,
        virtual_radio_path: str=None,
        vidrecv_path: str=None,
        show_gazebo: bool=False,
        disable_transmitter: bool=False
    ):
        self.aeroloop_gazebo = aeroloop_path
        self.world_path = world_path
        self.betaflight_path = betaflight_path

        # auxillary plugin paths            
        self.virtual_radio_path = virtual_radio_path
        self.vidrecv_path = vidrecv_path

        # enable / disable options
        self.show_gazebo = show_gazebo
        self.disable_transmitter = disable_transmitter

# ConfigField: used to store information about each config item pertinent to betaloop
class ConfigField:
    def __init__(
        self, 
        name: str,
        required: bool, 
        file_key: str, 
        cli_key: str
    ):
        self.name = name
        self.required = required
        self.file_key = file_key
        self.cli_key = cli_key

    def validate(self, value): raise NotImplementedError()
    def cli_value_invalid_error(self, value): raise NotImplementedError()
    def file_required_value_missing_error(self, filename: str): raise NotImplementedError()
    def file_value_invalid_error(self, value): raise NotImplementedError()
    def get_from_section(self, section: configparser.SectionProxy): raise NotImplementedError()

class PathConfigField(ConfigField):
    def validate(self, path):
        if not isinstance(path, str):
            return None
        if not os.path.exists(path):
            return None
        return path
    
    def cli_value_invalid_error(self, value):
        err = f"error: provided value for {self.cli_key} invalid\n" \
              f"       path: {value} does not exist"
        return err
    
    def file_required_value_missing_error(self, filename: str):
        err = f"error: required field {self.file_key} missing from {filename}\n" \
              f"       please add the missing field as:\n" \
              f"       {self.file_key}=/path/to/{self.name}"
        return err
    
    def file_value_invalid_error(self, value):
        err = f"error: provided value for {self.file_key} invalid\n" \
              f"       path {value} does not exist"
        return err
    
    def get_from_section(self, section: configparser.SectionProxy):
        return section.get(self.file_key)
    
class BoolConfigField(ConfigField):
    def validate(self, v):
        if not isinstance(v, bool):
            return None
        return v
    
    def cli_value_invalid_error(self, value):
        err = f"error: provided value for {self.cli_key} invalid\n" \
              f"       value must be a boolean"
        return err
    
    def file_required_value_missing_error(self, filename: str):
        err = f"error: required field {self.file_key} missing from {filename}\n" \
              f"       please add the missing field as:\n" \
              f"       {self.file_key}=True or {self.file_key}=False depending on desired behavior"
        return err
    
    def file_value_invalid_error(self, value):
        err = f"error: provided value for {self.file_key} invalid\n" \
              "        value must be a boolean (true or false)"
        return err
    
    def get_from_section(self, section: configparser.SectionProxy):
        return section.getboolean(self.file_key)
    
# BLConfigParser reads the configuration file and subsequently outputs a BLConfig object
# if something critical is missing it's logged and the user is informed how to resolve the
# missing element

class BetaloopConfigParser:
    def __init__(self, fpath: str):
        self._fields: typing.List[ConfigField]  = [
            # required fields
            PathConfigField("aeroloop_gazebo", True, "AeroloopGazeboHome", "gazebo_assets"),
            PathConfigField("world_file", True, "World", "world"),
            PathConfigField("betaflight_elf", True, "BetaflightElf", "elf"),

            # optional path fields
            PathConfigField("transmitter", False, "MspVirtualRadioHome", "transmitter"),
            PathConfigField("vidrecv", False, "VidRecv", "vidrecv"),

            # optional boolean fields
            BoolConfigField("show_gazebo", False, "ShowGazebo", "gazebo"),
            BoolConfigField("disable_transmitter", False, "DisableTransmitter", "disable_transmitter")
        ]

        self._config_file_name = os.path.basename(fpath)
        self._config_file_exists = os.path.exists(fpath)

        if self._config_file_exists:
            self._config_file_parser = configparser.ConfigParser()
            self._config_file_parser.read(fpath)

        self._config_cli_parser = argparse.ArgumentParser("Betaloop")
        for field in self._fields:
            cli_arg_str = "--" + field.cli_key.replace("_", "-")
            if isinstance(field, BoolConfigField):
                self._config_cli_parser.add_argument(cli_arg_str, action="store_true", default=None)
            elif isinstance(field, PathConfigField):
                self._config_cli_parser.add_argument(cli_arg_str, type=str)
        self._config_cli_args = self._config_cli_parser.parse_args()

    def parse(self):
        config_values = {}
    
        if self._config_file_exists:
            if not "Betaloop" in self._config_file_parser:
                err = "error: [Betaloop] section missing from config\n" \
                        "        format of config.txt is expected to be\n" \
                        "        [Betaloop]\n" \
                        "         ..."
                logger.error(err)
                return None
            
            config_section = self._config_file_parser["Betaloop"]
        else:
            config_section = None

        # config validation
        for field in self._fields:
            # check against the CLI
            field_from_cli = False
            field_value = getattr(self._config_cli_args, field.cli_key)

            if field_value is not None:
                field_from_cli = True
            elif self._config_file_exists:
                field_value = field.get_from_section(config_section)

                if field_value is None:
                    if field.required:
                        logger.error(field.file_required_value_missing_error(
                            self._config_file_name
                        ))
                        return None
            elif field.required:
                logger.error(f"error: required field {field.name} missing from CLI and config file")
                return None
            
            if field.name == "world_file":
                field_value = os.path.join(config_values["aeroloop_gazebo"], "worlds", field_value)

            if field_value is not None:
                if field.validate(field_value) is None:
                    if field_from_cli:
                        logger.error(field.cli_value_invalid_error(field_value))
                    else:
                        logger.error(field.file_value_invalid_error(field_value))
                    return None
            
            config_values[field.name] = field_value
                    
        return BetaloopConfig(
            aeroloop_path=config_values["aeroloop_gazebo"],
            world_path=config_values["world_file"],
            betaflight_path=config_values["betaflight_elf"],
            virtual_radio_path=config_values["transmitter"],
            vidrecv_path=config_values["vidrecv"],
            show_gazebo=config_values["show_gazebo"],
            disable_transmitter=config_values["disable_transmitter"]
        )

class Betaloop:
    def __init__(self, config: BetaloopConfig):
        self.pids = []
        self.host = "localhost"
        self.gz_port = 11345
        self.config = config

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self._load_gz_env_vars()

    def _load_gz_env_vars(self): 
        ld_library_path = get_env_var("LD_LIBRARY_PATH")
        gz_resource = get_env_var("GZ_SIM_RESOURCE_PATH")
        gz_plugins = get_env_var("GZ_SIM_SYSTEM_PLUGIN_PATH")
        gz_models = get_env_var("SDF_PATH")

        os.environ["GZ_SIM_RESOURCE_PATH"] = "/usr/share/gz/gz-sim8" + os.pathsep + gz_resource
        os.environ["GZ_SIM_SYSTEM_PLUGIN_PATH"] = "/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins" + os.pathsep + gz_plugins
        os.environ["SDF_PATH"] = "/usr/share/gz/gz-sim8/models" + os.pathsep + gz_models
        os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins" + os.pathsep + ld_library_path

        # Now load assets

        models = os.path.join(self.config.aeroloop_gazebo, "models")
        plugins = os.path.join(self.config.aeroloop_gazebo, "plugins", "build")

        os.environ["SDF_PATH"] = "{}:{}".format(models, os.environ["SDF_PATH"])
        os.environ["GZ_SIM_RESOURCE_PATH"] = "{}:{}".format(
            self.config.world_path, 
            os.environ["GZ_SIM_RESOURCE_PATH"]
        )
        os.environ["GZ_SIM_SYSTEM_PLUGIN_PATH"] = "{}:{}".format(plugins, os.environ["GZ_SIM_SYSTEM_PLUGIN_PATH"])

    def _start_subprocess(self, arguments, cwd=None):
        if cwd:
            p = subprocess.Popen(
                arguments,
                shell=False,
                stderr=subprocess.STDOUT,
                cwd=cwd
            )
        else:
            p = subprocess.Popen(
                arguments,
                shell=False,
                stderr=subprocess.STDOUT
            )
        self.pids.append(p.pid)

    def _start_gazebo(self, run_headless: bool):
        args = ["gz", "sim"]

        if not run_headless:
            args.append("-s")  # Server only (headless)

        args.extend(["-r", "-v", "4", self.config.world_path])

        self._start_subprocess(args)
        time.sleep(5)

    def _start_betaflight(self):
        # Need to wait until uart2 is bound so we cna connect our controller to it
        try:
            dir_path = os.path.dirname(self.config.betaflight_path)
            self._start_subprocess([self.config.betaflight_path], cwd=dir_path)
            time.sleep(3)
        except Exception as e:
            logger.error("Timeout starting betaflight")
            sys.exit()

    def _start_video_receiver(self):
        self._start_subprocess([self.config.vidrecv_path])

    def _start_msp_virtual_radio(self):
        self._start_subprocess(["node", self.config.virtual_radio_path])

    def _shutdown(self, sig=None, frame=None):
        """ Kill the gazebo processes based on the original PID  """
        for pid in self.pids:
            p = subprocess.run("kill {}".format(pid), shell=True)
            logger.info("Killed process {}".format(p))
        sys.exit()

    def start(self):
        show_gz_client = self.config.show_gazebo or \
                         self.config.vidrecv_path is None
        
        # Block until connected
        logger.info("Starting Gazebo world...")
        self._start_gazebo(show_gz_client)

        # Now start Betaflight and connect
        logger.info("Starting Betaflight SITL at {}.".format(self.config.betaflight_path))
        self._start_betaflight()

        # Finally we can connect our radio, after FC has started
        disable_transmitter = self.config.disable_transmitter or \
                              self.config.virtual_radio_path is None
        
        if not disable_transmitter:
            logger.info("Starting the transmitter...")
            self._start_msp_virtual_radio()
        
        if not show_gz_client:
            logger.info("Starting video receiver {}".format(self.config.vidrecv_path))
            self._start_video_receiver()

        # Keep it up so we can kill with ctrl + c
        while True: time.sleep(1)

def start_betaloop():
    betaloop_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(betaloop_dir, DEFAULT_CONFIG_FILE_NAME)

    config_parser = BetaloopConfigParser(config_file_path)
    result = config_parser.parse()

    if result is None:
        logger.error("Betaloop startup failure: one or more required fields missing or invalid")
    else:
        logger.info("configuration successfully parsed, starting betaloop")

        betaloop_config = result
        betaloop = Betaloop(betaloop_config)

        betaloop.start()

if __name__ == "__main__":
    start_betaloop()
