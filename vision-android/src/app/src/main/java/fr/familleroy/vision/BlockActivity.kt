package fr.familleroy.vision

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Écran plein affiché quand une appli bloquée s'ouvre, ou quand l'appareil
 * est fermé. On y lit pourquoi, jusqu'à quand, et on peut demander un peu de
 * temps : la demande part chez les parents, qui répondent depuis leur
 * téléphone. L'écran se retire tout seul dès que la maison rouvre.
 */
class BlockActivity : Activity() {
    private val h = Handler(Looper.getMainLooper())
    private lateinit var titre: TextView
    private lateinit var detail: TextView
    private lateinit var zoneDemande: LinearLayout
    private var demandeEnvoyee = 0L

    private val boucle = object : Runnable {
        override fun run() {
            if (!devraitRester()) { accueil(); finish(); return }
            peindre()
            h.postDelayed(this, 2000)
        }
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Ui.charger(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (android.os.Build.VERSION.SDK_INT >= 21) {
            window.statusBarColor = Ui.FOND; window.navigationBarColor = Ui.FOND
        }

        val fond = Ui.colonne(this, Ui.dp(this, 32f)).apply {
            gravity = Gravity.CENTER
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(0xFF1A2440.toInt(), Ui.FOND))
        }
        val d = Ui.dp(this, 112f)
        val cadre = LinearLayout(this).apply {
            gravity = Gravity.CENTER
            layoutParams = LinearLayout.LayoutParams(d, d).apply {
                gravity = Gravity.CENTER; bottomMargin = Ui.dp(this@BlockActivity, 28f) }
            background = Ui.fond(0x33E8B931, d / 2f)
            addView(Ui.icone(this@BlockActivity, R.drawable.ic_vision, 56f))
        }
        fond.addView(cadre)

        titre = Ui.texte(this, "", 26f, Ui.TEXTE, gras = true, centre = true)
        fond.addView(titre)
        detail = Ui.texte(this, "", 16f, Ui.TEXTE_2, centre = true)
        fond.addView(Ui.marge(this, detail, haut = 10f))

        zoneDemande = Ui.colonne(this).apply { gravity = Gravity.CENTER }
        fond.addView(Ui.marge(this, zoneDemande, haut = 36f))
        construireDemande()

        // Appareil fermé ou non, on peut toujours appeler, écrire, régler son réveil, ouvrir Pronote.
        val permises = if (ReglagesTvActivity.estTele(this)) emptyList() else Etat.toujoursPermises(this)
        if (permises.isNotEmpty()) {
            fond.addView(Ui.marge(this, Ui.texte(this, "Toujours accessibles", 13f, Ui.TEXTE_3, centre = true), haut = 30f))
            val rang = LinearLayout(this).apply { gravity = Gravity.CENTER }
            for (a in permises.take(6)) {
                val cell = LinearLayout(this).apply {
                    orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL
                    setPadding(Ui.dp(this@BlockActivity, 10f), Ui.dp(this@BlockActivity, 8f), Ui.dp(this@BlockActivity, 10f), Ui.dp(this@BlockActivity, 4f))
                    isClickable = true; isFocusable = true; contentDescription = a.nom
                    setOnClickListener { try { packageManager.getLaunchIntentForPackage(a.pkg)?.let { startActivity(it) } } catch (_: Exception) {} }
                }
                val t = Ui.dp(this, 50f)
                cell.addView(android.widget.ImageView(this).apply { setImageDrawable(Accueil.icone(this@BlockActivity, a.pkg)) }, LinearLayout.LayoutParams(t, t))
                cell.addView(Ui.marge(this, Ui.texte(this, a.nom, 12f, Ui.TEXTE_2, centre = true), haut = 5f))
                rang.addView(cell)
            }
            fond.addView(Ui.marge(this, rang, haut = 8f))
        }

        setContentView(fond, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        peindre()
    }

    /** Trois durées à demander ; après l'envoi, on attend la réponse d'un parent. */
    private fun construireDemande() {
        zoneDemande.removeAllViews()
        val pkg = intent.getStringExtra("pkg") ?: ""
        if (!Etat.verrouilleEffectif() && pkg.isNotEmpty()) {
            // Appli fermée (pas la session) : on demande l'accès à cette appli.
            val lib = Usage.libelle(this, pkg)
            if (Acces.dejaDemande("apps", pkg)) {
                val c = Ui.carte(this, Ui.CARTE); c.gravity = Gravity.CENTER
                c.addView(Ui.texte(this, "Demande envoyée", 15f, Ui.OR, gras = true, centre = true))
                c.addView(Ui.marge(this, Ui.texte(this, "Un parent la reçoit sur son téléphone. Tu seras prévenu de sa réponse.", 13f, Ui.TEXTE_2, centre = true), haut = 6f))
                zoneDemande.addView(c)
            } else {
                val btn = Ui.boutonPrimaire(this, "Demander l'accès à $lib") {
                    Acces.dialogue(this, "apps", pkg, lib) { construireDemande() }
                }
                btn.isFocusableInTouchMode = false
                zoneDemande.addView(btn); btn.requestFocus()
            }
            return
        }
        if (demandeEnvoyee > 0) {
            val c = Ui.carte(this, Ui.CARTE)
            c.gravity = Gravity.CENTER
            c.addView(Ui.texte(this, "Demande envoyée", 15f, Ui.OR, gras = true, centre = true))
            c.addView(Ui.marge(this, Ui.texte(this,
                "Un parent la reçoit sur son téléphone. L'écran s'ouvrira tout seul s'il accepte.",
                13f, Ui.TEXTE_2, centre = true), haut = 6f))
            zoneDemande.addView(c)
            return
        }
        zoneDemande.addView(Ui.texte(this, "Demander un peu de temps ?", 14f, Ui.TEXTE_2, centre = true))
        val r = Ui.rangee(this).apply { gravity = Gravity.CENTER }
        var premier: View? = null
        listOf(15 to "15 min", 30 to "30 min", 60 to "1 h").forEachIndexed { k, (min, lbl) ->
            val btn = Ui.boutonSecondaire(this, lbl) { demander(min) }
            btn.isFocusableInTouchMode = false
            r.addView(Ui.marge(this, btn, haut = 10f, gauche = if (k == 0) 0f else 10f))
            if (premier == null) premier = btn
        }
        zoneDemande.addView(r)
        premier?.requestFocus()
    }

    private fun demander(minutes: Int) {
        Config(this).demandeTemps = minutes
        AgentService.demarrer(this)
        demandeEnvoyee = System.currentTimeMillis()
        construireDemande()
    }

    override fun onResume() {
        super.onResume()
        h.removeCallbacks(boucle)
        h.post(boucle)
    }

    override fun onPause() {
        super.onPause()
        h.removeCallbacks(boucle)
    }

    private fun peindre() {
        if (Etat.verrouilleEffectif()) {
            titre.text = Etat.message.ifEmpty { "Accès fermé" }
            detail.text = if (Etat.prochainChangement > System.currentTimeMillis())
                "Réouverture à " + Etat.heure(Etat.prochainChangement) else "La maison a fermé l'accès"
        } else {
            titre.text = intent.getStringExtra("raison") ?: "Bloqué"
            val pkg = intent.getStringExtra("pkg") ?: ""
            val pourquoi = if (pkg.isNotEmpty()) Etat.raisonDe(pkg) else ""
            detail.text = if (pkg.isEmpty()) "" else Usage.libelle(this, pkg) + " n'est pas autorisé maintenant." +
                (if (pourquoi.isNotEmpty()) "\n\n" + pourquoi else "")
        }
        // Une demande restée sans réponse : au bout de dix minutes, on laisse redemander.
        if (demandeEnvoyee > 0 && System.currentTimeMillis() - demandeEnvoyee > 10 * 60_000L) {
            demandeEnvoyee = 0; construireDemande()
        }
    }

    /** L'écran reste tant que l'appareil est fermé, ou tant que l'appli visée reste au premier plan. */
    private fun devraitRester(): Boolean {
        if (Config(this).modeParent) return false
        if (Etat.verrouilleEffectif()) return true
        val pkg = intent.getStringExtra("pkg") ?: return false
        return Etat.doitBloquer(this, pkg) != null && pkg == Usage.dernierPaquet
    }

    private fun accueil() {
        try {
            startActivity(Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            })
        } catch (_: Exception) {}
    }

    // On ne quitte pas l'écran avec Retour ; Accueil est géré par le système.
    override fun onKeyDown(code: Int, e: KeyEvent?): Boolean =
        if (code == KeyEvent.KEYCODE_BACK) true else super.onKeyDown(code, e)

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() { /* ignoré */ }

    companion object {
        @Volatile private var dernierAffichage = 0L

        fun afficher(ctx: Context, raison: String, pkg: String) {
            val maintenant = System.currentTimeMillis()
            if (maintenant - dernierAffichage < 700) return
            dernierAffichage = maintenant
            try {
                ctx.startActivity(Intent(ctx, BlockActivity::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or
                        Intent.FLAG_ACTIVITY_SINGLE_TOP
                    putExtra("raison", raison)
                    putExtra("pkg", pkg)
                })
            } catch (_: Exception) {}
        }
    }
}
