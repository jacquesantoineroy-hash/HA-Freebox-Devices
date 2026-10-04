package fr.familleroy.vision

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.graphics.drawable.StateListDrawable
import android.os.Build
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/**
 * La charte de Vision, sans bibliothèque : la même que l'écran de veille et
 * le lanceur (thème de l'appareil et couleurs à la carte), cartes arrondies,
 * polices Figtree et Outfit, du vert pour ce qui va et du rouge pour ce qui
 * ferme. Tout est construit en code pour rester une seule petite APK,
 * téléphone comme TV. Chaque bouton garde un état « focus » visible pour la
 * télécommande.
 */
object Ui {
    // Palette courante : dérivée du thème de l'appareil (Beige, Sombre, Bleu nuit, Sauge, Rose poudré)
    // et des couleurs à la carte, les mêmes que l'écran de veille et le lanceur.
    // Des `var` pour pouvoir changer de thème sans relancer l'application.
    var FOND = 0xFFEFE6D6.toInt()
    var CARTE = 0xFFFBF6EC.toInt()
    var CARTE_HAUTE = 0xFFF3ECDF.toInt()
    var LIGNE = 0x558C2F4B
    var OR = 0xFF8F6110.toInt()
    var OR_SOMBRE = 0xFFFFFFFF.toInt()   // l'encre posée sur l'or (blanc sur or sombre, nuit sur or clair)
    var POURPRE = 0xFF8C2F4B.toInt()
    var VERT = 0xFF2F8A5E.toInt()
    var ROUGE = 0xFFC0392B.toInt()
    var BLEU = 0xFF3E7CC4.toInt()
    var TEXTE = 0xFF2A2026.toInt()
    var TEXTE_2 = 0xFF6E5A5E.toInt()
    var TEXTE_3 = 0xFF8F7D80.toInt()
    var SOMBRE = false
    private var police: Typeface? = null
    private var policeGras: Typeface? = null
    private var policeTitre: Typeface? = null

    /** Applique le thème de l'appareil (celui de l'écran de veille et du lanceur). À appeler au début de chaque écran. */
    fun charger(ctx: Context) {
        appliquer(Local.themeEffectif(ctx, Palette.APPLI))
        police = Polices.texte(ctx); policeGras = Polices.demiGras(ctx); policeTitre = Polices.outfit(ctx)
        val w = (ctx as? android.app.Activity)?.window ?: return
        w.statusBarColor = FOND; w.navigationBarColor = FOND
        if (Build.VERSION.SDK_INT >= 23) {
            var f = w.decorView.systemUiVisibility or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            f = if (SOMBRE) f and View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR.inv() else f or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
            if (Build.VERSION.SDK_INT >= 26) f = if (SOMBRE) f and View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR.inv() else f or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            w.decorView.systemUiVisibility = f
        }
    }

    fun appliquer(t: Theme) {
        SOMBRE = t.sombre
        FOND = t.fond; CARTE = t.carte; TEXTE = t.encre; TEXTE_2 = t.encre2; TEXTE_3 = t.encre3
        OR = t.or; POURPRE = t.pourpre
        CARTE_HAUTE = Palette.melanger(CARTE, TEXTE, 0.07f)
        LIGNE = Palette.melanger(CARTE, TEXTE, 0.16f)
        OR_SOMBRE = if (Palette.luminance(OR) > 0.55f) Palette.melanger(FOND, 0xFF000000.toInt(), 0.75f) else 0xFFFFFFFF.toInt()
        if (t.sombre) { VERT = 0xFF4CC38A.toInt(); ROUGE = 0xFFFF6B6B.toInt(); BLEU = 0xFF7FB8FF.toInt() }
        else { VERT = 0xFF2F8A5E.toInt(); ROUGE = 0xFFB8322A.toInt(); BLEU = 0xFF3E7CC4.toInt() }
    }

    fun dp(ctx: Context, v: Float): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, ctx.resources.displayMetrics).toInt()

    fun fond(couleur: Int, rayon: Float, bord: Int = 0, couleurBord: Int = LIGNE): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = rayon
            setColor(couleur)
            if (bord > 0) setStroke(bord, couleurBord)
        }

    /** Fond avec un état « focus » net pour la télécommande, et une ondulation au toucher. */
    private fun fondInteractif(ctx: Context, normal: Int, focus: Int, rayon: Float, bordFocus: Int = OR): android.graphics.drawable.Drawable {
        val etats = StateListDrawable().apply {
            addState(intArrayOf(android.R.attr.state_focused), fond(focus, rayon, dp(ctx, 2f), bordFocus))
            addState(intArrayOf(android.R.attr.state_pressed), fond(focus, rayon))
            addState(intArrayOf(), fond(normal, rayon))
        }
        return if (Build.VERSION.SDK_INT >= 21)
            RippleDrawable(ColorStateList.valueOf(0x33FFFFFF), etats, fond(Color.WHITE, rayon))
        else etats
    }

    /** La marque Vision, au milieu en haut, partout dans l'appli. */
    fun marque(ctx: Context): LinearLayout = LinearLayout(ctx).apply {
        gravity = Gravity.CENTER
        addView(ImageView(ctx).apply { setImageResource(R.drawable.ic_vision) }, LinearLayout.LayoutParams(dp(ctx, 20f), dp(ctx, 20f)))
        addView(TextView(ctx).apply { text = "VISION"; textSize = 12f; setTextColor(OR); typeface = Polices.gras(ctx); letterSpacing = 0.28f; setPadding(dp(ctx, 8f), 0, 0, 0) })
        layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { bottomMargin = dp(ctx, 16f) }
    }

    fun colonne(ctx: Context, pad: Int = 0): LinearLayout = LinearLayout(ctx).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(pad, pad, pad, pad)
    }

    fun rangee(ctx: Context): LinearLayout = LinearLayout(ctx).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
    }

    fun carte(ctx: Context, couleur: Int = CARTE): LinearLayout = LinearLayout(ctx).apply {
        orientation = LinearLayout.VERTICAL
        background = fond(couleur, dp(ctx, 22f).toFloat(), dp(ctx, 1f), LIGNE)
        val p = dp(ctx, 18f)
        setPadding(p, p, p, p)
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = dp(ctx, 14f) }
    }

    fun texte(ctx: Context, t: CharSequence, taille: Float = 15f, couleur: Int = TEXTE,
              gras: Boolean = false, centre: Boolean = false): TextView = TextView(ctx).apply {
        text = t; textSize = taille; setTextColor(couleur)
        typeface = if (gras) (policeGras ?: Typeface.DEFAULT_BOLD) else (police ?: Typeface.DEFAULT)
        if (centre) gravity = Gravity.CENTER
        setLineSpacing(0f, 1.15f)
    }

    fun titre(ctx: Context, t: String): TextView = texte(ctx, t, 26f, TEXTE, gras = true).apply { typeface = policeTitre ?: typeface }

    fun sousTitre(ctx: Context, t: String): TextView = texte(ctx, t, 14f, TEXTE_2)

    /** Intitulé de section, en petites capitales dorées. */
    fun section(ctx: Context, t: String): TextView = texte(ctx, t.uppercase(), 12f, OR, gras = true).apply {
        letterSpacing = 0.18f
        setTextColor(TEXTE_2)
        setPadding(dp(ctx, 4f), dp(ctx, 10f), 0, dp(ctx, 10f))
    }

    /** Petite pastille colorée avec un texte court : « Ouvert », « Fermé »… */
    fun chip(ctx: Context, t: String, couleur: Int): TextView = TextView(ctx).apply {
        text = t; textSize = 12f; setTextColor(couleur)
        typeface = policeGras ?: Typeface.DEFAULT_BOLD
        background = fond((couleur and 0x00FFFFFF) or 0x26000000, dp(ctx, 999f).toFloat(), dp(ctx, 1f), (couleur and 0x00FFFFFF) or 0x66000000)
        setPadding(dp(ctx, 12f), dp(ctx, 5f), dp(ctx, 12f), dp(ctx, 5f))
    }

    /** Rond d'état : vert coché, ou gris vide. */
    fun pastille(ctx: Context, ok: Boolean): TextView = TextView(ctx).apply {
        val d = dp(ctx, 28f)
        layoutParams = LinearLayout.LayoutParams(d, d).apply { rightMargin = dp(ctx, 14f) }
        gravity = Gravity.CENTER
        text = if (ok) "✓" else ""
        textSize = 15f
        setTextColor(Color.WHITE); typeface = policeGras ?: Typeface.DEFAULT_BOLD
        background = if (ok) fond(VERT, d / 2f) else fond(Color.TRANSPARENT, d / 2f, dp(ctx, 2f), TEXTE_3)
    }

    fun icone(ctx: Context, res: Int, taille: Float, teinte: Int = OR): ImageView = ImageView(ctx).apply {
        setImageResource(res)
        val d = dp(ctx, taille)
        layoutParams = LinearLayout.LayoutParams(d, d)
        if (Build.VERSION.SDK_INT >= 21) imageTintList = ColorStateList.valueOf(teinte)
    }

    fun boutonPrimaire(ctx: Context, t: String, action: () -> Unit): Button = Button(ctx).apply {
        text = t; isAllCaps = false; textSize = 15f
        setTextColor(OR_SOMBRE); typeface = policeGras ?: Typeface.DEFAULT_BOLD
        background = fondInteractif(ctx, OR, Palette.melanger(OR, TEXTE, 0.15f), dp(ctx, 999f).toFloat(), TEXTE)
        stateListAnimator = null
        minHeight = dp(ctx, 48f); minimumHeight = dp(ctx, 48f)
        setPadding(dp(ctx, 20f), 0, dp(ctx, 20f), 0)
        isFocusable = true
        setOnClickListener { action() }
    }

    fun boutonSecondaire(ctx: Context, t: String, action: () -> Unit): Button = Button(ctx).apply {
        text = t; isAllCaps = false; textSize = 14f
        setTextColor(TEXTE); typeface = policeGras ?: Typeface.DEFAULT_BOLD
        background = fondInteractif(ctx, CARTE_HAUTE, Palette.melanger(CARTE_HAUTE, TEXTE, 0.1f), dp(ctx, 999f).toFloat())
        stateListAnimator = null
        minHeight = dp(ctx, 44f); minimumHeight = dp(ctx, 44f)
        setPadding(dp(ctx, 16f), 0, dp(ctx, 16f), 0)
        isFocusable = true
        setOnClickListener { action() }
    }

    fun boutonDanger(ctx: Context, t: String, action: () -> Unit): Button =
        boutonSecondaire(ctx, t, action).apply { setTextColor(ROUGE) }

    fun champ(ctx: Context, indice: String, valeur: String, chiffres: Boolean = false): EditText = EditText(ctx).apply {
        hint = indice; setText(valeur)
        setTextColor(TEXTE); setHintTextColor(TEXTE_3); textSize = 15f; typeface = police ?: typeface
        background = fond(FOND, dp(ctx, 14f).toFloat(), dp(ctx, 1f), LIGNE)
        val p = dp(ctx, 14f); setPadding(p, p, p, p)
        inputType = if (chiffres)
            android.text.InputType.TYPE_CLASS_NUMBER or android.text.InputType.TYPE_NUMBER_VARIATION_PASSWORD
        else android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(ctx, 8f) }
    }

    fun separateur(ctx: Context): View = View(ctx).apply {
        setBackgroundColor(LIGNE)
        layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(ctx, 1f)).apply {
            topMargin = dp(ctx, 10f); bottomMargin = dp(ctx, 10f)
        }
    }

    fun espace(ctx: Context, h: Float): View = View(ctx).apply {
        layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(ctx, h))
    }

    fun poids(v: View, poids: Float = 1f): View = v.apply {
        layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, poids)
    }

    fun marge(ctx: Context, v: View, haut: Float = 0f, bas: Float = 0f, gauche: Float = 0f, droite: Float = 0f): View = v.apply {
        val lp = (layoutParams as? LinearLayout.LayoutParams) ?: LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        lp.topMargin = dp(ctx, haut); lp.bottomMargin = dp(ctx, bas)
        lp.leftMargin = dp(ctx, gauche); lp.rightMargin = dp(ctx, droite)
        layoutParams = lp
    }
}
