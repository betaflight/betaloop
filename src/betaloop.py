import os
import sys
import time
import subprocess
import signal
import atexit
import typing

from .util.sys_util import system_is_macos
from .util.env_util import append_to_env

from .config import BetaloopConfig, BetaloopConfigParser

def betaloop_log(msg: str):
    print(f"[BETALOOP] {msg}")

class Betaloop:
    """Core Betaloop launcher class which starts the simulated environment"""

    def __init__(self, config: BetaloopConfig):
        self.config = config
        self.process_handles: typing.List[subprocess.Popen] = []
        self.shutdown_started = False

        # detect legacy aeroloop gazebo version
        self.aeroloop_legacy = False
        if not os.path.exists(os.path.join(config.aeroloop_path, "build")):
            self.aeroloop_legacy = True

        atexit.register(self._kill_subprocesses)
        signal.signal(signal.SIGTERM, self._kill_subprocesses)
        signal.signal(signal.SIGINT, self._kill_subprocesses)

    def _setup_env(self):
        if self.aeroloop_legacy:
            assets_path = os.path.join(self.config.aeroloop_path)
            lib_path = os.path.join(self.config.aeroloop_path, "plugins", "build")
        else:
            assets_path = os.path.join(self.config.aeroloop_path, "assets")
            lib_path = os.path.join(self.config.aeroloop_path, "build")
        
        append_to_env("SDF_PATH", os.path.join(assets_path, "models"))
        append_to_env("GZ_SIM_RESOURCE_PATH", os.path.join(assets_path, "worlds"))
        append_to_env("GZ_SIM_SYSTEM_PLUGIN_PATH", lib_path)

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
        path = self.config.msp_virtual_radio_path
        if path is None:
            betaloop_log("msp_virtual_radio path missing; skipping startup")
            return
        self._start_subprocess(["node", path])

    def _start_websockify(self):
        """websockify is used to proxy in between the betaflight configurator
        websocket and the TCP socket from betaflight SITL"""

        self._start_subprocess(["websockify", "localhost:6761", "localhost:5761"])
    
    def _verify_gazebo_plugin(self):
        # ensure that the aeroloop gazebo plugin is built
        if self.aeroloop_legacy:
            plugin_dir = os.path.join(self.config.aeroloop_path, "plugins")
            build_dir = os.path.join(plugin_dir, "build")

            if not os.path.exists(build_dir):
                betaloop_log("startup failed, aeroloop_gazebo not built")
                return False
        else:
            build_dir = os.path.join(self.config.aeroloop_path, "build")
            if not os.path.exists(build_dir):
                betaloop_log("startup failed, aeroloop gazebo plugin not built")
                return False
        
        return True
    
    def _verify_msp_virtual_radio(self):
        # check that path to mspvirtualradio is correct
        virtual_radio_path = self.config.msp_virtual_radio_path
        emu_filename = "emu-dx6-msp.js"

        if not virtual_radio_path or not virtual_radio_path.endswith(emu_filename):
            betaloop_log(
                f"startup failed, ensure path provided for MspVirtualRadioHome leads to {emu_filename}"
            )
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
            if not self.config.disable_websockify:
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
            # can use this to do update steps with the plugins if needed
            
            time.sleep(1)

def start_betaloop(config_file_path: str):
    config_parser = BetaloopConfigParser(config_file_path)
    result, err_msg = config_parser.parse()

    if result is None:
        # log failure
        betaloop_log(err_msg)
        betaloop_log("config failed, one or more required fields missing or invalid")

        sys.exit(1)

    betaloop_log("config success, starting")

    betaloop_config = result
    betaloop = Betaloop(betaloop_config)

    betaloop.start()