package fr.familleroy.vision

/**
 * Les thèmes de couleurs de l'écran de veille et du lanceur. Les accents de
 * Vision (pourpre, or) restent les mêmes partout ; le fond, l'encre et les
 * lueurs changent. « Sombre » est aussi le mode nuit.
 */
class Theme(
    val nom: String,
    val fond: Int, val encre: Int, val encre2: Int, val encre3: Int,
    val carte: Int, val carteBord: Int, val pourpre: Int, val or: Int,
    val halos: IntArray, val sombre: Boolean,
)

object Themes {
    val liste: List<Theme> = listOf(
        // Palette calée sur la maquette du 04-10-2026 : cartes opaques, encre franche, or plus sombre sur les thèmes clairs.
        Theme("Beige", 0xFFEFE6D6.toInt(), 0xFF2A2026.toInt(), 0xFF6E5A5E.toInt(), 0xFF8F7D80.toInt(),
            0xFFFBF6EC.toInt(), 0x558C2F4B, 0xFF8C2F4B.toInt(), 0xFF8F6110.toInt(), intArrayOf(0xE8B45A, 0xD98A8A, 0x8FAAD6), false),
        Theme("Sombre", 0xFF17121C.toInt(), 0xFFF4EDE1.toInt(), 0xFFBDB1C4.toInt(), 0xFF8E8396.toInt(),
            0xFF251C2D.toInt(), 0x883A2D45.toInt(), 0xFFC2577B.toInt(), 0xFFE2B24A.toInt(), intArrayOf(0x8A4A2A, 0x5A2A3A, 0x2A3A5A), true),
        Theme("Bleu nuit", 0xFF0F1830.toInt(), 0xFFEAF0FA.toInt(), 0xFFB6C1D4.toInt(), 0xFF7F8CA3.toInt(),
            0xFF1A2647.toInt(), 0x882B3A64.toInt(), 0xFF6FA8E8.toInt(), 0xFFE2B24A.toInt(), intArrayOf(0x2E4C8A, 0x5A3A6A, 0x2A6A7A), true),
        Theme("Sauge", 0xFFDDE5DA.toInt(), 0xFF1F2A24.toInt(), 0xFF5E6E64.toInt(), 0xFF7F8F85.toInt(),
            0xFFF2F6EF.toInt(), 0x552F6B55, 0xFF2F6B55.toInt(), 0xFF7F5C0E.toInt(), intArrayOf(0xA9C98F, 0xE0CB7E, 0x98BDCF), false),
        // D'après les photos du salon (04-10) : mur greige, toiles en relief blanc cassé, chiffres en chêne clair, cadran d'acier noir, canapé taupe.
        Theme("Salon", 0xFFD9D1C5.toInt(), 0xFF2A2724.toInt(), 0xFF6B645C.toInt(), 0xFF8E867D.toInt(),
            0xFFF4F1EB.toInt(), 0x552A2724, 0xFFB07E4A.toInt(), 0xFF8A6433.toInt(), intArrayOf(0xD8B98F, 0xFFFFFF, 0x9A948B), false),
        Theme("Rose poudré", 0xFFF0DEDD.toInt(), 0xFF2C1F24.toInt(), 0xFF7A5A60.toInt(), 0xFF998287.toInt(),
            0xFFFBF1F0.toInt(), 0x5596405C, 0xFF96405C.toInt(), 0xFF875A12.toInt(), intArrayOf(0xEBA8B2, 0xEBCC95, 0xC2B0E0), false),
    )

    fun parNom(nom: String): Theme = liste.firstOrNull { it.nom.equals(nom, ignoreCase = true) } ?: liste[0]
}
