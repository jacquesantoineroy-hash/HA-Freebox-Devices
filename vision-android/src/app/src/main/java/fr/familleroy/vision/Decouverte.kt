package fr.familleroy.vision

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper

/**
 * Trouve Home Assistant sur le réseau de la maison (annonce mDNS
 * `_home-assistant._tcp`) et inscrit l'appareil sans clé à coller : Home
 * Assistant accepte une inscription sans clé quand elle vient du réseau local
 * et que les inscriptions sont ouvertes.
 */
object Decouverte {
    private val main = Handler(Looper.getMainLooper())
    @Volatile var enCours = false
    /** Ce qui s'est passé, pour l'écran : vide, « recherche », ou la raison de l'échec. */
    @Volatile var etat = ""

    private fun prive(url: String): Boolean {
        val h = url.substringAfter("://").substringBefore('/').substringBefore(':')
        return h.startsWith("192.168.") || h.startsWith("10.") || h.endsWith(".local") || Regex("^172\\.(1[6-9]|2[0-9]|3[01])\\.").containsMatchIn(h)
    }

    /** Cherche, pose les adresses trouvées et lance l'inscription. `fin(true)` si Home Assistant a été trouvé. */
    fun inscrireSeul(ctx: Context, fin: (Boolean) -> Unit) {
        val app = ctx.applicationContext
        val cfg = Config(app)
        if (cfg.inscrit || enCours) { fin(cfg.inscrit); return }
        enCours = true; etat = "Recherche de Home Assistant sur le réseau…"
        val nsd = app.getSystemService(Context.NSD_SERVICE) as? NsdManager
        if (nsd == null) { enCours = false; etat = "Recherche impossible sur cet appareil."; fin(false); return }
        val urls = LinkedHashSet<String>()
        var termine = false
        var ecouteur: NsdManager.DiscoveryListener? = null

        fun conclure() {
            if (termine) return
            termine = true
            try { ecouteur?.let { nsd.stopServiceDiscovery(it) } } catch (_: Exception) {}
            enCours = false
            if (urls.isEmpty()) { etat = "Home Assistant introuvable sur ce réseau (Wi-Fi invité, ou annonce réseau coupée)."; fin(false); return }
            val externe = urls.firstOrNull { !prive(it) } ?: urls.first()
            val interne = urls.firstOrNull { prive(it) } ?: ""
            cfg.urlExterne = externe; cfg.urlInterne = interne; cfg.sansCle = true
            etat = "Home Assistant trouvé, inscription…"
            AgentService.demarrer(app)
            fin(true)
        }

        val l = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(t: String) {}
            override fun onDiscoveryStopped(t: String) {}
            override fun onStartDiscoveryFailed(t: String, code: Int) { main.post { conclure() } }
            override fun onStopDiscoveryFailed(t: String, code: Int) {}
            override fun onServiceLost(s: NsdServiceInfo) {}
            override fun onServiceFound(s: NsdServiceInfo) {
                try {
                    @Suppress("DEPRECATION")
                    nsd.resolveService(s, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(si: NsdServiceInfo, code: Int) {}
                        override fun onServiceResolved(si: NsdServiceInfo) {
                            fun attribut(k: String) = try { si.attributes[k]?.let { String(it, Charsets.UTF_8).trim().trimEnd('/') } ?: "" } catch (_: Exception) { "" }
                            // L'adresse publique d'abord (certificat valide), puis l'interne, puis l'adresse brute.
                            for (k in listOf("external_url", "internal_url", "base_url")) attribut(k).takeIf { it.startsWith("http") }?.let { urls.add(it) }
                            @Suppress("DEPRECATION")
                            val ip = si.host?.hostAddress
                            if (!ip.isNullOrEmpty() && !ip.contains(':')) { urls.add("http://$ip:${si.port}") }
                            main.postDelayed({ conclure() }, 400)
                        }
                    })
                } catch (_: Exception) {}
            }
        }
        ecouteur = l
        try { nsd.discoverServices("_home-assistant._tcp", NsdManager.PROTOCOL_DNS_SD, l) } catch (_: Exception) { conclure(); return }
        main.postDelayed({ conclure() }, 9000)
    }
}
