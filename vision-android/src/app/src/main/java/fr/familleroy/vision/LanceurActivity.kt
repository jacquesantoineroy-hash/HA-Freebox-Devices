package fr.familleroy.vision

import android.app.Activity
import android.app.AlertDialog
import android.app.Dialog
import android.content.ClipData
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.view.DragEvent
import android.view.GestureDetector
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.widget.CheckBox
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * L'accueil Vision.
 *
 * Télé : la marque au milieu en haut, l'heure, la météo et la pluie, un mot
 * de la maison, la rangée d'applications (anneau d'or au focus, « + » en bout
 * de rangée pour en ajouter) et une roue de réglages en bas à droite. Appui
 * long sur une appli : ouvrir, déplacer (gauche et droite déplacent, OK
 * pose, comme sur Android TV), retirer, infos, désinstaller. Deux appuis sur
 * Accueil : l'écran de veille par-dessus la musique en cours.
 *
 * Téléphone : comme l'accueil d'Android. Une grille à quatre colonnes où
 * l'on pose applis, dossiers et widgets Vision où l'on veut ; appui long
 * pour soulever et déplacer, déposer sur une appli pour faire un dossier,
 * zone « retirer » en haut ; appui long sur le vide : widgets, couleurs,
 * réglages ; glisser vers le haut : toutes les applications. En bas, un dock
 * de trois icônes au choix (appui long pour les changer), rien d'autre.
 *
 * Tous les réglages sont ceux de l'appareil (Local) ; Home Assistant fournit
 * les données.
 */
class LanceurActivity : Activity() {
    private val main = Handler(Looper.getMainLooper())
    private lateinit var cfg: Config
    private var theme: Theme = Themes.liste[0]
    private var donnees: JSONObject? = null
    private lateinit var racine: FrameLayout
    private var heure: TextView? = null
    private var date: TextView? = null
    private var fil: Thread? = null
    private var empreinteApps = ""
    private val tele by lazy { ReglagesTvActivity.estTele(this) }
    private val heureFmt = SimpleDateFormat("HH:mm", Locale.FRANCE)
    private val dateFmt = SimpleDateFormat("EEEE d MMMM", Locale.FRANCE)
    private var versionLocale = -1
    private var dossierOuvert: Dialog? = null
    private var tiroir: Dialog? = null
    private var toucheEnfoncee = false
    private var reconstructionEnAttente = false
    private var profilConnu = ""
    private var dernierAccueilMs = 0L

    private val tic = object : Runnable {
        override fun run() {
            heure?.text = heureFmt.format(Date())
            date?.text = dateFmt.format(Date())
            racine.findViewWithTag<TextView>("w_heure")?.text = heureFmt.format(Date())
            if (Calendar.getInstance().get(Calendar.SECOND) == 0 || Local.version != versionLocale) rafraichirTheme()
            main.postDelayed(this, 1000)
        }
    }

    companion object {
        private const val PREFS = "lanceur"
        fun masquees(ctx: android.content.Context) = Accueil.masquees(ctx)
        fun cacher(ctx: android.content.Context, pkg: String, cachee: Boolean) = Accueil.cacher(ctx, pkg, cachee)
        fun applicationsInstallees(ctx: android.content.Context) = Accueil.applicationsInstallees(ctx)
        fun accueilSysteme(ctx: android.content.Context) = Accueil.accueilSysteme(ctx)
    }

    // ------------------------------------------------------------------ cycle de vie

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cfg = Config(this)
        theme = Local.themeEffectif(this, Palette.LANCEUR)
        profilConnu = getSharedPreferences(PREFS, MODE_PRIVATE).getString("profil", "") ?: ""
        barres()
        racine = FrameLayout(this)
        setContentView(racine)
        construire()
        Bulle.verifier(this)
        if (!cfg.inscrit) Decouverte.inscrireSeul(this) { }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        // Deux appuis rapprochés sur Accueil : l'écran de veille vient devant, la musique de l'autre appli continue.
        // Sur téléphone, Accueil ramène à l'accueil : le tiroir, un dossier ou le panneau ouverts se referment.
        if (!tele) { try { tiroir?.dismiss() } catch (_: Exception) {}; try { dossierOuvert?.dismiss() } catch (_: Exception) {}; cacherPanneau(); pageur?.aller(0) }
        val now = SystemClock.uptimeMillis()
        if (tele && now - dernierAccueilMs < 1500) { Veille.ouvrir(this); dernierAccueilMs = 0 } else dernierAccueilMs = now
    }

    private fun barres() {
        window.decorView.systemUiVisibility = if (tele)
            View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        else View.SYSTEM_UI_FLAG_LAYOUT_STABLE or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or (if (!theme.sombre) View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR else 0)
        if (!tele) { window.statusBarColor = 0; window.navigationBarColor = theme.fond }
    }

    override fun onResume() {
        super.onResume()
        main.post(tic)
        demarrerDonnees()
        if (empreinteApps != empreinte()) construire()
        armerVeille()
        retourDAppli()
    }

    /** On revient d'une appli : la sélection se remet sur elle, et si elle joue encore du son sans en avoir le droit, on l'arrête. */
    private fun retourDAppli() {
        val pkg = Accueil.dernierLance.ifEmpty { Usage.paquetQuitte }
        if (pkg.isEmpty() || pkg == packageName) return
        Accueil.dernierLance = ""; Usage.paquetQuitte = ""
        if (tele && deplacement == null) racine.post {
            val cle = if (trouverParTag(racine, pkg) != null) pkg
                      else try { Accueil.cases(this).firstOrNull { it.dossier?.pkgs?.contains(pkg) == true }?.cle } catch (_: Exception) { null }
            if (cle != null) trouverParTag(racine, cle)?.let { v -> v.requestFocus(); v.parent?.requestChildFocus(v, v) }
        }
        main.postDelayed({ faireTaire(pkg) }, 1200)
    }

    /** Free TV et d'autres continuent leur son une fois quittées : pause, puis arrêt de l'appli si elle insiste. */
    private fun faireTaire(pkg: String) {
        try {
            if (isFinishing || !hasWindowFocus()) return
            val am = getSystemService(AUDIO_SERVICE) as android.media.AudioManager
            if (!am.isMusicActive || Musique.enCours || Veille.ouverte || pkg in Local.fond(this)) return
            for (code in intArrayOf(KeyEvent.KEYCODE_MEDIA_PAUSE, KeyEvent.KEYCODE_MEDIA_STOP)) {
                am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, code)); am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, code))
            }
            main.postDelayed({
                try {
                    if (!isFinishing && hasWindowFocus() && am.isMusicActive && !Musique.enCours && !Veille.ouverte)
                        (getSystemService(ACTIVITY_SERVICE) as android.app.ActivityManager).killBackgroundProcesses(pkg)
                } catch (_: Exception) {}
            }, 1500)
        } catch (_: Exception) {}
    }

    override fun onPause() {
        super.onPause()
        main.removeCallbacks(tic)
        main.removeCallbacks(veilleAuto)
        fil?.interrupt(); fil = null
    }

    /** Sur télé : sans touche pendant le délai choisi, l'écran de veille vient (en plus du réglage système, quand il a pu être écrit). */
    private val veilleAuto = Runnable {
        val proteger = try { Local.appAProteger(this) } catch (_: Exception) { false }
        if (tele && !isFinishing && Local.delaiVeille(this) > 0 && !Veille.ouverte && !proteger) startActivity(Intent(this, VeilleActivity::class.java))
    }
    private fun armerVeille() {
        main.removeCallbacks(veilleAuto)
        val min = Local.delaiVeille(this)
        if (tele && min > 0) main.postDelayed(veilleAuto, min * 60_000L)
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN) armerVeille()
        toucheEnfoncee = event.action == KeyEvent.ACTION_DOWN
        if (event.action == KeyEvent.ACTION_UP && reconstructionEnAttente) { reconstructionEnAttente = false; main.postDelayed({ construire() }, 150) }
        return super.dispatchKeyEvent(event)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        // Le mode déplacement de la télé : gauche et droite déplacent la case, OK ou Retour la posent.
        val d = deplacement
        if (d != null) {
            when (keyCode) {
                KeyEvent.KEYCODE_DPAD_LEFT -> { glisserTele(d, -1); return true }
                KeyEvent.KEYCODE_DPAD_RIGHT -> { glisserTele(d, +1); return true }
                KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_BACK -> { deplacement = null; construire(); return true }
                KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_DOWN -> return true
            }
        }
        if (keyCode == KeyEvent.KEYCODE_BACK) { dossierOuvert?.dismiss(); cacherPanneau(); return true }
        return super.onKeyDown(keyCode, event)
    }

    override fun onBackPressed() { dossierOuvert?.dismiss(); cacherPanneau() }

    // ------------------------------------------------------------------ thème

    private fun rafraichirTheme() {
        versionLocale = Local.version
        val nouveau = Local.themeEffectif(this, Palette.LANCEUR)
        if (nouveau.nom != theme.nom || nouveau.fond != theme.fond || nouveau.carte != theme.carte || nouveau.encre != theme.encre || nouveau.pourpre != theme.pourpre) {
            theme = nouveau
            barres()
            demanderReconstruction()
        }
    }

    /** Jamais pendant qu'une touche est tenue : un écran rebâti sous le pouce clique n'importe où. */
    private fun demanderReconstruction() {
        if (toucheEnfoncee) { reconstructionEnAttente = true; return }
        construire()
    }

    // ------------------------------------------------------------------ outils

    private fun px(dp: Float) = Ui.dp(this, dp)
    private val dm get() = resources.displayMetrics
    private fun empreinte(): String = Accueil.masquees(this).sorted().joinToString(",") + "|" + Accueil.ordre(this).joinToString(",") + "|" + theme.nom + theme.fond + "|" + Accueil.dossiers(this).joinToString { it.cle + it.nom + it.pkgs.size } + "|" + profilConnu + "|" + (if (tele) "" else Accueil.disposition(this).joinToString { it.cle + it.col + "," + it.row } + "|" + Accueil.dock(this).joinToString(",") + "|" + Accueil.mode(this))

    private fun texte(t: String, taille: Float, couleur: Int, police: Typeface = Polices.texte(this), espacement: Float = 0f): TextView = TextView(this).apply {
        text = t; textSize = taille; setTextColor(couleur); typeface = police; letterSpacing = espacement
    }

    /** Taille en sp qui suit la hauteur de l'écran de la télé (1080 p = 540 dp : 176 px de maquette = 88 sp). */
    private fun tv(pxMaquette: Float): Float = pxMaquette * (dm.heightPixels / dm.density) / 1080f

    private fun etiquetteSection(t: String, taille: Float): TextView = texte(t.uppercase(Locale.FRANCE), taille, theme.encre2, Polices.gras(this), 0.22f)

    private fun icone(res: Int, tailleDp: Float, teinte: Int): ImageView = ImageView(this).apply {
        setImageResource(res); if (res != R.drawable.ic_vision) setColorFilter(teinte); layoutParams = ViewGroup.LayoutParams(px(tailleDp), px(tailleDp))
    }

    private fun fondCarte(rayonDp: Float, couleur: Int = theme.carte, bord: Int = theme.carteBord, epaisseurDp: Float = 1f): GradientDrawable =
        GradientDrawable().apply { cornerRadius = px(rayonDp).toFloat(); setColor(couleur); setStroke(px(epaisseurDp), bord) }

    private fun carte(rayonDp: Float = 22f, padDp: Float = 16f, orientation: Int = LinearLayout.VERTICAL, bordOr: Boolean = false): LinearLayout = LinearLayout(this).apply {
        this.orientation = orientation
        background = if (bordOr) fondCarte(rayonDp, bord = theme.or, epaisseurDp = 1.5f) else fondCarte(rayonDp)
        setPadding(px(padDp), px(padDp - 2f), px(padDp), px(padDp - 2f))
    }

    private fun bouton(t: String, plein: Boolean, action: () -> Unit): TextView = texte(t, 14f, if (plein) theme.fond else theme.encre, Polices.gras(this)).apply {
        gravity = Gravity.CENTER; setPadding(px(16f), 0, px(16f), 0); minHeight = px(44f)
        background = if (plein) GradientDrawable().apply { cornerRadius = px(22f).toFloat(); setColor(theme.or) } else fondCarte(22f, couleur = 0, bord = theme.carteBord)
        isClickable = true; isFocusable = true
        setOnClickListener { action() }
    }

    private fun pastille(couleur: Int): View = View(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(couleur) } }

    private fun disque(dessin: Drawable?, tailleDp: Float): FrameLayout {
        val taille = px(tailleDp)
        val cadre = FrameLayout(this)
        val image = ImageView(this).apply {
            setImageDrawable(dessin); scaleType = ImageView.ScaleType.CENTER_CROP
            clipToOutline = true
            outlineProvider = object : android.view.ViewOutlineProvider() {
                override fun getOutline(v: View, o: android.graphics.Outline) { o.setOval(0, 0, v.width, v.height) }
            }
        }
        cadre.addView(image, FrameLayout.LayoutParams(taille, taille, Gravity.CENTER))
        return cadre
    }

    /** L'icône d'un dossier : quatre pastilles des applis qu'il contient, sur un disque. */
    private fun disqueDossier(d: Accueil.Dossier, tailleDp: Float): FrameLayout {
        val taille = px(tailleDp)
        val cadre = FrameLayout(this)
        cadre.addView(pastille(Palette.melanger(theme.carte, theme.encre, 0.08f)), FrameLayout.LayoutParams(taille, taille, Gravity.CENTER))
        val grille = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val mini = (taille * 0.30f).toInt(); val gap = (taille * 0.06f).toInt()
        for (r in 0 until 2) {
            val ligne = LinearLayout(this)
            for (c in 0 until 2) {
                val pkg = d.pkgs.getOrNull(r * 2 + c)
                val v = if (pkg != null) disque(Accueil.icone(this, pkg), mini / dm.density) else View(this)
                ligne.addView(v, LinearLayout.LayoutParams(mini, mini).apply { setMargins(gap / 2, gap / 2, gap / 2, gap / 2) })
            }
            grille.addView(ligne)
        }
        cadre.addView(grille, FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        return cadre
    }

    private fun salutation(): String {
        val h = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val prenom = donnees?.optJSONObject("moi")?.optString("prenom").orEmpty()
        val qui = if (!tele && prenom.isNotEmpty() && profil() != "affichage") prenom else "la famille"
        return when { h < 5 -> "Bonne nuit $qui"; h < 12 -> "Bonjour $qui"; h < 18 -> "Bon après-midi $qui"; else -> "Bonsoir $qui" }
    }

    /** affichage (télé commune), parent, enfant : dit par Home Assistant, sinon le dernier connu, sinon déduit du poll. */
    private fun profil(): String {
        val p = donnees?.optJSONObject("moi")?.optString("public").orEmpty()
        if (p.isNotEmpty()) return p
        if (profilConnu.isNotEmpty()) return profilConnu
        return if (tele) "affichage" else if (Etat.parent) "parent" else if (cfg.personne.isNotEmpty()) "enfant" else "affichage"
    }

    /** La marque, au milieu en haut, partout. */
    private fun marque(tailleLogoDp: Float, tailleTexte: Float): View {
        val m = LinearLayout(this).apply { gravity = Gravity.CENTER }
        m.addView(icone(R.drawable.ic_vision, tailleLogoDp, theme.or))
        m.addView(texte("VISION", tailleTexte, theme.or, Polices.gras(this), 0.28f).apply { setPadding(px(8f), 0, 0, 0) })
        return m
    }

    /** La roue des réglages, en bas à droite. */
    private fun roueReglages(tailleDp: Float): View {
        val b = FrameLayout(this).apply { background = fondCarte(999f); isClickable = true; isFocusable = true; contentDescription = "Réglages Vision"; tag = "roue" }
        b.addView(icone(R.drawable.ic_reglages, tailleDp * 0.5f, theme.or), FrameLayout.LayoutParams(px(tailleDp * 0.5f), px(tailleDp * 0.5f), Gravity.CENTER))
        b.setOnFocusChangeListener { v, a -> v.background = if (a) fondCarte(999f, bord = theme.or, epaisseurDp = 1.5f) else fondCarte(999f); v.animate().scaleX(if (a) 1.1f else 1f).scaleY(if (a) 1.1f else 1f).setDuration(120).start() }
        b.setOnClickListener { startActivity(Intent(this, ReglagesTvActivity::class.java)) }
        return b
    }

    // ------------------------------------------------------------------ construction

    private fun construire() {
        val focusAvant = (currentFocus?.tag as? String) ?: (currentFocus?.tag as? Accueil.Place)?.cle
        empreinteApps = empreinte()
        panneau = null
        racine.removeAllViews()
        racine.setBackgroundColor(theme.fond)
        racine.addView(FondAnime(this) { theme }, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        if (tele) construireTele() else construireTelephone()
        Ui.laisserDeborder(racine)
        appliquerDonnees()
        if (focusAvant != null) racine.post { trouverParTag(racine, focusAvant)?.requestFocus() }
    }

    private fun trouverParTag(v: View, cle: String): View? {
        val t = v.tag
        if ((t is String && t == cle) || (t is Accueil.Place && t.cle == cle)) return v
        if (v is ViewGroup) for (i in 0 until v.childCount) trouverParTag(v.getChildAt(i), cle)?.let { return it }
        return null
    }

    // ================================================================== TÉLÉ

    private var deplacement: String? = null
    private var rangeeApps: LinearLayout? = null

    private fun construireTele() {
        val margeX = (dm.widthPixels * 0.05f).toInt(); val margeY = (dm.heightPixels * 0.04f).toInt()
        val colonne = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(margeX, margeY, margeX, margeY) }
        racine.addView(colonne, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))

        colonne.addView(marque(tv(40f), tv(22f)), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        // L'heure et la date à gauche ; la météo et la pluie à droite.
        val entete = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, px(6f), 0, 0) }
        val blocHeure = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        heure = texte("", tv(176f), theme.encre, Polices.outfitFin(this), -0.02f).apply { includeFontPadding = false }
        date = texte("", tv(34f), theme.encre2, Polices.moyen(this))
        blocHeure.addView(heure); blocHeure.addView(date)
        blocHeure.addView(texte("", tv(38f), theme.encre, Polices.moyen(this)).apply { tag = "salut"; setPadding(0, px(10f), 0, 0) })
        entete.addView(blocHeure, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val droite = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.END; setPadding(0, px(14f), 0, 0) }
        val ligneMeteo = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        ligneMeteo.addView(icone(R.drawable.ic_meteo, tv(64f), theme.encre2))
        ligneMeteo.addView(texte("", tv(72f), theme.encre, Polices.outfitLeger(this)).apply { tag = "temp"; setPadding(px(10f), 0, 0, 0); includeFontPadding = false })
        droite.addView(ligneMeteo)
        droite.addView(texte("", tv(24f), theme.encre2).apply { tag = "cond"; gravity = Gravity.END })
        droite.addView(lignePluie(tv(18f), tv(28f)).apply { tag = "pluie" })
        val demandes = LinearLayout(this).apply {
            tag = "demandes"; gravity = Gravity.CENTER_VERTICAL; visibility = View.GONE
            background = fondCarte(999f); setPadding(px(14f), px(6f), px(16f), px(6f))
        }
        demandes.addView(pastille(theme.pourpre), LinearLayout.LayoutParams(px(8f), px(8f)).apply { rightMargin = px(10f) })
        demandes.addView(texte("", tv(20f), theme.encre, Polices.demiGras(this)).apply { tag = "demandes_texte" })
        droite.addView(demandes, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = px(12f) })
        entete.addView(droite)
        colonne.addView(entete)

        colonne.addView(View(this), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        // Les applications, en rangée (qui défile si elle déborde), et le « + » au bout.
        colonne.addView(etiquetteSection("Applications", tv(20f)))
        val rangee = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(px(6f), px(10f), px(6f), px(6f)); clipToPadding = false; clipChildren = false }
        rangeeApps = rangee
        val defile = HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; clipChildren = false; clipToPadding = false }
        defile.addView(rangee)
        colonne.addView(defile)
        remplirRangeeTele()

        // Le pied : l'aide du mode déplacement, et la roue des réglages à droite.
        val pied = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL or Gravity.END; setPadding(0, px(14f), 0, 0) }
        pied.addView(texte(if (deplacement != null) "Gauche et droite déplacent · OK pose" else "", tv(20f), theme.encre2).apply { tag = "aide" }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        pied.addView(roueReglages(tv(56f)), LinearLayout.LayoutParams(px(tv(56f)), px(tv(56f))))
        colonne.addView(pied)
    }

    private fun remplirRangeeTele() {
        val rangee = rangeeApps ?: return
        rangee.removeAllViews()
        val cases = Accueil.cases(this)
        val cles = cases.map { it.cle }
        cases.forEach { c -> rangee.addView(caseTele(c, cles), LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { rightMargin = px(10f) }) }
        rangee.addView(casePlusTele(), LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT))
    }

    /** Une appli ou un dossier sur la télé : disque, nom ; anneau d'or et grossissement au focus ; soulevée en mode déplacement. */
    private fun caseTele(c: Accueil.Case, cles: List<String>): View {
        val taille = tv(124f)
        val contenu = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(px(8f), px(10f), px(8f), px(8f)); tag = c.cle }
        val enDeplacement = deplacement == c.cle
        val anneau = View(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(0); setStroke(px(4f), if (enDeplacement) theme.pourpre else theme.or) }; visibility = if (enDeplacement) View.VISIBLE else View.INVISIBLE }
        val cadre = FrameLayout(this)
        val d = if (c.dossier != null) disqueDossier(c.dossier, taille) else disque(Accueil.icone(this, c.pkg!!), taille)
        cadre.addView(d, FrameLayout.LayoutParams(px(taille), px(taille), Gravity.CENTER))
        cadre.addView(anneau, FrameLayout.LayoutParams(px(taille + 16f), px(taille + 16f), Gravity.CENTER))
        contenu.addView(cadre, LinearLayout.LayoutParams(px(taille + 16f), px(taille + 16f)))
        val nom = if (c.dossier != null) c.dossier.nom else Accueil.etiquette(this, c.pkg!!)
        val libelle = texte(nom, tv(22f), theme.encre2, Polices.moyen(this)).apply { maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END; gravity = Gravity.CENTER; setPadding(0, px(8f), 0, 0); maxWidth = px(taille + 24f) }
        contenu.addView(libelle)
        contenu.isFocusable = true; contenu.isClickable = true
        if (enDeplacement) { contenu.scaleX = 1.18f; contenu.scaleY = 1.18f; contenu.translationY = -px(10f).toFloat() }
        contenu.setOnFocusChangeListener { v, a ->
            if (deplacement != null) return@setOnFocusChangeListener
            anneau.visibility = if (a) View.VISIBLE else View.INVISIBLE
            libelle.setTextColor(if (a) theme.encre else theme.encre2); libelle.typeface = if (a) Polices.gras(this) else Polices.moyen(this)
            v.animate().scaleX(if (a) 1.12f else 1f).scaleY(if (a) 1.12f else 1f).setDuration(140).start()
        }
        contenu.setOnClickListener { if (deplacement != null) { deplacement = null; construire() } else if (c.dossier != null) ouvrirDossier(c.dossier, cles) else Accueil.lancer(this, c.pkg!!) }
        contenu.setOnLongClickListener { if (deplacement == null) menuTele(c, cles); true }
        return contenu
    }

    /** Le « + » en bout de rangée : choisir d'autres applications à montrer. */
    private fun casePlusTele(): View {
        val taille = tv(124f)
        val contenu = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(px(8f), px(10f), px(8f), px(8f)); tag = "plus" }
        val rond = FrameLayout(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(0); setStroke(px(3f), theme.encre2, px(10f).toFloat(), px(8f).toFloat()) } }
        rond.addView(icone(R.drawable.ic_plus, taille * 0.4f, theme.encre2), FrameLayout.LayoutParams(px(taille * 0.4f), px(taille * 0.4f), Gravity.CENTER))
        val cadre = FrameLayout(this)
        cadre.addView(rond, FrameLayout.LayoutParams(px(taille), px(taille), Gravity.CENTER))
        contenu.addView(cadre, LinearLayout.LayoutParams(px(taille + 16f), px(taille + 16f)))
        contenu.addView(texte("Ajouter", tv(22f), theme.encre2, Polices.moyen(this)).apply { gravity = Gravity.CENTER; setPadding(0, px(8f), 0, 0) })
        contenu.isFocusable = true; contenu.isClickable = true
        contenu.setOnFocusChangeListener { v, a -> rond.background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(if (a) theme.carte else 0); setStroke(px(3f), if (a) theme.or else theme.encre2, px(10f).toFloat(), px(8f).toFloat()) }; v.animate().scaleX(if (a) 1.12f else 1f).scaleY(if (a) 1.12f else 1f).setDuration(140).start() }
        contenu.setOnClickListener { choisirApplis() }
        return contenu
    }

    /** Afficher ou cacher des applications : la liste complète, à cocher. */
    private fun choisirApplis() {
        val pm = packageManager
        val toutes = Accueil.applicationsInstallees(this)
        val masquees = Accueil.masquees(this).toMutableSet()
        val noms = toutes.map { it.loadLabel(pm).toString() }.toTypedArray()
        val coches = toutes.map { it.activityInfo.packageName !in masquees }.toBooleanArray()
        AlertDialog.Builder(this).setTitle("Applications sur l'accueil")
            .setMultiChoiceItems(noms, coches) { _, k, on -> val p = toutes[k].activityInfo.packageName; if (on) masquees.remove(p) else masquees.add(p) }
            .setPositiveButton("Garder") { _, _ ->
                toutes.forEach { ri -> val p = ri.activityInfo.packageName; val cachee = p in masquees; if (cachee != (p in Accueil.masquees(this))) { Accueil.cacher(this, p, cachee); if (!tele && !cachee) Accueil.ajouterALaGrille(this, p) } }
                construire()
            }
            .setNegativeButton("Annuler", null).show()
    }

    /** Le mode déplacement : la case suit gauche et droite. */
    private fun glisserTele(cle: String, sens: Int) {
        val cles = Accueil.cases(this).map { it.cle }
        val k = cles.indexOf(cle)
        if (k < 0) return
        val vers = (k + sens).coerceIn(0, cles.size - 1)
        if (vers == k) return
        Accueil.deplacer(this, cles, cle, vers)
        remplirRangeeTele()
        empreinteApps = empreinte()
        rangeeApps?.post { trouverParTag(racine, cle)?.let { v -> v.requestFocus(); v.parent?.requestChildFocus(v, v) } }
    }

    /** Le menu de la télé, comme celui d'Android TV : ouvrir, déplacer, retirer, infos, désinstaller. */
    private fun menuTele(c: Accueil.Case, cles: List<String>) {
        val nom = if (c.dossier != null) c.dossier.nom else Accueil.etiquette(this, c.pkg!!)
        val choix = ArrayList<Pair<String, () -> Unit>>()
        choix.add("Ouvrir" to { if (c.dossier != null) ouvrirDossier(c.dossier, cles) else Accueil.lancer(this, c.pkg!!) })
        choix.add("Déplacer" to { deplacement = c.cle; construire(); racine.post { trouverParTag(racine, c.cle)?.requestFocus() }; Unit })
        if (c.pkg != null) {
            choix.add("Retirer de l'accueil" to { Accueil.cacher(this, c.pkg, true); construire() })
            choix.add("Infos de l'application" to { try { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${c.pkg}"))) } catch (_: Exception) {} })
            choix.add("Désinstaller" to { try { startActivity(Intent(Intent.ACTION_DELETE, Uri.parse("package:${c.pkg}"))) } catch (_: Exception) {} })
        } else {
            choix.add("Renommer le dossier" to { renommer(c.dossier!!) })
            choix.add("Défaire le dossier" to { dissoudre(c.cle); construire() })
        }
        AlertDialog.Builder(this).setTitle(nom).setItems(choix.map { it.first }.toTypedArray()) { _, i -> choix[i].second() }.show()
    }

    // ================================================================== TÉLÉPHONE

    private var zoneRetrait: View? = null
    private var enDrag: String? = null
    private var enDragNouveau: Accueil.Widget? = null
    private var dragSorti = false
    private var grille: GrilleAccueil? = null
    private var pageur: Pageur? = null
    private var pagesUtiles = 1
    private var pageMemo = 0
    private var points: LinearLayout? = null
    private var panneau: View? = null
    private var flipEnAttente: Runnable? = null

    private fun construireTelephone() {
        val profil = profil()
        val pages = Accueil.mode(this) == Accueil.MODE_PAGES
        // Le bas de l'écran (poignée du tiroir et dock) est fixe ; le reste défile ou se feuillette au-dessus.
        val hauteurBas = px(110f)
        val colonne = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(px(16f), px(40f), px(16f), if (pages) 0 else px(12f)); clipChildren = false; clipToPadding = false }
        val defile: View = if (pages) colonne else ScrollView(this).apply { isVerticalScrollBarEnabled = false; isFillViewport = true; clipToPadding = false; clipChildren = false; addView(colonne) }
        racine.addView(defile, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT).apply { bottomMargin = hauteurBas })
        // Tout le bas de l'écran ouvre le tiroir d'un glissement vers le haut, même en partant d'une icône du dock.
        val bas = object : LinearLayout(this) {
            private var y0 = 0f; private var x0 = 0f
            override fun onInterceptTouchEvent(e: MotionEvent): Boolean {
                when (e.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { y0 = e.rawY; x0 = e.rawX }
                    MotionEvent.ACTION_MOVE -> if (y0 - e.rawY > px(22f) && Math.abs(y0 - e.rawY) > Math.abs(x0 - e.rawX) * 1.3f && enDrag == null && enDragNouveau == null) { tiroirApplis(); return true }
                }
                return false
            }
        }.apply { orientation = LinearLayout.VERTICAL; setPadding(px(16f), 0, px(16f), px(8f)) }
        racine.addView(bas, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, hauteurBas, Gravity.BOTTOM))

        colonne.addView(marque(24f, 13f), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        // L'en-tête : heure et date à gauche, météo à droite.
        val entete = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.BOTTOM; setPadding(px(4f), px(6f), px(4f), 0) }
        val blocHeure = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        heure = texte("", 64f, theme.encre, Polices.outfitFin(this), -0.02f).apply { includeFontPadding = false }
        val ligneDate = LinearLayout(this)
        date = texte("", 14f, theme.encre2, Polices.moyen(this))
        ligneDate.addView(date)
        val prenom = donnees?.optJSONObject("moi")?.optString("prenom").orEmpty()
        val qui = when (profil) { "parent" -> "Parent"; "enfant" -> prenom; else -> "" }
        if (qui.isNotEmpty()) ligneDate.addView(texte(" · $qui", 14f, theme.or, Polices.gras(this)))
        blocHeure.addView(heure); blocHeure.addView(ligneDate)
        entete.addView(blocHeure, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val droite = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.END }
        val ligneMeteo = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        ligneMeteo.addView(icone(R.drawable.ic_meteo, 24f, theme.encre2))
        ligneMeteo.addView(texte("", 28f, theme.encre, Polices.outfitLeger(this)).apply { tag = "temp"; setPadding(px(8f), 0, 0, 0); includeFontPadding = false })
        droite.addView(ligneMeteo)
        droite.addView(texte("", 12f, theme.encre2).apply { tag = "cond"; gravity = Gravity.END })
        entete.addView(droite)
        colonne.addView(entete)

        // La grille, comme Android : tout est posé où on l'a mis. Une longue grille qui défile, ou des pages.
        val lc = ((dm.widthPixels - px(32f)) / Accueil.COLONNES)
        val hc = (lc * 1.14f).toInt()
        val lignesVisibles = ((dm.heightPixels - px(40f + 150f) - hauteurBas) / hc).coerceAtLeast(3)
        Accueil.lignesParPage = if (pages) lignesVisibles else 0
        val places = Accueil.synchroniser(this, profil)
        fun grilleNeuve(page: Int) = GrilleAccueil(this).apply { setPadding(0, px(14f), 0, 0); couleurCible = theme.or; hauteurCellule = hc; lignesMin = lignesVisibles; hauteurFixe = pages; decalageLignes = page * lignesVisibles }
        if (pages) {
            val maxRow = places.maxOfOrNull { it.row + it.h } ?: 0
            val n = ((maxRow + lignesVisibles - 1) / lignesVisibles).coerceAtLeast(1)
            pagesUtiles = n
            val pg = Pageur(this).apply { pagesVisibles = n; clipChildren = false }
            pageur = pg
            for (p in 0..n) {   // une page de plus, vide : on y glisse une case pour l'ouvrir
                val g = grilleNeuve(p)
                places.filter { it.row / lignesVisibles == p }.forEach { g.addView(vuePlace(it)) }
                brancherGrille(g, p)
                pg.ajouterPage(g)
            }
            grille = pg.rangee.getChildAt(0) as GrilleAccueil
            colonne.addView(pg, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
            val pts = LinearLayout(this).apply { gravity = Gravity.CENTER; setPadding(0, px(4f), 0, 0) }
            points = pts
            pg.surPage = { pageMemo = it; peindrePoints() }
            colonne.addView(pts)
            pg.post { pg.aller(pageMemo.coerceAtMost(n - 1), false); peindrePoints() }
            brancherGestes(pg)
        } else {
            pageur = null; points = null
            val g = grilleNeuve(0)
            grille = g
            places.forEach { pl -> g.addView(vuePlace(pl)) }
            brancherGrille(g, 0)
            colonne.addView(g, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
            colonne.addView(View(this), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
            // La grille défile : glisser vers le haut sert à ça, le tiroir s'ouvre depuis la poignée ou le dock.
            // Mais arrivé en bas de la grille (ou si elle tient dans l'écran), le même geste ouvre le tiroir.
            brancherGestes(defile, si = { !defile.canScrollVertically(1) })
        }

        // La poignée du tiroir : un trait, comme Android ; toucher ou glisser vers le haut ouvre toutes les applications.
        val poignee = LinearLayout(this).apply { gravity = Gravity.CENTER; setPadding(0, px(16f), 0, px(12f)); contentDescription = "Toutes les applications" }
        poignee.addView(View(this).apply { background = GradientDrawable().apply { cornerRadius = px(3f).toFloat(); setColor(theme.encre3) } }, LinearLayout.LayoutParams(px(56f), px(5f)))
        brancherGestes(poignee, consomme = true, toucher = { tiroirApplis() })
        bas.addView(poignee)

        // Le dock : trois applications au choix, sans autre bouton. Appui long sur une icône pour la changer.
        val dock = LinearLayout(this).apply { gravity = Gravity.CENTER; setPadding(px(8f), px(2f), px(8f), px(6f)); tag = "dock" }
        val pkgs = Accueil.dock(this)
        pkgs.forEachIndexed { k, pkg ->
            val b = disque(Accueil.icone(this, pkg), 56f).apply {
                isClickable = true; isFocusable = true; contentDescription = Accueil.etiquette(this@LanceurActivity, pkg); tag = "dock:$k"
                setOnClickListener { Accueil.lancer(this@LanceurActivity, pkg) }
                setOnLongClickListener { menuDock(k); true }
            }
            dock.addView(b, LinearLayout.LayoutParams(px(56f), px(56f)).apply { leftMargin = px(14f); rightMargin = px(14f) })
        }
        if (pkgs.isEmpty()) dock.addView(texte("Appui long ici : choisir les applications du dock", 12f, theme.encre3).apply { setPadding(px(8f), px(16f), px(8f), px(16f)) })
        dock.setOnLongClickListener { if (pkgs.size < Accueil.DOCK_MAX) choisirAppliDock(pkgs.size); true }
        dock.isLongClickable = true
        bas.addView(dock)
        brancherGestes(bas, consomme = true)

        // La zone « retirer », visible pendant un glisser.
        zoneRetrait = LinearLayout(this).apply {
            gravity = Gravity.CENTER; visibility = View.GONE
            background = GradientDrawable().apply { cornerRadius = px(22f).toFloat(); setColor(theme.carte); setStroke(px(2f), theme.pourpre, px(8f).toFloat(), px(6f).toFloat()) }
            addView(icone(R.drawable.ic_retirer, 20f, theme.pourpre))
            addView(texte("Glisser ici pour retirer de l'accueil", 14f, theme.pourpre, Polices.demiGras(this@LanceurActivity)).apply { setPadding(px(10f), 0, 0, 0) })
            setOnDragListener { v, e ->
                when (e.action) {
                    DragEvent.ACTION_DRAG_ENTERED -> { dragSorti = true; v.alpha = 1f; v.scaleX = 1.03f; v.scaleY = 1.03f; grilles().forEach { it.cacherCible() } }
                    DragEvent.ACTION_DRAG_EXITED -> { v.alpha = 0.85f; v.scaleX = 1f; v.scaleY = 1f }
                    DragEvent.ACTION_DROP -> { enDrag?.let { cle -> if (cle.startsWith(Accueil.PREFIXE_DOSSIER)) Accueil.defaireSurGrille(this@LanceurActivity, cle) else Accueil.retirerDeLaGrille(this@LanceurActivity, cle) }; enDragNouveau = null; enDrag = null; construire() }
                }
                true
            }
        }
        racine.addView(zoneRetrait, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(44f), Gravity.TOP).apply { setMargins(px(20f), px(14f), px(20f), 0) })
    }

    private fun grilles(): List<GrilleAccueil> {
        val pg = pageur ?: return listOfNotNull(grille)
        return (0 until pg.pages).map { pg.rangee.getChildAt(it) as GrilleAccueil }
    }

    private fun peindrePoints() {
        val pts = points ?: return; val pg = pageur ?: return
        pts.removeAllViews()
        if (pg.pagesVisibles <= 1) return
        for (p in 0 until pg.pagesVisibles) {
            val on = p == pg.page
            pts.addView(View(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(if (on) theme.or else theme.encre3); alpha = if (on) 255 else 120 } }, LinearLayout.LayoutParams(px(if (on) 8f else 6f), px(if (on) 8f else 6f)).apply { leftMargin = px(4f); rightMargin = px(4f) })
        }
    }

    /**
     * Les gestes sur le vide, comme Android : appui long ouvre le panneau
     * (widgets, couleurs, réglages), glisser vers le haut ouvre le tiroir.
     * Posés sur la vue qui reçoit les touchers du vide (le défilement ou les
     * pages), sans lui voler le défilement.
     */
    private fun brancherGestes(v: View, consomme: Boolean = false, glisser: Boolean = true, si: (() -> Boolean)? = null, toucher: (() -> Unit)? = null) {
        val gestes = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onLongPress(e: MotionEvent) { if (enDrag == null && enDragNouveau == null && panneau == null) montrerPanneau() }
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, vx: Float, vy: Float): Boolean { if (glisser && (si == null || si()) && e1 != null && e1.y - e2.y > px(40f) && vy < -350 && Math.abs(vy) > Math.abs(vx)) { tiroirApplis(); return true }; return false }
            override fun onSingleTapUp(e: MotionEvent): Boolean { toucher?.invoke(); return toucher != null }
            override fun onDown(e: MotionEvent) = true
        })
        v.setOnTouchListener { _, e -> gestes.onTouchEvent(e); consomme }
    }

    /** Le glisser dans une grille (une page, ou la grille unique) : une case existante, ou un widget neuf venu du panneau. */
    private fun brancherGrille(g: GrilleAccueil, page: Int) {
        g.setOnDragListener { _, e ->
            val source = enDrag; val nouveau = enDragNouveau
            if (source == null && nouveau == null) return@setOnDragListener false
            val pl = if (source != null) (Accueil.disposition(this).firstOrNull { it.cle == source } ?: return@setOnDragListener false) else Accueil.Place(Accueil.PREFIXE_WIDGET + nouveau!!.code, 0, 0, nouveau.w, nouveau.h)
            when (e.action) {
                DragEvent.ACTION_DRAG_STARTED -> true
                DragEvent.ACTION_DRAG_LOCATION -> {
                    val (c, r) = g.cellule(e.x, e.y)
                    val col = (c - (pl.w - 1) / 2).coerceIn(0, Accueil.COLONNES - pl.w)
                    val sous = Accueil.placeA(Accueil.disposition(this).filter { it.cle != source }, c, r)
                    if (source != null && sous != null && !sous.estWidget && pl.w == 1 && pl.h == 1 && !pl.estDossier && surLeCentre(g, sous, e.x, e.y)) g.montrerCible(sous.col, sous.row, 1, 1) else g.montrerCible(col, r, pl.w, pl.h)
                    if (sous == null || sous.cle != source) dragSorti = true
                    tournerPage(g, page, e.x)
                    true
                }
                DragEvent.ACTION_DRAG_EXITED -> { g.cacherCible(); annulerFlip(); true }
                DragEvent.ACTION_DROP -> {
                    g.cacherCible(); annulerFlip()
                    val (c, r) = g.cellule(e.x, e.y)
                    val col = (c - (pl.w - 1) / 2).coerceIn(0, Accueil.COLONNES - pl.w)
                    val sous = Accueil.placeA(Accueil.disposition(this).filter { it.cle != source }, c, r)
                    if (nouveau != null) Accueil.poserSurGrille(this, pl.cle, col, r, pl.w, pl.h)
                    else if (sous != null && !sous.estWidget && pl.w == 1 && pl.h == 1 && !pl.estDossier && surLeCentre(g, sous, e.x, e.y)) Accueil.fusionnerSurGrille(this, sous.cle, source!!)
                    else Accueil.deplacerSurGrille(this, source!!, col, r)
                    // La case d'origine est reconstruite : elle ne recevra pas la fin du glisser, on libère ici.
                    enDragNouveau = null; enDrag = null
                    construire(); true
                }
                DragEvent.ACTION_DRAG_ENDED -> {
                    g.cacherCible(); annulerFlip()
                    if (enDragNouveau != null) { enDragNouveau = null; zoneRetrait?.visibility = View.GONE }
                    pageur?.let { pg -> pg.pagesVisibles = pagesUtiles; if (pg.page >= pagesUtiles) pg.aller(pagesUtiles - 1); peindrePoints() }
                    true
                }
                else -> true
            }
        }
    }

    /** Pendant un glisser, rester au bord d'une page la tourne, comme Android. */
    private fun tournerPage(g: GrilleAccueil, page: Int, x: Float) {
        val pg = pageur ?: return
        val bord = px(36f)
        val cible = when { x < bord && page > 0 -> page - 1; x > g.width - bord && page < pg.pages - 1 -> page + 1; else -> { annulerFlip(); return } }
        if (flipEnAttente != null) return
        val r = Runnable { flipEnAttente = null; pg.pagesVisibles = pg.pages; pg.aller(cible); peindrePoints() }
        flipEnAttente = r
        main.postDelayed(r, 550)
    }

    private fun annulerFlip() { flipEnAttente?.let { main.removeCallbacks(it) }; flipEnAttente = null }

    /** Appui long sur une icône du dock : la remplacer, la retirer, en ajouter une. */
    private fun menuDock(k: Int) {
        val pkgs = Accueil.dock(this).toMutableList()
        val choix = ArrayList<String>().apply { add("Remplacer"); add("Retirer du dock"); if (pkgs.size < Accueil.DOCK_MAX) add("Ajouter une application") }
        AlertDialog.Builder(this).setTitle(Accueil.etiquette(this, pkgs[k])).setItems(choix.toTypedArray()) { _, i ->
            when (i) {
                0 -> choisirAppliDock(k)
                1 -> { pkgs.removeAt(k); Accueil.ecrireDock(this, pkgs); construire() }
                2 -> choisirAppliDock(pkgs.size)
            }
        }.show()
    }

    /** Le choix d'une application pour une place du dock (k = taille actuelle pour en ajouter une). */
    private fun choisirAppliDock(k: Int) {
        val pm = packageManager
        val toutes = Accueil.applicationsInstallees(this)
        val noms = toutes.map { it.loadLabel(pm).toString() }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Application du dock").setItems(noms) { _, i ->
            val pkg = toutes[i].activityInfo.packageName
            val pkgs = Accueil.dock(this).toMutableList()
            pkgs.remove(pkg)
            if (k < pkgs.size) pkgs[k] = pkg else pkgs.add(pkg)
            Accueil.ecrireDock(this, pkgs); construire()
        }.show()
    }

    private fun surLeCentre(g: GrilleAccueil, pl: Accueil.Place, x: Float, y: Float): Boolean {
        val lc = g.largeurCellule; val cx = g.paddingLeft + (pl.col + 0.5f) * lc; val cy = g.paddingTop + pl.row * g.hauteurCellule + lc * 0.45f
        return Math.hypot((x - cx).toDouble(), (y - cy).toDouble()) < lc * 0.33
    }

    /**
     * Le panneau de l'appui long, comme sur Android : en haut les raccourcis
     * (couleurs, réglages, défilement ou pages, applications), dessous les
     * widgets disponibles. Appui long sur un widget puis glisser : il se
     * pose où on le lâche ; un simple toucher le pose à la première place
     * libre, ou le retire s'il y est déjà.
     */
    private fun montrerPanneau() {
        cacherPanneau()
        val voile = FrameLayout(this).apply { setBackgroundColor(0x55000000); isClickable = true; setOnClickListener { cacherPanneau() } }
        val feuille = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; background = fondCarte(30f); setPadding(px(18f), px(10f), px(18f), px(18f)); isClickable = true; clipChildren = false }
        feuille.addView(View(this).apply { background = GradientDrawable().apply { cornerRadius = px(3f).toFloat(); setColor(theme.encre3) } }, LinearLayout.LayoutParams(px(40f), px(4f)).apply { gravity = Gravity.CENTER_HORIZONTAL; bottomMargin = px(12f) })

        val pages = Accueil.mode(this) == Accueil.MODE_PAGES
        val raccourcis = LinearLayout(this).apply { gravity = Gravity.CENTER }
        fun raccourci(res: Int, t: String, action: () -> Unit) {
            val c = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; isClickable = true; setPadding(px(4f), px(4f), px(4f), px(4f)) }
            val rond = FrameLayout(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Palette.melanger(theme.carte, theme.encre, 0.08f)) } }
            rond.addView(icone(res, 22f, theme.or), FrameLayout.LayoutParams(px(22f), px(22f), Gravity.CENTER))
            c.addView(rond, LinearLayout.LayoutParams(px(48f), px(48f)))
            c.addView(texte(t, 11f, theme.encre2, Polices.moyen(this)).apply { gravity = Gravity.CENTER; setPadding(0, px(5f), 0, 0); maxLines = 2 })
            c.setOnClickListener { cacherPanneau(); action() }
            raccourcis.addView(c, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        raccourci(R.drawable.ic_couleurs, "Couleurs") { startActivity(Intent(this, CouleursActivity::class.java)) }
        raccourci(R.drawable.ic_reglages, "Réglages") { startActivity(Intent(this, ReglagesTvActivity::class.java)) }
        raccourci(R.drawable.ic_grille, if (pages) "Pages → défilement" else "Défilement → pages") { Accueil.poserMode(this, if (pages) Accueil.MODE_DEFILEMENT else Accueil.MODE_PAGES); construire() }
        raccourci(R.drawable.ic_widgets, "Applications") { tiroirApplis() }
        if (pages && pageur != null) raccourci(R.drawable.ic_retirer, "Supprimer cette page") { supprimerPage() }
        feuille.addView(raccourcis)
        feuille.addView(View(this).apply { setBackgroundColor(theme.carteBord) }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(1f)).apply { topMargin = px(12f); bottomMargin = px(10f) })

        feuille.addView(etiquetteSection("Widgets", 11f))
        feuille.addView(texte("Appui long puis glisser sur l'accueil pour le poser où tu veux. Toucher : poser à la première place libre, ou retirer.", 12f, theme.encre3).apply { setPadding(0, px(4f), 0, px(8f)) })
        val profil = profil()
        val poses = Accueil.disposition(this).map { it.cle }.toSet()
        val dispo = Accueil.WIDGETS.filter { it.publics.isEmpty() || profil in it.publics }
        val defilant = ScrollView(this).apply { isVerticalScrollBarEnabled = false; clipChildren = false }
        val liste = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; clipChildren = false }
        defilant.addView(liste)
        var rang: LinearLayout? = null
        dispo.forEachIndexed { k, w ->
            if (k % 2 == 0) { rang = LinearLayout(this).apply { clipChildren = false }; liste.addView(rang) }
            val cle = Accueil.PREFIXE_WIDGET + w.code
            val pose = cle in poses
            val tuile = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; background = fondCarte(18f, couleur = Palette.melanger(theme.carte, theme.encre, 0.05f)); setPadding(px(12f), px(10f), px(12f), px(10f)); isClickable = true; alpha = if (pose) 0.55f else 1f }
            // Un petit aperçu : des cellules à la taille du widget.
            val apercu = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
            apercu.addView(View(this).apply { background = GradientDrawable().apply { cornerRadius = px(6f).toFloat(); setColor(theme.or); alpha = 200 } }, LinearLayout.LayoutParams(px(10f * w.w), px(8f * w.h)))
            apercu.addView(texte("${w.w} × ${w.h}", 11f, theme.encre3, Polices.moyen(this)).apply { setPadding(px(8f), 0, 0, 0) })
            tuile.addView(apercu)
            tuile.addView(texte(w.nom, 13f, theme.encre, Polices.demiGras(this)).apply { setPadding(0, px(8f), 0, 0); maxLines = 2 })
            if (pose) tuile.addView(texte("Posé · toucher pour retirer", 11f, theme.encre3).apply { setPadding(0, px(4f), 0, 0) })
            tuile.setOnClickListener {
                if (pose) Accueil.retirerDeLaGrille(this, cle) else Accueil.ajouterALaGrille(this, cle, w.w, w.h)
                cacherPanneau(); construire()
            }
            tuile.setOnLongClickListener { v -> souleverNouveau(v, w); true }
            rang!!.addView(tuile, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(px(4f), px(4f), px(4f), px(4f)) })
        }
        if (dispo.size % 2 == 1) rang!!.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
        feuille.addView(defilant, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0).apply { height = (dm.heightPixels * 0.38f).toInt() })

        voile.addView(feuille, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
        racine.addView(voile, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        panneau = voile
        feuille.translationY = px(300f).toFloat(); feuille.alpha = 0f
        feuille.animate().translationY(0f).alpha(1f).setDuration(180).start()
    }

    private fun cacherPanneau() { panneau?.let { racine.removeView(it) }; panneau = null }

    /** Comme Android : la page courante disparaît avec tout ce qu'elle porte ; les applis retournent au tiroir. */
    private fun supprimerPage() {
        val pg = pageur ?: return
        val page = pg.page
        val lignes = Accueil.lignesParPage
        val dedans = Accueil.disposition(this).count { it.row / lignes == page }
        val texte = if (dedans == 0) "Cette page est vide. La retirer ?" else "Retirer la page ${page + 1} et ses $dedans case${if (dedans > 1) "s" else ""} ? Les applis restent dans le tiroir ; les widgets et les dossiers sont retirés."
        AlertDialog.Builder(this).setTitle("Supprimer la page").setMessage(texte)
            .setPositiveButton("Supprimer") { _, _ -> Accueil.supprimerPage(this, page, lignes); pageMemo = (page - 1).coerceAtLeast(0); construire() }
            .setNegativeButton("Annuler", null).show()
    }

    /** Un widget neuf qu'on glisse depuis le panneau : le panneau s'efface, la grille montre où il tombera. */
    private fun souleverNouveau(v: View, w: Accueil.Widget): Boolean {
        enDrag = null; enDragNouveau = w; dragSorti = true
        val ok = if (Build.VERSION.SDK_INT >= 24) v.startDragAndDrop(ClipData.newPlainText("widget", w.code), View.DragShadowBuilder(v), w, 0) else @Suppress("DEPRECATION") v.startDrag(ClipData.newPlainText("widget", w.code), View.DragShadowBuilder(v), w, 0)
        if (ok) {
            v.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS)
            cacherPanneau()
            pageur?.let { pg -> pg.pagesVisibles = pg.pages }
        } else enDragNouveau = null
        return ok
    }

    /** Une case de la grille : appli, dossier ou widget. */
    private fun vuePlace(pl: Accueil.Place): View {
        val v: View = when {
            pl.estWidget -> vueWidget(pl)
            pl.estDossier -> { val d = Accueil.dossiers(this).firstOrNull { it.cle == pl.cle }; if (d != null) caseTelephone(Accueil.Case(pl.cle, dossier = d)) else View(this) }
            else -> caseTelephone(Accueil.Case(pl.cle, pkg = pl.cle))
        }
        v.tag = pl
        return v
    }

    private fun soulever(v: View, ombre: View, cle: String): Boolean {
        enDrag = cle; dragSorti = false
        val builder = View.DragShadowBuilder(ombre)
        val ok = if (Build.VERSION.SDK_INT >= 24) v.startDragAndDrop(ClipData.newPlainText("case", cle), builder, cle, 0) else @Suppress("DEPRECATION") v.startDrag(ClipData.newPlainText("case", cle), builder, cle, 0)
        if (ok) { v.alpha = 0.25f; zoneRetrait?.let { it.visibility = View.VISIBLE; it.alpha = 0.85f }; pageur?.let { pg -> pg.pagesVisibles = pg.pages } }
        v.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS)
        return ok
    }

    private fun finDrag(v: View, e: DragEvent, menu: () -> Unit) {
        v.alpha = 1f
        zoneRetrait?.visibility = View.GONE
        val ouvrirMenu = !dragSorti && !e.result
        enDrag = null
        if (ouvrirMenu) main.post { menu() }
    }

    private fun caseTelephone(c: Accueil.Case): View {
        val taille = 56f
        val contenu = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(px(2f), px(6f), px(2f), px(2f)); clipChildren = false }
        val d = if (c.dossier != null) disqueDossier(c.dossier, taille) else disque(Accueil.icone(this, c.pkg!!), taille)
        contenu.addView(d, LinearLayout.LayoutParams(px(taille), px(taille)))
        val nom = if (c.dossier != null) c.dossier.nom else Accueil.etiquette(this, c.pkg!!)
        contenu.addView(texte(nom, 11.5f, theme.encre2, Polices.moyen(this)).apply { maxLines = 2; ellipsize = android.text.TextUtils.TruncateAt.END; gravity = Gravity.CENTER; setPadding(px(2f), px(5f), px(2f), 0) })
        contenu.isClickable = true; contenu.isFocusable = true
        contenu.setOnClickListener { if (c.dossier != null) ouvrirDossier(c.dossier, emptyList()) else Accueil.lancer(this, c.pkg!!) }
        contenu.setOnLongClickListener { v -> soulever(v, d, c.cle) }
        contenu.setOnDragListener { v, e -> if (e.action == DragEvent.ACTION_DRAG_ENDED && enDrag == c.cle) finDrag(v, e) { menuTelephone(c, null) }; false }
        return contenu
    }

    /** Le menu d'appui long du téléphone : une feuille en bas de l'écran. */
    private fun menuTelephone(c: Accueil.Case, dossierParent: Accueil.Dossier?) {
        val dlg = Dialog(this)
        dlg.requestWindowFeature(Window.FEATURE_NO_TITLE)
        val feuille = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; background = fondCarte(30f); setPadding(px(18f), px(20f), px(18f), px(14f)) }
        val tete = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(px(6f), 0, px(6f), px(12f)) }
        val ic = FrameLayout(this)
        val dsq = if (c.dossier != null) disqueDossier(c.dossier, 48f) else disque(Accueil.icone(this, c.pkg!!), 48f)
        ic.addView(dsq, FrameLayout.LayoutParams(px(48f), px(48f), Gravity.CENTER))
        ic.addView(View(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(0); setStroke(px(1.5f), theme.or) } }, FrameLayout.LayoutParams(px(56f), px(56f), Gravity.CENTER))
        tete.addView(ic, LinearLayout.LayoutParams(px(56f), px(56f)))
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(px(14f), 0, 0, 0) }
        val nom = if (c.dossier != null) c.dossier.nom else Accueil.etiquette(this, c.pkg!!)
        col.addView(texte(nom, 18f, theme.encre, Polices.gras(this)))
        val sous = if (c.pkg != null) { val raison = Etat.doitBloquer(this, c.pkg); if (raison == null) "Autorisée" else "Fermée · $raison" } else "${c.dossier!!.pkgs.size} applis"
        col.addView(texte(sous, 13f, theme.encre2))
        tete.addView(col)
        feuille.addView(tete)
        feuille.addView(View(this).apply { setBackgroundColor(theme.carteBord) }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(1f)))
        fun ligne(res: Int, t: String, danger: Boolean = false, action: () -> Unit) {
            val l = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; minimumHeight = px(52f); setPadding(px(6f), 0, px(6f), 0); isClickable = true; isFocusable = true }
            val couleur = if (danger) theme.pourpre else theme.encre
            l.addView(icone(res, 24f, couleur))
            l.addView(texte(t, 17f, couleur, Polices.moyen(this)).apply { setPadding(px(16f), 0, 0, 0) })
            l.setOnClickListener { dlg.dismiss(); action() }
            feuille.addView(l)
        }
        if (dossierParent != null) ligne(R.drawable.ic_sortir, "Sortir du dossier") { Accueil.sortirSurGrille(this, dossierParent.cle, c.pkg!!); dossierOuvert?.dismiss(); construire() }
        if (c.pkg != null) {
            if (dossierParent == null) ligne(R.drawable.ic_retirer, "Retirer de l'accueil") { Accueil.retirerDeLaGrille(this, c.pkg); construire() }
            ligne(R.drawable.ic_infos, "Infos") { try { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${c.pkg}"))) } catch (_: Exception) {} }
            ligne(R.drawable.ic_desinstaller, "Désinstaller", danger = true) { try { startActivity(Intent(Intent.ACTION_DELETE, Uri.parse("package:${c.pkg}"))) } catch (_: Exception) {} }
        } else {
            ligne(R.drawable.ic_crayon, "Renommer") { renommer(c.dossier!!) }
            ligne(R.drawable.ic_retirer, "Défaire le dossier") { Accueil.defaireSurGrille(this, c.cle); construire() }
        }
        feuille.addView(texte("Pour déplacer : maintenir l'icône puis la faire glisser.", 13f, theme.encre2).apply { setPadding(px(6f), px(10f), px(6f), px(4f)) })
        dlg.setContentView(feuille)
        dlg.window?.let { w ->
            w.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(0))
            w.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            w.setGravity(Gravity.BOTTOM)
            w.attributes = w.attributes.apply { y = px(12f) }
            w.setDimAmount(0.45f)
        }
        dlg.show()
    }

    /** Le menu d'un widget : le retirer, ou en ajouter. */
    private fun menuWidget(pl: Accueil.Place) {
        val w = Accueil.widget(pl.code) ?: return
        AlertDialog.Builder(this).setTitle(w.nom).setItems(arrayOf("Retirer de l'accueil", "Ajouter un widget")) { _, k ->
            if (k == 0) { Accueil.retirerDeLaGrille(this, pl.cle); construire() } else montrerPanneau()
        }.show()
    }

    private fun dissoudre(cle: String) {
        val ds = Accueil.dossiers(this)
        val d = ds.firstOrNull { it.cle == cle } ?: return
        val l = ArrayList(Accueil.ordre(this))
        val k = l.indexOf(cle).let { if (it < 0) l.size else it }
        l.remove(cle)
        d.pkgs.reversed().forEach { l.add(k.coerceIn(0, l.size), it) }
        ds.remove(d)
        Accueil.ecrireDossiers(this, ds); Accueil.ecrireOrdre(this, l)
    }

    private fun renommer(d: Accueil.Dossier) {
        val champ = EditText(this).apply { setText(d.nom); setSelectAllOnFocus(true) }
        AlertDialog.Builder(this).setTitle("Nom du dossier").setView(champ)
            .setPositiveButton("Garder") { _, _ -> Accueil.renommerDossier(this, d.cle, champ.text.toString()); dossierOuvert?.dismiss(); construire() }
            .setNegativeButton("Annuler", null).show()
    }

    /** Le dossier ouvert : ses applis en grille, un bouton pour renommer. */
    private fun ouvrirDossier(d: Accueil.Dossier, cles: List<String>) {
        val dlg = Dialog(this)
        dlg.requestWindowFeature(Window.FEATURE_NO_TITLE)
        val boite = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; background = fondCarte(30f); setPadding(px(18f), px(20f), px(18f), px(16f)) }
        val tete = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        tete.addView(texte(d.nom, if (tele) tv(34f) else 22f, theme.encre, Polices.gras(this)), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val crayon = FrameLayout(this).apply { background = fondCarte(22f, couleur = 0); isClickable = true; isFocusable = true; setOnClickListener { renommer(d) } }
        crayon.addView(icone(R.drawable.ic_crayon, 22f, theme.or), FrameLayout.LayoutParams(px(22f), px(22f), Gravity.CENTER))
        tete.addView(crayon, LinearLayout.LayoutParams(px(44f), px(44f)))
        boite.addView(tete)
        val grilleD = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, px(14f), 0, 0) }
        val parLigne = if (tele) 6 else 3
        var ligne: LinearLayout? = null
        d.pkgs.forEachIndexed { i, pkg ->
            if (i % parLigne == 0) { ligne = LinearLayout(this); grilleD.addView(ligne) }
            val taille = if (tele) tv(96f) else 56f
            val cell = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(px(4f), px(8f), px(4f), px(8f)); isClickable = true; isFocusable = true }
            val dsq = disque(Accueil.icone(this, pkg), taille)
            val anneau = View(this).apply { background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(0); setStroke(px(1.5f), theme.or) }; visibility = View.INVISIBLE }
            val cadre = FrameLayout(this)
            cadre.addView(dsq, FrameLayout.LayoutParams(px(taille), px(taille), Gravity.CENTER))
            cadre.addView(anneau, FrameLayout.LayoutParams(px(taille + 12f), px(taille + 12f), Gravity.CENTER))
            cell.addView(cadre, LinearLayout.LayoutParams(px(taille + 12f), px(taille + 12f)))
            cell.addView(texte(Accueil.etiquette(this, pkg), if (tele) tv(20f) else 12f, theme.encre2, Polices.moyen(this)).apply { maxLines = 2; gravity = Gravity.CENTER; ellipsize = android.text.TextUtils.TruncateAt.END; setPadding(0, px(5f), 0, 0) })
            cell.setOnFocusChangeListener { _, a -> anneau.visibility = if (a) View.VISIBLE else View.INVISIBLE }
            cell.setOnClickListener { dlg.dismiss(); Accueil.lancer(this, pkg) }
            cell.setOnLongClickListener {
                if (tele) AlertDialog.Builder(this).setTitle(Accueil.etiquette(this, pkg)).setItems(arrayOf("Sortir du dossier", "Retirer de l'accueil")) { _, k ->
                    if (k == 0) Accueil.sortirDuDossier(this, cles, d.cle, pkg) else Accueil.cacher(this, pkg, true)
                    dlg.dismiss(); construire()
                }.show()
                else menuTelephone(Accueil.Case(pkg, pkg = pkg), d)
                true
            }
            ligne!!.addView(cell, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        val reste = d.pkgs.size % parLigne
        if (reste != 0) repeat(parLigne - reste) { ligne!!.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f)) }
        boite.addView(grilleD)
        dlg.setContentView(boite)
        dlg.window?.let { w ->
            w.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(0))
            w.setLayout(if (tele) (dm.widthPixels * 0.6f).toInt() else ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            w.attributes = w.attributes.apply { horizontalMargin = 0.06f }
            w.setDimAmount(0.55f)
        }
        dlg.setOnDismissListener { dossierOuvert = null }
        dossierOuvert = dlg
        dlg.show()
    }

    /** Le tiroir : toutes les applications, par ordre alphabétique ; un appui long propose de les ajouter à l'accueil. */
    private fun tiroirApplis() {
        if (tiroir?.isShowing == true) return
        val dlg = Dialog(this)
        tiroir = dlg
        dlg.setOnDismissListener { if (tiroir === dlg) tiroir = null }
        dlg.requestWindowFeature(Window.FEATURE_NO_TITLE)
        val defile = ScrollView(this).apply { background = fondCarte(30f) }
        val boite = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(px(18f), px(20f), px(18f), px(16f)) }
        defile.addView(boite)
        boite.addView(texte("Applications", 22f, theme.encre, Polices.gras(this)))
        boite.addView(texte("Appui long : ajouter à l'accueil, infos, désinstaller.", 12f, theme.encre2).apply { setPadding(0, px(2f), 0, px(8f)) })
        val pm = packageManager
        val toutes = Accueil.applicationsInstallees(this)
        val surAccueil = Accueil.disposition(this).map { it.cle }.toSet() + Accueil.dossiers(this).flatMap { it.pkgs }
        var ligne: LinearLayout? = null
        toutes.forEachIndexed { i, ri ->
            val pkg = ri.activityInfo.packageName
            if (i % 4 == 0) { ligne = LinearLayout(this); boite.addView(ligne) }
            val cell = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(px(2f), px(8f), px(2f), px(8f)); isClickable = true; isFocusable = true }
            cell.addView(disque(ri.loadIcon(pm), 52f), LinearLayout.LayoutParams(px(52f), px(52f)))
            cell.addView(texte(ri.loadLabel(pm).toString(), 11.5f, theme.encre2, Polices.moyen(this)).apply { maxLines = 2; gravity = Gravity.CENTER; ellipsize = android.text.TextUtils.TruncateAt.END; setPadding(0, px(5f), 0, 0); alpha = if (pkg in surAccueil) 1f else 0.7f })
            cell.setOnClickListener { dlg.dismiss(); Accueil.lancer(this, pkg) }
            cell.setOnLongClickListener {
                val deja = pkg in surAccueil
                AlertDialog.Builder(this).setTitle(ri.loadLabel(pm)).setItems(arrayOf(if (deja) "Déjà sur l'accueil" else "Ajouter à l'accueil", "Infos", "Désinstaller")) { _, k ->
                    when (k) {
                        0 -> if (!deja) { Accueil.ajouterALaGrille(this, pkg); dlg.dismiss(); construire() }
                        1 -> try { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$pkg"))) } catch (_: Exception) {}
                        2 -> try { startActivity(Intent(Intent.ACTION_DELETE, Uri.parse("package:$pkg"))) } catch (_: Exception) {}
                    }
                }.show(); true
            }
            ligne!!.addView(cell, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        val reste = toutes.size % 4
        if (reste != 0) repeat(4 - reste) { ligne!!.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f)) }
        dlg.setContentView(defile)
        dlg.window?.let { w -> w.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(0)); w.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, (dm.heightPixels * 0.82f).toInt()); w.setGravity(Gravity.BOTTOM); w.setDimAmount(0.5f); w.setWindowAnimations(0) }
        // Le tiroir monte du bas et se pose en douceur, comme tiré par le doigt.
        val course = dm.heightPixels * 0.82f
        defile.translationY = course; defile.alpha = 0.6f
        dlg.show()
        defile.animate().translationY(0f).alpha(1f).setDuration(300).setInterpolator(android.view.animation.DecelerateInterpolator(2.2f)).start()
    }

    // ---------------------------------------------------------------- widgets

    private fun vueWidget(pl: Accueil.Place): View {
        val d = donnees
        val cadre = FrameLayout(this).apply { setPadding(px(4f), px(4f), px(4f), px(4f)); clipChildren = false }
        val c: View = when (pl.code) {
            "horloge" -> widgetHorloge()
            "infos" -> widgetInfos()
            "devoirs" -> widgetDevoirs()
            "temps" -> widgetTemps()
            "demandes" -> widgetDemandes()
            "enfants" -> widgetEnfants()
            "chauffage" -> widgetChauffage()
            "fioul" -> widgetFioul()
            "ecole" -> widgetEcole()
            "camera" -> widgetCamera()
            "batteries" -> widgetBatteries()
            "maison" -> widgetMaison()
            else -> carte().also { it.addView(texte(pl.code, 13f, theme.encre3)) }
        }
        cadre.addView(c, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        cadre.isClickable = true
        cadre.setOnLongClickListener { v -> soulever(v, c, pl.cle) }
        cadre.setOnDragListener { v, e -> if (e.action == DragEvent.ACTION_DRAG_ENDED && enDrag == pl.cle) finDrag(v, e) { menuWidget(pl) }; false }
        if (d == null && pl.code != "horloge") c.alpha = 0.6f
        return cadre
    }

    private fun w(titre: String?, orientation: Int = LinearLayout.VERTICAL, bordOr: Boolean = false): LinearLayout = carte(24f, 14f, orientation, bordOr).also { c ->
        if (titre != null) c.addView(etiquetteSection(titre, 11f).apply { setPadding(0, 0, 0, px(4f)) })
    }

    private fun widgetHorloge(): View {
        val c = w(null, LinearLayout.HORIZONTAL).apply { gravity = Gravity.CENTER_VERTICAL }
        val g = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        g.addView(texte(heureFmt.format(Date()), 46f, theme.encre, Polices.outfitFin(this)).apply { includeFontPadding = false; tag = "w_heure" })
        g.addView(texte(dateFmt.format(Date()), 13f, theme.encre2, Polices.moyen(this)))
        c.addView(g, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val dr = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.END }
        dr.addView(texte("", 30f, theme.encre, Polices.outfitLeger(this)).apply { tag = "temp"; includeFontPadding = false })
        dr.addView(lignePluie(0f, 20f).apply { tag = "pluie" })
        dr.addView(texte("", 11f, theme.encre2).apply { tag = "pluie_texte" })
        c.addView(dr)
        return c
    }

    private fun ecoleDe(prenom: String): JSONObject? {
        val a = donnees?.optJSONArray("ecole") ?: return null
        for (i in 0 until a.length()) { val e = a.getJSONObject(i); if (prenom.isNotEmpty() && e.optString("prenom").equals(prenom, true)) return e }
        return if (a.length() == 1) a.getJSONObject(0) else null
    }

    private fun widgetInfos(): View {
        val moi = donnees?.optJSONObject("moi")
        val ecole = ecoleDe(moi?.optString("prenom").orEmpty())
        val controles = ecole?.optJSONArray("controles")
        val moy = moi?.optJSONObject("moyenne")
        val titre = when {
            controles != null && controles.length() > 0 -> "Contrôle de ${controles.getJSONObject(0).optString("matiere").lowercase(Locale.FRANCE)} ${if (ecole!!.optBoolean("demain")) "demain" else ecole.optString("jour")}"
            ecole != null -> "${if (ecole.optBoolean("demain")) "Demain" else ecole.optString("jour").replaceFirstChar { it.uppercase() }} : école de ${heureJolie(ecole.optString("debut"))} à ${heureJolie(ecole.optString("fin"))}"
            else -> "Rien de particulier"
        }
        val sous = ArrayList<String>()
        if (moy != null && !moy.isNull("valeur")) sous.add("Moyenne ${String.format(Locale.FRANCE, "%.1f", moy.optDouble("valeur"))}")
        moy?.optString("etat")?.let { if (it.contains("divertissement")) sous.add(it) }
        val c = w(null, LinearLayout.HORIZONTAL, bordOr = true).apply { gravity = Gravity.CENTER_VERTICAL }
        c.addView(icone(R.drawable.ic_alerte, 26f, theme.or))
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(px(12f), 0, 0, 0) }
        col.addView(texte(titre, 14.5f, theme.encre, Polices.gras(this)).apply { maxLines = 2; ellipsize = android.text.TextUtils.TruncateAt.END })
        if (sous.isNotEmpty()) col.addView(texte(sous.joinToString(" · "), 12f, theme.encre2).apply { maxLines = 1 })
        c.addView(col)
        return c
    }

    private fun widgetDevoirs(): View {
        val moi = donnees?.optJSONObject("moi")
        val ecole = ecoleDe(moi?.optString("prenom").orEmpty())
        val devoirs = ecole?.optJSONArray("devoirs")
        val c = w(null).apply { setPadding(px(14f), px(10f), px(14f), px(6f)) }
        val jour = ecole?.optString("jour")?.split(" ")?.firstOrNull().orEmpty()
        val tete = LinearLayout(this)
        tete.addView(etiquetteSection(if (jour.isEmpty()) "Devoirs" else "Devoirs pour $jour", 11f), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val compte = texte("", 12f, theme.encre2)
        tete.addView(compte)
        c.addView(tete)
        if (devoirs == null || devoirs.length() == 0) { c.addView(texte("Pas de devoirs connus", 13f, theme.encre3).apply { setPadding(0, px(8f), 0, 0) }); return c }
        val faits = getSharedPreferences(PREFS, MODE_PRIVATE).getStringSet("devoirs_faits", emptySet()) ?: emptySet()
        val cases = ArrayList<CheckBox>()
        fun recompter() { compte.text = "${cases.count { it.isChecked }} sur ${cases.size} fait${if (cases.count { it.isChecked } > 1) "s" else ""}" }
        for (i in 0 until minOf(4, devoirs.length())) {
            val dv = devoirs.getJSONObject(i)
            val cle = (ecole!!.optString("date") + "|" + dv.optString("matiere") + "|" + dv.optString("texte")).hashCode().toString()
            val ligne = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; minimumHeight = px(32f) }
            val cb = CheckBox(this).apply { isChecked = cle in faits; buttonTintList = android.content.res.ColorStateList.valueOf(theme.or) }
            val mat = texte(dv.optString("matiere"), 13f, theme.encre, Polices.gras(this)).apply { minWidth = px(60f) }
            val txt = texte(dv.optString("texte"), 13f, theme.encre2).apply { maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END }
            fun peindre() { val a = if (cb.isChecked) 0.6f else 1f; mat.alpha = a; txt.alpha = a; mat.paintFlags = if (cb.isChecked) mat.paintFlags or android.graphics.Paint.STRIKE_THRU_TEXT_FLAG else mat.paintFlags and android.graphics.Paint.STRIKE_THRU_TEXT_FLAG.inv() }
            cb.setOnCheckedChangeListener { _, coche ->
                val s = HashSet(getSharedPreferences(PREFS, MODE_PRIVATE).getStringSet("devoirs_faits", emptySet()) ?: emptySet())
                if (coche) s.add(cle) else s.remove(cle)
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putStringSet("devoirs_faits", s).apply()
                peindre(); recompter()
            }
            ligne.addView(cb); ligne.addView(mat); ligne.addView(txt, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            ligne.setOnClickListener { cb.toggle() }
            cases.add(cb); peindre()
            c.addView(ligne)
        }
        recompter()
        return c
    }

    private fun widgetTemps(): View {
        val moi = donnees?.optJSONObject("moi")
        val c = w(null, LinearLayout.HORIZONTAL).apply { gravity = Gravity.CENTER_VERTICAL }
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val verrou = moi?.optBoolean("verrouille") == true
        val prochain = moi?.optString("prochain_verrou").orEmpty().takeIf { it.length >= 16 }.orEmpty()
        val minutes = moi?.optInt("minutes_actif") ?: 0
        col.addView(texte(when { verrou -> "Écran fermé en ce moment"; prochain.isNotEmpty() -> "Écran ouvert jusqu'à ${prochain.substring(11, 16)}"; else -> "${duree(minutes)} d'écran aujourd'hui" }, 14f, theme.encre, Polices.demiGras(this)).apply { maxLines = 1 })
        if (prochain.isNotEmpty() && !verrou) {
            val fin = try { Calendar.getInstance().apply { set(Calendar.HOUR_OF_DAY, prochain.substring(11, 13).toInt()); set(Calendar.MINUTE, prochain.substring(14, 16).toInt()) }.timeInMillis } catch (_: Exception) { 0L }
            val reste = ((fin - System.currentTimeMillis()) / 60_000L).coerceAtLeast(0L)
            val total = (reste + minutes).coerceAtLeast(1L)
            val part = (minutes / total.toFloat()).coerceIn(0f, 1f)
            val barre = FrameLayout(this).apply { background = GradientDrawable().apply { cornerRadius = px(3f).toFloat(); setColor(Palette.melanger(theme.carte, theme.encre, 0.08f)) } }
            barre.addView(View(this).apply { background = GradientDrawable().apply { cornerRadius = px(3f).toFloat(); setColor(theme.pourpre) } }, FrameLayout.LayoutParams((dm.widthPixels * 0.45f * part).toInt().coerceAtLeast(px(4f)), px(5f)))
            col.addView(barre, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(5f)).apply { topMargin = px(6f) })
            col.addView(texte("encore ${duree(reste.toInt())}", 11f, theme.encre2).apply { setPadding(0, px(3f), 0, 0) })
        }
        c.addView(col, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        c.addView(bouton("Du temps", true) { demanderTemps() }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, px(40f)).apply { leftMargin = px(8f) })
        return c
    }

    private fun demanderTemps() {
        val choix = arrayOf("15 minutes", "30 minutes", "1 heure")
        AlertDialog.Builder(this).setTitle("Demander du temps aux parents").setItems(choix) { _, k ->
            cfg.demandeTemps = listOf(15, 30, 60)[k]
            android.widget.Toast.makeText(this, "Demande envoyée aux parents.", android.widget.Toast.LENGTH_LONG).show()
        }.setNegativeButton("Annuler", null).show()
    }

    private fun widgetDemandes(): View {
        val demandes = donnees?.optJSONArray("demandes")
        if (demandes == null || demandes.length() == 0) return w("Demandes").also { it.addView(texte("Aucune demande en attente", 13f, theme.encre3).apply { setPadding(0, px(6f), 0, 0) }) }
        val dem = demandes.getJSONObject(0)
        val c = w(if (demandes.length() > 1) "Demande en attente · ${demandes.length()}" else "Demande en attente", bordOr = true)
        c.addView(texte("${dem.optString("prenom")} demande ${dem.optString("libelle")}", 16f, theme.encre, Polices.demiGras(this)).apply { setPadding(0, px(4f), 0, px(8f)); maxLines = 2 })
        val boutons = LinearLayout(this)
        val pc = dem.optString("pc"); val id = dem.optString("id"); val temps = dem.optString("genre") == "temps"
        boutons.addView(bouton("Refuser", false) { if (temps) ReponseReceiver.envoyer(this, pc, id, 0) { demarrerDonnees() } else Acces.repondre(this, pc, id, "non") { demarrerDonnees() } }, LinearLayout.LayoutParams(0, px(40f), 1f).apply { rightMargin = px(8f) })
        boutons.addView(bouton("Accepter", true) { if (temps) ReponseReceiver.envoyer(this, pc, id, dem.optInt("minutes", 30).coerceAtLeast(5)) { demarrerDonnees() } else Acces.repondre(this, pc, id, "temporaire") { demarrerDonnees() } }, LinearLayout.LayoutParams(0, px(40f), 1f))
        c.addView(boutons)
        return c
    }

    private fun widgetEnfants(): View {
        val maison = donnees?.optJSONArray("maison")
        val c = w("Les enfants")
        if (maison == null || maison.length() == 0) { c.addView(texte("Personne pour l'instant", 13f, theme.encre3)); return c }
        for (i in 0 until minOf(4, maison.length())) {
            val p = maison.getJSONObject(i)
            val apps = p.optJSONArray("appareils")
            var enLigne = 0; var verrou = 0
            for (k in 0 until (apps?.length() ?: 0)) { val a = apps!!.getJSONObject(k); if (a.optBoolean("en_ligne")) enLigne++; if (a.optBoolean("verrouille")) verrou++ }
            val etat = when { verrou > 0 && verrou == (apps?.length() ?: 0) -> "fermé"; enLigne > 0 -> "${duree(p.optInt("minutes"))} · en ligne"; else -> duree(p.optInt("minutes")) }
            val ligne = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; minimumHeight = px(30f) }
            ligne.addView(texte(p.optString("prenom"), 14f, theme.encre, Polices.demiGras(this)), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            ligne.addView(texte(etat, 13f, theme.encre2))
            c.addView(ligne)
        }
        c.setOnClickListener { startActivity(Intent(this, ParentsActivity::class.java)) }
        return c
    }

    private fun widgetChauffage(): View {
        val ch = donnees?.optJSONObject("chauffage")
        val c = w("Chauffage")
        if (ch == null) { c.addView(texte("–", 30f, theme.encre3)); return c }
        c.addView(texte(if (ch.isNull("dedans")) "–" else String.format(Locale.FRANCE, "%.1f°", ch.optDouble("dedans")), 30f, theme.encre, Polices.outfitLeger(this)).apply { includeFontPadding = false })
        val dets = ArrayList<String>()
        if (!ch.isNull("consigne")) dets.add("consigne ${String.format(Locale.FRANCE, "%.0f°", ch.optDouble("consigne"))}")
        if (!ch.isNull("dehors")) dets.add("dehors ${String.format(Locale.FRANCE, "%.0f°", ch.optDouble("dehors"))}")
        c.addView(texte(dets.joinToString(" · "), 11.5f, theme.encre2).apply { maxLines = 2 })
        val l = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(0, px(6f), 0, 0) }
        l.addView(pastille(if (ch.optBoolean("bruleur_on")) theme.pourpre else theme.encre3), LinearLayout.LayoutParams(px(8f), px(8f)).apply { rightMargin = px(8f) })
        l.addView(texte(if (ch.optBoolean("bruleur_on")) "Brûleur en marche" else "Brûleur au repos", 11.5f, theme.encre2))
        c.addView(l)
        return c
    }

    private fun widgetFioul(): View {
        val ch = donnees?.optJSONObject("chauffage")
        val c = w("Fioul")
        val js = ch?.optJSONArray("jours"); val n = js?.length() ?: 0
        if (n == 0) { c.addView(texte("–", 30f, theme.encre3)); return c }
        var somme = 0.0; var max = 1.0
        for (i in 0 until n) { val v = js!!.getJSONObject(i).optDouble("litres", 0.0); somme += v; max = maxOf(max, v) }
        c.addView(texte(String.format(Locale.FRANCE, "%.1f L", somme / n), 30f, theme.encre, Polices.outfitLeger(this)).apply { includeFontPadding = false })
        c.addView(texte("par jour, sur $n jours", 11.5f, theme.encre2))
        val barres = LinearLayout(this).apply { gravity = Gravity.BOTTOM; setPadding(0, px(8f), 0, 0) }
        for (i in maxOf(0, n - 7) until n) {
            val h = (px(26f) * js!!.getJSONObject(i).optDouble("litres", 0.0) / max).toInt().coerceAtLeast(px(3f))
            barres.addView(View(this).apply { background = GradientDrawable().apply { cornerRadius = px(3f).toFloat(); setColor(if (i == n - 1) theme.pourpre else theme.or) } }, LinearLayout.LayoutParams(0, h, 1f).apply { setMargins(px(2f), 0, px(2f), 0) })
        }
        c.addView(barres, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(26f)))
        return c
    }

    private fun widgetEcole(): View {
        val ecoles = donnees?.optJSONArray("ecole")
        val e = ecoles?.let { if (it.length() > 0) it.getJSONObject(0) else null }
        val c = w(if (e == null) "École" else "École · ${e.optString("prenom")}")
        if (e == null) { c.addView(texte("Pas de cours connus", 13f, theme.encre3)); return c }
        val controles = e.optJSONArray("controles")
        if (controles != null && controles.length() > 0) c.addView(texte("Contrôle de ${controles.getJSONObject(0).optString("matiere").lowercase(Locale.FRANCE)} ${if (e.optBoolean("demain")) "demain" else e.optString("jour")}", 14f, theme.encre, Polices.demiGras(this)))
        val cours = e.optJSONArray("cours")
        val noms = ArrayList<String>(); for (k in 0 until minOf(4, cours?.length() ?: 0)) noms.add(cours!!.getJSONObject(k).optString("matiere"))
        if (noms.isNotEmpty()) c.addView(texte("${e.optString("jour").replaceFirstChar { it.uppercase() }} ${heureJolie(e.optString("debut"))} : ${noms.joinToString(", ")}", 12.5f, theme.encre2).apply { maxLines = 2 })
        val nd = e.optJSONArray("devoirs")?.length() ?: 0
        c.addView(texte(if (nd == 0) "Pas de devoirs" else "$nd devoir${if (nd > 1) "s" else ""} à faire", 11.5f, theme.encre2))
        return c
    }

    private fun widgetCamera(): View {
        val cams = donnees?.optJSONArray("cameras")
        val c = w(null).apply { setPadding(px(8f), px(8f), px(8f), px(8f)) }
        if (cams == null || cams.length() == 0) { c.addView(texte("Caméra", 13f, theme.encre3)); return c }
        val img = ImageView(this).apply { scaleType = ImageView.ScaleType.CENTER_CROP; clipToOutline = true; outlineProvider = object : android.view.ViewOutlineProvider() { override fun getOutline(v: View, o: android.graphics.Outline) { o.setRoundRect(0, 0, v.width, v.height, px(16f).toFloat()) } } }
        c.addView(img, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        val cam = cams.getJSONObject(0)
        c.addView(texte(cam.optString("nom"), 11.5f, theme.encre2).apply { setPadding(px(4f), px(4f), 0, 0); maxLines = 1 })
        chargerImageCamera(cam.optString("id"), img)
        c.setOnClickListener { Veille.ouvrir(this) }
        return c
    }

    private fun widgetBatteries(): View {
        val bats = donnees?.optJSONArray("batteries")
        val c = w("Batteries")
        if (bats == null || bats.length() == 0) { c.addView(texte("–", 13f, theme.encre3)); return c }
        for (i in 0 until minOf(3, bats.length())) {
            val b = bats.getJSONObject(i)
            val l = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
            l.addView(texte(b.optString("nom"), 11.5f, theme.encre).apply { maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            l.addView(texte("${b.optInt("niveau")} %", 11.5f, theme.encre2, Polices.demiGras(this)))
            c.addView(l)
            val niveau = b.optInt("niveau")
            val barre = FrameLayout(this).apply { background = GradientDrawable().apply { cornerRadius = px(2f).toFloat(); setColor(Palette.melanger(theme.carte, theme.encre, 0.08f)) } }
            barre.addView(View(this).apply { background = GradientDrawable().apply { cornerRadius = px(2f).toFloat(); setColor(if (niveau <= 20) theme.pourpre else theme.or) } }, FrameLayout.LayoutParams(0, px(4f)).also { lp -> barre.post { lp.width = (barre.width * niveau / 100f).toInt().coerceAtLeast(px(3f)); barre.requestLayout() } })
            c.addView(barre, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(4f)).apply { topMargin = px(3f); bottomMargin = px(5f) })
        }
        return c
    }

    private fun widgetMaison(): View {
        val maison = donnees?.optJSONArray("maison")
        val c = w(null, LinearLayout.HORIZONTAL).apply { gravity = Gravity.CENTER_VERTICAL }
        if (maison == null || maison.length() == 0) { c.addView(texte("La maison", 13f, theme.encre3)); return c }
        for (i in 0 until minOf(4, maison.length())) {
            val p = maison.getJSONObject(i)
            val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
            col.addView(texte(p.optString("prenom"), 12.5f, theme.encre, Polices.demiGras(this)).apply { maxLines = 1 })
            col.addView(texte(duree(p.optInt("minutes")), 11.5f, theme.encre2))
            c.addView(col, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        return c
    }

    private fun chargerImageCamera(entite: String, img: ImageView) {
        Thread {
            try {
                val octets = Net.postBytes(this, cfg, "/api/pc_parental/veille/image", JSONObject().put("id", cfg.id).put("secret", cfg.secret).put("entite", entite), 15_000)
                val bm: Bitmap? = octets?.let { BitmapFactory.decodeByteArray(it, 0, it.size) }
                if (bm != null) main.post { img.setImageBitmap(bm) }
            } catch (_: Exception) {}
        }.also { it.isDaemon = true }.start()
    }

    private fun duree(min: Int): String { val h = min / 60; val m = min % 60; return if (h > 0) "$h h ${String.format(Locale.FRANCE, "%02d", m)}" else "$m min" }
    private fun heureJolie(h: String): String = h.replace(Regex("^(\\d{1,2}):(\\d\\d).*")) { "${it.groupValues[1].toInt()} h ${it.groupValues[2]}" }

    /** La barre « pluie dans l'heure » : douze segments, plus hauts quand il pleut. */
    private fun lignePluie(tailleTexte: Float, hauteurMax: Float): LinearLayout {
        val l = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL or Gravity.END; setPadding(0, px(6f), 0, 0) }
        if (tailleTexte > 0) l.addView(texte("Pluie dans l'heure", tailleTexte, theme.encre2).apply { tag = "pluie_texte"; setPadding(0, 0, px(14f), 0) })
        val barres = LinearLayout(this).apply { gravity = Gravity.BOTTOM; tag = "pluie_barres" }
        repeat(12) { barres.addView(View(this).apply { background = GradientDrawable().apply { cornerRadius = px(4f).toFloat(); setColor(theme.pourpre) }; alpha = 0.35f }, LinearLayout.LayoutParams(px(if (tele) 12f else 7f), px(hauteurMax * 0.25f)).apply { setMargins(px(2.5f), 0, px(2.5f), 0) }) }
        l.addView(barres, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, px(hauteurMax)))
        return l
    }

    // ------------------------------------------------------------------ données

    private fun demarrerDonnees() {
        fil?.interrupt()
        fil = Thread {
            while (!Thread.currentThread().isInterrupted) {
                try {
                    val r = Net.post(this, cfg, "/api/pc_parental/veille", JSONObject().put("id", cfg.id).put("secret", cfg.secret).put("ecran", if (tele) "tele" else "telephone").put("locaux", Local.locaux(this)), 20_000)
                    Local.amorcer(this, r.optJSONObject("reglages"))
                    donnees = r
                    if (!tele) VerrouActivity.retenir(this, r)
                    val p = r.optJSONObject("moi")?.optString("public").orEmpty()
                    val profilChange = p.isNotEmpty() && p != profilConnu
                    if (profilChange) { profilConnu = p; getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("profil", p).apply() }
                    main.post { if (profilChange && !tele) demanderReconstruction() else appliquerDonnees() }
                } catch (_: Exception) {}
                try { Thread.sleep(60_000) } catch (_: InterruptedException) { break }
            }
        }.also { it.isDaemon = true; it.start() }
    }

    private fun appliquerDonnees() {
        val d = donnees ?: return
        val m = d.optJSONObject("meteo")
        racine.findViewWithTag<TextView>("temp")?.text = if (m == null || m.isNull("temperature")) "" else String.format(Locale.FRANCE, "%.0f°", m.optDouble("temperature"))
        val cond = ArrayList<String>()
        m?.optString("etat")?.takeIf { it.isNotEmpty() }?.let { cond.add(Meteo.libelle(it)) }
        val vig = d.optJSONObject("vigilance")
        if (vig != null && vig.optInt("rang", 0) >= 2) cond.add("Vigilance ${vig.optString("niveau")}")
        racine.findViewWithTag<TextView>("cond")?.text = cond.joinToString(" · ")
        racine.findViewWithTag<TextView>("salut")?.text = salutation()
        // La pluie dans l'heure.
        val pl = d.optJSONObject("pluie")
        val barres = racine.findViewWithTag<LinearLayout>("pluie_barres")
        if (barres != null) {
            val niveaux = IntArray(12)
            pl?.optJSONArray("points")?.let { pts -> for (i in 0 until pts.length()) { val p = pts.getJSONObject(i); val k = (p.optInt("min") / 5).coerceIn(0, 11); niveaux[k] = maxOf(niveaux[k], p.optInt("niveau")) } }
            for (i in 0 until barres.childCount) {
                val v = barres.getChildAt(i); val lp = v.layoutParams
                val n = niveaux[i]
                v.alpha = if (n <= 0) 0.3f else 0.55f + 0.15f * n
                lp.height = ((barres.height.takeIf { it > 0 } ?: px(28f)) * (if (n <= 0) 0.25f else 0.45f + 0.18f * n)).toInt().coerceAtLeast(px(4f))
                v.layoutParams = lp
            }
            racine.findViewWithTag<TextView>("pluie_texte")?.text = when {
                pl == null -> "Pluie : pas de données"
                !pl.isNull("dans") && pl.optInt("dans") <= 0 -> "Il pleut"
                !pl.isNull("dans") -> "Pluie dans ${pl.optInt("dans")} min"
                pl.optBoolean("pluie") -> "Pluie possible dans l'heure"
                else -> "Pas de pluie dans l'heure"
            }
        }
        val dem = d.optJSONArray("demandes")
        racine.findViewWithTag<View>("demandes")?.let { v ->
            val n = dem?.length() ?: 0
            v.visibility = if (n > 0) View.VISIBLE else View.GONE
            racine.findViewWithTag<TextView>("demandes_texte")?.text = if (n == 1) "${dem!!.getJSONObject(0).optString("prenom")} demande ${dem.getJSONObject(0).optString("libelle")}" else "$n demandes en attente"
        }
        // Sur le téléphone, les widgets portent des données : on les rafraîchit sans toucher au reste.
        if (!tele) grille?.let { g ->
            for (i in 0 until g.childCount) {
                val v = g.getChildAt(i); val p = v.tag as? Accueil.Place ?: continue
                if (p.estWidget && p.code != "horloge" && enDrag == null) { val n = vueWidget(p); n.tag = p; g.removeViewAt(i); g.addView(n, i) }
            }
        }
    }
}
