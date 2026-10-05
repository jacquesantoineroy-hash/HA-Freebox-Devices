package fr.familleroy.vision

import android.app.Activity
import android.os.Bundle
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout

/**
 * L'écran de veille à la demande, depuis le lanceur : la même vue que le
 * service de rêve, en plein écran ; se feuillette et se retire sur Retour.
 */
class VeilleActivity : Activity() {
    private var vue: VeilleView? = null
    private var parGeste = false
    private val gestes by lazy { GestesVeille(this, { vue }) { parGeste = true; finish() } }
    /** Un flux permis en fond démarre : la veille continue en couche, par-dessus lui. */
    private val guetteur by lazy { Flux.Guetteur(this, { _ -> if (Veille.permise(this)) { parGeste = true; Veille.ouvrir(applicationContext); finish() } }) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (android.os.Build.VERSION.SDK_INT >= 28) window.attributes = window.attributes.apply { layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES }
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        val cadre = FrameLayout(this)
        val v = VeilleView(this)
        val cameras = CamerasCouche(this)
        v.cameras = cameras
        cadre.addView(v, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        cadre.addView(cameras, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        VeilleWeb.attacher(cadre, v)
        vue = v
        setContentView(cadre)
    }

    override fun onResume() { super.onResume(); Veille.fermer(); vue?.demarrer(); parGeste = false; guetteur.demarrer() }
    override fun onPause() {
        guetteur.arreter()
        // Recouverte sans qu'on l'ait demandé (un cast ouvre son appli par-dessus) : la veille reviendra en couche si le flux est permis.
        if (!parGeste && !isFinishing && !Veille.ouverte) Flux.guetterApres(this)
        vue?.arreter(); super.onPause()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean = gestes.touche(event)
    override fun onTouchEvent(event: MotionEvent?): Boolean = event?.let { gestes.toucher(it) } ?: true
}
