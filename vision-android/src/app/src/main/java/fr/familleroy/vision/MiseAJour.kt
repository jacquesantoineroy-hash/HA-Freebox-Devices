package fr.familleroy.vision

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import java.io.File
import java.security.MessageDigest

/**
 * Mise à jour de Vision, dans les règles d'Android : l'app télécharge la
 * nouvelle version annoncée par Home Assistant, vérifie son empreinte, puis
 * l'installe par-dessus elle-même.
 *
 * Depuis Android 12, une appli peut se mettre à jour **sans confirmation** si
 * c'est elle qui a installé la version en place. La première mise à jour passe
 * donc par l'écran du système (une seule fois) ; à partir de là Vision est
 * son propre installateur et les suivantes se font toutes seules, avec juste
 * une notification pour prévenir. Même clé de signature : inscription,
 * réglages et autorisations sont conservés.
 */
object MiseAJour {
    @Volatile var disponible: String = ""      // version proposée par HA, "" sinon
    @Volatile private var enCours = false
    @Volatile private var depuis = 0L
    /** Ce que fait la mise à jour en ce moment, ou pourquoi elle a échoué : affiché dans Réglages. */
    @Volatile var etat: String = ""
    @Volatile var surEtat: ((String) -> Unit)? = null
    @Volatile private var dernierPath = ""
    @Volatile private var dernierSha = ""

    private fun dire(ctx: Context, t: String) {
        etat = t
        android.util.Log.i("Vision", "MiseAJour : $t")
        surEtat?.let { cb -> android.os.Handler(ctx.mainLooper).post { cb(t) } }
    }

    fun dossier(ctx: Context): File = File(ctx.cacheDir, "maj").apply { mkdirs() }

    /**
     * Appelé à chaque réponse de HA. `version`, `path` et `sha256` viennent du
     * serveur. Silencieux quand Android le permet, sinon proposé une fois par
     * version par notification (puis à nouveau à chaque ouverture de l'app).
     */
    fun traiter(ctx: Context, cfg: Config, version: String, path: String, sha256: String, forcer: Boolean = false) {
        val actuelle = BuildConfigCompat.version(ctx)
        // On ne propose que ce qui est plus récent : une télé installée en avance
        // par ADB ne doit pas se voir offrir un retour en arrière.
        if (version.isEmpty() || path.isEmpty() || !plusRecente(version, actuelle)) { disponible = ""; return }
        disponible = version; dernierPath = path; dernierSha = sha256
        // Une tentative bloquée (réseau muet) ne doit pas empêcher les suivantes pour toujours.
        if (enCours && System.currentTimeMillis() - depuis > 3 * 60_000L) enCours = false
        if (enCours) { if (forcer) dire(ctx, "Déjà en cours…"); return }
        val silencieux = peutInstallerSansDemander(ctx)
        if (!forcer && !silencieux && cfg.majProposee == version) return
        enCours = true; depuis = System.currentTimeMillis()
        Thread {
            try {
                dire(ctx, "Téléchargement de la $version…")
                val f = telecharger(ctx, cfg, version, path, sha256)
                if (f != null) {
                    cfg.majProposee = version
                    if (silencieux || forcer) installer(ctx, f) else { proposer(ctx, version, f); dire(ctx, "Prête : touche la notification, ou « Installer » ici.") }
                }
            } catch (e: Exception) {
                dire(ctx, "Échec : ${e.javaClass.simpleName} ${e.message ?: ""}".trim())
            } finally {
                enCours = false
            }
        }.start()
    }

    /** Le bouton « Installer » : on télécharge (ou reprend l'APK vérifié) et on lance l'installation tout de suite. */
    fun installerMaintenant(ctx: Context, cfg: Config) {
        if (disponible.isEmpty() || dernierPath.isEmpty()) { dire(ctx, "Aucune version annoncée par Home Assistant pour l'instant."); return }
        traiter(ctx, cfg, disponible, dernierPath, dernierSha, forcer = true)
    }

    private fun telecharger(ctx: Context, cfg: Config, version: String, path: String, sha256: String): File? {
        val cible = File(dossier(ctx), "vision-$version.apk")
        if (cible.isFile && sha256.isNotEmpty() && empreinte(cible) == sha256.lowercase()) { dire(ctx, "APK $version déjà téléchargé et vérifié."); return cible }
        val base = cfg.urlActive.ifEmpty { cfg.adresses().firstOrNull() ?: run { dire(ctx, "Aucune adresse Home Assistant connue."); return null } }
        val octets = Net.getBytes(ctx, base + path) ?: run { dire(ctx, "Téléchargement impossible depuis $base (${Net.derniereErreur})."); return null }
        if (sha256.isNotEmpty()) {
            val h = MessageDigest.getInstance("SHA-256").digest(octets).joinToString("") { "%02x".format(it) }
            if (h != sha256.lowercase()) { dire(ctx, "Empreinte différente : annoncée ${sha256.take(12)}…, reçue ${h.take(12)}… (${octets.size} octets). Le vision.json de HA ne correspond pas à l'APK servi."); return null }
        }
        dire(ctx, "APK vérifié (${octets.size / 1024} Ko).")
        // On nettoie les anciennes versions téléchargées.
        dossier(ctx).listFiles()?.forEach { if (it.name != cible.name) it.delete() }
        cible.writeBytes(octets)
        return cible
    }

    private fun empreinte(f: File): String =
        MessageDigest.getInstance("SHA-256").digest(f.readBytes()).joinToString("") { "%02x".format(it) }

    /** Notification « nouvelle version disponible » : un toucher lance l'installation. */
    fun proposer(ctx: Context, version: String, f: File) {
        val i = Intent(ctx, SetupActivity::class.java).apply {
            putExtra(EXTRA_INSTALLER, f.name)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pi = PendingIntent.getActivity(ctx, 7, i,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        notifier(ctx, "Vision $version est disponible",
            "Touche pour installer la mise à jour. Les prochaines se feront toutes seules.", pi)
    }

    /**
     * Installe par une session du système. Sans confirmation quand Vision est
     * déjà son propre installateur (Android 12+) ; sinon le système demande
     * son accord à l'utilisateur, par une notification si l'app est en fond.
     */
    /** Dernier APK vérifié : sert au repli si l'installation silencieuse échoue. */
    @Volatile private var dernierApk: File? = null

    fun installer(ctx: Context, f: File) {
        (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(NOTIF)
        dernierApk = f
        try {
            val pi = ctx.packageManager.packageInstaller
            // Installation silencieuse seulement si Vision a le droit de la faire
            // sans rien demander. Sinon on laisse le système afficher sa
            // confirmation : forcer le silence sans en avoir le droit échoue
            // (INSTALL_FAILED_VERIFICATION_FAILURE) au lieu de demander.
            val silencieux = peutInstallerSansDemander(ctx)
            val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
                setAppPackageName(ctx.packageName)
                setSize(f.length())
                if (Build.VERSION.SDK_INT >= 31) {
                    setRequireUserAction(
                        if (silencieux) PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED
                        else PackageInstaller.SessionParams.USER_ACTION_REQUIRED
                    )
                }
                // On ne réclame pas le rôle de « propriétaire des mises à jour » :
                // chaque demande de ce rôle déclenche une confirmation du système.
                // Sans propriétaire déclaré, il suffit d'être l'installateur en
                // place pour que les mises à jour suivantes soient silencieuses.
            }
            val id = pi.createSession(params)
            dire(ctx, "Installation : session $id ouverte" + (if (silencieux) ", sans confirmation." else ", Android va demander confirmation."))
            pi.openSession(id).use { s ->
                s.openWrite("vision.apk", 0, f.length()).use { out ->
                    f.inputStream().use { it.copyTo(out) }
                    s.fsync(out)
                }
                val retour = Intent(ctx, InstallReceiver::class.java).setAction(InstallReceiver.ACTION)
                var flags = PendingIntent.FLAG_UPDATE_CURRENT
                if (Build.VERSION.SDK_INT >= 31) flags = flags or PendingIntent.FLAG_MUTABLE
                s.commit(PendingIntent.getBroadcast(ctx, id, retour, flags).intentSender)
            }
        } catch (e: Exception) {
            dire(ctx, "Session refusée (${e.message ?: e.javaClass.simpleName}) : passage par l'écran d'installation du système.")
            installerParIntent(ctx, f)
        }
    }

    /** Le résultat de la session, remonté par InstallReceiver. */
    fun resultat(ctx: Context, statut: Int, message: String?) {
        dire(ctx, when (statut) {
            PackageInstaller.STATUS_SUCCESS -> "Installée. Vision redémarre."
            PackageInstaller.STATUS_PENDING_USER_ACTION -> "En attente de ta confirmation à l'écran."
            PackageInstaller.STATUS_FAILURE_BLOCKED -> "Refusée par Android (bloquée) : ${message ?: ""}"
            PackageInstaller.STATUS_FAILURE_INCOMPATIBLE -> "Refusée : APK incompatible (autre clé de signature ?) ${message ?: ""}"
            PackageInstaller.STATUS_FAILURE_INVALID -> "Refusée : APK invalide ${message ?: ""}"
            PackageInstaller.STATUS_FAILURE_STORAGE -> "Refusée : plus de place ${message ?: ""}"
            PackageInstaller.STATUS_FAILURE_ABORTED -> "Annulée ${message ?: ""}"
            else -> "Échec de la session ($statut) ${message ?: ""} : nouvel essai par l'écran du système."
        }.trim())
    }

    /** Si la session échoue (vérification refusée…), on retente par l'écran du système. */
    fun reessayerInteractif(ctx: Context) {
        dernierApk?.let { installerParIntent(ctx, it) }
    }

    /** Repli : l'écran d'installation du système, comme un APK ouvert à la main. */
    private fun installerParIntent(ctx: Context, f: File) {
        val i = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(ApkProvider.uri(f.name), "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
            if (Build.VERSION.SDK_INT >= 24) putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true)
        }
        try { ctx.startActivity(i) } catch (e: Exception) { dire(ctx, "Impossible d'ouvrir l'installateur : ${e.message}") }
    }

    /** Vrai si Android autorise cette app à lancer une installation (réglage utilisateur). */
    /** `a` est-elle strictement plus récente que `b` ? Comparaison numérique, segment par segment. */
    fun plusRecente(a: String, b: String): Boolean {
        val x = a.split('.').map { it.filter(Char::isDigit).toIntOrNull() ?: 0 }
        val y = b.split('.').map { it.filter(Char::isDigit).toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(x.size, y.size)) {
            val d = (x.getOrNull(i) ?: 0) - (y.getOrNull(i) ?: 0)
            if (d != 0) return d > 0
        }
        return false
    }

    fun peutInstaller(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < 26 || ctx.packageManager.canRequestPackageInstalls()

    /**
     * Vrai si la mise à jour peut se faire sans rien demander.
     * Android 14+ : il faut être le « propriétaire des mises à jour » du paquet.
     * Android 12-13 : il suffit d'avoir installé la version en place.
     */
    fun peutInstallerSansDemander(ctx: Context): Boolean {
        if (Build.VERSION.SDK_INT < 31 || !peutInstaller(ctx)) return false
        return try {
            val src = ctx.packageManager.getInstallSourceInfo(ctx.packageName)
            val installeur = src.installingPackageName == ctx.packageName
            if (Build.VERSION.SDK_INT < 34) return installeur
            // Android 14+ : sans propriétaire déclaré, une app qui se met à jour
            // elle-même n'a besoin que d'être son propre installateur.
            val proprietaire = src.updateOwnerPackageName
            proprietaire == ctx.packageName || (proprietaire == null && installeur)
        } catch (_: Exception) { false }
    }

    /** Pour l'écran de réglages : où en est l'automatisation. */
    fun etatAuto(ctx: Context): String = when {
        !peutInstaller(ctx) -> "Autorise d'abord Vision à installer des applis."
        Build.VERSION.SDK_INT < 31 -> "Android ${Build.VERSION.RELEASE} : une confirmation à chaque version."
        peutInstallerSansDemander(ctx) -> "Automatiques : Vision se met à jour toute seule."
        // Sur un appareil installé hors Play Store et en Android 14+, le rôle de
        // propriétaire des mises à jour ne s'obtient qu'à la première installation :
        // on en reste à une confirmation par version, imposée par le système.
        else -> "Une confirmation par version (sécurité Android)."
    }

    fun notifier(ctx: Context, titre: String, texte: String, pi: PendingIntent?) {
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(NotificationChannel(
                CANAL, "Mises à jour de Vision", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Prévient quand une nouvelle version de Vision est prête"
            })
        }
        val b = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(ctx, CANAL)
                else @Suppress("DEPRECATION") Notification.Builder(ctx)
        b.setSmallIcon(R.drawable.ic_vision)
            .setContentTitle(titre)
            .setContentText(texte)
            .setStyle(Notification.BigTextStyle().bigText(texte))
            .setAutoCancel(true)
        if (pi != null) b.setContentIntent(pi)
        nm.notify(NOTIF, b.build())
    }

    const val EXTRA_INSTALLER = "installer_maj"
    private const val CANAL = "vision_maj"
    const val NOTIF = 2
}
