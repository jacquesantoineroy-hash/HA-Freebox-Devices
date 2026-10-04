package fr.familleroy.vision

import android.content.Context
import android.media.AudioManager
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
    private var appFond: String? = null

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
        // Une appli joue : si elle a le droit de rester en fond (Spotify…), la veille passe dessus sans sa radio ;
        // sinon (Netflix, un jeu…) ce n'est pas le moment, on rend la main tout de suite.
        appFond = try { Local.appEnFond(this) } catch (_: Exception) { null }
        val proteger = try { Local.appAProteger(this) } catch (_: Exception) { false }
        if (proteger) { finish(); return }
        Veille.fermer()
        vue?.demarrer()
    }

    override fun onDreamingStopped() {
        vue?.arreter()
        // L'appli de fond jouait : on reprend dessus, ou on va à l'accueil ? L'utilisateur choisit.
        val pk = appFond; appFond = null
        val eveille = try { (getSystemService(Context.POWER_SERVICE) as android.os.PowerManager).isInteractive } catch (_: Exception) { true }
        if (pk != null && eveille) RetourActivity.proposer(this, pk)
        super.onDreamingStopped()
    }

    override fun onDetachedFromWindow() {
        vue?.arreter()
        vue = null
        super.onDetachedFromWindow()
    }
}
