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
        // Thèmes d'univers : jeux (Tactique, Briques, Corsaire, Royale), passions (Circuit, Cockpit, Bourse, Écrin), dehors (Prairie, Large, Sommet, Sous-bois).
        Theme("Tactique", 0xFF0F1923.toInt(), 0xFFECE8E1.toInt(), 0xFF9AA7B1.toInt(), 0xFF69757F.toInt(),
            0xFF1B2733.toInt(), 0x55FF4655, 0xFFFF4655.toInt(), 0xFFFF4655.toInt(), intArrayOf(0xAB3644, 0x707C86, 0x763341), true),
        Theme("Briques", 0xFFF2F4F5.toInt(), 0xFF191B1D.toInt(), 0xFF60666C.toInt(), 0xFF93989C.toInt(),
            0xFFFFFFFF.toInt(), 0x550A84D6, 0xFF0A84D6.toInt(), 0xFF0A84D6.toInt(), intArrayOf(0x5BABE1, 0x8C9195, 0x9DCEEF), false),
        Theme("Corsaire", 0xFF0B2A3A.toInt(), 0xFFF4EBD0.toInt(), 0xFFA9C3C9.toInt(), 0xFF728D97.toInt(),
            0xFF123C50.toInt(), 0x55F2A93B, 0xFFF2A93B.toInt(), 0xFFF2A93B.toInt(), intArrayOf(0xA17D3B, 0x7A959E, 0x6C6848), true),
        Theme("Royale", 0xFF1B1035.toInt(), 0xFFF5F3FF.toInt(), 0xFFB9AEE0.toInt(), 0xFF8277A4.toInt(),
            0xFF2A1B55.toInt(), 0x55F8D21A, 0xFFF8D21A.toInt(), 0xFFF8D21A.toInt(), intArrayOf(0xAB8E23, 0x8A7FAD, 0x7C643D), true),
        Theme("Circuit", 0xFF121212.toInt(), 0xFFF2F2F2.toInt(), 0xFFA0A0A0.toInt(), 0xFF6E6E6E.toInt(),
            0xFF1E1E1E.toInt(), 0x55E5281B, 0xFFE5281B.toInt(), 0xFFE5281B.toInt(), intArrayOf(0x9B2018, 0x757575, 0x6E221D), true),
        Theme("Cockpit", 0xFF0E1A24.toInt(), 0xFFE8F1F8.toInt(), 0xFF9DB2C4.toInt(), 0xFF6B7D8C.toInt(),
            0xFF16283A.toInt(), 0x55FFB000, 0xFFFFB000.toInt(), 0xFFFFB000.toInt(), intArrayOf(0xAB7C0D, 0x728494, 0x735E23), true),
        Theme("Bourse", 0xFF0B0F0E.toInt(), 0xFFE6F2EC.toInt(), 0xFF8FA59B.toInt(), 0xFF61706A.toInt(),
            0xFF141B19.toInt(), 0x5521C77A, 0xFF21C77A.toInt(), 0xFF21C77A.toInt(), intArrayOf(0x198754, 0x677871, 0x196040), true),
        Theme("Écrin", 0xFF0E0C0A.toInt(), 0xFFF3EBDD.toInt(), 0xFFB4A68F.toInt(), 0xFF7A7060.toInt(),
            0xFF1A1714.toInt(), 0x55C9A45C, 0xFFC9A45C.toInt(), 0xFFC9A45C.toInt(), intArrayOf(0x886F3F, 0x827867, 0x604F31), true),
        Theme("Prairie", 0xFFEEF3E6.toInt(), 0xFF22301F.toInt(), 0xFF5F7058.toInt(), 0xFF919E8A.toInt(),
            0xFFFAFCF5.toInt(), 0x554F8A2B, 0xFF4F8A2B.toInt(), 0xFF4F8A2B.toInt(), intArrayOf(0x87AF6C, 0x8A9783, 0xB6CEA4), false),
        Theme("Large", 0xFFE6F1F5.toInt(), 0xFF12303D.toInt(), 0xFF55737F.toInt(), 0xFF889FA8.toInt(),
            0xFFF7FBFD.toInt(), 0x550F7EA3, 0xFF0F7EA3.toInt(), 0xFF0F7EA3.toInt(), intArrayOf(0x5AA6C0, 0x8099A2, 0x9AC9D9), false),
        Theme("Sommet", 0xFFE9EDF1.toInt(), 0xFF1F2933.toInt(), 0xFF5C6B7A.toInt(), 0xFF8D98A4.toInt(),
            0xFFF8FAFC.toInt(), 0x55C2553A, 0xFFC2553A.toInt(), 0xFFC2553A.toInt(), intArrayOf(0xD08A7A, 0x86929E, 0xE2B8AE), false),
        Theme("Sous-bois", 0xFF1A2119.toInt(), 0xFFECE6D6.toInt(), 0xFFA9B19C.toInt(), 0xFF777F6E.toInt(),
            0xFF252E23.toInt(), 0x55C58B3B, 0xFFC58B3B.toInt(), 0xFFC58B3B.toInt(), intArrayOf(0x89662F, 0x7E8675, 0x65532D), true),
        // Thèmes d'histoires : écran (Code, Plume, Galaxie, Rétro 85, Grimoire), contes (Féerie, Banquise, Lagon), créatures (Étincelle).
        Theme("Code", 0xFF030A05.toInt(), 0xFFD7FFE0.toInt(), 0xFF6FBF87.toInt(), 0xFF49805A.toInt(),
            0xFF0A1A10.toInt(), 0x552BEA6B, 0xFF2BEA6B.toInt(), 0xFF2BEA6B.toInt(), intArrayOf(0x1D9C47, 0x4F8960, 0x176D34), true),
        Theme("Plume", 0xFFE8F1F7.toInt(), 0xFF23313D.toInt(), 0xFF5F7482.toInt(), 0xFF8FA0AB.toInt(),
            0xFFF8FBFD.toInt(), 0x55A8552F, 0xFFA8552F.toInt(), 0xFFA8552F.toInt(), intArrayOf(0xBE8C75, 0x889AA5, 0xD8B9AB), false),
        Theme("Galaxie", 0xFF05060A.toInt(), 0xFFF4F1E4.toInt(), 0xFF9AA0B4.toInt(), 0xFF666A78.toInt(),
            0xFF10131C.toInt(), 0x55FFD426, 0xFFFFD426.toInt(), 0xFFFFD426.toInt(), intArrayOf(0xA88C1C, 0x6D7281, 0x706020), true),
        Theme("Rétro 85", 0xFF14100E.toInt(), 0xFFF6EDE2.toInt(), 0xFFB8A698.toInt(), 0xFF7F7268.toInt(),
            0xFF221B17.toInt(), 0x55FF7A1A, 0xFFFF7A1A.toInt(), 0xFFFF7A1A.toInt(), intArrayOf(0xAD5516, 0x87796F, 0x7A4118), true),
        Theme("Grimoire", 0xFF1C1210.toInt(), 0xFFF1E6CF.toInt(), 0xFFB9A583.toInt(), 0xFF82725B.toInt(),
            0xFF2A1C18.toInt(), 0x55D4A843, 0xFFD4A843.toInt(), 0xFFD4A843.toInt(), intArrayOf(0x947431, 0x8A7960, 0x6E5429), true),
        Theme("Féerie", 0xFF141A3C.toInt(), 0xFFF6F3FF.toInt(), 0xFFB4B8E0.toInt(), 0xFF7C81A7.toInt(),
            0xFF1F2757.toInt(), 0x55FFD36E, 0xFFFFD36E.toInt(), 0xFFFFD36E.toInt(), intArrayOf(0xAD925C, 0x8489AF, 0x796C60), true),
        Theme("Banquise", 0xFFE9F4FB.toInt(), 0xFF173247.toInt(), 0xFF5C7C92.toInt(), 0xFF8DA6B7.toInt(),
            0xFFF8FCFF.toInt(), 0x552F8FCB, 0xFF2F8FCB.toInt(), 0xFF2F8FCB.toInt(), intArrayOf(0x70B2DC, 0x86A0B2, 0xA8D0EA), false),
        Theme("Lagon", 0xFF06343B.toInt(), 0xFFF3F0DC.toInt(), 0xFF9CC7C2.toInt(), 0xFF689493.toInt(),
            0xFF0C4750.toInt(), 0x55FF8A5B, 0xFFFF8A5B.toInt(), 0xFFFF8A5B.toInt(), intArrayOf(0xA86C50, 0x6F9B9A, 0x6D6254), true),
        Theme("Étincelle", 0xFFFFF4CC.toInt(), 0xFF2B2416.toInt(), 0xFF75683F.toInt(), 0xFFA59970.toInt(),
            0xFFFFFBEA.toInt(), 0x55D93A2B, 0xFFD93A2B.toInt(), 0xFFD93A2B.toInt(), intArrayOf(0xE67B63, 0x9E9269, 0xF0AE9E), false),
    )

    /** Le nom d'un thème en clé simple (« Rose poudré » → « rose-poudre ») : c'est elle qui choisit l'horloge de la veille. */
    fun cle(nom: String): String = java.text.Normalizer.normalize(nom, java.text.Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"), "").lowercase().replace(' ', '-')

    fun parNom(nom: String): Theme = liste.firstOrNull { it.nom.equals(nom, ignoreCase = true) } ?: liste[0]
}
