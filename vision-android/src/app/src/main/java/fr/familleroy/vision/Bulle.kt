package fr.familleroy.vision

import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/**
 * La bulle Vision : une petite icône posée par-dessus les autres applis
 * quand de la musique joue (Spotify, YouTube Music…), pour ramener l'écran
 * de veille devant sans couper le son. Au doigt : toucher ouvre l'écran de
 * veille, un appui long range la bulle (elle se réactive dans les
 * réglages). À la télécommande, la bulle rappelle le geste : deux appuis
 * sur Accueil.
 *
 * Option de l'appareil (« bulle »), permission « par-dessus les autres
 * applis » requise. Tenue en vie par l'agent, qui tourne toujours.
 */
object Bulle {
    private const val PREFS = "local"
    private val main = Handler(Looper.getMainLooper())
    private var vue: View? = null
    private var lance = false
    private var appCtx: Context? = null

    fun activee(ctx: Context): Boolean = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("bulle", true)
    fun poser(ctx: Context, on: Boolean) { ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("bulle", on).apply(); if (!on) retirer() }
    fun permise(ctx: Context): Boolean = Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(ctx)

    /** Démarre la surveillance (idempotent). */
    fun verifier(ctx: Context) {
        appCtx = ctx.applicationContext
        if (lance) return
        lance = true
        main.post(tour)
    }

    private val tour = object : Runnable {
        override fun run() {
            val ctx = appCtx ?: return
            try {
                val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
                val nous = Usage.dernierPaquet == ctx.packageName || Usage.dernierPaquet.isEmpty()
                val musique = am.isMusicActive && !Musique.enCours
                val voulue = activee(ctx) && permise(ctx) && musique && !nous
                if (voulue) montrer(ctx) else retirer()
            } catch (_: Exception) {}
            main.postDelayed(this, 4000)
        }
    }

    private fun montrer(ctx: Context) {
        if (vue != null) return
        val tele = ReglagesTvActivity.estTele(ctx)
        val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val dp = { v: Float -> Ui.dp(ctx, v) }
        val theme = Local.themeEffectif(ctx, Palette.LANCEUR)
        val boite = LinearLayout(ctx).apply {
            gravity = Gravity.CENTER_VERTICAL
            background = GradientDrawable().apply { cornerRadius = dp(999f).toFloat(); setColor(theme.carte); setStroke(dp(1f), theme.carteBord) }
            setPadding(dp(6f), dp(6f), dp(if (tele) 14f else 6f), dp(6f))
            alpha = 0.92f
        }
        boite.addView(ImageView(ctx).apply { setImageResource(R.drawable.ic_vision) }, LinearLayout.LayoutParams(dp(if (tele) 34f else 40f), dp(if (tele) 34f else 40f)))
        if (tele) boite.addView(TextView(ctx).apply { text = "Accueil ×2 : écran de veille"; textSize = 12f; setTextColor(theme.encre2); typeface = Polices.moyen(ctx); setPadding(dp(8f), 0, 0, 0) })
        boite.setOnClickListener { ctx.startActivity(Intent(ctx, VeilleActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
        boite.setOnLongClickListener { poser(ctx, false); Toast.makeText(ctx, "Bulle rangée. Elle se réactive dans Réglages Vision.", Toast.LENGTH_LONG).show(); true }
        val type = if (Build.VERSION.SDK_INT >= 26) WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE
        val lp = WindowManager.LayoutParams(WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN, PixelFormat.TRANSLUCENT)
        lp.gravity = Gravity.BOTTOM or Gravity.END
        lp.x = dp(if (tele) 40f else 16f); lp.y = dp(if (tele) 40f else 96f)
        try { wm.addView(boite, lp); vue = boite } catch (_: Exception) { vue = null }
    }

    fun retirer() {
        val v = vue ?: return
        vue = null
        try { (appCtx?.getSystemService(Context.WINDOW_SERVICE) as? WindowManager)?.removeView(v) } catch (_: Exception) {}
    }
}
