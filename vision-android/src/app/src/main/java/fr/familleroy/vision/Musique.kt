package fr.familleroy.vision

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer

/**
 * La musique de fond de l'écran de veille : une radio sans publicité, choisie
 * dans Home Assistant. Elle monte en douceur, et se tait dès qu'on reprend la
 * télécommande (le service s'arrête). Si le flux casse, on réessaie un peu plus
 * tard, sans jamais déranger.
 */
class Musique(private val ctx: Context) {
    companion object {
        /** Vrai quand c'est nous qui jouons : la bulle et la veille s'en servent pour ne pas se marcher dessus. */
        @Volatile var enCours = false
    }
    private val main = Handler(Looper.getMainLooper())
    private var joueur: ExoPlayer? = null
    private var adresse = ""
    private var depart = 0L
    private val volumeCible = 0.7f

    private val fondu = object : Runnable {
        override fun run() {
            val p = joueur ?: return
            val t = (System.currentTimeMillis() - depart) / 4_000f
            p.volume = volumeCible * t.coerceIn(0f, 1f)
            if (t < 1f) main.postDelayed(this, 250)
        }
    }

    /** Joue cette adresse (ou change de station) ; vide = silence. */
    fun jouer(url: String) {
        if (url == adresse && (joueur != null || url.isEmpty())) return
        arreter()
        adresse = url
        if (url.isEmpty()) return
        try {
            val p = ExoPlayer.Builder(ctx).build()
            p.setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                true,
            )
            p.volume = 0f
            p.addListener(object : Player.Listener {
                override fun onPlayerError(error: PlaybackException) {
                    // Flux coupé : on laisse souffler, puis on relance la même adresse.
                    main.postDelayed({ if (adresse == url) { adresse = ""; jouer(url) } }, 30_000)
                }
                override fun onPlaybackStateChanged(playbackState: Int) {
                    // Une radio ne finit jamais : si le flux « se termine », c'est qu'il est tombé.
                    if (playbackState == Player.STATE_ENDED) main.postDelayed({ if (adresse == url) { adresse = ""; jouer(url) } }, 5_000)
                }
            })
            p.setMediaItem(MediaItem.fromUri(url))
            p.playWhenReady = true
            p.prepare()
            joueur = p
            enCours = true
            depart = System.currentTimeMillis()
            main.post(fondu)
        } catch (_: Exception) {
            joueur = null
        }
    }

    fun arreter() {
        main.removeCallbacks(fondu)
        try { joueur?.release() } catch (_: Exception) {}
        joueur = null
        enCours = false
        adresse = ""
    }
}
