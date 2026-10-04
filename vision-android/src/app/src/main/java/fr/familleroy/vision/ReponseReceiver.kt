package fr.familleroy.vision

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import org.json.JSONObject

/**
 * Le parent a touché « 30 min », « 1 h » ou « Non » sur la notification :
 * on transmet à Home Assistant, qui ouvre l'appareil de l'enfant et le
 * prévient. L'appareil qui répond doit porter l'étiquette « Parents ».
 */
class ReponseReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, i: Intent) {
        if (i.action != ACTION) return
        val pc = i.getStringExtra(EXTRA_PC) ?: return
        val demande = i.getStringExtra(EXTRA_DEMANDE) ?: return
        val minutes = i.getIntExtra(EXTRA_MINUTES, 0)
        val notif = i.getIntExtra(EXTRA_NOTIF, 0)
        if (notif != 0) (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(notif)
        val decision = i.getStringExtra(EXTRA_DECISION)
        if (decision != null) Acces.repondre(ctx.applicationContext, pc, demande, decision, minutes)
        else envoyer(ctx.applicationContext, pc, demande, minutes)
    }

    companion object {
        const val ACTION = "fr.familleroy.vision.REPONSE_TEMPS"
        const val EXTRA_PC = "pc"
        const val EXTRA_DEMANDE = "demande"
        const val EXTRA_MINUTES = "minutes"
        const val EXTRA_NOTIF = "notif"
        /** Présent pour une demande d'accès : toujours | temporaire | non. */
        const val EXTRA_DECISION = "decision"

        fun envoyer(ctx: Context, pc: String, demande: String, minutes: Int, apres: ((String) -> Unit)? = null) {
            val cfg = Config(ctx)
            val principal = Handler(Looper.getMainLooper())
            Thread {
                val texte = try {
                    val r = Net.post(ctx, cfg, "/api/pc_parental/reponse", JSONObject()
                        .put("id", cfg.id).put("secret", cfg.secret)
                        .put("pc", pc).put("demande", demande).put("minutes", minutes))
                    when {
                        r.optBoolean("deja") -> "Déjà traité par un autre parent."
                        !r.optBoolean("ok") -> "Home Assistant a refusé la réponse."
                        minutes > 0 -> "Accordé : $minutes min de plus."
                        else -> "Refusé. L'enfant est prévenu."
                    }
                } catch (e: Net.Echec) {
                    if (e.code == 403) "Cet appareil n'est pas marqué « Parents » dans Vision."
                    else "Envoi impossible (${e.code})."
                } catch (_: Exception) { "Home Assistant injoignable." }
                principal.post {
                    Toast.makeText(ctx, texte, Toast.LENGTH_LONG).show()
                    apres?.invoke(texte)
                }
            }.start()
        }
    }
}
