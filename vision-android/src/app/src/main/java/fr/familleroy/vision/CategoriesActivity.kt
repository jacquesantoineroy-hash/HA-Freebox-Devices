package fr.familleroy.vision

import android.app.Activity
import android.app.AlertDialog
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject

/**
 * Pour un parent : les catégories (étiquettes) d'un enfant, chacune avec un
 * interrupteur « coupé », et ce qu'elle contient. Les catégories de la maison
 * (sécurité, interdits) sont verrouillées ici : elles se lèvent dans Vision.
 */
class CategoriesActivity : Activity() {
    private lateinit var racine: LinearLayout
    private lateinit var liste: LinearLayout
    private lateinit var a: JSONObject
    private var categories = JSONArray()
    private val etats = HashMap<String, JSONObject>()

    companion object {
        @Volatile var fiche: JSONObject? = null
        @Volatile var cats: JSONArray? = null
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Ui.charger(this)
        a = fiche ?: run { finish(); return }
        categories = cats ?: JSONArray()
        val e = a.optJSONObject("etiquettes_etat") ?: JSONObject()
        for (k in e.keys()) etats[k] = e.optJSONObject(k) ?: JSONObject().put("choix", e.optString(k)).put("coupe", e.optString(k) == "bloquer")
        if (android.os.Build.VERSION.SDK_INT >= 21) { window.statusBarColor = Ui.FOND; window.navigationBarColor = Ui.FOND }
        val scroll = ScrollView(this).apply { setBackgroundColor(Ui.FOND); isFillViewport = true }
        racine = Ui.colonne(this, Ui.dp(this, 20f))
        scroll.addView(racine); setContentView(scroll)

        racine.addView(Ui.marque(this))
        val r = Ui.rangee(this)
        val col = Ui.colonne(this)
        val prenom = a.optString("prenom").ifEmpty { a.optString("nom") }
        col.addView(Ui.titre(this, "Catégories"))
        col.addView(Ui.sousTitre(this, "Ce que $prenom peut utiliser, sur tous ses appareils"))
        r.addView(Ui.marge(this, col, gauche = 2f))
        racine.addView(Ui.marge(this, r, bas = 14f))
        racine.addView(Ui.texte(this, "Interrupteur à droite : coupé. Touche le nom pour voir ce qu'il y a dedans. Le planning et la règle de moyenne s'ajoutent par-dessus.", 13f, Ui.TEXTE_2))
        liste = Ui.colonne(this)
        racine.addView(Ui.marge(this, liste, haut = 10f))
        remplir()
    }

    private fun remplir() {
        liste.removeAllViews()
        val libres = ArrayList<JSONObject>(); val maison = ArrayList<JSONObject>()
        for (i in 0 until categories.length()) {
            val c = categories.optJSONObject(i) ?: continue
            if (c.optBoolean("maison") || c.optBoolean("securite")) maison.add(c) else libres.add(c)
        }
        // Les âges d'abord, puis le reste.
        val ages = libres.filter { it.optBoolean("age") }
        val autres = libres.filter { !it.optBoolean("age") }
        if (ages.isNotEmpty()) { liste.addView(Ui.section(this, "Âge")); liste.addView(carte(ages)) }
        if (autres.isNotEmpty()) { liste.addView(Ui.section(this, "Catégories")); liste.addView(carte(autres)) }
        if (maison.isNotEmpty()) {
            liste.addView(Ui.section(this, "Toute la maison (verrouillé)"))
            liste.addView(carte(maison, verrou = true))
        }
        liste.addView(Ui.espace(this, 24f))
    }

    private fun carte(cs: List<JSONObject>, verrou: Boolean = false): View {
        val c = Ui.carte(this)
        cs.forEachIndexed { k, cat ->
            if (k > 0) c.addView(Ui.separateur(this))
            c.addView(ligne(cat, verrou))
        }
        return c
    }

    private fun ligne(cat: JSONObject, verrou: Boolean): View {
        val nom = cat.optString("nom")
        val nA = cat.optJSONArray("apps")?.length() ?: 0
        val nS = cat.optJSONArray("sites")?.length() ?: 0
        val e = etats[nom] ?: JSONObject()
        val choix = e.optString("choix", "neutre")
        val coupe = e.optBoolean("coupe", choix == "bloquer")
        val bloqueParRegle = e.optBoolean("verrou") && !verrou   // moyenne ou planning : coché, mais pas à toi de le décocher
        val r = Ui.rangee(this)
        val col = Ui.colonne(this)
        col.addView(Ui.texte(this, nom, 15f, if (verrou) Ui.TEXTE_2 else Ui.TEXTE, gras = true))
        val detail = buildString {
            append(if (nA == 0 && nS == 0) "vide" else listOfNotNull(if (nA > 0) "$nA applis" else null, if (nS > 0) "$nS sites" else null).joinToString(", "))
            if (choix == "autoriser") append(" · autorisé explicitement")
        }
        col.addView(Ui.texte(this, detail, 12f, Ui.TEXTE_2))
        val raison = e.optString("raison")
        if (raison.isNotEmpty() && (bloqueParRegle || verrou)) col.addView(Ui.texte(this, raison, 12f, if (bloqueParRegle) Ui.OR else Ui.TEXTE_3))
        col.setOnClickListener { contenu(cat) }
        r.addView(Ui.poids(col))
        if (verrou) {
            r.addView(Ui.chip(this, "maison", Ui.TEXTE_3))
        } else {
            val sw = Switch(this)
            sw.isChecked = coupe
            if (bloqueParRegle) { sw.isEnabled = false; sw.alpha = 0.6f }
            if (android.os.Build.VERSION.SDK_INT >= 23) {
                sw.thumbTintList = android.content.res.ColorStateList(arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()), intArrayOf(Ui.ROUGE, Ui.TEXTE_2))
                sw.trackTintList = android.content.res.ColorStateList(arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()), intArrayOf(Ui.ROUGE and 0x66FFFFFF, Ui.LIGNE))
            }
            sw.setOnCheckedChangeListener { _, coche -> basculer(nom, if (coche) "bloquer" else "neutre") }
            r.addView(sw)
        }
        r.setPadding(0, Ui.dp(this, 8f), 0, Ui.dp(this, 8f))
        return r
    }

    private fun contenu(cat: JSONObject) {
        val apps = cat.optJSONArray("apps") ?: JSONArray()
        val sites = cat.optJSONArray("sites") ?: JSONArray()
        val lignes = ArrayList<String>()
        for (i in 0 until apps.length()) lignes.add("• " + (apps.optJSONObject(i)?.optString("libelle") ?: ""))
        for (i in 0 until sites.length()) lignes.add("◦ " + sites.optString(i))
        val vue = ScrollView(this)
        val col = Ui.colonne(this, Ui.dp(this, 20f))
        col.addView(Ui.texte(this, if (lignes.isEmpty()) "Rien de classé ici pour l'instant." else lignes.joinToString("\n"), 14f, Ui.TEXTE))
        vue.addView(col)
        AlertDialog.Builder(this).setTitle(cat.optString("nom")).setView(vue).setPositiveButton("Fermer", null).show()
    }

    private fun basculer(nom: String, etat: String) {
        etats[nom] = (etats[nom] ?: JSONObject()).put("choix", etat).put("coupe", etat == "bloquer")
        val cfg = Config(this)
        Thread {
            val texte = try {
                Net.post(this, cfg, "/api/pc_parental/parent", JSONObject()
                    .put("id", cfg.id).put("secret", cfg.secret).put("action", "etiquette")
                    .put("pc", a.optString("id")).put("etiquette", nom).put("etat", etat)).optString("retour").ifEmpty { "C'est fait." }
            } catch (e: Net.Echec) { "Refusé (${e.code})." } catch (_: Exception) { "Home Assistant injoignable." }
            runOnUiThread { Toast.makeText(this, texte, Toast.LENGTH_SHORT).show() }
        }.start()
    }
}
