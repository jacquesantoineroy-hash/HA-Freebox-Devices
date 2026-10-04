package fr.familleroy.vision

import android.service.dreams.DreamService
import android.widget.FrameLayout

/**
 * L'écran de veille Vision : quand la télé n'est plus regardée, elle montre
 * la maison. Heure, météo et vigilance Météo-France, qui est devant quel
 * écran, et les chiffres que la maison a choisis dans Home Assistant.
 *
 * Rien d'interactif : la première touche de la télécommande rend la main.
 */
class VeilleService : DreamService() {
    private var vue: VeilleView? = null

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        isInteractive = false
        isFullscreen = true
        isScreenBright = true
        val cadre = FrameLayout(this)
        val v = VeilleView(this)
        val cameras = CamerasCouche(this)
        v.cameras = cameras
        cadre.addView(v, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        cadre.addView(cameras, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        vue = v
        setContentView(cadre)
    }

    override fun onDreamingStarted() {
        super.onDreamingStarted()
        vue?.demarrer()
    }

    override fun onDreamingStopped() {
        vue?.arreter()
        super.onDreamingStopped()
    }

    override fun onDetachedFromWindow() {
        vue?.arreter()
        vue = null
        super.onDetachedFromWindow()
    }
}
