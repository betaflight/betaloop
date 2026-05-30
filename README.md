# Betaloop

Betaloop is a simulation launcher that creates an environment for evaluation of the Betaflight SITL target

## Simulation Environment

The simulated environment runs in Gazebo Harmonic and interfaces with Betaflight SITL through the aeroloop gazebo plugin. Additionally this launcher provides the ability to
use an RC transmitter with a USB Joystick to control the simulated drone through an additional plugin.

## Supported Platforms

This launcher has native support and has been tested with Ubuntu Linux and MacOS. Windows is only supported through WSL2. 

## Prerequisites

* git
* python 3.7+
* Betaflight cloned locally + required build toolchain
* websockify (install `pip install websockify`)
* [aeroloop_gazebo]((https://github.com/betaflight/aeroloop_gazebo/tree/gz)) cloned locally and built.

## Setup Guide

* build Betaflight SITL target
* build the aeroloop_gazebo plugin

## Optional Setup

* MSP Virtual Radio (https://github.com/Aeroloop/msp_virtualradio)

   MSP Virtual Radio can be used to provide joystick input to the simulated drone.
   Compatibility with it has been maintained in the current version of Betaloop to maintain parity with existing setups. Given that active development has seemed to cease on the project a plugin `betaloop_joystick` is planned to succeed it

## Usage

Betaloop can be configured through a combination of either a configuration file or CLI arguments provided when running `start.py`. Fields provided as CLI arguments override their counterparts in the configuration file.

config file should follow the format provided in `config.template.txt` and be named `config.txt`

### Required Config

   * Path to aeroloop_gazebo
      * CLI : `--gazebo_assets /path/to/aeroloop_gazebo`
      * Config : `AeroloopGazeboHome=/path/to/aeroloop_gazebo`
   
   * World file name
      * specify the base filename of the Gazebo world (found in the aeroloop_gazebo worlds directory) to load that world; future releases may accept external world files.

      * CLI : `--world world.sdf`
      * Config : `World=world.sdf`
   
   * Path to Betaflight SITL elf
      * CLI : `--elf /path/to/betaflightelf`
      * Config : `BetaflightElf=/path/to/betaflightelf`
   
### Optional Config

   * Path to MSP Virtual Radio
      * CLI : `--transmitter /path/to/mspvirtualradio`
      * Config : `MSPVirtualRadioHome=/path/to/mspvirtualradio`
   
   * Option to enable Gazebo GUI
      * CLI : `--gazebo`
      * Config : `ShowGazebo=true` or `ShowGazebo=false`
   
   * Option to disable transmitter input
      * CLI : `--disable-transmitter`
      * Config : `DisableTransmitter=true` or `DisableTransmitter=false`

   * Option to disable websockify
      * CLI: `--disable-websockify`
      * Config : `DisableWebsockify=true` or `DisableWebsockify=false`

## Acknowledgements

This repository is derived from the original [Betaloop](https://github.com/Aeroloop/betaloop) and builds on the work of [wil3](https://github.com/wil3). Thanks to Will for his work in initially creating this tool.