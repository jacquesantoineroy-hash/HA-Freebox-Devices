package fr.familleroy.vision

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Les réglages de cet appareil, rangés sur l'appareil : le thème, le mode
 * nuit, la radio, les tableaux de l'écran de veille (lesquels, combien de
 * temps) et les tableaux composés ici même. Home Assistant reste la source
 * des données (entités, météo, école…), jamais le maître des réglages.
 *
 * `version` monte à chaque changement : les écrans ouverts s'en aperçoivent
 * et se repeignent tout de suite.
 */
object Local {
    private const val PREFS = "local"
    @Volatile var version = 0
        private set

    val RADIOS: List<Pair<String, String>> = listOf(
        "SomaFM Fluid · lofi, hip-hop instrumental" to "https://ice1.somafm.com/fluid-128-mp3",
        "SomaFM Groove Salad · ambient, downtempo" to "https://ice1.somafm.com/groovesalad-128-mp3",
        "SomaFM Lush · électro douce, voix" to "https://ice1.somafm.com/lush-128-mp3",
        "SomaFM Beat Blender · deep house" to "https://ice1.somafm.com/beatblender-128-mp3",
        "SomaFM Drone Zone · ambiance" to "https://ice1.somafm.com/dronezone-128-mp3",
        "SomaFM Secret Agent · lounge" to "https://ice1.somafm.com/secretagent-128-mp3",
        "Radio Paradise Mellow" to "https://stream.radioparadise.com/mellow-128",
        "Radio Paradise" to "https://stream.radioparadise.com/mp3-128",
        "FIP" to "https://icecast.radiofrance.fr/fip-midfi.mp3",
        "FIP Jazz" to "https://icecast.radiofrance.fr/fipjazz-midfi.mp3",
        "FIP Électro" to "https://icecast.radiofrance.fr/fipelectro-midfi.mp3",
        "FIP Groove" to "https://icecast.radiofrance.fr/fipgroove-midfi.mp3",
        "FIP Pop" to "https://icecast.radiofrance.fr/fippop-midfi.mp3",
    )
    val PLAGES_NUIT = listOf("23:00-07:00", "22:00-07:00", "00:00-06:30", "")

    private fun p(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private fun toucher() { version++ }

    // ------------------------------------------------------------ ambiance

    fun theme(ctx: Context): String = p(ctx).getString("theme", "Beige") ?: "Beige"
    fun poserTheme(ctx: Context, nom: String) { p(ctx).edit().putString("theme", nom).apply(); toucher() }

    fun nuit(ctx: Context): String = p(ctx).getString("nuit", "23:00-07:00") ?: "23:00-07:00"
    fun poserNuit(ctx: Context, plage: String) { p(ctx).edit().putString("nuit", plage).apply(); toucher() }

    /** L'adresse du flux joué en veille ; vide = silence. */
    fun musique(ctx: Context): String = p(ctx).getString("musique", RADIOS[0].second) ?: ""
    fun poserMusique(ctx: Context, url: String) { p(ctx).edit().putString("musique", url).apply(); toucher() }
    fun nomRadio(url: String): String = if (url.isEmpty()) "Silence" else RADIOS.firstOrNull { it.second == url }?.first?.substringBefore(" ·") ?: "Personnalisée"

    /** Vrai si l'heure courante est dans la plage « HH:MM-HH:MM » (qui peut passer minuit). */
    fun dansPlage(plage: String): Boolean {
        val m = Regex("(\\d\\d):(\\d\\d)-(\\d\\d):(\\d\\d)").matchEntire(plage.trim()) ?: return false
        val (h1, m1, h2, m2) = m.destructured
        val debut = h1.toInt() * 60 + m1.toInt(); val fin = h2.toInt() * 60 + m2.toInt()
        val cal = java.util.Calendar.getInstance()
        val now = cal.get(java.util.Calendar.HOUR_OF_DAY) * 60 + cal.get(java.util.Calendar.MINUTE)
        return if (debut <= fin) now in debut until fin else now >= debut || now < fin
    }

    fun estNuit(ctx: Context): Boolean = dansPlage(nuit(ctx))

    /** Télé : minutes sans toucher la télécommande avant l'écran de veille (0 = le réglage de la télé). */
    val DELAIS_VEILLE = listOf(0, 1, 2, 5, 10, 15, 30)
    fun delaiVeille(ctx: Context): Int = p(ctx).getInt("delai_veille", 0)
    fun poserDelaiVeille(ctx: Context, min: Int) {
        p(ctx).edit().putInt("delai_veille", min).apply(); toucher()
        // Le réglage système « écran de veille après » (celui des réglages de la télé), quand Vision a le droit de l'écrire.
        if (min > 0) try {
            if (android.os.Build.VERSION.SDK_INT < 23 || android.provider.Settings.System.canWrite(ctx))
                android.provider.Settings.System.putInt(ctx.contentResolver, android.provider.Settings.System.SCREEN_OFF_TIMEOUT, min * 60_000)
        } catch (_: Exception) {}
    }
    fun peutEcrireSysteme(ctx: Context): Boolean = android.os.Build.VERSION.SDK_INT < 23 || android.provider.Settings.System.canWrite(ctx)

    /** Téléphone : l'écran de verrouillage Vision, montré au réveil de l'écran. */
    fun verrou(ctx: Context): Boolean = p(ctx).getBoolean("verrou", false)
    fun poserVerrou(ctx: Context, on: Boolean) { p(ctx).edit().putBoolean("verrou", on).apply(); toucher() }

    /** Le thème effectif du moment, le même pour tout l'appareil : nuit = Sombre, sinon le thème choisi et ses couleurs à la carte. */
    fun themeEffectif(ctx: Context, cible: String): Theme {
        val base = Themes.parNom(theme(ctx))
        if (estNuit(ctx) && !base.sombre) return Themes.parNom("Sombre")
        return Palette.appliquer(ctx, cible, base)
    }

    /** Au premier lancement seulement : on part des réglages que Home Assistant avait (thème, nuit, radio). */
    fun amorcer(ctx: Context, reglages: JSONObject?) {
        if (reglages == null || p(ctx).contains("theme")) return
        p(ctx).edit()
            .putString("theme", reglages.optString("theme", "Beige").ifEmpty { "Beige" })
            .putString("nuit", reglages.optString("nuit", "23:00-07:00"))
            .putString("musique", reglages.optString("musique", RADIOS[0].second))
            .apply()
        toucher()
    }

    // ------------------------------------------------------------ tableaux de veille

    /** Les choix par tableau : {"horloge": {"actif": true, "duree": 15}, "entites:abc": {...}}. */
    private fun choix(ctx: Context): JSONObject = try { JSONObject(p(ctx).getString("tableaux", "{}") ?: "{}") } catch (_: Exception) { JSONObject() }

    fun cleTableau(code: String, id: String): String = if (code == "entites") "entites:$id" else code

    fun actif(ctx: Context, cle: String, defaut: Boolean): Boolean = choix(ctx).optJSONObject(cle)?.optBoolean("actif", defaut) ?: defaut
    fun duree(ctx: Context, cle: String, defaut: Int): Int = choix(ctx).optJSONObject(cle)?.optInt("duree", defaut) ?: defaut

    fun poserTableau(ctx: Context, cle: String, actif: Boolean? = null, duree: Int? = null) {
        val c = choix(ctx)
        val o = c.optJSONObject(cle) ?: JSONObject()
        if (actif != null) o.put("actif", actif)
        if (duree != null) o.put("duree", duree.coerceIn(5, 120))
        c.put(cle, o)
        p(ctx).edit().putString("tableaux", c.toString()).apply(); toucher()
    }

    /** Les tableaux composés sur cet appareil : [{id, titre, duree, cases: [{entite, libelle, rendu}]}]. */
    fun locaux(ctx: Context): JSONArray = try { JSONArray(p(ctx).getString("locaux", "[]") ?: "[]") } catch (_: Exception) { JSONArray() }

    fun ecrireLocaux(ctx: Context, a: JSONArray) { p(ctx).edit().putString("locaux", a.toString()).apply(); toucher() }

    fun nouveauLocal(ctx: Context, titre: String): JSONObject {
        val t = JSONObject().put("id", java.lang.Long.toHexString(System.currentTimeMillis()).takeLast(7)).put("titre", titre).put("duree", 22).put("cases", JSONArray())
        val a = locaux(ctx); a.put(t); ecrireLocaux(ctx, a)
        return t
    }

    fun local(ctx: Context, id: String): JSONObject? {
        val a = locaux(ctx)
        for (i in 0 until a.length()) if (a.getJSONObject(i).optString("id") == id) return a.getJSONObject(i)
        return null
    }

    fun remplacerLocal(ctx: Context, t: JSONObject) {
        val a = locaux(ctx); val n = JSONArray()
        var vu = false
        for (i in 0 until a.length()) { val x = a.getJSONObject(i); if (x.optString("id") == t.optString("id")) { n.put(t); vu = true } else n.put(x) }
        if (!vu) n.put(t)
        ecrireLocaux(ctx, n)
    }

    fun supprimerLocal(ctx: Context, id: String) {
        val a = locaux(ctx); val n = JSONArray()
        for (i in 0 until a.length()) { val x = a.getJSONObject(i); if (x.optString("id") != id) n.put(x) }
        ecrireLocaux(ctx, n)
    }
}
