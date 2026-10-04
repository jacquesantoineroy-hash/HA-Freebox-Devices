package fr.familleroy.vision

/** Les états météo de Home Assistant, en français. */
object Meteo {
    fun libelle(etat: String): String = when (etat) {
        "sunny" -> "Ensoleillé"
        "clear-night" -> "Nuit claire"
        "partlycloudy" -> "Éclaircies"
        "cloudy" -> "Nuageux"
        "fog" -> "Brouillard"
        "rainy" -> "Pluie"
        "pouring" -> "Fortes pluies"
        "lightning", "lightning-rainy" -> "Orages"
        "snowy" -> "Neige"
        "snowy-rainy" -> "Neige et pluie"
        "hail" -> "Grêle"
        "windy", "windy-variant" -> "Venteux"
        "exceptional" -> "Exceptionnel"
        else -> etat.replaceFirstChar { it.uppercase() }
    }
}
