package fr.familleroy.vision

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Toast
import org.json.JSONObject
import java.util.Locale

/**
 * Pour un parent : ce qui est fermé sur l'appareil d'un enfant, rangé par
 * motif (sécurité, maison, moyenne, âge, planning, parents), avec le libellé
 * lisible et de quoi agir ligne par ligne : ouvrir un moment, autoriser.
 */
class DetailFermesActivity : Activity() {
    private lateinit var racine: LinearLayout
    private lateinit var liste: LinearLayout
    private var filtre = ""
    private var montrerSecurite = false
    private lateinit var a: JSONObject
    private val motifs = ArrayList<Pair<String, String>>()   // code, texte

    companion object {
        /** Les fiches sont trop grosses pour un Intent : on les passe par ici. */
        @Volatile var fiche: JSONObject? = null
        val ORDRE = listOf("plage", "moyenne", "regle", "age", "maison", "securite")
        val TITRES = mapOf(
            "plage" to "Planning", "moyenne" to "Moyenne", "regle" to "Décision des parents",
            "age" to "Âge (PEGI)", "maison" to "Toute la maison", "securite" to "Sécurité")
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Ui.charger(this)
        a = fiche ?: run { finish(); return }
        if (android.os.Build.VERSION.SDK_INT >= 21) { window.statusBarColor = Ui.FOND; window.navigationBarColor = Ui.FOND }
        val m = a.optJSONArray("motifs")
        if (m != null) for (i in 0 until m.length()) {
            val s = m.optString(i); motifs.add(s.substringBefore('|') to s.substringAfter('|'))
        }
        val scroll = ScrollView(this).apply { setBackgroundColor(Ui.FOND); isFillViewport = true }
        racine = Ui.colonne(this, Ui.dp(this, 20f))
        scroll.addView(racine); setContentView(scroll)

        racine.addView(Ui.marque(this))
        val r = Ui.rangee(this)
        val col = Ui.colonne(this)
        col.addView(Ui.titre(this, a.optString("prenom").ifEmpty { a.optString("nom") }))
        col.addView(Ui.sousTitre(this, "Ce qui est fermé sur ${a.optString("nom")}"))
        r.addView(Ui.marge(this, col, gauche = 2f))
        racine.addView(Ui.marge(this, r, bas = 14f))

        val champ = Ui.champ(this, "Chercher", "")
        champ.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { filtre = s?.toString()?.trim()?.lowercase(Locale.ROOT) ?: ""; remplir() }
            override fun beforeTextChanged(s: CharSequence?, x: Int, y: Int, z: Int) {}
            override fun onTextChanged(s: CharSequence?, x: Int, y: Int, z: Int) {}
        })
        racine.addView(champ)
        liste = Ui.colonne(this)
        racine.addView(Ui.marge(this, liste, haut = 6f))
        remplir()
    }

    private data class Ligne(val genre: String, val nom: String, val libelle: String, val code: String, val texte: String)

    private fun lignes(): List<Ligne> {
        val raisons = a.optJSONObject("raisons") ?: JSONObject()
        fun motifDe(nom: String): Pair<String, String>? {
            var d = nom.lowercase(Locale.ROOT)
            while (true) {
                if (raisons.has(d)) return motifs.getOrNull(raisons.optInt(d, -1))
                if (!d.contains('.')) return null
                d = d.substringAfter('.')
            }
        }
        val out = ArrayList<Ligne>()
        for ((genre, cle) in listOf("apps" to "apps", "sites" to "sites")) {
            val arr = a.optJSONArray(cle) ?: continue
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val nom = o.optString("nom"); val lib = o.optString("libelle").ifEmpty { nom }
                if (genre == "sites" && nom.count { it == '.' } != 1) continue
                val (code, texte) = motifDe(nom) ?: ("regle" to "Coupé par les parents.")
                if (filtre.isNotEmpty() && !lib.lowercase(Locale.ROOT).contains(filtre) && !nom.contains(filtre)) continue
                out.add(Ligne(genre, nom, lib, code, texte))
            }
        }
        return out
    }

    private fun remplir() {
        liste.removeAllViews()
        val toutes = lignes()
        val parCode = toutes.groupBy { it.code }
        for (code in ORDRE) {
            val l = parCode[code] ?: continue
            val titre = TITRES[code] ?: code
            liste.addView(Ui.section(this, "$titre (${l.size})"))
            if (code == "securite" && !montrerSecurite) {
                liste.addView(Ui.carte(this).apply {
                    addView(Ui.texte(this@DetailFermesActivity, "Sites dangereux, pièges et traçage : coupés partout, pour tout le monde.", 13f, Ui.TEXTE_2))
                    addView(Ui.marge(this@DetailFermesActivity, Ui.boutonSecondaire(this@DetailFermesActivity, "Afficher la liste") { montrerSecurite = true; remplir() }, haut = 8f))
                })
                continue
            }
            val c = Ui.carte(this)
            // Un seul texte de motif par groupe quand il est identique partout.
            val textes = l.map { it.texte }.distinct()
            if (textes.size == 1) c.addView(Ui.marge(this, Ui.texte(this, textes[0], 12f, Ui.TEXTE_2), bas = 6f))
            val apps = l.filter { it.genre == "apps" }.sortedBy { it.libelle.lowercase(Locale.ROOT) }
            val sites = l.filter { it.genre == "sites" }.sortedBy { it.nom }
            var k = 0
            for (x in apps + sites) {
                if (k++ > 0) c.addView(Ui.separateur(this))
                c.addView(ligne(x, textes.size > 1))
            }
            liste.addView(c)
        }
        if (toutes.isEmpty()) liste.addView(Ui.carte(this).apply { addView(Ui.texte(this@DetailFermesActivity, "Rien de fermé.", 14f, Ui.TEXTE_2)) })
        liste.addView(Ui.espace(this, 24f))
    }

    private fun ligne(x: Ligne, avecMotif: Boolean): View {
        val r = Ui.rangee(this)
        val col = Ui.colonne(this)
        col.addView(Ui.texte(this, x.libelle, 15f, Ui.TEXTE, gras = true))
        col.addView(Ui.texte(this, (if (x.genre == "apps") "Appli" else "Site") + (if (avecMotif) " · " + x.texte else ""), 12f, Ui.TEXTE_2))
        r.addView(Ui.poids(col))
        if (x.code != "securite") {
            r.addView(Ui.boutonSecondaire(this, "Ouvrir…") { agir(x) })
        }
        r.setPadding(0, Ui.dp(this, 6f), 0, Ui.dp(this, 6f))
        return r
    }

    private fun agir(x: Ligne) {
        val choix = if (x.code == "maison") arrayOf("30 minutes", "1 heure", "2 heures")
                    else arrayOf("30 minutes", "1 heure", "2 heures", "Toujours (sur les appareils de ${a.optString("prenom").ifEmpty { "cette personne" }})")
        AlertDialog.Builder(this).setTitle("Ouvrir ${x.libelle} ?")
            .setItems(choix) { _, k ->
                val (decision, minutes) = when (k) { 0 -> "temporaire" to 30; 1 -> "temporaire" to 60; 2 -> "temporaire" to 120; else -> "toujours" to 0 }
                val cfg = Config(this)
                Thread {
                    val texte = try {
                        val rep = Net.post(this, cfg, "/api/pc_parental/parent", JSONObject()
                            .put("id", cfg.id).put("secret", cfg.secret).put("action", "autoriser")
                            .put("pc", a.optString("id")).put("genre", x.genre).put("nom", x.nom)
                            .put("decision", decision).put("minutes", minutes))
                        rep.optString("retour").ifEmpty { "C'est fait." }
                    } catch (e: Net.Echec) { if (e.code == 409) "Interdit pour toute la maison : à lever dans Vision." else "Refusé (${e.code})." }
                    catch (_: Exception) { "Home Assistant injoignable." }
                    runOnUiThread { Toast.makeText(this, texte, Toast.LENGTH_LONG).show() }
                }.start()
            }.setNegativeButton("Annuler", null).show()
    }
}
