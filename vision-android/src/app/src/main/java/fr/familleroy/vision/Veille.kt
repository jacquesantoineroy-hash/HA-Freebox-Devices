package fr.familleroy.vision

import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout

/**
 * L'écran de veille à la demande (deux appuis sur Accueil, la bulle, le
 * réglage « Lancer l'écran de veille »). Posé en **couche par-dessus**
 * l'appli ouverte plutôt qu'en activité : YouTube, Spotify ou un jeu restent
 * au premier plan pour Android et continuent, image et son compris. La
 * première touche ou le premier toucher retire la couche et rend la main à
 * ce qui jouait. Sans le droit d'afficher par-dessus, on retombe sur
 * l'activité classique (qui, elle, met l'appli du dessous en pause). Seule
 * l'inactivité (le rêve du système, ou la minuterie de l'accueil) coupe ce
 * qui est en cours.
 */
object Veille {
    private val main = Handler(Looper.getMainLooper())
    private var couche: View? = null
    private var vue: VeilleView? = null
    private var appCtx: Context? = null

    fun permise(ctx: Context): Boolean = Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(ctx)

    /** Montre l'écran de veille sans interrompre l'appli ouverte quand c'est possible. */
    fun ouvrir(ctx: Context) {
        if (couche != null) return
        if (!permise(ctx)) { ctx.startActivity(Intent(ctx, VeilleActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return }
        val app = ctx.applicationContext
        appCtx = app
        val wm = app.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val cadre = object : FrameLayout(app) {
            override fun dispatchKeyEvent(e: KeyEvent): Boolean { if (e.action == KeyEvent.ACTION_DOWN) fermer(); return true }
            override fun dispatchTouchEvent(e: MotionEvent): Boolean { if (e.action == MotionEvent.ACTION_DOWN) fermer(); return true }
        }
        cadre.isFocusable = true; cadre.isFocusableInTouchMode = true
        val v = VeilleView(app)
        val cameras = CamerasCouche(app)
        v.cameras = cameras
        cadre.addView(v, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        cadre.addView(cameras, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        val type = if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE
        val lp = WindowManager.LayoutParams(WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT, type,
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or WindowManager.LayoutParams.FLAG_FULLSCREEN,
            PixelFormat.OPAQUE)
        lp.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        try {
            wm.addView(cadre, lp)
            couche = cadre; vue = v
            Bulle.retirer()
            main.post { cadre.requestFocus(); v.demarrer() }
        } catch (_: Exception) {
            couche = null; vue = null
            ctx.startActivity(Intent(ctx, VeilleActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }

    fun fermer() {
        val c = couche ?: return
        couche = null
        try { vue?.arreter() } catch (_: Exception) {}
        vue = null
        try { (appCtx?.getSystemService(Context.WINDOW_SERVICE) as? WindowManager)?.removeView(c) } catch (_: Exception) {}
    }

    val ouverte get() = couche != null
}
