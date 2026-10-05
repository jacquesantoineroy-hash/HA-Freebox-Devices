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
import org.json.JSONArray
import org.json.JSONObject

/**
 * Pour un parent : les exceptions d'une personne, c'est-à-dire ce qui est décidé
 * nom par nom en plus des catégories. « Snapchat : toujours autorisé pour Jules. »
 * On les voit, on les inverse, on les retire, on en ajoute. Elles valent sur tous
 * les appareils de la personne ; le planning et les interdits de toute la maison
 * restent plus forts.
 */
class ExceptionsActivity : Activity() {
    private class Element(val genre: String, val nom: String, val libelle: String, val maison: Boolean = false)

    private lateinit var liste: LinearLayout
    private lateinit var resultats: LinearLayout
    private lateinit var a: JSONObject
    private val autorises = ArrayList<Element>()
    private val bloques = ArrayList<Element>()
    private val disponibles = ArrayList<Element>()
    private val connus = ArrayList<Element>()
    private var recherche = ""

    companion object {
        @Volatile var fiche: JSONObject? = null
        @Volatile var cats: JSONArray? = null
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Ui.charger(this)
        a = fiche ?: run { finish(); return }
        val ex = a.optJSONObject("exceptions")
        lire(ex?.optJSONArray("autorises"), autorises)
        lire(ex?.optJSONArray("bloques"), bloques)
        lire(ex?.optJSONArray("toujours"), disponibles)
        // Tout ce que Vision connaît déjà : les applis et les sites classés dans une catégorie.
        val vus = HashSet<String>()
        val categories = cats ?: JSONArray()
        for (i in 0 until categories.length()) {
            val c = categories.optJSONObject(i) ?: continue
            val apps = c.optJSONArray("apps") ?: JSONArray()
            for (k in 0 until apps.length()) { val o = apps.optJSONObject(k) ?: continue; val n = o.optString("nom"); if (n.isNotEmpty() && vus.add("a:" + n.lowercase())) connus.add(Element("apps", n, o.optString("libelle").ifEmpty { n })) }
            val sites = c.optJSONArray("sites") ?: JSONArray()
            for (k in 0 until sites.length()) { val n = sites.optString(k); if (n.isNotEmpty() && vus.add("s:" + n.lowercase())) connus.add(Element("sites", n, n)) }
        }
        connus.sortBy { it.libelle.lowercase() }

        if (android.os.Build.VERSION.SDK_INT >= 21) { window.statusBarColor = Ui.FOND; window.navigationBarColor = Ui.FOND }
        val scroll = ScrollView(this).apply { setBackgroundColor(Ui.FOND); isFillViewport = true }
        val racine = Ui.colonne(this, Ui.dp(this, 20f))
        scroll.addView(racine); setContentView(scroll)
        racine.addView(Ui.marque(this))
        val prenom = a.optString("prenom").ifEmpty { a.optString("nom") }
        val col = Ui.colonne(this)
        col.addView(Ui.titre(this, "Autorisations"))
        col.addView(Ui.sousTitre(this, "Ce qui est décidé à part pour $prenom, sur tous ses appareils"))
        racine.addView(Ui.marge(this, col, bas = 14f))
        racine.addView(Ui.texte(this, "Toujours autorisé : ouvert en dehors des plages de coupure. Exception : disponible même pendant les coupures. Touche une ligne pour la changer.", 13f, Ui.TEXTE_2))
        if (ex == null) racine.addView(Ui.marge(this, Ui.texte(this, "Les exceptions arrivent avec la prochaine mise à jour de Home Assistant.", 13f, Ui.OR), haut = 10f))
        liste = Ui.colonne(this)
        racine.addView(Ui.marge(this, liste, haut = 6f))

        racine.addView(Ui.section(this, "Ajouter"))
        val carte = Ui.carte(this)
        val champ = Ui.champ(this, "Nom d'une appli ou adresse d'un site", "")
        champ.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { recherche = s?.toString()?.trim()?.lowercase() ?: ""; chercher() }
            override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, af: Int) {}
            override fun onTextChanged(s: CharSequence?, st: Int, bf: Int, c: Int) {}
        })
        carte.addView(champ)
        resultats = Ui.colonne(this)
        carte.addView(Ui.marge(this, resultats, haut = 6f))
        racine.addView(carte)
        racine.addView(Ui.espace(this, 24f))
        remplir(); chercher()
    }

    private fun lire(source: JSONArray?, vers: ArrayList<Element>) {
        if (source == null) return
        for (i in 0 until source.length()) {
            val o = source.optJSONObject(i) ?: continue
            vers.add(Element(o.optString("genre", "apps"), o.optString("nom"), o.optString("libelle").ifEmpty { o.optString("nom") }, o.optBoolean("maison")))
        }
    }

    private fun remplir() {
        liste.removeAllViews()
        // Toujours disponibles : ce qui reste ouvert quand le planning ferme l'appareil.
        liste.addView(Ui.section(this, "Exceptions : même pendant les coupures (${disponibles.size})"))
        val cd = Ui.carte(this)
        if (disponibles.isEmpty()) cd.addView(Ui.texte(this, "Rien de plus que le téléphone, les messages, le réveil et Pronote.", 14f, Ui.TEXTE_3))
        disponibles.sortedBy { it.libelle.lowercase() }.forEachIndexed { k, e ->
            if (k > 0) cd.addView(Ui.separateur(this))
            cd.addView(ligne(e, if (e.maison) "pour toute la maison" else "") {
                if (e.maison) Toast.makeText(this, "Pour toute la maison : étiquette « Toujours autorisé » dans Vision.", Toast.LENGTH_LONG).show()
                else AlertDialog.Builder(this).setTitle(e.libelle).setItems(arrayOf("Retirer : elle suivra le planning")) { _, _ -> decider(e, "indisponible") }.setNegativeButton("Annuler", null).show()
            })
        }
        liste.addView(cd)
        for ((titre, vide, elements, autorise) in listOf(
            Quatre("Toujours autorisé, hors coupures", "Rien d'autorisé à part.", autorises, true),
            Quatre("Toujours fermé", "Rien de fermé à part.", bloques, false),
        )) {
            liste.addView(Ui.section(this, "$titre (${elements.size})"))
            val c = Ui.carte(this)
            if (elements.isEmpty()) c.addView(Ui.texte(this, vide, 14f, Ui.TEXTE_3))
            elements.sortedBy { it.libelle.lowercase() }.forEachIndexed { k, e ->
                if (k > 0) c.addView(Ui.separateur(this))
                c.addView(ligne(e, if (e.maison) "interdit pour toute la maison" else "") { choisir(e, autorise) })
            }
            liste.addView(c)
        }
    }

    private data class Quatre(val titre: String, val vide: String, val elements: ArrayList<Element>, val autorise: Boolean)

    private fun ligne(e: Element, note: String, action: () -> Unit): View {
        val col = Ui.colonne(this)
        col.addView(Ui.texte(this, e.libelle, 15f, Ui.TEXTE, gras = true))
        val sous = listOf(if (e.genre == "apps") "Appli" else "Site", if (e.libelle != e.nom) e.nom else "", note).filter { it.isNotEmpty() }.joinToString(" · ")
        col.addView(Ui.texte(this, sous, 12f, Ui.TEXTE_2))
        col.setPadding(0, Ui.dp(this, 9f), 0, Ui.dp(this, 9f))
        col.isClickable = true; col.isFocusable = true
        col.setOnClickListener { action() }
        return col
    }

    /** Une exception existante : l'inverser ou la retirer. */
    private fun choisir(e: Element, autorise: Boolean) {
        val inverse = if (autorise) "Fermer plutôt" else "Autoriser plutôt"
        AlertDialog.Builder(this).setTitle(e.libelle)
            .setItems(arrayOf(inverse, "Retirer l'exception")) { _, k ->
                if (k == 0) decider(e, if (autorise) "bloquer" else "toujours") else decider(e, "oublier")
            }.setNegativeButton("Annuler", null).show()
    }

    private fun chercher() {
        resultats.removeAllViews()
        if (recherche.length < 2) { resultats.addView(Ui.texte(this, "Deux lettres suffisent pour chercher.", 13f, Ui.TEXTE_3)); return }
        val trouves = ArrayList(connus.filter { it.libelle.lowercase().contains(recherche) || it.nom.lowercase().contains(recherche) }.take(10))
        // Une adresse écrite en entier et que Vision ne connaît pas encore : on la propose telle quelle.
        if (Regex("^[a-z0-9-]+(\\.[a-z0-9-]+)+$").matches(recherche) && trouves.none { it.nom.lowercase() == recherche }) trouves.add(0, Element("sites", recherche, recherche))
        if (trouves.isEmpty()) { resultats.addView(Ui.texte(this, "Rien de ce nom. Pour un site, écris son adresse (exemple.fr).", 13f, Ui.TEXTE_3)); return }
        trouves.forEachIndexed { k, e ->
            if (k > 0) resultats.addView(Ui.separateur(this))
            resultats.addView(ligne(e, "") {
                val choix = if (e.genre == "apps") arrayOf("Toujours autoriser (hors coupures)", "Toujours fermer", "Exception : même pendant les coupures") else arrayOf("Toujours autoriser (hors coupures)", "Toujours fermer")
                AlertDialog.Builder(this).setTitle(e.libelle)
                    .setItems(choix) { _, i -> decider(e, when (i) { 0 -> "toujours"; 1 -> "bloquer"; else -> "disponible" }) }
                    .setNegativeButton("Annuler", null).show()
            })
        }
    }

    /** Envoie la décision, et met la liste à jour dès que Home Assistant l'a acceptée. */
    private fun decider(e: Element, decision: String) {
        val cfg = Config(this)
        Thread {
            var ok = false
            var x404 = false
            val texte = try {
                val r = Net.post(this, cfg, "/api/pc_parental/parent", JSONObject()
                    .put("id", cfg.id).put("secret", cfg.secret).put("action", "autoriser")
                    .put("pc", a.optString("id")).put("genre", e.genre).put("nom", e.nom).put("decision", decision))
                ok = true
                r.optString("retour").ifEmpty { "C'est fait." }
            } catch (x: Net.Echec) {
                when (x.code) { 409 -> "Interdit pour toute la maison : à lever dans Vision."; 404 -> { x404 = true; "Ce n'est déjà plus dans la liste." }; else -> "Refusé (${x.code})." }
            } catch (_: Exception) { "Home Assistant injoignable." }
            runOnUiThread {
                Toast.makeText(this, texte, Toast.LENGTH_SHORT).show()
                if (ok || x404) {
                    when (decision) {
                        "disponible" -> {
                            if (disponibles.none { it.nom.equals(e.nom, true) }) disponibles.add(e)
                            bloques.removeAll { it.nom.equals(e.nom, true) }
                            if (autorises.none { it.nom.equals(e.nom, true) }) autorises.add(e)
                        }
                        "indisponible" -> disponibles.removeAll { it.nom.equals(e.nom, true) }
                        else -> {
                            autorises.removeAll { it.nom.equals(e.nom, true) }; bloques.removeAll { it.nom.equals(e.nom, true) }
                            if (decision == "toujours") autorises.add(e) else if (decision == "bloquer") bloques.add(e)
                        }
                    }
                    remplir()
                }
            }
        }.start()
    }
}
