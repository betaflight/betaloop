import os
import argparse
import configparser
import typing

from dataclasses import dataclass

@dataclass
class BetaloopConfig:
    """Config class used to store all of the Betaloop arguments
       after being parsed by BetaloopConfigParser"""
    
    # core paths
    aeroloop_path: str
    world_path: str
    betaflight_elf_path: str

    # auxiliary paths
    msp_virtual_radio_path: typing.Optional[str]
    
    # launch settings
    show_gazebo: typing.Optional[bool]
    disable_msp_virtual_radio: typing.Optional[bool]
    disable_websockify: typing.Optional[bool]
    verbose: typing.Optional[bool]

class _ConfigField:
    """Configuration Field to hold information regarding each of the simulators
       arguments. Also used to enforce required arguments that are non-negotiable
       paths / values that are needed to setup the simulation environment"""
    
    def __init__(self, name: str, required: bool, file_key: str, cli_key: str):
        self.name = name
        self.required = required
        self.file_key = file_key
        self.cli_key = cli_key

    def validate(self, value) -> bool: 
        raise NotImplementedError()
    
    def cli_value_invalid_err(self, value): 
        raise NotImplementedError()
    
    def file_required_value_missing_err(self, filename: str): 
        raise NotImplementedError()
    
    def file_value_invalid_err(self, value): 
        raise NotImplementedError()
    
    def get_from_section(self, section: configparser.SectionProxy):
        raise NotImplementedError()
    
    def register_cli_argument(self, argparser: argparse.ArgumentParser): 
        raise NotImplementedError()

    def _get_cli_cmd_str(self) -> str:
        return "--" + self.cli_key.replace("_", "-")

class FilePathConfigField(_ConfigField):
    """Configuration Field for defining a path to some resource"""

    def validate(self, value) -> bool:
        if value is None:
            return False
        if not isinstance(value, str):
            return False
        return os.path.isfile(value)
    
    def cli_value_invalid_err(self, value):
        err = f"provided value for {self.cli_key} invalid\n" \
              f"-> file: {value} does not exist"
        return err
    
    def file_required_value_missing_err(self, filename: str):
        err = f"required field {self.file_key} missing from ({filename})\n" \
              f"-> please add the missing field as {self.file_key}=/path/to/{self.name}"
        return err
    
    def file_value_invalid_err(self, value):
        err = f"provided value for {self.file_key} invalid\n" \
              f"-> file {value} does not exist"
        return err
    
    def get_from_section(self, section: configparser.SectionProxy):
        return section.get(self.file_key)

    def register_cli_argument(self, argparser: argparse.ArgumentParser):
        argparser.add_argument(self._get_cli_cmd_str(), type=str)

class DirectoryPathConfigField(_ConfigField):
    def validate(self, value) -> bool:
        if value is None:
            return False
        if not isinstance(value, str):
            return False
        return os.path.isdir(value)

    def cli_value_invalid_err(self, value):
        err = f"provided value for {self.cli_key} invalid\n" \
              f"-> directory: {value} does not exist"
        return err

    def file_required_value_missing_err(self, filename: str):
        err = f"required field {self.file_key} missing from ({filename})\n" \
              f"-> please add the missing field as {self.file_key}=/path/to/{self.name}"
        return err

    def file_value_invalid_err(self, value):
        err = f"provided value for {self.file_key} invalid\n" \
              f"-> directory {value} does not exist"
        return err
    
    def get_from_section(self, section: configparser.SectionProxy):
        return section.get(self.file_key)

    def register_cli_argument(self, argparser: argparse.ArgumentParser):
        argparser.add_argument(self._get_cli_cmd_str(), type=str)

class BoolConfigField(_ConfigField):
    """Configuation Field for enabling disabling specific behaviors
        i.e. if Gazebo UI runs headless"""
    
    def validate(self, value):
        if value is None:
            return False
        return isinstance(value, bool)
    
    def cli_value_invalid_err(self, value):
        err = f"provided value for {self.cli_key} invalid, value must be a boolean"
        return err
    
    def file_required_value_missing_err(self, filename: str):
        err = f"required field {self.file_key} missing from {filename}\n" \
              f"-> please add the missing field as:\n" \
              f"   {self.file_key}=True or {self.file_key}=False depending on desired behavior"
        return err
    
    def file_value_invalid_err(self, value=None):
        err = f"provided value for {self.file_key} invalid\n" \
                "-> value must be a boolean (true or false)"
        return err
    
    def get_from_section(self, section: configparser.SectionProxy):
        return section.getboolean(self.file_key)
    
    def register_cli_argument(self, argparser: argparse.ArgumentParser):
        argparser.add_argument(self._get_cli_cmd_str(), action="store_true", default=None)

class BetaloopConfigParser:
    """Configuration Parser class used for coalescing config input from both config file
       (if it exists) and/or from the cli arguments passed when running the python script
       additionally in the case of misconfigurations it provides user with hints 
       to help them resolve the issue"""
    
    def __init__(self, fpath: str):
        # store list of configuration fields

        self._fields: typing.List[_ConfigField]  = [
            # required fields
            DirectoryPathConfigField("aeroloop_path", True, "AeroloopGazeboHome", "gazebo_assets"),
            FilePathConfigField("world_file", True, "World", "world"),
            FilePathConfigField("betaflight_elf", True, "BetaflightElf", "elf"),

            # optional path fields
            FilePathConfigField("transmitter", False, "MspVirtualRadioHome", "transmitter"),

            # optional boolean fields
            BoolConfigField("show_gazebo", False, "ShowGazebo", "gazebo"),
            BoolConfigField("disable_transmitter", False, "DisableTransmitter", "disable_transmitter"),
            BoolConfigField("disable_websockify", False, "DisableWebsockify", "disable_websockify"),
            BoolConfigField("verbose", False, "Verbose", "verbose"),
        ]

        # setup file parser
        
        self._config_file_name = os.path.basename(fpath)
        self._config_file_exists = os.path.exists(fpath)

        if self._config_file_exists:
            self._config_file_parser = configparser.ConfigParser()
            self._config_file_parser.read(fpath)
        else:
            self._config_file_parser = None

        # setup CLI parser

        self._config_cli_parser = argparse.ArgumentParser("Betaloop")

        for field in self._fields:
            field.register_cli_argument(self._config_cli_parser)

        self._config_cli_args = self._config_cli_parser.parse_args()

    def parse(self):
        config_values = {}
    
        if self._config_file_exists:
            if "Betaloop" not in self._config_file_parser:
                err_msg = "section missing from config.txt\n" \
                        "-> format of config.txt is expected to be\n" \
                        "[Betaloop]\n..."
                return None, err_msg
            
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
                try:
                    value = field.get_from_section(config_section)
                except ValueError:
                    # only way this raises is if its a boolean
                    err_msg = field.file_value_invalid_err()
                    return None, err_msg
                
                if field.required:
                    if value is None:
                        # log error that the value could not be found in the file
                        err_msg = field.file_required_value_missing_err(
                            filename=self._config_file_name)
                        
                        return None, err_msg
                
            elif field.required:
                # required field that wasn't found in CLI or the config file
                err_msg = f"required field {field.name} missing"
                return None, err_msg

            # world value is the only field that is specfically a filename and is dependent on
            # gazebo_assets

            # note: don't want to break existing configs so this functionality is here
            
            if field.name == "world_file":
                if value is not None and not os.path.isabs(value):
                    aeroloop_path = config_values["aeroloop_path"]

                    # check for worlds using the legacy path initially
                    world_path = os.path.join(aeroloop_path, "worlds")
                    
                    if not os.path.exists(world_path):
                        world_path = os.path.join(aeroloop_path, "assets", "worlds")
                    
                    value = os.path.join(world_path, value)
            
            if value is not None:
                if not field.validate(value):
                    if value_from_cli:
                        err_msg = field.cli_value_invalid_err(value)
                    else:
                        err_msg = field.file_value_invalid_err(value)
                    return None, err_msg

            config_values[field.name] = value

        betaloop_config = BetaloopConfig(
            # required
            aeroloop_path=config_values["aeroloop_path"],
            world_path=config_values["world_file"],
            betaflight_elf_path=config_values["betaflight_elf"],

            # optional paths
            msp_virtual_radio_path=config_values["transmitter"],

            # optional booleans
            show_gazebo=config_values["show_gazebo"],
            disable_msp_virtual_radio=config_values["disable_transmitter"],
            disable_websockify=config_values["disable_websockify"],
            verbose=config_values["verbose"]
        )
                    
        return betaloop_config, ""
    