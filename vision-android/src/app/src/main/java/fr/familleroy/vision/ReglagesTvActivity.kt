package fr.familleroy.vision

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.app.UiModeManager
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/**
 * Les réglages Vision de l'appareil : tout se décide ici, sur l'appareil.
 *
 * Tableaux de l'écran de veille : ceux de l'appli, ceux composés dans Home
 * Assistant et ceux composés ici (bouton « + Tableau »), chacun avec son
 * interrupteur et sa durée. Source du son, mode nuit, thème, couleurs à la
 * carte, bulle, applications visibles.
 *
 * Au pavé : chaque interrupteur, chaque − et chaque + est une case à part,
 * gauche et droite passent de l'une à l'autre, puis à la colonne de droite.
 * Sur un téléphone, une seule colonne.
 */
class ReglagesTvActivity : Activity() {
    private val main = Handler(Looper.getMainLooper())
    private lateinit var cfg: Config
    private var theme: Theme = Themes.liste[0]
    private var reglages: JSONObject? = null
    private var tableauxHA: JSONArray? = null
    private lateinit var racine: ScrollView
    private lateinit var contenu: LinearLayout
    private var focusTag: String? = null
    private var enCharge = false
    private val tele by lazy { estTele(this) }

    companion object {
        fun estTele(ctx: Context): Boolean {
            val ui = ctx.getSystemService(Context.UI_MODE_SERVICE) as? UiModeManager
            return ui?.currentModeType == Configuration.UI_MODE_TYPE_TELEVISION || ctx.packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cfg = Config(this)
        if (tele) window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        racine = ScrollView(this).apply { isVerticalScrollBarEnabled = false }
        contenu = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        racine.addView(contenu)
        setContentView(racine)
        charger()
    }

    override fun onResume() { super.onResume(); appliquerTheme(); construire() }

    private fun px(dp: Float) = Ui.dp(this, dp)
    private val dm get() = resources.displayMetrics
    private fun t(pxMaquette: Float): Float = if (tele) pxMaquette * (dm.heightPixels / dm.density) / 1080f else pxMaquette * 0.62f

    private fun texte(s: String, taille: Float, couleur: Int, police: android.graphics.Typeface = Polices.texte(this), espacement: Float = 0f): TextView =
        TextView(this).apply { text = s; textSize = taille; setTextColor(couleur); typeface = police; letterSpacing = espacement }

    private fun fondCarte(rayonDp: Float, couleur: Int = theme.carte, bord: Int = theme.carteBord, epaisseurDp: Float = 1f): GradientDrawable =
        GradientDrawable().apply { cornerRadius = px(rayonDp).toFloat(); setColor(couleur); setStroke(px(epaisseurDp), bord) }

    private fun section(s: String): TextView = texte(s.uppercase(Locale.FRANCE), t(18f), theme.encre2, Polices.gras(this), 0.22f).apply { setPadding(0, px(16f), 0, px(8f)) }

    private fun focusable(v: View, tag: String, rayon: Float = 18f) {
        v.isFocusable = true; v.isClickable = true; v.tag = tag
        v.background = fondCarte(rayon)
        v.setOnFocusChangeListener { x, a -> x.background = if (a) fondCarte(rayon, bord = theme.or, epaisseurDp = 1.5f) else fondCarte(rayon); if (a) focusTag = tag }
    }

    private fun trouver(v: View, tag: String): View? {
        if (v.tag == tag) return v
        if (v is ViewGroup) for (i in 0 until v.childCount) trouver(v.getChildAt(i), tag)?.let { return it }
        return null
    }

    private fun repeindre() { construire(); focusTag?.let { tag -> racine.post { trouver(contenu, tag)?.requestFocus() } } }

    // ------------------------------------------------------------------ construction

    private fun construire() {
        contenu.removeAllViews()
        racine.setBackgroundColor(theme.fond)
        if (!tele) { window.navigationBarColor = theme.fond; window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LAYOUT_STABLE or (if (!theme.sombre) View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR else 0) }
        val mx = if (tele) (dm.widthPixels * 0.05f).toInt() else px(18f); val my = if (tele) (dm.heightPixels * 0.05f).toInt() else px(40f)
        contenu.setPadding(mx, my, mx, my)

        // La marque au milieu en haut, puis le titre et la durée d'un tour.
        val marque = LinearLayout(this).apply { gravity = Gravity.CENTER }
        marque.addView(ImageView(this).apply { setImageResource(R.drawable.ic_vision) }, LinearLayout.LayoutParams(px(t(40f)), px(t(40f))))
        marque.addView(texte("VISION", t(22f), theme.or, Polices.gras(this), 0.28f).apply { setPadding(px(8f), 0, 0, 0) })
        contenu.addView(marque, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        val tete = LinearLayout(this).apply { gravity = Gravity.BOTTOM; setPadding(0, px(10f), 0, 0) }
        tete.addView(texte("Réglages de l'appareil", t(44f), theme.encre, Polices.outfit(this)).apply { includeFontPadding = false }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val liste = listeTableaux()
        var total = 0; var actifs = 0
        liste.forEach { if (it.actif) { total += it.duree; actifs++ } }
        tete.addView(texte(if (liste.isEmpty()) "…" else "Un tour : ${total / 60} min ${String.format(Locale.FRANCE, "%02d", total % 60)} s · $actifs tableaux", t(22f), theme.encre2))
        contenu.addView(tete)

        val colonnes = LinearLayout(this).apply { orientation = if (tele) LinearLayout.HORIZONTAL else LinearLayout.VERTICAL; setPadding(0, px(10f), 0, 0) }
        contenu.addView(colonnes)
        val gauche = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val droite = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        if (tele) {
            colonnes.addView(gauche, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.25f).apply { rightMargin = px(24f) })
            colonnes.addView(droite, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        } else { colonnes.addView(gauche); colonnes.addView(droite) }

        // --- Écran de veille : ce qu'il montre, comment, quand -------------------------------
        gauche.addView(section("Écran de veille"))
        if (liste.isEmpty()) gauche.addView(texte("Chargement…", t(20f), theme.encre3))
        liste.forEach { gauche.addView(rangTableau(it), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { bottomMargin = px(8f) }) }
        gauche.addView(texte("Les tableaux de bord rendus disponibles dans Home Assistant. Ici, cet appareil choisit ceux qu'il montre, leur durée et, en appuyant sur un nom, leurs cartes.", t(17f), theme.encre3).apply { setPadding(px(4f), px(2f), 0, px(10f)) })
        val releve = Local.listeWebA(this)
        gauche.addView(ligne("Actualiser les tableaux", if (enCharge) "Relevé en cours…" else if (releve > 0) "Relevé à " + java.text.SimpleDateFormat("HH:mm", Locale.FRANCE).format(java.util.Date(releve)) else "maintenant", "actualiser") { charger() })
        val web = Local.veilleWeb(this)
        gauche.addView(ligne("Cartes affichées", if (web) "Celles de Home Assistant" else "Dessin simplifié", "veille_web") { Local.poserVeilleWeb(this, !web); repeindre() })
        if (web) {
            val styles = Local.STYLES
            val style = Local.styleCartes(this)
            gauche.addView(ligne("Style des cartes", styles.first { it.first == style }.second, "style") { Local.poserStyleCartes(this, styles[(styles.indexOfFirst { it.first == style } + 1) % styles.size].first); repeindre() })
            gauche.addView(ligne("Fond sous les cartes", if (Local.fondCartes(this)) "Oui" else "Non", "fond_cartes") { Local.poserFondCartes(this, !Local.fondCartes(this)); repeindre() })
            gauche.addView(ligne("Contour des cartes", if (Local.contourCartes(this)) "Oui" else "Non", "contour_cartes") { Local.poserContourCartes(this, !Local.contourCartes(this)); repeindre() })
        }
        if (tele) {
            val delai = Local.delaiVeille(this)
            val libelle = if (delai == 0) "Réglage de la télé" else "$delai min sans télécommande" + (if (Local.peutEcrireSysteme(this)) "" else " (accueil Vision seulement)")
            gauche.addView(ligne("Démarre après", libelle, "delai") {
                val l = Local.DELAIS_VEILLE
                Local.poserDelaiVeille(this, l[(l.indexOf(delai) + 1) % l.size]); repeindre()
            })
        }
        gauche.addView(ligne("Applis qui continuent en fond", "${Local.fond(this).size} choisie${if (Local.fond(this).size > 1) "s" else ""}", "fond") { choisirFond() })
        gauche.addView(ligne("Voir l'écran de veille", "maintenant", "veille") { Veille.ouvrir(this) })

        // --- Apparence : les couleurs de tout l'appareil ---------------------------------------
        droite.addView(section("Apparence"))
        droite.addView(ligne("Thème de couleurs", Local.theme(this), "theme") { choisirTheme() })
        droite.addView(ligne("Couleurs à la carte", if (Palette.personnalisee(this, Palette.LANCEUR) || Palette.personnalisee(this, Palette.APPLI)) "Personnalisées" else "Celles du thème", "couleurs") { startActivity(Intent(this, CouleursActivity::class.java)) })
        val nuit = Local.nuit(this)
        droite.addView(ligne("Mode nuit", if (nuit.isEmpty()) "Jamais" else "Sombre et sans son de ${nuit.replace("-", " à ")}", "nuit") { Local.poserNuit(this, Local.PLAGES_NUIT[(Local.PLAGES_NUIT.indexOf(nuit) + 1) % Local.PLAGES_NUIT.size]); repeindre() })

        // --- Son de la veille -----------------------------------------------------------------
        droite.addView(section("Son pendant la veille"))
        val musique = Local.musique(this)
        val radioCourante = Local.RADIOS.firstOrNull { it.second == musique }
        val perso = getSharedPreferences("local", MODE_PRIVATE).getString("flux_perso", "") ?: ""
        if (musique.isNotEmpty() && radioCourante == null && musique != perso) getSharedPreferences("local", MODE_PRIVATE).edit().putString("flux_perso", musique).apply()
        droite.addView(ligne("Source du son", when { musique.isEmpty() -> "Silence"; radioCourante != null -> radioCourante.first.substringBefore(" ·"); else -> "Flux personnalisé" }, "son") { choisirSon() })
        droite.addView(texte("Si une autre appli joue déjà (Spotify, YouTube Music…), l'écran de veille la laisse.", t(17f), theme.encre3).apply { setPadding(px(4f), 0, 0, px(6f)) })

        // --- Accueil -------------------------------------------------------------------------
        droite.addView(section("Accueil"))
        val toutes = Accueil.applicationsInstallees(this).size
        droite.addView(ligne("Applications visibles", "${toutes - Accueil.masquees(this).size} sur $toutes", "applis") { choisirApplis() })
        droite.addView(ligne("Bulle Vision par-dessus la musique", if (!Bulle.activee(this)) "Rangée" else if (Bulle.permise(this)) "Active" else "Permission à donner", "bulle") {
            if (!Bulle.permise(this)) { try { startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))) } catch (_: Exception) {} }
            else { Bulle.poser(this, !Bulle.activee(this)); repeindre() }
        })
        if (tele) {
            droite.addView(ligne("Vision à la place de l'accueil", if (Local.accueilForce(this)) "Oui (touche Accueil)" else "Non, accueil de la télé", "accueil_force") {
                Local.poserAccueilForce(this, !Local.accueilForce(this)); repeindre()
            })
        } else {
            val pages = Accueil.mode(this) == Accueil.MODE_PAGES
            droite.addView(ligne("Disposition", if (pages) "Des pages à feuilleter" else "Une grille qui défile", "mode") { Accueil.poserMode(this, if (pages) Accueil.MODE_DEFILEMENT else Accueil.MODE_PAGES); repeindre() })
            droite.addView(ligne("Écran de verrouillage Vision", if (Local.verrou(this)) "Au réveil de l'écran" else "Désactivé", "verrou") {
                Local.poserVerrou(this, !Local.verrou(this)); AgentService.demarrer(this); repeindre()
            })
            droite.addView(ligne("Voir l'écran de verrouillage", "maintenant", "verrou_voir") { VerrouActivity.montrer(this) })
        }

        // --- Vision : le compte, la connexion, l'appareil ---------------------------------------
        droite.addView(section("Vision"))
        droite.addView(ligne("Connexion, personne, parents", "ouvrir", "appli") { startActivity(Intent(this, SetupActivity::class.java)) })
        if (tele) droite.addView(ligne("Accueil d'origine de la télé", "ouvrir", "origine") { Accueil.accueilSysteme(this)?.let { try { startActivity(it) } catch (_: Exception) {} } })

        contenu.addView(texte(if (tele) "OK : afficher ou masquer, − et + : durée · Retour : fermer · Deux appuis sur Accueil : l'écran de veille par-dessus la musique" else "", t(18f), theme.encre3).apply { setPadding(0, px(18f), 0, 0) })
            Ui.laisserDeborder(racine)
}

    // ------------------------------------------------------------------ tableaux

    private class Ligne(val cle: String, val nom: String, val actif: Boolean, val duree: Int, val local: JSONObject?, val cartes: JSONArray? = null)

    /** Les tableaux connus : ceux de Home Assistant (ordre et défauts), puis ceux de l'appareil ; l'appareil a le dernier mot. */
    private fun listeTableaux(): List<Ligne> {
        val sortie = ArrayList<Ligne>()
        val ha = tableauxHA
        if (ha != null) for (i in 0 until ha.length()) {
            val o = ha.getJSONObject(i)
            val cle = Local.cleTableau(o.optString("code"), o.optString("id"))
            // Avec les vraies cartes de Home Assistant, la liste est celle de la page de veille (cartes de la communauté comprises).
            val cartes = (if (Local.veilleWeb(this) && o.optString("code") == "dash") cartesWeb(o.optString("id")) else null) ?: o.optJSONArray("cartes")
            val montrees = if (cartes == null) 0 else { val m = Local.cartesMasquees(this, cle); (0 until cartes.length()).count { !masquee(cartes.getJSONObject(it), m) } }
            val nom = if (cartes == null) o.optString("nom") else "${o.optString("nom")}  · $montrees/${cartes.length()} cartes"
            sortie.add(Ligne(cle, nom, Local.actif(this, cle, o.optBoolean("actif", true)), Local.duree(this, cle, o.optInt("duree", 20)), null, cartes))
        } else {
            // Sans Home Assistant : les tableaux de l'appli, dans l'ordre d'origine.
            sortie.add(Ligne("horloge", "Horloge", Local.actif(this, "horloge", true), Local.duree(this, "horloge", 20), null))
        }
        return sortie
    }

    private fun cartesWeb(id: String): JSONArray? {
        val l = Local.listeWeb(this)
        for (i in 0 until l.length()) if (l.getJSONObject(i).optString("id") == id) return l.getJSONObject(i).optJSONArray("cartes")
        return null
    }

    /** Une carte est masquée si sa clé l'est, ou si tous ses éléments le sont (choix faits avant les vraies cartes). */
    private fun masquee(carte: JSONObject, m: Set<String>): Boolean {
        if (carte.optString("cle") in m) return true
        val cles = carte.optJSONArray("cles") ?: return false
        return cles.length() > 0 && (0 until cles.length()).all { cles.optString(it) in m }
    }

    /** Une ligne de tableau : interrupteur, nom, − durée + ; trois cases focusables. */
    private fun rangTableau(l: Ligne): View {
        val rang = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(px(10f), px(6f), px(10f), px(6f)); background = fondCarte(22f) }
        val bascule = FrameLayout(this).apply { setPadding(px(8f), px(6f), px(8f), px(6f)) }
        val fondB = GradientDrawable().apply { cornerRadius = px(22f).toFloat(); setColor(if (l.actif) theme.or else Palette.melanger(theme.carte, theme.encre, 0.12f)) }
        val piste = FrameLayout(this).apply { background = fondB }
        piste.addView(View(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(if (l.actif) theme.fond else theme.encre2) } },
            FrameLayout.LayoutParams(px(24f), px(24f), (if (l.actif) Gravity.END else Gravity.START) or Gravity.CENTER_VERTICAL).apply { setMargins(px(4f), 0, px(4f), 0) })
        bascule.addView(piste, FrameLayout.LayoutParams(px(58f), px(32f)))
        focusable(bascule, "b_" + l.cle, 22f); bascule.background = fondCarte(22f, couleur = 0, bord = 0)
        bascule.setOnFocusChangeListener { x, a -> x.background = fondCarte(22f, couleur = 0, bord = if (a) theme.or else 0, epaisseurDp = 1.5f); if (a) focusTag = "b_" + l.cle }
        bascule.setOnClickListener { Local.poserTableau(this, l.cle, actif = !l.actif); repeindre() }
        rang.addView(bascule, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { rightMargin = px(8f) })
        val nom = texte(l.nom, t(26f), theme.encre, Polices.moyen(this)).apply { alpha = if (l.actif) 1f else 0.45f; maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END; setPadding(px(6f), px(8f), px(6f), px(8f)) }
        if (l.local != null) {
            nom.isClickable = true; nom.isLongClickable = true
            nom.setOnLongClickListener { menuLocal(l.local); true }
            nom.setOnClickListener { menuLocal(l.local) }
        }
        if (l.cartes != null) {
            focusable(nom, "c_" + l.cle, 18f)
            nom.setOnClickListener { choisirCartes(l) }
        }
        rang.addView(nom, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        fun pas(signe: String, tag: String, action: () -> Unit): View = texte(signe, t(28f), theme.encre, Polices.outfit(this)).apply {
            gravity = Gravity.CENTER
            focusable(this, tag, 24f); background = fondCarte(24f, couleur = 0)
            setOnFocusChangeListener { x, a -> x.background = fondCarte(24f, couleur = if (a) theme.carte else 0, bord = if (a) theme.or else theme.carteBord, epaisseurDp = if (a) 1.5f else 1f); if (a) focusTag = tag }
            setOnClickListener { action() }
        }
        rang.addView(pas("−", "m_" + l.cle) { Local.poserTableau(this, l.cle, duree = l.duree - 5); repeindre() }, LinearLayout.LayoutParams(px(40f), px(40f)))
        rang.addView(texte("${l.duree} s", t(24f), theme.encre, Polices.demiGras(this)).apply { gravity = Gravity.CENTER; alpha = if (l.actif) 1f else 0.45f }, LinearLayout.LayoutParams(px(64f), ViewGroup.LayoutParams.WRAP_CONTENT))
        rang.addView(pas("+", "p_" + l.cle) { Local.poserTableau(this, l.cle, duree = l.duree + 5); repeindre() }, LinearLayout.LayoutParams(px(40f), px(40f)))
        return rang
    }

    /** Les cartes d'un tableau de bord : cocher celles que cet appareil montre. */
    private fun choisirCartes(l: Ligne) {
        val cartes = l.cartes ?: return
        // Masquer une carte, c'est retenir sa clé et celles de ses éléments : la page de veille et le dessin simplifié s'y retrouvent.
        val cles = (0 until cartes.length()).map { i -> val o = cartes.getJSONObject(i); val a = o.optJSONArray("cles"); listOf(o.optString("cle")) + (0 until (a?.length() ?: 0)).map { a!!.optString(it) } }
        val noms = (0 until cartes.length()).map { val o = cartes.getJSONObject(it); val s = o.optString("section"); if (s.isEmpty()) o.optString("nom") else "$s · ${o.optString("nom")}" }
        val masquees = Local.cartesMasquees(this, l.cle)
        val coches = BooleanArray(cles.size) { !masquee(cartes.getJSONObject(it), masquees) }
        AlertDialog.Builder(this).setTitle(l.nom.substringBefore("  ·"))
            .setMultiChoiceItems(noms.toTypedArray(), coches) { _, i, c -> coches[i] = c }
            .setPositiveButton("Valider") { _, _ -> Local.poserCartesMasquees(this, l.cle, cles.filterIndexed { i, _ -> !coches[i] }.flatten().distinct()); repeindre() }
            .setNegativeButton("Annuler", null).show()
    }

    private fun menuLocal(t: JSONObject) {
        AlertDialog.Builder(this).setTitle(t.optString("titre")).setItems(arrayOf("Modifier", "Supprimer")) { _, k ->
            if (k == 0) startActivity(Intent(this, TableauEditeurActivity::class.java).putExtra("id", t.optString("id")))
            else { Local.supprimerLocal(this, t.optString("id")); repeindre() }
        }.show()
    }

    /** Une ligne focusable : titre à gauche, valeur à droite, liseré d'or au focus. */
    private fun ligne(titre: String, valeur: String, tag: String, action: () -> Unit): View {
        val r = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(px(18f), px(12f), px(18f), px(12f)) }
        r.addView(texte(titre, t(22f), theme.encre, Polices.moyen(this)), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        r.addView(texte(valeur, t(20f), theme.encre2, Polices.demiGras(this)).apply { maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END; maxWidth = (dm.widthPixels * (if (tele) 0.22f else 0.45f)).toInt() })
        focusable(r, tag, 18f)
        r.setOnClickListener { action() }
        r.layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { bottomMargin = px(8f) }
        return r
    }

    /** Le thème de couleurs : une liste où l'on choisit, plutôt qu'un bouton à presser dix-neuf fois. */
    private fun choisirTheme() {
        val noms = Themes.liste.map { it.nom }
        AlertDialog.Builder(this).setTitle("Thème de couleurs")
            .setSingleChoiceItems(noms.toTypedArray(), noms.indexOf(Local.theme(this)).coerceAtLeast(0)) { d, k -> Local.poserTheme(this, noms[k]); appliquerTheme(); d.dismiss(); repeindre() }
            .setNegativeButton("Annuler", null).show()
    }

    /** Le son de la veille : une radio, un flux à soi, ou le silence. */
    private fun choisirSon() {
        val musique = Local.musique(this)
        val perso = getSharedPreferences("local", MODE_PRIVATE).getString("flux_perso", "") ?: ""
        val noms = listOf("Silence") + Local.RADIOS.map { it.first } + listOf(if (perso.isEmpty()) "Flux personnalisé…" else "Flux personnalisé : ${perso.take(40)}")
        val courant = when { musique.isEmpty() -> 0; else -> Local.RADIOS.indexOfFirst { it.second == musique }.let { if (it >= 0) it + 1 else noms.size - 1 } }
        AlertDialog.Builder(this).setTitle("Son pendant la veille")
            .setSingleChoiceItems(noms.toTypedArray(), courant) { d, k ->
                d.dismiss()
                when {
                    k == 0 -> { Local.poserMusique(this, ""); repeindre() }
                    k <= Local.RADIOS.size -> { Local.poserMusique(this, Local.RADIOS[k - 1].second); repeindre() }
                    else -> {
                        val champ = EditText(this).apply { setText(perso); hint = "https://…" }
                        AlertDialog.Builder(this).setTitle("Adresse du flux").setView(champ)
                            .setPositiveButton("Jouer") { _, _ -> val u = champ.text.toString().trim(); if (u.startsWith("http")) { getSharedPreferences("local", MODE_PRIVATE).edit().putString("flux_perso", u).apply(); Local.poserMusique(this, u); repeindre() } }
                            .setNegativeButton("Annuler", null).show()
                    }
                }
            }
            .setNegativeButton("Annuler", null).show()
    }

    /** Les applis que l'écran de veille peut recouvrir sans les couper (leur son continue, la radio de Vision se tait). */
    private fun choisirFond() {
        val pm = packageManager
        val toutes = Accueil.applicationsInstallees(this)
        val choisies = Local.fond(this).toMutableSet()
        val noms = toutes.map { it.loadLabel(pm).toString() }.toTypedArray()
        val coches = toutes.map { it.activityInfo.packageName in choisies }.toBooleanArray()
        AlertDialog.Builder(this).setTitle("Pendant la veille, ces applis continuent en fond")
            .setMultiChoiceItems(noms, coches) { _, k, on -> val p = toutes[k].activityInfo.packageName; if (on) choisies.add(p) else choisies.remove(p) }
            .setPositiveButton("Garder") { _, _ -> Local.poserFond(this, choisies); repeindre() }
            .setNegativeButton("Annuler", null).show()
    }

    private fun choisirApplis() {
        val pm = packageManager
        val toutes = Accueil.applicationsInstallees(this)
        val masquees = Accueil.masquees(this).toMutableSet()
        val noms = toutes.map { it.loadLabel(pm).toString() }.toTypedArray()
        val coches = toutes.map { it.activityInfo.packageName !in masquees }.toBooleanArray()
        AlertDialog.Builder(this).setTitle("Applications sur l'accueil")
            .setMultiChoiceItems(noms, coches) { _, k, on -> val p = toutes[k].activityInfo.packageName; if (on) masquees.remove(p) else masquees.add(p) }
            .setPositiveButton("Garder") { _, _ -> toutes.forEach { ri -> val p = ri.activityInfo.packageName; val cachee = p in masquees; if (cachee != (p in Accueil.masquees(this))) { Accueil.cacher(this, p, cachee); if (!tele && !cachee) Accueil.ajouterALaGrille(this, p) } }; repeindre() }
            .setNegativeButton("Annuler", null).show()
    }

    private fun charger() {
        if (enCharge) return
        enCharge = true
        main.post { if (::contenu.isInitialized && contenu.childCount > 0) repeindre() }
        Thread {
            // Les tableaux et leurs cartes tels que la page de veille les montre (cartes de la communauté comprises).
            try {
                val a = Net.post(this, cfg, "/api/pc_parental/veille/acces", JSONObject().put("id", cfg.id).put("secret", cfg.secret).put("ecran", if (tele) "tele" else "telephone"), 20_000)
                Local.retenirListeWeb(this, a.optJSONArray("tableaux"))
            } catch (_: Exception) {}
            try {
                val r = Net.post(this, cfg, "/api/pc_parental/veille", JSONObject().put("id", cfg.id).put("secret", cfg.secret).put("ecran", if (tele) "tele" else "telephone"), 20_000)
                Local.amorcer(this, r.optJSONObject("reglages"))
                reglages = r.optJSONObject("reglages")
                tableauxHA = reglages?.optJSONArray("tableaux")
            } catch (_: Exception) {}
            main.post { enCharge = false; appliquerTheme(); repeindre() }
        }.also { it.isDaemon = true }.start()
    }

    private fun appliquerTheme() { theme = Local.themeEffectif(this, Palette.APPLI) }
}
