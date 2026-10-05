package fr.familleroy.vision

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject

/**
 * L'espace parents : ce que montre le tableau de bord de la maison, sur le
 * téléphone d'un parent. Chaque appareil d'enfant avec son état, ce qui est
 * coupé, le planning du jour, et de quoi agir d'un geste : du temps en plus,
 * fermer, revenir au planning, envoyer un mot. Home Assistant reste seul juge :
 * il ne répond qu'aux appareils portant l'étiquette « Parents ».
 */
class ParentsActivity : Activity() {
    private lateinit var racine: LinearLayout
    private val cfg by lazy { Config(this) }
    private val principal = Handler(Looper.getMainLooper())
    private var appareils: JSONArray = JSONArray()
    private var demandes: JSONArray = JSONArray()
    private var categories: JSONArray = JSONArray()
    private var erreur = ""
    private var chargement = false
    private val deplies = HashSet<String>()
    private val rafraichir = object : Runnable {
        override fun run() { charger(); principal.postDelayed(this, 20_000) }
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Ui.charger(this)
        if (android.os.Build.VERSION.SDK_INT >= 21) {
            window.statusBarColor = Ui.FOND; window.navigationBarColor = Ui.FOND
        }
        val scroll = ScrollView(this).apply { setBackgroundColor(Ui.FOND); isFillViewport = true }
        racine = Ui.colonne(this, Ui.dp(this, 20f))
        scroll.addView(racine)
        setContentView(scroll)
        dessiner()
    }

    override fun onResume() { super.onResume(); principal.post(rafraichir) }
    override fun onPause() { super.onPause(); principal.removeCallbacks(rafraichir) }

    // ------------------------------------------------------------ Réseau

    private fun charger(action: String = "", pc: String = "", minutes: Int = 0, texte: String = "") {
        if (chargement && action.isEmpty()) return
        chargement = true
        Thread {
            try {
                val corps = JSONObject().put("id", cfg.id).put("secret", cfg.secret)
                if (action.isNotEmpty()) {
                    corps.put("action", action).put("pc", pc).put("minutes", minutes)
                    if (texte.isNotEmpty()) corps.put("texte", texte)
                }
                val r = Net.post(this, cfg, "/api/pc_parental/parent", corps)
                appareils = r.optJSONArray("appareils") ?: JSONArray()
                demandes = r.optJSONArray("demandes") ?: JSONArray()
                categories = r.optJSONArray("categories") ?: JSONArray()
                erreur = ""
                val retour = r.optString("retour", "")
                principal.post { if (retour.isNotEmpty()) toast(retour); dessiner() }
            } catch (e: Net.Echec) {
                erreur = if (e.code == 403) "Cet appareil n'est pas marqué « Parents » dans Vision."
                         else "Home Assistant a répondu ${e.code}."
                principal.post { dessiner() }
            } catch (_: Exception) {
                erreur = "Home Assistant injoignable."
                principal.post { dessiner() }
            } finally { chargement = false }
        }.start()
    }

    // ------------------------------------------------------------ Écran

    private fun dessiner() {
        racine.removeAllViews()
        racine.addView(Ui.marque(this))
        val r = Ui.rangee(this)
        val col = Ui.colonne(this)
        col.addView(Ui.titre(this, "La maison"))
        col.addView(Ui.sousTitre(this, "Les appareils des enfants, en direct"))
        r.addView(Ui.marge(this, Ui.poids(col), gauche = 2f))
        r.addView(Ui.boutonSecondaire(this, "↻") { charger() })
        racine.addView(Ui.marge(this, r, bas = 18f))

        if (erreur.isNotEmpty()) {
            val c = Ui.carte(this, Ui.CARTE_HAUTE)
            c.addView(Ui.texte(this, erreur, 14f, Ui.ROUGE))
            racine.addView(c)
        }
        if (demandes.length() > 0) {
            racine.addView(Ui.section(this, "Demandes d'accès"))
            for (i in 0 until demandes.length()) {
                val d = demandes.optJSONObject(i) ?: continue
                val c = Ui.carte(this, Ui.CARTE_HAUTE)
                c.addView(Ui.texte(this, "${d.optString("prenom")} demande ${d.optString("libelle")}", 16f, Ui.TEXTE, gras = true))
                c.addView(Ui.marge(this, Ui.texte(this, if (d.optString("genre") == "apps") "Application" else "Site : ${d.optString("cle")}", 13f, Ui.TEXTE_2), haut = 4f))
                val lien = d.optString("lien"); val motif = d.optString("motif")
                if (lien.isNotEmpty()) c.addView(Ui.marge(this, Ui.texte(this, lien, 13f, Ui.OR).apply {
                    setOnClickListener { try { startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(if (lien.contains("://")) lien else "https://$lien"))) } catch (_: Exception) {} }
                }, haut = 4f))
                if (motif.isNotEmpty()) c.addView(Ui.marge(this, Ui.texte(this, "« $motif »", 13f, Ui.TEXTE_2), haut = 4f))
                d.optString("raison").takeIf { it.isNotEmpty() }?.let { c.addView(Ui.marge(this, Ui.texte(this, "Fermé car : $it", 13f, Ui.TEXTE_3), haut = 6f)) }
                val duree = d.optString("duree")
                val etiquettes = d.optJSONArray("etiquettes")?.let { a -> (0 until a.length()).map { a.optString(it) }.filter { it.isNotEmpty() } }.orEmpty()
                val souhait = when (duree) { "1h" -> "1 heure"; "toujours" -> "en permanence (quand l'écran est ouvert)"; "categorie" -> "toute la catégorie" + (if (etiquettes.isNotEmpty()) " (${etiquettes.joinToString(", ")})" else ""); else -> "" }
                if (souhait.isNotEmpty()) c.addView(Ui.marge(this, Ui.texte(this, "Souhait : $souhait", 13f, Ui.OR), haut = 6f))
                val r = Ui.rangee(this)
                val pc = d.optString("pc"); val id = d.optString("id")
                fun choix(t: String, principal: Boolean, action: () -> Unit) = if (principal) Ui.boutonPrimaire(this, t, action) else Ui.boutonSecondaire(this, t, action)
                r.addView(Ui.poids(choix("1 h", duree == "1h" || duree.isEmpty()) { repondreAcces(pc, id, "temporaire", 60) }))
                r.addView(Ui.marge(this, Ui.poids(choix("Exception", duree == "toujours" || duree.isEmpty()) { repondreAcces(pc, id, "toujours") }), gauche = 8f))
                r.addView(Ui.marge(this, Ui.poids(Ui.boutonDanger(this, "Non") { repondreAcces(pc, id, "non") }), gauche = 8f))
                c.addView(Ui.marge(this, r, haut = 14f))
                if (etiquettes.isNotEmpty()) c.addView(Ui.marge(this, choix("Toute la catégorie : ${etiquettes.joinToString(", ")}", duree == "categorie") { repondreAcces(pc, id, "categorie") }, haut = 8f))
                if (d.optString("genre") == "apps") c.addView(Ui.marge(this, Ui.boutonSecondaire(this, "Toujours disponible, même pendant les coupures") { repondreAcces(pc, id, "exception") }, haut = 8f))
                c.addView(Ui.marge(this, Ui.texte(this, "Exception : autorisé même si sa catégorie est fermée, coupé pendant les plages de coupure.", 12f, Ui.TEXTE_3), haut = 6f))
                c.addView(Ui.marge(this, Ui.boutonSecondaire(this, "Autre durée…") {
                    AlertDialog.Builder(this).setTitle("Ouvrir ${d.optString("libelle")} pour…")
                        .setItems(arrayOf("15 minutes", "30 minutes", "2 heures", "Jusqu'à ce soir (6 h)")) { _, k ->
                            repondreAcces(pc, id, "temporaire", listOf(15, 30, 120, 360)[k]) }
                        .setNegativeButton("Annuler", null).show()
                }, haut = 8f))
                racine.addView(c)
            }
            racine.addView(Ui.section(this, "Appareils"))
        }
        var vus = 0
        for (i in 0 until appareils.length()) {
            val a = appareils.optJSONObject(i) ?: continue
            if (a.optBoolean("parent")) continue
            vus++
            racine.addView(carteAppareil(a))
        }
        if (vus == 0 && erreur.isEmpty()) {
            racine.addView(Ui.carte(this).apply {
                addView(Ui.texte(this@ParentsActivity, if (appareils.length() == 0) "Chargement…" else "Aucun appareil d'enfant.", 14f, Ui.TEXTE_2))
            })
        }
        racine.addView(Ui.espace(this, 24f))
    }

    private fun carteAppareil(a: JSONObject): View {
        val id = a.optString("id")
        val enLigne = a.optBoolean("en_ligne")
        val ferme = a.optBoolean("verrouille")
        val derog = a.optJSONObject("derogation")
        val maintenant = System.currentTimeMillis()
        val prochain = Etat.lireDate(a.optString("prochain"))
        val prochainVerrou = Etat.lireDate(a.optString("prochain_verrou"))

        val c = Ui.carte(this, Ui.CARTE_HAUTE)
        val haut = Ui.rangee(this)
        val col = Ui.colonne(this)
        val prenom = a.optString("prenom")
        col.addView(Ui.texte(this, prenom.ifEmpty { a.optString("nom") }, 20f, Ui.TEXTE, gras = true))
        col.addView(Ui.texte(this, if (prenom.isEmpty()) (if (a.optBoolean("android")) "Android" else "PC")
                                   else a.optString("nom"), 13f, Ui.TEXTE_2))
        haut.addView(Ui.poids(col))
        val (lib, coul) = when {
            !enLigne -> "Hors ligne" to Ui.TEXTE_2
            ferme -> "Fermé" to Ui.ROUGE
            else -> "Ouvert" to Ui.VERT
        }
        haut.addView(Ui.chip(this, lib, coul))
        c.addView(haut)

        // Ce qui vient.
        val detail = when {
            derog != null && derog.optLong("fin") > 0 ->
                (if (derog.optString("mode") == "locked") "Fermé par un parent" else "Ouvert par un parent") +
                " jusqu'à ${Etat.heure(derog.optLong("fin") * 1000)}."
            derog != null -> if (derog.optString("mode") == "locked") "Fermé par un parent jusqu'au prochain créneau." else "Ouvert par un parent jusqu'au prochain créneau."
            ferme && prochain > maintenant -> "Réouverture à ${Etat.heure(prochain)}."
            ferme -> "Fermé par le planning."
            prochainVerrou > maintenant -> "Fermeture prévue à ${Etat.heure(prochainVerrou)}."
            else -> "Aucune fermeture prévue."
        }
        c.addView(Ui.marge(this, Ui.texte(this, detail, 14f, Ui.TEXTE_2), haut = 10f))

        // Activité et temps d'écran.
        val focus = a.optString("focus_libelle").ifEmpty { a.optString("focus") }
        val inactif = a.optInt("inactif_s")
        if (enLigne && focus.isNotEmpty()) {
            val act = if (inactif > 300) "Inactif depuis ${inactif / 60} min (dernier : $focus)" else "En ce moment : $focus"
            c.addView(ligneInfo("Activité", act))
        }
        val u = a.optJSONObject("usage")
        if (u != null) c.addView(ligneInfo("Écran aujourd'hui", duree(u.optInt("actif")) + " sur " + duree(u.optInt("ouvert")) + " d'ouverture"))

        // Étiquettes coupées sur cet appareil.
        val et = a.optJSONArray("etiquettes")
        if (et != null && et.length() > 0) {
            val flux = Ui.rangee(this).apply { gravity = Gravity.START }
            val scroll = android.widget.HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false }
            for (k in 0 until et.length()) flux.addView(Ui.marge(this, Ui.chip(this, et.optString(k), Ui.OR), droite = 6f))
            scroll.addView(flux)
            c.addView(Ui.marge(this, scroll, haut = 10f))
        }

        // Ce qui est fermé : un écran propre, rangé par motif.
        val nApps = a.optJSONArray("apps")?.length() ?: 0
        val nSites = (a.optJSONArray("sites")?.let { arr -> (0 until arr.length()).count { (arr.optJSONObject(it)?.optString("nom") ?: "").count { ch -> ch == '.' } == 1 } }) ?: 0
        c.addView(Ui.separateur(this))
        val rB = Ui.rangee(this)
        rB.addView(Ui.poids(Ui.boutonSecondaire(this, "Catégories") {
            CategoriesActivity.fiche = a; CategoriesActivity.cats = categories
            startActivity(Intent(this, CategoriesActivity::class.java))
        }))
        rB.addView(Ui.marge(this, Ui.poids(Ui.boutonSecondaire(this, "Fermé : $nApps + $nSites") {
            DetailFermesActivity.fiche = a
            startActivity(Intent(this, DetailFermesActivity::class.java))
        }), gauche = 8f))
        c.addView(Ui.marge(this, rB, haut = 8f))
        // Les exceptions de la personne : ce qui est autorisé ou fermé à part, nom par nom.
        val ex = a.optJSONObject("exceptions")
        val nEx = (ex?.optJSONArray("autorises")?.length() ?: 0) + (ex?.optJSONArray("bloques")?.length() ?: 0) + (ex?.optJSONArray("toujours")?.let { t -> (0 until t.length()).count { t.optJSONObject(it)?.optBoolean("maison") != true } } ?: 0)
        c.addView(Ui.marge(this, Ui.boutonSecondaire(this, if (nEx > 0) "Autorisations : $nEx" else "Autorisations") {
            ExceptionsActivity.fiche = a; ExceptionsActivity.cats = categories
            startActivity(Intent(this, ExceptionsActivity::class.java))
        }, haut = 8f))
        c.addView(planning(id, a.optJSONArray("plages")))

        // Actions.
        val r1 = Ui.rangee(this)
        r1.addView(Ui.poids(Ui.boutonPrimaire(this, "+30 min") { charger("ouvrir", id, 30) }))
        r1.addView(Ui.marge(this, Ui.poids(Ui.boutonPrimaire(this, "+1 h") { charger("ouvrir", id, 60) }), gauche = 8f))
        r1.addView(Ui.marge(this, Ui.poids(Ui.boutonDanger(this, "Fermer") { confirmerFermeture(id, prenom.ifEmpty { a.optString("nom") }) }), gauche = 8f))
        c.addView(Ui.marge(this, r1, haut = 14f))
        val r2 = Ui.rangee(this)
        if (derog != null) r2.addView(Ui.poids(Ui.boutonSecondaire(this, "Retour au planning") { charger("annuler", id) }))
        r2.addView(Ui.marge(this, Ui.poids(Ui.boutonSecondaire(this, "Envoyer un mot") { envoyerMot(id, prenom.ifEmpty { a.optString("nom") }) }),
            gauche = if (derog != null) 8f else 0f))
        c.addView(Ui.marge(this, r2, haut = 8f))
        return c
    }

    private fun repliable(cle: String, titre: String, liste: JSONArray?, libelle: (JSONObject) -> String): View {
        val n = liste?.length() ?: 0
        val bloc = Ui.colonne(this)
        val ouvert = cle in deplies
        val entete = Ui.rangee(this)
        entete.addView(Ui.poids(Ui.texte(this, "$titre ($n)", 14f, if (n > 0) Ui.TEXTE else Ui.TEXTE_3, gras = true)))
        entete.addView(Ui.texte(this, if (ouvert) "▴" else "▾", 14f, Ui.TEXTE_2))
        entete.setPadding(0, Ui.dp(this, 8f), 0, Ui.dp(this, 8f))
        entete.isClickable = n > 0
        entete.setOnClickListener { if (ouvert) deplies.remove(cle) else deplies.add(cle); dessiner() }
        bloc.addView(Ui.separateur(this))
        bloc.addView(entete)
        if (ouvert && liste != null) {
            val noms = (0 until liste.length()).mapNotNull { liste.optJSONObject(it)?.let(libelle) }.filter { it.isNotEmpty() }
            bloc.addView(Ui.marge(this, Ui.texte(this, noms.joinToString(" · "), 13f, Ui.TEXTE_2), bas = 6f))
        }
        return bloc
    }

    private fun planning(id: String, plages: JSONArray?): View {
        val bloc = Ui.colonne(this)
        bloc.addView(Ui.separateur(this))
        val cle = "$id:plages"
        val ouvert = cle in deplies
        val n = plages?.length() ?: 0
        val entete = Ui.rangee(this)
        entete.addView(Ui.poids(Ui.texte(this, "Planning ($n)", 14f, if (n > 0) Ui.TEXTE else Ui.TEXTE_3, gras = true)))
        entete.addView(Ui.texte(this, if (ouvert) "▴" else "▾", 14f, Ui.TEXTE_2))
        entete.setPadding(0, Ui.dp(this, 8f), 0, Ui.dp(this, 8f))
        entete.setOnClickListener { if (ouvert) deplies.remove(cle) else deplies.add(cle); dessiner() }
        bloc.addView(entete)
        if (!ouvert || plages == null) return bloc
        val jours = listOf("L", "M", "M", "J", "V", "S", "D")
        for (i in 0 until plages.length()) {
            val p = plages.optJSONObject(i) ?: continue
            val actif = p.optBoolean("actif")
            val activee = p.optBoolean("active", true)
            val r = Ui.rangee(this)
            val col = Ui.colonne(this)
            val quoi = when (p.optString("portee")) {
                "etiquettes" -> {
                    val e = p.optJSONArray("etiquettes")
                    "Coupe : " + (0 until (e?.length() ?: 0)).joinToString(", ") { e!!.optString(it) }
                }
                "elements" -> "Coupe des applis ou sites précis"
                else -> "Ferme tout l'appareil"
            }
            val js = p.optJSONArray("jours")
            val lettres = (0 until 7).joinToString(" ") { if (js?.optBoolean(it, true) != false) jours[it] else "·" }
            col.addView(Ui.texte(this, "${p.optString("nom").ifEmpty { "Plage" }}  ${p.optString("debut")} → ${p.optString("fin")}",
                14f, if (!activee) Ui.TEXTE_3 else if (actif) Ui.OR else Ui.TEXTE, gras = actif))
            col.addView(Ui.texte(this, "$quoi   $lettres", 12f, Ui.TEXTE_2))
            r.addView(Ui.poids(col))
            if (actif) r.addView(Ui.chip(this, "en cours", Ui.OR))
            else if (!activee) r.addView(Ui.chip(this, "désactivée", Ui.TEXTE_3))
            bloc.addView(Ui.marge(this, r, haut = 4f, bas = 6f))
        }
        return bloc
    }

    private fun repondreAcces(pc: String, demande: String, decision: String, minutes: Int = 60) {
        Acces.repondre(this, pc, demande, decision, minutes) { charger() }
    }

    private fun confirmerFermeture(id: String, nom: String) {
        AlertDialog.Builder(this)
            .setTitle("Fermer l'appareil de $nom ?")
            .setItems(arrayOf("30 minutes", "1 heure", "Jusqu'au prochain créneau du planning")) { _, k ->
                charger("fermer", id, listOf(30, 60, 0)[k])
            }
            .setNegativeButton("Annuler", null)
            .show()
    }

    private fun envoyerMot(id: String, nom: String) {
        val champ = Ui.champ(this, "Ex. : à table dans 10 minutes", "")
        val cadre = Ui.colonne(this, Ui.dp(this, 20f)).apply { addView(champ) }
        AlertDialog.Builder(this)
            .setTitle("Un mot pour $nom")
            .setView(cadre)
            .setPositiveButton("Envoyer") { _, _ ->
                val t = champ.text.toString().trim()
                if (t.isNotEmpty()) charger("message", id, 0, t)
            }
            .setNegativeButton("Annuler", null)
            .show()
    }

    private fun ligneInfo(cle: String, valeur: String): View {
        val r = Ui.rangee(this)
        r.addView(Ui.poids(Ui.texte(this, cle, 13f, Ui.TEXTE_2)))
        r.addView(Ui.texte(this, valeur, 13f, Ui.TEXTE, gras = true).apply {
            gravity = Gravity.END
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.8f)
        })
        return Ui.marge(this, r, haut = 4f, bas = 2f)
    }

    private fun duree(min: Int): String = if (min < 60) "$min min" else "${min / 60} h ${"%02d".format(min % 60)}"
    private fun toast(t: String) = Toast.makeText(this, t, Toast.LENGTH_LONG).show()
}
