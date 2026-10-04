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
 * service de rêve, en plein écran, qui se retire à la première touche.
 */
class VeilleActivity : Activity() {
    private var vue: VeilleView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        val cadre = FrameLayout(this)
        val v = VeilleView(this)
        val cameras = CamerasCouche(this)
        v.cameras = cameras
        cadre.addView(v, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        cadre.addView(cameras, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        vue = v
        setContentView(cadre)
    }

    override fun onResume() { super.onResume(); Veille.fermer(); vue?.demarrer() }
    override fun onPause() { vue?.arreter(); super.onPause() }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean { finish(); return true }
    override fun onTouchEvent(event: MotionEvent?): Boolean { finish(); return true }
}
