#!/bin/sh
# Installe l'APK sur un appareil ADB avec reprises, repose les droits, (re)choisit l'écran de veille
# et, si demandé, met Vision en accueil : sh deployer_tv.sh /chemin/vision.apk 192.168.1.183:5555 [accueil]
A=/homeassistant/vision_adb/platform-tools/adb
APK=$1
TV=$2
LOG=/homeassistant/vision_adb/veille/deploiement_$(echo $TV | tr ':.' '__').log
echo "debut $(date +%T)" > $LOG
i=1
while [ $i -le 4 ]; do
  $A -s $TV install -r $APK >> $LOG 2>&1
  if grep -q Success $LOG; then break; fi
  sleep 4
  i=$((i+1))
done
$A -s $TV shell dpm set-active-admin fr.familleroy.vision/.AdminReceiver >> $LOG 2>&1
$A -s $TV shell appops set fr.familleroy.vision REQUEST_INSTALL_PACKAGES allow >> $LOG 2>&1
$A -s $TV shell pm grant fr.familleroy.vision android.permission.POST_NOTIFICATIONS >> $LOG 2>&1
$A -s $TV shell settings put secure enabled_accessibility_services fr.familleroy.vision/fr.familleroy.vision.VisionAccessibility >> $LOG 2>&1
$A -s $TV shell settings put secure accessibility_enabled 1 >> $LOG 2>&1
# Voir ce qui joue (cast lancé d'un téléphone) : les télés n'ont pas toujours l'écran de réglage correspondant.
$A -s $TV shell cmd notification allow_listener fr.familleroy.vision/fr.familleroy.vision.EcouteFlux >> $LOG 2>&1
$A -s $TV shell settings put secure screensaver_enabled 1 >> $LOG 2>&1
$A -s $TV shell settings put secure screensaver_components fr.familleroy.vision/.VeilleService >> $LOG 2>&1
if [ "$3" = "accueil" ]; then
  $A -s $TV shell cmd package set-home-activity fr.familleroy.vision/.LanceurActivity >> $LOG 2>&1
  $A -s $TV shell am start -a android.intent.action.MAIN -c android.intent.category.HOME >> $LOG 2>&1
fi
$A -s $TV shell dumpsys package fr.familleroy.vision | grep versionName >> $LOG 2>&1
echo "fin $(date +%T)" >> $LOG
