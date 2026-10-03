#!/bin/sh
# Lance une capture en arrière-plan (exec_command est limité à 15 s).
cd /homeassistant/vision_adb/veille
nohup sh attrape_cameras.sh "$1" > /dev/null 2>&1 &
echo lance
