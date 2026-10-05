import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val signing = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "fr.familleroy.vision"
    compileSdk = 34

    defaultConfig {
        applicationId = "fr.familleroy.vision"
        // Android 5.0 : couvre Fire OS 5+, vieux téléphones et TV.
        minSdk = 21
        // 33 : évite les contraintes de type de service au premier plan
        // d'Android 14 tout en restant installable partout.
        targetSdk = 36
        versionCode = 90
        versionName = "1.40.0"
    }

    signingConfigs {
        create("release") {
            if (signing.isNotEmpty()) {
                storeFile = rootProject.file(signing.getProperty("storeFile"))
                storePassword = signing.getProperty("storePassword")
                keyAlias = signing.getProperty("keyAlias")
                keyPassword = signing.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (signing.isNotEmpty()) signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    // Les flux HLS des caméras (segments fMP4 de Home Assistant) : le MediaPlayer du système ne les lit pas.
    implementation("androidx.media3:media3-exoplayer:1.4.1")
    implementation("androidx.media3:media3-exoplayer-hls:1.4.1")
}
