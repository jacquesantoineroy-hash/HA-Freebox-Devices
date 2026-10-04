package fr.familleroy.vision

import android.content.Context
import android.content.SharedPreferences
import java.security.MessageDigest

/** Réglages persistants de l'agent. Aucun jeton Home Assistant : juste l'id et le secret de cet appareil. */
class Config(ctx: Context) {
    private val p: SharedPreferences =
        ctx.applicationContext.getSharedPreferences("vision", Context.MODE_PRIVATE)

    var urlInterne: String
        get() = p.getString("url_int", "") ?: ""
        set(v) = p.edit().putString("url_int", nettoyer(v)).apply()
    var urlExterne: String
        get() = p.getString("url_ext", "") ?: ""
        set(v) = p.edit().putString("url_ext", nettoyer(v)).apply()
    /** Dernière adresse qui a répondu : on la tente en premier. */
    var urlActive: String
        get() = p.getString("url_ok", "") ?: ""
        set(v) = p.edit().putString("url_ok", v).apply()

    var id: String
        get() = p.getString("id", "") ?: ""
        set(v) = p.edit().putString("id", v).apply()
    var secret: String
        get() = p.getString("secret", "") ?: ""
        set(v) = p.edit().putString("secret", v).apply()
    var host: String
        get() = p.getString("host", "") ?: ""
        set(v) = p.edit().putString("host", v).apply()
    var utilisateur: String
        get() = p.getString("user", "") ?: ""
        set(v) = p.edit().putString("user", v).apply()
    var nom: String
        get() = p.getString("nom", "") ?: ""
        set(v) = p.edit().putString("nom", v).apply()
    /** Clé d'inscription de la maison, saisie une fois à l'installation. */
    var cleInscription: String
        get() = p.getString("cle", "") ?: ""
        set(v) = p.edit().putString("cle", v.trim()).apply()

    /** Dernière réponse de Home Assistant, appliquée telle quelle hors ligne. */
    var etat: String
        get() = p.getString("etat", "") ?: ""
        set(v) = p.edit().putString("etat", v).apply()
    var versionListeNoire: String
        get() = p.getString("noire_v", "") ?: ""
        set(v) = p.edit().putString("noire_v", v).apply()

    /** Mode parent : protections levées jusqu'à cet instant (ms). */
    var parentJusqua: Long
        get() = p.getLong("parent_until", 0)
        set(v) = p.edit().putLong("parent_until", v).apply()

    /** Minutes demandées par l'enfant, en attente d'envoi à HA (0 = rien). */
    var demandeTemps: Int
        get() = p.getInt("demande_min", 0)
        set(v) = p.edit().putInt("demande_min", v).apply()

    /** Personnes de la maison reçues à l'inscription (JSON), pour l'écran de choix. */
    var personnes: String
        get() = p.getString("personnes", "") ?: ""
        set(v) = p.edit().putString("personnes", v).apply()
    /** Personne choisie (person.xxx) ; envoyée à HA au prochain relevé si « à envoyer ». */
    var personne: String
        get() = p.getString("personne", "") ?: ""
        set(v) = p.edit().putString("personne", v).apply()
    var personneAEnvoyer: Boolean
        get() = p.getBoolean("personne_envoi", false)
        set(v) = p.edit().putBoolean("personne_envoi", v).apply()


    /** Dernière version dont l'installation a déjà été proposée à l'écran. */
    var majProposee: String
        get() = p.getString("maj_proposee", "") ?: ""
        set(v) = p.edit().putString("maj_proposee", v).apply()

    val inscrit: Boolean get() = id.isNotEmpty() && secret.isNotEmpty()

    /** Home Assistant trouvé sur le réseau : l'inscription se fait sans clé (acceptée seulement depuis la maison). */
    var sansCle: Boolean
        get() = p.getBoolean("sans_cle", false)
        set(v) = p.edit().putBoolean("sans_cle", v).apply()
    val modeParent: Boolean get() = System.currentTimeMillis() < parentJusqua
    val aUnCode: Boolean get() = (p.getString("pin", "") ?: "").isNotEmpty()

    fun definirCode(code: String) = p.edit().putString("pin", hacher(code)).apply()
    fun verifierCode(code: String): Boolean {
        val attendu = p.getString("pin", "") ?: ""
        return attendu.isNotEmpty() && attendu == hacher(code)
    }

    fun oublierInscription() {
        p.edit().remove("id").remove("secret").remove("etat").remove("noire_v")
            .remove("personnes").remove("personne").remove("personne_envoi").apply()
    }

    fun adresses(): List<String> =
        listOf(urlActive, urlInterne, urlExterne).filter { it.isNotEmpty() }.distinct()

    private fun hacher(code: String): String {
        val d = MessageDigest.getInstance("SHA-256").digest(("vision:" + code).toByteArray())
        return d.joinToString("") { "%02x".format(it) }
    }

    companion object {
        fun nettoyer(url: String): String {
            var u = url.trim().trimEnd('/')
            if (u.isNotEmpty() && !u.startsWith("http://") && !u.startsWith("https://")) u = "http://$u"
            return u
        }
    }
}
