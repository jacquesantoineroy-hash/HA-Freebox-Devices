package fr.familleroy.vision

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.GestureDetector
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

/**
 * L'écran de verrouillage Vision du téléphone : préparé quand l'écran
 * s'éteint, il est là au réveil, par-dessus le verrou du système. L'heure,
 * la date, la météo et le temps d'écran du jour, dans le style de l'écran de
 * veille ; glisser vers le haut l'enlève. Option de l'appareil (« verrou »),
 * tenue par l'agent qui écoute l'extinction de l'écran.
 */
class VerrouActivity : Activity() {
    private val main = Handler(Looper.getMainLooper())
    private lateinit var racine: FrameLayout
    private lateinit var feuille: LinearLayout
    private var heure: TextView? = null
    private var date: TextView? = null
    private val heureFmt = SimpleDateFormat("HH:mm", Locale.FRANCE)
    private val dateFmt = SimpleDateFormat("EEEE d MMMM", Locale.FRANCE)
    private val tic = object : Runnable { override fun run() { heure?.text = heureFmt.format(Date()); date?.text = dateFmt.format(Date()); main.postDelayed(this, 1000) } }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 27) { setShowWhenLocked(true); setTurnScreenOn(false) }
        else @Suppress("DEPRECATION") window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED)
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LAYOUT_STABLE or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        window.statusBarColor = 0; window.navigationBarColor = 0
        racine = FrameLayout(this)
        setContentView(racine)
        construire()
    }

    override fun onResume() { super.onResume(); main.post(tic) }
    override fun onPause() { super.onPause(); main.removeCallbacks(tic) }
    override fun onBackPressed() {}
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean = if (keyCode == KeyEvent.KEYCODE_BACK) true else super.onKeyDown(keyCode, event)

    private fun px(dp: Float) = Ui.dp(this, dp)

    private fun texte(t: String, taille: Float, couleur: Int, police: android.graphics.Typeface, espacement: Float = 0f): TextView =
        TextView(this).apply { text = t; textSize = taille; setTextColor(couleur); typeface = police; letterSpacing = espacement }

    private fun construire() {
        val theme = Local.themeEffectif(this, Palette.LANCEUR)
        val d = donneesConnues(this)
        racine.removeAllViews()
        racine.setBackgroundColor(theme.fond)
        racine.addView(FondAnime(this) { theme }, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        feuille = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(px(24f), px(56f), px(24f), px(40f)) }
        racine.addView(feuille, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))

        val marque = LinearLayout(this).apply { gravity = Gravity.CENTER }
        marque.addView(ImageView(this).apply { setImageResource(R.drawable.ic_vision) }, LinearLayout.LayoutParams(px(24f), px(24f)))
        marque.addView(texte("VISION", 13f, theme.or, Polices.gras(this), 0.28f).apply { setPadding(px(8f), 0, 0, 0) })
        feuille.addView(marque)

        feuille.addView(View(this), LinearLayout.LayoutParams(1, 0, 1f))
        heure = texte(heureFmt.format(Date()), 96f, theme.encre, Polices.outfitFin(this), -0.03f).apply { includeFontPadding = false; gravity = Gravity.CENTER }
        feuille.addView(heure)
        date = texte(dateFmt.format(Date()), 17f, theme.encre2, Polices.moyen(this)).apply { gravity = Gravity.CENTER; setPadding(0, px(6f), 0, 0) }
        feuille.addView(date)

        // La météo, quand le lanceur l'a vue récemment.
        val m = d?.optJSONObject("meteo")
        if (m != null) {
            val l = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(0, px(18f), 0, 0) }
            l.addView(ImageView(this).apply { setImageResource(R.drawable.ic_meteo); setColorFilter(theme.encre2) }, LinearLayout.LayoutParams(px(22f), px(22f)))
            val t = m.optDouble("temperature", Double.NaN)
            val cond = Meteo.libelle(m.optString("etat"))
            l.addView(texte((if (!t.isNaN()) "${Math.round(t)}°  " else "") + cond, 16f, theme.encre, Polices.moyen(this)).apply { setPadding(px(8f), 0, 0, 0) })
            feuille.addView(l)
        }

        // Le temps d'écran du jour, pour un enfant.
        val moi = d?.optJSONObject("moi")
        if (moi != null && moi.optString("public") == "enfant") {
            val verrou = moi.optBoolean("verrouille")
            val prochain = moi.optString("prochain_verrou").takeIf { it.length >= 16 }.orEmpty()
            val minutes = moi.optInt("minutes_actif")
            val carte = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; background = GradientDrawable().apply { cornerRadius = px(22f).toFloat(); setColor(theme.carte); setStroke(px(1f), theme.carteBord) }; setPadding(px(18f), px(14f), px(18f), px(14f)) }
            carte.addView(texte("TEMPS D'ÉCRAN", 11f, theme.encre2, Polices.gras(this), 0.22f))
            val h = minutes / 60; val mn = minutes % 60
            val phrase = when { verrou -> "Écran fermé en ce moment"; prochain.isNotEmpty() -> "Ouvert jusqu'à ${prochain.substring(11, 13)} h ${prochain.substring(14, 16)}"; else -> (if (h > 0) "$h h ${String.format(Locale.FRANCE, "%02d", mn)}" else "$mn min") + " aujourd'hui" }
            carte.addView(texte(phrase, 16f, theme.encre, Polices.demiGras(this)).apply { setPadding(0, px(6f), 0, 0) })
            feuille.addView(carte, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = px(28f) })
        }

        feuille.addView(View(this), LinearLayout.LayoutParams(1, 0, 1.4f))
        val indice = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
        indice.addView(ImageView(this).apply { setImageResource(R.drawable.ic_retour); rotation = 90f; setColorFilter(theme.encre3) }, LinearLayout.LayoutParams(px(22f), px(22f)))
        indice.addView(texte("Glisser vers le haut", 13f, theme.encre3, Polices.moyen(this)).apply { setPadding(0, px(4f), 0, 0) })
        feuille.addView(indice)

        // Le geste : un glisser vers le haut emporte la feuille.
        var depart = 0f
        val gestes = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, vx: Float, vy: Float): Boolean { if (vy < -900) { partir(); return true }; return false }
            override fun onDown(e: MotionEvent) = true
        })
        racine.setOnTouchListener { _, e ->
            gestes.onTouchEvent(e)
            when (e.action) {
                MotionEvent.ACTION_DOWN -> depart = e.rawY
                MotionEvent.ACTION_MOVE -> { val dy = (e.rawY - depart).coerceAtMost(0f); feuille.translationY = dy; feuille.alpha = (1f + dy / (racine.height * 0.6f)).coerceIn(0.2f, 1f) }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> if (-feuille.translationY > racine.height * 0.28f) partir() else feuille.animate().translationY(0f).alpha(1f).setDuration(160).start()
            }
            true
        }
    }

    private fun partir() {
        feuille.animate().translationY(-racine.height.toFloat()).alpha(0f).setDuration(180).withEndAction { finish(); overridePendingTransition(0, 0) }.start()
    }

    companion object {
        private var recepteur: BroadcastReceiver? = null

        /** Le lanceur range ici la dernière réponse de Home Assistant, pour l'écran de verrouillage. */
        fun retenir(ctx: Context, d: JSONObject) { ctx.getSharedPreferences("lanceur", Context.MODE_PRIVATE).edit().putString("donnees", d.toString()).putLong("donnees_ts", System.currentTimeMillis()).apply() }
        fun donneesConnues(ctx: Context): JSONObject? {
            val p = ctx.getSharedPreferences("lanceur", Context.MODE_PRIVATE)
            if (System.currentTimeMillis() - p.getLong("donnees_ts", 0) > 3 * 3600_000L) return null
            return try { JSONObject(p.getString("donnees", null) ?: return null) } catch (_: Exception) { null }
        }

        /** L'agent appelle ceci une fois : à chaque extinction de l'écran, l'écran de verrouillage se prépare. */
        fun ecouter(ctx: Context) {
            if (recepteur != null || ReglagesTvActivity.estTele(ctx)) return
            val r = object : BroadcastReceiver() {
                override fun onReceive(c: Context, i: Intent) {
                    if (i.action == Intent.ACTION_SCREEN_OFF && Local.verrou(c)) montrer(c)
                }
            }
            recepteur = r
            try {
                if (android.os.Build.VERSION.SDK_INT >= 33) ctx.applicationContext.registerReceiver(r, IntentFilter(Intent.ACTION_SCREEN_OFF), Context.RECEIVER_NOT_EXPORTED)
                else ctx.applicationContext.registerReceiver(r, IntentFilter(Intent.ACTION_SCREEN_OFF))
            } catch (_: Exception) { recepteur = null }
        }

        fun montrer(ctx: Context) {
            try { ctx.startActivity(Intent(ctx, VerrouActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_NO_ANIMATION)) } catch (_: Exception) {}
        }
    }
}
