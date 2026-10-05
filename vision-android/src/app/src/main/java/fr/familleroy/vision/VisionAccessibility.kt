package fr.familleroy.vision

import android.accessibilityservice.AccessibilityService
import android.content.ComponentName
import android.content.Context
import android.provider.Settings
import android.content.Intent
import android.os.SystemClock
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import java.util.Locale

/**
 * Voit quelle appli passe au premier plan et la recouvre si elle est bloquée.
 * Protège aussi les écrans de réglages qui permettraient de couper Vision.
 */
class VisionAccessibility : AccessibilityService() {

    override fun onServiceConnected() {
        actif = true
        AgentService.demarrer(this)
    }

    override fun onDestroy() {
        actif = false
        super.onDestroy()
    }

    override fun onInterrupt() {}

    // ---- Vision à la place de l'accueil du système (Google TV impose le sien : on ne peut que passer devant) ----

    private var accueilVerifieA = 0L
    private var accueilAutre = false
    private val redirections = ArrayDeque<Long>()

    /** Vrai sur une télé inscrite dont l'accueil système n'est pas Vision, option active. */
    private fun prendAccueil(): Boolean {
        val now = SystemClock.uptimeMillis()
        if (accueilVerifieA == 0L || now - accueilVerifieA > 60_000) {
            accueilVerifieA = now
            accueilAutre = try {
                val r = packageManager.resolveActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), 0)
                ReglagesTvActivity.estTele(this) && r?.activityInfo?.packageName != packageName
            } catch (_: Exception) { false }
        }
        return accueilAutre && Local.accueilForce(this) && Config(this).inscrit
    }

    private fun ouvrirVision(): Boolean {
        // Garde-fou : si Vision ne tient pas devant (plantage), on rend l'accueil du système plutôt que de boucler.
        val now = SystemClock.uptimeMillis()
        while (redirections.isNotEmpty() && now - redirections.first() > 30_000) redirections.removeFirst()
        if (redirections.size >= 5) return false
        redirections.addLast(now)
        return try {
            startActivity(Intent(this, LanceurActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NO_ANIMATION)); true
        } catch (_: Exception) { false }
    }

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_HOME || !prendAccueil()) return false
        // Appui long laissé au système (tableau de bord Google TV).
        if (event.action == KeyEvent.ACTION_DOWN) return event.repeatCount == 0
        if (event.action == KeyEvent.ACTION_UP) { Usage.derniereInteraction = System.currentTimeMillis(); return ouvrirVision() }
        return false
    }

    override fun onAccessibilityEvent(e: AccessibilityEvent?) {
        e ?: return
        val pkg = e.packageName?.toString() ?: return
        // Seul un geste compte comme de l'activité : un clic, un défilement, une
        // saisie, un changement d'écran. Le contenu qui bouge tout seul (vidéo,
        // messages qui arrivent, animations) n'est pas une personne devant l'écran.
        if (e.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            if (e.eventType in GESTES) Usage.derniereInteraction = System.currentTimeMillis()
            if (e.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED && pkg in reglages) proteger(pkg)
            return
        }
        Usage.derniereInteraction = System.currentTimeMillis()
        // Les claviers et la barre système ne sont pas « l'appli utilisée ».
        if (pkg != "com.android.systemui" && !pkg.contains("inputmethod") && !pkg.contains("keyboard")) {
            if (pkg != Usage.dernierPaquet && Usage.dernierPaquet.isNotEmpty() && Usage.dernierPaquet != packageName) Usage.paquetQuitte = Usage.dernierPaquet
            Usage.dernierPaquet = pkg
        }
        // L'accueil du système vient de passer devant (démarrage, sortie d'une appli) : Vision prend sa place.
        if (pkg != packageName && pkg.contains("launcher") && (e.className?.toString() ?: "").contains("home", ignoreCase = true)
            && pkg in Usage.lanceurs(this) && prendAccueil()) { ouvrirVision(); return }
        if (pkg in reglages && proteger(pkg)) return
        Etat.doitBloquer(this, pkg)?.let { raison ->
            BlockActivity.afficher(this, raison, pkg)
        }
    }

    /** Renvoie vrai si l'écran a été refermé. */
    private fun proteger(pkg: String): Boolean {
        val cfg = Config(this)
        if (!cfg.inscrit || cfg.modeParent) return false
        val racine = rootInActiveWindow ?: return false
        val texte = StringBuilder()
        collecter(racine, texte, intArrayOf(400))
        val t = texte.toString().lowercase(Locale.ROOT)
        val nom = getString(R.string.app_name).lowercase(Locale.ROOT)
        if (!t.contains(nom)) return false
        if (motsSensibles.none { t.contains(it) }) return false
        performGlobalAction(GLOBAL_ACTION_BACK)
        performGlobalAction(GLOBAL_ACTION_HOME)
        AgentService.tentatives++
        BlockActivity.afficher(this, "Réglage protégé par Vision", pkg)
        return true
    }

    private fun collecter(n: AccessibilityNodeInfo?, sb: StringBuilder, reste: IntArray) {
        if (n == null || reste[0] <= 0) return
        reste[0]--
        n.text?.let { sb.append(it).append('\n') }
        n.contentDescription?.let { sb.append(it).append('\n') }
        for (i in 0 until n.childCount) collecter(n.getChild(i), sb, reste)
    }

    companion object {
        private val GESTES = setOf(
            AccessibilityEvent.TYPE_VIEW_CLICKED,
            AccessibilityEvent.TYPE_VIEW_LONG_CLICKED,
            AccessibilityEvent.TYPE_VIEW_SCROLLED,
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_TEXT_SELECTION_CHANGED,
            AccessibilityEvent.TYPE_TOUCH_INTERACTION_START,
            AccessibilityEvent.TYPE_GESTURE_DETECTION_START,
            // Télécommande : passer d'une case à l'autre, c'est quelqu'un devant l'écran.
            AccessibilityEvent.TYPE_VIEW_FOCUSED,
            AccessibilityEvent.TYPE_VIEW_SELECTED,
        )
        @Volatile var actif = false

        private val reglages = setOf(
            "com.android.settings", "com.android.tv.settings", "com.google.android.tv.settings",
            "com.amazon.tv.settings", "com.amazon.tv.settings.v2", "com.samsung.android.settings",
            "com.android.packageinstaller", "com.google.android.packageinstaller",
            "com.google.android.permissioncontroller", "com.android.permissioncontroller",
            "com.miui.securitycenter", "com.coloros.safecenter", "com.huawei.systemmanager",
        )

        private val motsSensibles = listOf(
            "désinstaller", "desinstaller", "uninstall",
            "forcer l'arrêt", "forcer l’arrêt", "force stop",
            "désactiver", "deactivate", "disable",
            "utiliser vision", "use vision", "raccourci", "shortcut",
            "arrêter", "stop", "administrat", "vpn", "effacer", "clear storage", "clear data",
        )

        fun estActive(ctx: Context): Boolean {
            if (actif) return true
            val attendu = ComponentName(ctx, VisionAccessibility::class.java).flattenToString()
            val actives = Settings.Secure.getString(
                ctx.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ) ?: return false
            return actives.split(':').any { it.equals(attendu, ignoreCase = true) }
        }
    }
}
