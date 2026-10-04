package fr.familleroy.vision

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Relance l'agent au démarrage de l'appareil et après une mise à jour de Vision. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, i: Intent) {
        if (i.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            MiseAJour.notifier(ctx, "Vision mise à jour",
                "Version ${BuildConfigCompat.version(ctx)} installée. Tout est conservé.", null)
        }
        if (Config(ctx).inscrit) {
            Etat.charger(ctx)
            AgentService.demarrer(ctx)
        }
    }
}
