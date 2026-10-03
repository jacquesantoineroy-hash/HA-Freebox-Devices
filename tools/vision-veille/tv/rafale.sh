#!/bin/sh
# Lance l'écran de veille, attend N s, puis capture la télé toutes les ~10 s : sh rafale.sh E 125 9
A=/homeassistant/vision_adb/platform-tools/adb
TV=192.168.1.183:5555
$A -s $TV shell am start -n com.android.systemui/.Somnambulator
sleep $2
i=1
while [ $i -le $3 ]; do
  $A -s $TV shell screencap -p /sdcard/v.png
  $A -s $TV pull /sdcard/v.png /homeassistant/www/vision-tv$1$i.png
  echo "$i $(date +%T)" >> /homeassistant/vision_adb/veille/rafale$1.txt
  sleep 8
  i=$((i+1))
done
