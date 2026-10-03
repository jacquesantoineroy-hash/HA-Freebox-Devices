#!/bin/sh
# Attend que l'écran de veille ouvre les caméras, puis capture la télé 25 s plus tard.
A=/homeassistant/vision_adb/platform-tools/adb
TV=192.168.1.183:5555
NOM=$1
$A -s $TV shell logcat -c
i=0
while [ $i -lt 60 ]; do
  n=$($A -s $TV shell logcat -d -t 500 | grep -c 'ExoPlayerImpl: Init')
  if [ "$n" -gt 0 ]; then break; fi
  sleep 4; i=$((i+1))
done
sleep 25
$A -s $TV shell screencap -p /sdcard/v.png
$A -s $TV pull /sdcard/v.png /homeassistant/www/$NOM.png
echo "<html><body style='margin:0;background:#222'><img src='$NOM.png' style='width:100vw'></body></html>" > /homeassistant/www/$NOM.html
$A -s $TV shell logcat -d | grep -E 'ExoPlayerImpl|Playback error|Caused by|SoftVideo|MediaCodecVideoRenderer' | grep -v '    at' | tail -40 > /homeassistant/vision_adb/veille/$NOM.log
$A -s $TV shell top -n 1 -m 4 -b 2>/dev/null | tail -6 >> /homeassistant/vision_adb/veille/$NOM.log
echo fini >> /homeassistant/vision_adb/veille/$NOM.log
