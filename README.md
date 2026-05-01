# Betaloop

Betaloop is a simulation launcher that creates an environment for evaluation of the Betaflight SITL target. Betaloop uses Gazebo Harmonic as the physics simulation environment which is used to provide sensor data to the Betaflight SITL instance which is created by this launcher as well.

# Prerequisites

* git
* python 3.7+
* CMake 3.10.2+
* Gazebo Harmonic
* betaflight cloned locally

# Setup Guide

This setup guide 

1. clone this repository `git clone https://github.com/betaflight/betaloop`
2. 



// TODO : add cross platform note
// TODO : add dependencies notes

# Features

1. Uses real flight control firmware (Betaflight)  
2. Supports first person view (FPV) flight
3. Use your own radio controller!  

# Requirements



1. Gazebo 8 
2. [Aeroloop Gazebo resources](https://github.com/Aeroloop/aeroloop_gazebo)
2. [Betaflight](https://github.com/betaflight/betaflight) [compiled for
   SITL](https://github.com/betaflight/betaflight/tree/master/src/main/target/SITL)
3. Python3
4. [VidRecv](https://github.com/Aeroloop/vidrecv)
5. [MSP virtual radio](https://github.com/Aeroloop/msp_virtualradio) 

# Instructions
For required software part of Aeroloop make sure to follow the install
instructions specified by their respective README file.
For ease of use, add your arguments to config.txt, if needed these can be
overridden by command line arguments. 

Run the script to start the simulator,
```
python3 start.py
```

# Notes
When Betaflight is started a .bin is created and the configuration settings are
saved here. This is saved in the *current* directory. Be careful as this can
currently cause a .bin to be overwritten if testing multiple builds.
