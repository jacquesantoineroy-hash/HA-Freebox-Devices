package fr.familleroy.vision

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import org.json.JSONArray
import org.json.JSONObject

/**
 * Le battement de l'agent : il se présente à Home Assistant, dit ce qu'il voit,
 * reçoit ce qu'il doit appliquer. Tourne en service de premier plan, avec une
 * notification visible en permanence (exigée par Android, et de toute façon
 * voulue : Vision ne se cache pas).
 */
class AgentService : Service() {

    private lateinit var fil: HandlerThread
    private lateinit var h: Handler
    private val principal = Handler(android.os.Looper.getMainLooper())
    /** Dernier envoi de l'inventaire des applis installées (0 = jamais depuis le démarrage). */
    @Volatile private var dernierInventaire = 0L

    private val battement = object : Runnable {
        override fun run() {
            val attente = try { interroger() } catch (_: Exception) { 60 }
            surveillerPremierPlan()
            h.postDelayed(this, attente.toLong() * 1000)
        }
    }

    override fun onCreate() {
        super.onCreate()
        fil = HandlerThread("vision-agent").apply { start() }
        h = Handler(fil.looper)
        demarrerPremierPlan()
        Bulle.verifier(this)
        VerrouActivity.ecouter(this)
    }

    override fun onStartCommand(i: Intent?, flags: Int, id: Int): Int {
        h.removeCallbacks(battement)
        h.post(battement)
        return START_STICKY
    }

    override fun onDestroy() {
        h.removeCallbacks(battement)
        fil.quitSafely()
        // Android a tué le service : on demande à être relancé.
        if (Config(this).inscrit) demarrer(this)
        super.onDestroy()
    }

    override fun onBind(i: Intent?): IBinder? = null

    // --------------------------------------------------------- Le cycle

    private fun interroger(): Int {
        val cfg = Config(this)
        if (!cfg.inscrit) {
            if (!inscrire(cfg)) return 60
        }
        val corps = rapport(cfg)
        val r = try {
            Net.post(this, cfg, "/api/pc_parental/poll", corps)
        } catch (e: Net.Echec) {
            // Secret refusé : l'appareil a été retiré de HA, on repart de zéro.
            if (e.code == 401) { cfg.oublierInscription() }
            majNotification()
            return 30
        } catch (_: Exception) {
            majNotification()
            return 30
        }

        when (r.optString("action")) {
            "uninstall" -> { seDesinscrire(cfg); return 300 }
        }
        Etat.appliquer(r, cfg)
        if (cfg.personneAEnvoyer) cfg.personneAEnvoyer = false
        synchroniserListeNoire(cfg, r.optString("liste_noire", ""))
        appliquerConsignesVpn()
        Messages.afficher(this, r.optJSONArray("notify"))
        // Préavis : « le PC se verrouille à 21h00 » et plages d'étiquettes.
        Messages.preavis(this,
            if (r.optInt("warn", 0) > 0) r.optString("message", "") else "",
            r.optJSONArray("avertissements"))
        traiterMiseAJour(cfg, r.optJSONObject("update"))
        majNotification()

        // Si une appli bloquée est déjà au premier plan, on la recouvre tout de suite.
        Usage.dernierPaquet.takeIf { it.isNotEmpty() }?.let { pkg ->
            Etat.doitBloquer(this, pkg)?.let { raison ->
                principal.post { BlockActivity.afficher(this, raison, pkg) }
            }
        }
        return Etat.poll
    }

    private fun inscrire(cfg: Config): Boolean {
        if (cfg.cleInscription.isEmpty()) return false
        val corps = JSONObject().apply {
            put("key", cfg.cleInscription)
            put("host", appareil())
            put("user", cfg.utilisateur)
            put("platform", "android")
        }
        return try {
            val r = Net.post(this, cfg, "/api/pc_parental/enroll", corps)
            if (r.optBoolean("ok")) {
                cfg.id = r.optString("id")
                cfg.secret = r.optString("secret")
                cfg.nom = r.optString("name")
                cfg.host = appareil()
                r.optJSONArray("personnes")?.let { cfg.personnes = it.toString() }
                true
            } else false
        } catch (_: Exception) { false }
    }

    /** Ce que l'agent remonte : qui, état, ce qu'il a vu, et l'état de ses protections. */
    private fun rapport(cfg: Config): JSONObject {
        val sites = JSONArray().also { a -> synchronized(Etat.sitesVus) {
            Etat.sitesVus.forEach { a.put(it) }; Etat.sitesVus.clear() } }
        val alertes = JSONArray().also { a -> synchronized(Etat.alertes) {
            Etat.alertes.forEach { a.put(JSONObject().put("domaine", it).put("source", "vpn")) }
            Etat.alertes.clear() } }
        val listeOuvertes = Usage.ouvertes(this, 90_000)
        val ouvertes = JSONArray().also { a -> listeOuvertes.forEach { a.put(it) } }
        val maintenant = System.currentTimeMillis()

        return JSONObject().apply {
            put("id", cfg.id)
            put("secret", cfg.secret)
            put("platform", "android")
            put("version", BuildConfigCompat.version(this@AgentService))
            put("host", cfg.host.ifEmpty { appareil() })
            put("user", cfg.utilisateur)
            put("locked", Etat.verrouilleEffectif())
            put("focus", Usage.dernierPaquet)
            put("idle_seconds", Usage.inactifSecondes(this@AgentService))
            put("apps_ouverts", ouvertes)
            put("sites_vus", sites)
            put("alertes", alertes)
            // Noms affichés des applis citées (le catalogue montre « YouTube »).
            put("apps_libelles", JSONObject(Usage.libelles(this@AgentService,
                listeOuvertes.plus(Usage.dernierPaquet))))
            // Inventaire complet au démarrage, puis une fois par heure.
            if (maintenant - dernierInventaire > 3_600_000L) {
                val inv = JSONArray()
                Usage.inventaire(this@AgentService).forEach { (p, l) ->
                    inv.put(JSONObject().put("pkg", p).put("label", l))
                }
                put("apps_installees", inv)
                dernierInventaire = maintenant
            }
            // L'état des protections : HA peut ainsi afficher « Agent injoignable »
            // au sens fort, et prévenir si une protection a été coupée.
            put("protections", protections())
            // Demande de temps faite par l'enfant depuis l'écran de blocage.
            val mins = cfg.demandeTemps
            if (mins > 0) { put("demande_temps", mins); cfg.demandeTemps = 0 }
            // Personne choisie dans l'app, à faire connaître à HA une fois.
            if (cfg.personneAEnvoyer && cfg.personne.isNotEmpty()) put("person", cfg.personne)
        }
    }

    /** Vrai pour chaque protection en place ; une protection tombée se voit dans HA. */
    private fun protections(): JSONObject = JSONObject().apply {
        put("accessibilite", VisionAccessibility.estActive(this@AgentService))
        put("vpn", DnsVpnService.actif)
        put("usage", Usage.accesUsage(this@AgentService))
        put("admin", AdminReceiver.estActif(this@AgentService))
        put("batterie", batterieIgnoree())
    }

    private fun synchroniserListeNoire(cfg: Config, version: String) {
        if (version.isEmpty() || version == cfg.versionListeNoire) return
        try {
            val r = Net.post(this, cfg, "/api/pc_parental/liste-noire",
                JSONObject().put("id", cfg.id).put("secret", cfg.secret))
            if (r.optBoolean("ok")) {
                Etat.majListeNoire(this, r.optString("version"),
                    r.optJSONArray("connus") ?: JSONArray())
            }
        } catch (_: Exception) {}
    }

    private fun appliquerConsignesVpn() {
        val besoin = Etat.sites.isNotEmpty() || Etat.listeNoire.isNotEmpty() || Etat.dns.isNotEmpty()
        if (besoin && !DnsVpnService.actif && DnsVpnService.autorise(this)) {
            DnsVpnService.demarrer(this)
        }
    }

    /**
     * Mise à jour annoncée par HA pour Android : {version, path, sha256}.
     * Le payload Windows (scripts) n'a pas de `path` et est ignoré.
     */
    private fun traiterMiseAJour(cfg: Config, u: JSONObject?) {
        if (u == null) { MiseAJour.disponible = ""; return }
        val path = u.optString("path", "")
        if (path.isEmpty()) return
        MiseAJour.traiter(this, cfg, u.optString("version", ""), path, u.optString("sha256", ""))
    }

    /** Repli quand l'accessibilité est coupée : on lit le premier plan via UsageStats. */
    private fun surveillerPremierPlan() {
        if (VisionAccessibility.estActive(this)) return
        val pkg = Usage.premierPlan(this) ?: return
        Usage.dernierPaquet = pkg
        Etat.doitBloquer(this, pkg)?.let { raison ->
            principal.post { BlockActivity.afficher(this, raison, pkg) }
        }
    }

    private fun seDesinscrire(cfg: Config) {
        try {
            Net.post(this, cfg, "/api/pc_parental/poll",
                JSONObject().put("id", cfg.id).put("secret", cfg.secret)
                    .put("uninstalled", true).put("platform", "android"))
        } catch (_: Exception) {}
        cfg.oublierInscription()
        DnsVpnService.arreter(this)
        majNotification()
    }

    // ----------------------------------------------------- Notification

    private fun demarrerPremierPlan() {
        if (Build.VERSION.SDK_INT >= 26) {
            val nm = getSystemService(NotificationManager::class.java)
            // Importance minimale : pas d'icône dans la barre d'état, rangée tout
            // en bas du volet. Android impose une notification à un service de
            // premier plan ; on la rend la plus discrète possible.
            try { nm.deleteNotificationChannel("vision_etat") } catch (_: Exception) {}
            nm.createNotificationChannel(NotificationChannel(
                CANAL, "Vision en arrière-plan", NotificationManager.IMPORTANCE_MIN).apply {
                setShowBadge(false)
                description = "Présence discrète de Vision (imposée par Android)"
            })
        }
        startForeground(NOTIF, construireNotif())
    }

    private fun majNotification() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(NOTIF, construireNotif())
    }

    private fun construireNotif(): Notification {
        val ouvrir = PendingIntent.getActivity(this, 0,
            Intent(this, SetupActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

        val b = if (Build.VERSION.SDK_INT >= 26)
            Notification.Builder(this, CANAL) else @Suppress("DEPRECATION") Notification.Builder(this)
        return b.setSmallIcon(R.drawable.ic_vision)
            .setContentTitle(titreNotif())
            .setContentText(texteNotif())
            .setOngoing(true)
            .setContentIntent(ouvrir)
            .setVisibility(Notification.VISIBILITY_SECRET)
            .apply { if (Build.VERSION.SDK_INT < 26) @Suppress("DEPRECATION") setPriority(Notification.PRIORITY_MIN) }
            .build()
    }

    private fun titreNotif(): String = when {
        !Config(this).inscrit -> "Vision : à configurer"
        Config(this).modeParent -> "Vision en pause (parent)"
        Etat.verrouilleEffectif() -> Etat.message.ifEmpty { "Accès fermé" }
        else -> "Vision : accès ouvert"
    }

    private fun texteNotif(): String {
        if (Etat.horsLigne() && Config(this).inscrit)
            return "Hors ligne — dernières règles appliquées"
        if (!Etat.verrouilleEffectif() && Etat.prochainChangement > System.currentTimeMillis())
            return "Fermeture à " + Etat.heure(Etat.prochainChangement)
        if (Etat.verrouilleEffectif() && Etat.prochainChangement > System.currentTimeMillis())
            return "Réouverture à " + Etat.heure(Etat.prochainChangement)
        return if (manque().isNotEmpty()) "Action requise : " + manque() else "Protections actives"
    }

    /** Liste courte des protections attendues mais absentes, pour la notification. */
    private fun manque(): String {
        val m = mutableListOf<String>()
        if (!VisionAccessibility.estActive(this)) m.add("accessibilité")
        if (!Usage.accesUsage(this)) m.add("usage")
        return m.joinToString(", ")
    }

    private fun batterieIgnoree(): Boolean {
        if (Build.VERSION.SDK_INT < 23) return true
        val pm = getSystemService(Context.POWER_SERVICE) as android.os.PowerManager
        return pm.isIgnoringBatteryOptimizations(packageName)
    }

    private fun appareil(): String {
        val m = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
        return m.ifEmpty { "Appareil Android" }
    }

    companion object {
        @Volatile var tentatives = 0
        private const val CANAL = "vision_fond"
        private const val NOTIF = 1

        fun demarrer(ctx: Context) {
            val i = Intent(ctx, AgentService::class.java)
            try {
                if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i)
                else ctx.startService(i)
            } catch (_: Exception) {}
        }
    }
}
