package fr.familleroy.vision

import android.annotation.SuppressLint
import android.graphics.Color
import android.net.http.SslError
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import org.json.JSONObject
import java.net.URLEncoder

/**
 * La page de veille de Home Assistant, posée par-dessus le dessin de l'appli.
 *
 * C'est la même page que sur les PC : les vraies cartes des tableaux de bord,
 * dessinées par Home Assistant, dans les couleurs et le style de cet
 * appareil. L'appareil garde la main sur tout ce qui est à lui : les tableaux
 * montrés, leurs cartes, leurs durées, le thème, la nuit, la radio.
 *
 * Tant que la page n'a pas dit « je suis là », rien ne change à l'écran : le
 * dessin de l'appli (horloge, cartes simplifiées) reste visible. Si la page
 * ne vient pas (pas de réseau, moteur web trop ancien, certificat refusé),
 * elle est retirée et le dessin de l'appli continue seul.
 */
class VeilleWeb(private val cadre: FrameLayout, private val native: VeilleView) {
    private val ctx = cadre.context
    private val main = Handler(Looper.getMainLooper())
    private var web: WebView? = null
    private var jeton = ""
    private var base = ""
    private var chargee = ""
    private var versionVue = -1
    @Volatile private var actif = false
    @Volatile private var abandonnee = false
    private var annonce = ""

    /**
     * Vrai tant que la page est attendue : le dessin de l'appli se tait alors (un fond uni, rien d'autre),
     * pour que jamais deux horloges ne se voient l'une sur l'autre. Si la page ne vient pas, il reprend.
     */
    val enAttente: Boolean get() = actif && !abandonnee && !montree

    /** Vrai quand la page est à l'écran : les gestes vont alors à elle. */
    @Volatile var montree = false
        private set

    fun demarrer() {
        if (actif || abandonnee) return
        if (!Local.veilleWeb(ctx)) return
        actif = true
        // Passé ce délai sans page à l'écran, le dessin de l'appli reprend pour de bon : on ne laisse pas un écran vide.
        main.postDelayed(tropLong, 20_000)
        Thread {
            try {
                val cfg = Config(ctx)
                if (!cfg.inscrit) { abandonnee = true; return@Thread }
                val r = Net.post(ctx, cfg, "/api/pc_parental/veille/acces",
                    JSONObject().put("id", cfg.id).put("secret", cfg.secret).put("ecran", ecran()), 15_000)
                val j = r.optString("jeton")
                if (j.isEmpty() || cfg.urlActive.isEmpty()) { abandonnee = true; return@Thread }
                Local.retenirListeWeb(ctx, r.optJSONArray("tableaux"))
                jeton = j; base = cfg.urlActive
                main.post { if (actif) ouvrir() }
            } catch (_: Exception) { abandonnee = true /* le dessin de l'appli reprend */ }
        }.also { it.isDaemon = true }.start()
    }

    fun arreter() {
        actif = false
        main.removeCallbacks(veilleur)
        main.removeCallbacks(tropLong); main.removeCallbacks(fonduFini)
        retirer()
    }

    fun naviguer(delta: Int) { js("window.__visionVeille&&window.__visionVeille.aller(${if (delta < 0) -1 else 1})") }
    fun basculerPause() { js("window.__visionVeille&&window.__visionVeille.figer()") }

    /** Un mot à montrer en bas à droite de la page (une demande d'accès en attente) ; vide pour l'effacer. */
    fun annoncer(texte: String) {
        annonce = texte
        if (montree) js("window.__visionVeille&&window.__visionVeille.annoncer(${JSONObject.quote(texte)})")
    }

    private fun ecran(): String = if (ReglagesTvActivity.estTele(ctx)) "tele" else "telephone"

    private fun js(code: String) { try { web?.evaluateJavascript(code, null) } catch (_: Exception) {} }

    @SuppressLint("SetJavaScriptEnabled")
    private fun ouvrir() {
        val theme = Local.themeEffectif(ctx, Palette.APPLI)
        val w = try { WebView(ctx) } catch (_: Throwable) { abandonnee = true; return }
        try {
            w.settings.javaScriptEnabled = true
            w.settings.domStorageEnabled = true
            w.settings.mediaPlaybackRequiresUserGesture = false
            w.settings.loadWithOverviewMode = false
            w.settings.useWideViewPort = false
            w.settings.textZoom = 100
            w.setBackgroundColor(theme.fond or 0xFF000000.toInt())
            w.isFocusable = false; w.isFocusableInTouchMode = false
            w.isVerticalScrollBarEnabled = false; w.isHorizontalScrollBarEnabled = false
            w.overScrollMode = View.OVER_SCROLL_NEVER
            w.alpha = 0f
            w.addJavascriptInterface(Pont(), "VisionAndroid")
            w.webViewClient = object : WebViewClient() {
                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) abandonner()
                }
                // Un certificat que l'appareil ne reconnaît pas : on ne passe jamais outre, le dessin de l'appli prend le relais.
                override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) { handler.cancel(); abandonner() }
                override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean { abandonner(); return true }
            }
            cadre.addView(w, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            web = w
            chargee = adresse()
            versionVue = Local.version
            w.loadUrl(chargee)
            main.postDelayed(veilleur, 20_000)
        } catch (_: Throwable) { web = w; abandonner() }
    }

    /** La page n'est pas là après vingt secondes : elle ne viendra pas cette fois. */
    private val tropLong = Runnable { if (!montree) abandonner() }
    private val fonduFini = Runnable { if (montree) native.couverte = true }

    /** Le thème a changé (la nuit tombe, un réglage) : la page se recharge avec les nouvelles couleurs. */
    private val veilleur = object : Runnable {
        override fun run() {
            if (!actif || web == null) return
            val a = adresse()
            if (a != chargee) { chargee = a; versionVue = Local.version; try { web?.loadUrl(a) } catch (_: Exception) {} }
            main.postDelayed(this, if (Local.version != versionVue) 1_000 else 20_000)
        }
    }

    private fun abandonner() {
        abandonnee = true
        main.removeCallbacks(veilleur); main.removeCallbacks(tropLong); main.removeCallbacks(fonduFini)
        retirer()
    }

    private fun retirer() {
        val w = web ?: return
        web = null
        montree = false
        native.couverte = false
        try { cadre.removeView(w) } catch (_: Exception) {}
        try { w.stopLoading(); w.loadUrl("about:blank"); w.destroy() } catch (_: Exception) {}
    }

    private inner class Pont {
        /** Appelée par la page dès que l'heure y est affichée. */
        @JavascriptInterface fun pret() {
            main.post {
                val w = web ?: return@post
                if (!montree) {
                    montree = true
                    main.removeCallbacks(tropLong)
                    // Le dessin de l'appli est déjà muet (fond uni) : la page apparaît seule, sans rien dessous.
                    w.animate().alpha(1f).setDuration(500).start()
                    main.postDelayed(fonduFini, 600)
                }
                if (annonce.isNotEmpty()) main.postDelayed({ annoncer(annonce) }, 1500)
            }
        }
    }

    // ------------------------------------------------------------ l'adresse

    private fun hex(c: Int): String = String.format("%06X", c and 0xFFFFFF)

    /** Une couleur translucide posée sur le fond : la teinte réellement vue. */
    private fun surFond(c: Int, fond: Int): Int = Palette.melanger(fond, c, Color.alpha(c) / 255f)

    private fun adresse(): String {
        val cfg = Config(ctx)
        val t = Local.themeEffectif(ctx, Palette.APPLI)
        val carte = surFond(t.carte, t.fond)
        // L'accent : l'or de Vision, ou la couleur choisie à la main dans « Couleurs à la carte ».
        val accent = if (Palette.lire(ctx, Palette.APPLI)?.has("accent") == true && !Local.estNuit(ctx)) t.pourpre else t.or
        val masques = ArrayList<String>()
        val cartes = ArrayList<String>()
        val durees = ArrayList<String>()
        if (!Local.actif(ctx, "horloge", true)) masques.add("horloge")
        Local.duree(ctx, "horloge", 0).let { if (it > 0) durees.add("horloge:$it") }
        val liste = Local.listeWeb(ctx)
        for (i in 0 until liste.length()) {
            val id = liste.getJSONObject(i).optString("id")
            val cle = Local.cleTableau("dash", id)
            if (!Local.actif(ctx, cle, true)) masques.add(id)
            Local.cartesMasquees(ctx, cle).forEach { cartes.add("$id|$it") }
            Local.duree(ctx, cle, 0).let { if (it > 0) durees.add("$id:$it") }
        }
        fun e(s: String) = URLEncoder.encode(s, "UTF-8")
        val q = "id=${e(cfg.id)}&ecran=${ecran()}&dec=0" +
            "&fond=${hex(t.fond)}&carte=${hex(carte)}&texte=${hex(t.encre)}&texte2=${hex(t.encre2)}&accent=${hex(accent)}&ligne=${hex(Palette.melanger(carte, t.encre, 0.18f))}" +
            "&masques=${e(masques.joinToString(","))}&cartes=${e(cartes.joinToString(","))}&durees=${e(durees.joinToString(","))}" +
            "&horloge=${Themes.cle(t.nom)}&style=${Local.styleCartes(ctx)}&cfond=${if (Local.fondCartes(ctx)) 1 else 0}&ccontour=${if (Local.contourCartes(ctx)) 1 else 0}"
        return "$base/api/pc_parental/veille/entree#t=$jeton&q=${e(q).replace("+", "%20")}"
    }

    companion object {
        /** Les trois endroits où vit l'écran de veille posent la page de la même façon. */
        fun attacher(cadre: FrameLayout, vue: VeilleView) {
            if (Build.VERSION.SDK_INT < 24) return
            vue.web = VeilleWeb(cadre, vue)
        }
    }
}
