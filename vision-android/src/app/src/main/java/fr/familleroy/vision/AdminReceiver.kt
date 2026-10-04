package fr.familleroy.vision

import android.app.admin.DeviceAdminReceiver
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context

/**
 * Administrateur de l'appareil : empêche la désinstallation directe de Vision.
 * Volontairement limité à `force-lock` ; aucun effacement, aucune prise de
 * contrôle. La désinstallation reste possible, mais passe par le code parent.
 */
class AdminReceiver : DeviceAdminReceiver() {
    override fun onDisableRequested(context: Context, intent: android.content.Intent): CharSequence =
        "Vision va cesser de protéger cet appareil."

    companion object {
        fun composant(ctx: Context) = ComponentName(ctx, AdminReceiver::class.java)

        fun estActif(ctx: Context): Boolean {
            val dpm = ctx.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
            return dpm.isAdminActive(composant(ctx))
        }
    }
}
