package fr.familleroy.vision

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import org.json.JSONObject

/**
 * Un message envoyé depuis Home Assistant, en plein écran : rappel,
 * avertissement, ou demande de temps d'un enfant à laquelle le parent
 * répond ici même.
 */
class MessageActivity : Activity() {
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Ui.charger(this)
        if (android.os.Build.VERSION.SDK_INT >= 27) { setShowWhenLocked(true); setTurnScreenOn(true) }
        if (android.os.Build.VERSION.SDK_INT >= 21) {
            window.statusBarColor = Ui.FOND; window.navigationBarColor = Ui.FOND
        }
        val urgent = intent.getBooleanExtra("urgent", false)
        val demande = intent.getStringExtra("demande")?.let { try { JSONObject(it) } catch (_: Exception) { null } }
        val acces = intent.getStringExtra("acces")?.let { try { JSONObject(it) } catch (_: Exception) { null } }

        val fond = Ui.colonne(this, Ui.dp(this, 28f)).apply {
            gravity = Gravity.CENTER
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(if (urgent) 0xFF3A1A22.toInt() else 0xFF1A2440.toInt(), Ui.FOND))
        }
        val carte = Ui.carte(this, Ui.CARTE)
        val entete = Ui.rangee(this)
        entete.addView(Ui.icone(this, R.drawable.ic_vision, 28f, if (urgent) Ui.ROUGE else Ui.OR))
        entete.addView(Ui.marge(this, Ui.poids(Ui.texte(this,
            intent.getStringExtra("titre") ?: "Vision", 13f, if (urgent) Ui.ROUGE else Ui.OR, gras = true)), gauche = 10f))
        carte.addView(entete)
        carte.addView(Ui.marge(this, Ui.texte(this, intent.getStringExtra("texte") ?: "", 20f, Ui.TEXTE, gras = true), haut = 14f))

        if (demande != null) {
            carte.addView(Ui.marge(this, Ui.texte(this,
                "Accorder du temps à ${demande.optString("nom", "cet appareil")} ?", 14f, Ui.TEXTE_2), haut = 8f))
            val r = Ui.rangee(this)
            listOf(30 to "30 min", 60 to "1 h", 0 to "Non").forEachIndexed { k, (minutes, lbl) ->
                val btn = if (minutes > 0) Ui.boutonPrimaire(this, lbl) { repondre(demande, minutes) }
                          else Ui.boutonDanger(this, lbl) { repondre(demande, 0) }
                r.addView(Ui.marge(this, Ui.poids(btn), gauche = if (k == 0) 0f else 8f))
            }
            carte.addView(Ui.marge(this, r, haut = 18f))
        } else if (acces != null) {
            carte.addView(Ui.marge(this, Ui.texte(this,
                "Autoriser ${acces.optString("libelle")} pour ${acces.optString("prenom", "cet appareil")} ?", 14f, Ui.TEXTE_2), haut = 8f))
            val lien = acces.optString("lien"); val motif = acces.optString("motif")
            if (lien.isNotEmpty()) carte.addView(Ui.marge(this, Ui.texte(this, lien, 13f, Ui.OR).apply {
                setOnClickListener { try { startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(if (lien.contains("://")) lien else "https://$lien"))) } catch (_: Exception) {} }
            }, haut = 6f))
            if (motif.isNotEmpty()) carte.addView(Ui.marge(this, Ui.texte(this, "« $motif »", 13f, Ui.TEXTE_2), haut = 4f))
            acces.optString("raison").takeIf { it.isNotEmpty() }?.let { carte.addView(Ui.marge(this, Ui.texte(this, "Fermé car : $it", 13f, Ui.TEXTE_3), haut = 6f)) }
            val r = Ui.rangee(this)
            listOf("temporaire" to "1 h", "toujours" to "Exception", "non" to "Non").forEachIndexed { k, (dec, lbl) ->
                val btn = if (dec != "non") Ui.boutonPrimaire(this, lbl) { Acces.repondre(this, acces.optString("pc"), acces.optString("id"), dec); finish() }
                          else Ui.boutonDanger(this, lbl) { Acces.repondre(this, acces.optString("pc"), acces.optString("id"), dec); finish() }
                r.addView(Ui.marge(this, Ui.poids(btn), gauche = if (k == 0) 0f else 8f))
            }
            carte.addView(Ui.marge(this, r, haut = 18f))
        } else {
            carte.addView(Ui.marge(this, Ui.boutonPrimaire(this, "OK") { finish() }, haut = 22f))
        }
        fond.addView(carte)
        setContentView(fond, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    }

    private fun repondre(demande: JSONObject, minutes: Int) {
        ReponseReceiver.envoyer(this, demande.optString("pc"), demande.optString("id"), minutes)
        finish()
    }

    companion object {
        fun intention(ctx: Context, titre: String, texte: String, urgent: Boolean, demande: JSONObject?, acces: JSONObject? = null): Intent =
            Intent(ctx, MessageActivity::class.java).apply {
                putExtra("titre", titre); putExtra("texte", texte); putExtra("urgent", urgent)
                if (demande != null) putExtra("demande", demande.toString())
                if (acces != null) putExtra("acces", acces.toString())
            }

        fun afficher(ctx: Context, titre: String, texte: String, urgent: Boolean, demande: JSONObject? = null, acces: JSONObject? = null) {
            try {
                ctx.startActivity(intention(ctx, titre, texte, urgent, demande, acces).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                })
            } catch (_: Exception) {}
        }
    }
}
