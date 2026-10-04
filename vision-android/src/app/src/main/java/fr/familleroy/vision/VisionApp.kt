package fr.familleroy.vision

import android.app.Application

/** Charge le dernier état connu dès le démarrage, pour agir même hors ligne. */
class VisionApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Etat.charger(this)
        if (Config(this).inscrit) AgentService.demarrer(this)
    }
}
