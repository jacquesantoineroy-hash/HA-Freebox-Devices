package fr.familleroy.vision

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import org.json.JSONObject

/**
 * Demander l'accès à une appli ou un site fermé : la demande part chez les
 * parents, qui répondent depuis leur téléphone (pour de bon, un moment, ou
 * non). La réponse revient ici comme un message ordinaire.
 */
object Acces {
    /** Demandes déjà parties (clé → heure), pour ne pas insister. */
    private val envoyees = HashMap<String, Long>()

    fun dejaDemande(genre: String, nom: String): Boolean {
        val t = envoyees["$genre:$nom"] ?: return false
        return System.currentTimeMillis() - t < 15 * 60_000L
    }

    fun demander(ctx: Context, genre: String, nom: String, libelle: String, lien: String = "", motif: String = "", apres: ((Boolean) -> Unit)? = null) {
        val cfg = Config(ctx.applicationContext)
        val principal = Handler(Looper.getMainLooper())
        envoyees["$genre:$nom"] = System.currentTimeMillis()
        Thread {
            val ok = try {
                Net.post(ctx, cfg, "/api/pc_parental/demande", JSONObject()
                    .put("id", cfg.id).put("secret", cfg.secret)
                    .put("genre", genre).put("nom", nom).put("libelle", libelle)
                    .put("lien", lien).put("motif", motif)).optBoolean("ok")
            } catch (_: Exception) { false }
            if (!ok) envoyees.remove("$genre:$nom")
            principal.post {
                Toast.makeText(ctx, if (ok) "Demande envoyée aux parents." else "Envoi impossible, réessaie.", Toast.LENGTH_LONG).show()
                apres?.invoke(ok)
            }
        }.start()
    }

    /** « youtu.be/abc » ou « https://m.youtube.com/watch?v=… » → « youtube.com ». */
    fun hoteDe(lien: String): String {
        var l = lien.trim()
        if (l.isEmpty()) return ""
        if (!Regex("^[a-zA-Z][a-zA-Z0-9+.-]*://").containsMatchIn(l)) l = "https://$l"
        val h = try { java.net.URI(l).host ?: "" } catch (_: Exception) { "" }
        return Etat.domainePrincipal(h.removePrefix("www."))
    }

    /**
     * Petite boîte « lien ou motif » avant d'envoyer : les parents voient
     * exactement ce qui est demandé. Facultatif : vide, la demande part quand même.
     */
    fun dialogue(act: android.app.Activity, genre: String, nom: String, libelle: String, lienInitial: String = "", apres: ((Boolean) -> Unit)? = null) {
        val cadre = Ui.colonne(act, Ui.dp(act, 20f))
        val lien = if (genre == "sites") Ui.champ(act, "Lien de la page (facultatif)", lienInitial) else null
        if (lien != null) cadre.addView(lien)
        val motif = Ui.champ(act, "Pourquoi ? (facultatif)", "")
        cadre.addView(Ui.marge(act, motif, haut = 8f))
        android.app.AlertDialog.Builder(act)
            .setTitle("Demander l'accès à $libelle")
            .setView(cadre)
            .setPositiveButton("Envoyer") { _, _ ->
                val l = lien?.text?.toString()?.trim() ?: ""
                val h = hoteDe(l)
                demander(act, genre, if (genre == "sites" && h.isNotEmpty()) h else nom,
                    if (genre == "sites" && h.isNotEmpty()) h else libelle, l, motif.text.toString().trim(), apres)
            }
            .setNegativeButton("Annuler", null)
            .show()
    }

    /** Un parent répond à une demande d'accès. decision : toujours | temporaire | non. */
    fun repondre(ctx: Context, pc: String, demande: String, decision: String, minutes: Int = 60, apres: ((String) -> Unit)? = null) {
        val cfg = Config(ctx.applicationContext)
        val principal = Handler(Looper.getMainLooper())
        Thread {
            val texte = try {
                val r = Net.post(ctx, cfg, "/api/pc_parental/parent", JSONObject()
                    .put("id", cfg.id).put("secret", cfg.secret)
                    .put("action", "acces").put("pc", pc).put("demande", demande)
                    .put("decision", decision).put("minutes", minutes))
                when {
                    r.optBoolean("deja") -> "Déjà traité par un autre parent."
                    !r.optBoolean("ok") -> "Home Assistant a refusé."
                    else -> r.optString("retour").ifEmpty { "C'est fait." }
                }
            } catch (e: Net.Echec) {
                if (e.code == 403) "Cet appareil n'est pas marqué « Parents » dans Vision." else "Envoi impossible (${e.code})."
            } catch (_: Exception) { "Home Assistant injoignable." }
            principal.post { Toast.makeText(ctx, texte, Toast.LENGTH_LONG).show(); apres?.invoke(texte) }
        }.start()
    }
}
