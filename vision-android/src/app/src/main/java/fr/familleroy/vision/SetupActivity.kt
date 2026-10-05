package fr.familleroy.vision

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.net.VpnService
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Toast

/**
 * Écran unique : connexion à la maison, puis l'état de l'appareil, les
 * autorisations à accorder (chacune avec son état et un bouton qui ouvre le
 * bon réglage), la version et l'espace parent. Tout est navigable à la
 * télécommande. Les réglages sensibles sont derrière le code parent.
 */
class SetupActivity : Activity() {

    private lateinit var racine: LinearLayout
    private val cfg by lazy { Config(this) }

    /** Une protection à accorder : son état et le réglage système qui l'active. */
    private inner class Protection(val titre: String, val detail: String, val ok: () -> Boolean,
                                   /** Ce qu'on perd sans elle. */ val sans: String = "",
                                   /** Faux quand cet appareil n'a pas l'écran de réglage qui l'accorde (souvent sur télé). */ val possible: () -> Boolean = { true },
                                   val ouvrir: () -> Unit)

    private fun existe(i: Intent): Boolean = try { i.resolveActivity(packageManager) != null } catch (_: Exception) { false }
    private val pkgUri get() = Uri.parse("package:$packageName")

    private fun protections(): List<Protection> {
        val l = ArrayList<Protection>()
        val tele = ReglagesTvActivity.estTele(this)
        l.add(Protection("Données d'usage", "Temps d'écran et appli au premier plan", { Usage.accesUsage(this) },
            "Sans : pas de temps d'écran, et les applis bloquées ne sont repérées que par l'accessibilité.",
            { existe(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) }) { ouvrir(Settings.ACTION_USAGE_ACCESS_SETTINGS) })
        l.add(Protection("Accessibilité", "Ferme les applis bloquées dès qu'elles s'ouvrent", { VisionAccessibility.estActive(this) },
            "Sans : une appli bloquée met quelques secondes à se fermer" + (if (tele) ", la touche Accueil n'ouvre pas Vision et la veille ne sait pas si quelqu'un regarde." else "."),
            { existe(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }) { ouvrir(Settings.ACTION_ACCESSIBILITY_SETTINGS) })
        l.add(Protection("Affichage par-dessus", "Écran de blocage et messages urgents", { peutRecouvrir() },
            "Sans : pas d'écran de blocage ni de message par-dessus" + (if (tele) ", et l'écran de veille coupe l'appli en cours au lieu de passer devant." else "."),
            { Build.VERSION.SDK_INT < 23 || existe(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, pkgUri)) }) { demanderOverlay() })
        l.add(Protection("Filtre des sites", "VPN local : seul le DNS passe par Vision", { DnsVpnService.actif || DnsVpnService.autorise(this) },
            "Sans : aucun site n'est filtré sur cet appareil ; seules les applis le sont.",
            { try { VpnService.prepare(this)?.let { existe(it) } ?: true } catch (_: Exception) { false } }) { demanderVpn() })
        l.add(Protection("Désinstallation protégée", "Impossible de retirer Vision sans le code parent", { AdminReceiver.estActif(this) },
            "Sans : Vision peut être désinstallée depuis les réglages, sans le code parent.",
            { existe(Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN)) }) { demanderAdmin() })
        if (Build.VERSION.SDK_INT >= 23)
            l.add(Protection("Batterie", "Vision reste active en arrière-plan", { batterieIgnoree() },
                "Sans : Android peut endormir Vision ; les règles et les messages arrivent avec retard.",
                { existe(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, pkgUri)) || existe(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }) { demanderBatterie() })
        l.add(Protection("Mises à jour", "Vision peut installer ses nouvelles versions", { MiseAJour.peutInstaller(this) },
            "Sans : chaque nouvelle version attend une confirmation à l'écran.",
            { Build.VERSION.SDK_INT < 26 || existe(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, pkgUri)) }) { demanderInstallation() })
        if (tele && Build.VERSION.SDK_INT >= 23)
            l.add(Protection("Réglages système", "Délai avant l'écran de veille", { Local.peutEcrireSysteme(this) },
                "Sans : le délai de veille choisi dans Vision ne vaut que sur l'accueil Vision ; ailleurs c'est celui de la télé.",
                { existe(Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, pkgUri)) }) { try { startActivity(Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, pkgUri)) } catch (_: Exception) {} })
        return l
    }

    /** Assistant : on enchaîne les réglages manquants, un par un, au retour de chaque écran. */
    private var assistant = false
    private var assistantDerniere: String = ""
    private var rechercheFaite = false

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Ui.charger(this)
        if (Build.VERSION.SDK_INT >= 21) {
            window.statusBarColor = Ui.FOND
            window.navigationBarColor = Ui.FOND
        }
        val scroll = ScrollView(this).apply {
            setBackgroundColor(Ui.FOND)
            isFillViewport = true
        }
        racine = Ui.colonne(this, Ui.dp(this, 20f))
        scroll.addView(racine)
        setContentView(scroll)
        if (Build.VERSION.SDK_INT >= 33) {
            try { requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 9) } catch (_: Exception) {}
        }
        traiterIntent(intent)
    }

    override fun onNewIntent(i: Intent?) {
        super.onNewIntent(i)
        traiterIntent(i)
    }

    /** Toucher de la notification « nouvelle version » : on ouvre l'installation. Ou une page partagée vers Vision. */
    private fun traiterIntent(i: Intent?) {
        // Relier sans clavier (télé, box) : « adb shell am start -n …/.SetupActivity --es bloc "adresse: … cle: …" ».
        // Accepté seulement tant que l'appareil n'est pas inscrit : ensuite, un bloc n'a plus rien à faire ici.
        val bloc = i?.getStringExtra(EXTRA_BLOC)
        if (!bloc.isNullOrBlank() && !cfg.inscrit) {
            i.removeExtra(EXTRA_BLOC)
            val (externe, interne, cle) = analyserBloc(bloc)
            if ((externe.isNotEmpty() || interne.isNotEmpty()) && cle.isNotEmpty()) {
                cfg.urlExterne = externe.ifEmpty { interne }
                cfg.urlInterne = interne
                cfg.cleInscription = cle
                i.getStringExtra(EXTRA_UTILISATEUR)?.let { cfg.utilisateur = it.trim() }
                toast("Connexion…")
                AgentService.demarrer(this)
                racine.postDelayed({ dessiner() }, 2500)
            } else toast("Bloc incomplet : il faut une adresse et une clé")
            return
        }
        if (i?.action == Intent.ACTION_SEND && cfg.inscrit) {
            val texte = i.getStringExtra(Intent.EXTRA_TEXT) ?: ""
            val lien = Regex("https?://\\S+").find(texte)?.value ?: texte.trim()
            val hote = Acces.hoteDe(lien)
            i.action = ""
            if (hote.isNotEmpty()) Acces.dialogue(this, "sites", hote, hote, lien) { dessiner() }
            else toast("Aucun lien dans ce partage")
            return
        }
        val nom = i?.getStringExtra(MiseAJour.EXTRA_INSTALLER) ?: return
        i.removeExtra(MiseAJour.EXTRA_INSTALLER)
        val f = java.io.File(MiseAJour.dossier(this), nom)
        if (f.isFile) MiseAJour.installer(this, f) else toast("Fichier de mise à jour introuvable")
    }

    override fun onResume() {
        super.onResume(); auPremierPlan = true
        if (assistant) avancerAssistant() else dessiner()
    }

    private fun avancerAssistant() {
        val manquantes = protections().filter { !it.ok() && it.possible() }
        if (manquantes.isEmpty()) {
            assistant = false; assistantDerniere = ""
            toast("Tout est en place."); dessiner(); return
        }
        val suivante = manquantes.first()
        dessiner()
        // On n'ouvre automatiquement que si l'étape précédente a été accordée :
        // sinon l'utilisateur a refusé ou s'est perdu, on lui laisse la main.
        if (suivante.titre != assistantDerniere) {
            assistantDerniere = suivante.titre
            racine.postDelayed({ if (assistant && !suivante.ok()) suivante.ouvrir() }, 450)
        }
    }
    override fun onPause() { auPremierPlan = false; MiseAJour.surEtat = null; super.onPause() }

    // ------------------------------------------------------------- Écran

    private fun dessiner() {
        racine.removeAllViews()
        entete()
        if (!cfg.inscrit) { ecranConnexion(); return }

        carteEtat()

        if (cfg.personne.isEmpty() && cfg.personnes.isNotEmpty()) { choixPersonne(); return }

        val toutes = protections()
        val manquantes = toutes.filter { !it.ok() && it.possible() }
        val impossibles = toutes.filter { !it.ok() && !it.possible() }
        if (manquantes.isNotEmpty()) {
            val c = Ui.carte(this, Ui.CARTE_HAUTE)
            val etape = manquantes.first()
            if (assistant) {
                val total = toutes.size - impossibles.size
                val faites = total - manquantes.size
                c.addView(Ui.texte(this, "Étape ${faites.plus(1)} sur $total : ${etape.titre}", 16f, Ui.OR, gras = true))
                c.addView(Ui.marge(this, Ui.texte(this, etape.detail, 14f, Ui.TEXTE_2), haut = 6f))
                val r = Ui.rangee(this)
                r.addView(Ui.poids(Ui.boutonPrimaire(this, "Ouvrir le réglage") { etape.ouvrir() }))
                r.addView(Ui.marge(this, Ui.boutonSecondaire(this, "Arrêter") { assistant = false; dessiner() }, gauche = 8f))
                c.addView(Ui.marge(this, r, haut = 14f))
            } else {
                c.addView(Ui.texte(this, "${manquantes.size} autorisation${if (manquantes.size > 1) "s" else ""} à accorder", 16f, Ui.TEXTE, gras = true))
                c.addView(Ui.marge(this, Ui.texte(this, "Vision t'emmène dans chaque réglage, l'un après l'autre.", 13f, Ui.TEXTE_2), haut = 4f))
                c.addView(Ui.marge(this, Ui.boutonPrimaire(this, "Configurer maintenant") {
                    assistant = true; assistantDerniere = ""; avancerAssistant()
                }, haut = 12f))
            }
            racine.addView(c)
        }

        racine.addView(Ui.section(this, "Protections"))
        val protections = Ui.carte(this)
        protections().forEachIndexed { k, pr ->
            if (k > 0) protections.addView(Ui.separateur(this))
            protections.addView(ligneProtection(pr.titre, pr.detail, pr.ok(), pr.ouvrir, pr.sans, pr.possible()))
        }
        racine.addView(protections)
        if (impossibles.isNotEmpty()) {
            val c = Ui.carte(this, Ui.FOND)
            c.addView(Ui.texte(this, "${impossibles.size} autorisation${if (impossibles.size > 1) "s" else ""} que cet appareil ne permet pas d'accorder à l'écran", 14f, Ui.TEXTE, gras = true))
            c.addView(Ui.marge(this, Ui.texte(this, "Son système n'a pas l'écran de réglage correspondant. Home Assistant peut les accorder par le réseau (débogage ADB activé sur l'appareil) ; sinon Vision fonctionne, avec les limites indiquées ci-dessus.", 13f, Ui.TEXTE_2), haut = 4f))
            racine.addView(c)
        }

        racine.addView(Ui.section(this, "Version"))
        val version = Ui.carte(this)
        version.addView(ligneInfo("Installée", BuildConfigCompat.version(this)))
        version.addView(ligneInfo("Mises à jour", MiseAJour.etatAuto(this)))
        if (MiseAJour.disponible.isNotEmpty()) {
            version.addView(ligneInfo("Disponible", MiseAJour.disponible))
            val etat = Ui.texte(this, MiseAJour.etat.ifEmpty { "Prête à être installée." }, 13f, Ui.TEXTE_2)
            MiseAJour.surEtat = { t -> etat.text = t }
            version.addView(Ui.marge(this, Ui.boutonPrimaire(this, "Installer la ${MiseAJour.disponible}") {
                etat.text = "Téléchargement…"
                cfg.majProposee = ""
                MiseAJour.installerMaintenant(this, cfg)
            }, haut = 12f))
            version.addView(Ui.marge(this, etat, haut = 8f))
        } else if (MiseAJour.etat.isNotEmpty()) version.addView(Ui.marge(this, Ui.texte(this, MiseAJour.etat, 13f, Ui.TEXTE_2), haut = 6f))
        racine.addView(version)

        if (Build.VERSION.SDK_INT >= 31) {
            val aide = Ui.carte(this, Ui.FOND)
            aide.addView(Ui.texte(this,
                "Accessibilité grisée ? Infos de l'appli ▸ menu ⋮ ▸ « Autoriser les paramètres restreints ».",
                13f, Ui.TEXTE_3))
            racine.addView(aide)
        }

        if (!cfg.modeParent && !Etat.parent) {
            racine.addView(Ui.section(this, "Demander un accès"))
            val s = Ui.carte(this)
            val nb = Etat.recentsBloques().size
            s.addView(Ui.texte(this, "Une appli ou un site fermé ? Vois pourquoi, et demande l'accès : un parent répond sur son téléphone. Tu peux aussi « Partager » une page vers Vision.", 13f, Ui.TEXTE_2))
            s.addView(Ui.marge(this, Ui.boutonPrimaire(this, if (nb > 0) "Ce qui est fermé ($nb récents)" else "Ce qui est fermé") {
                startActivity(Intent(this, FermesActivity::class.java))
            }, haut = 12f))
            racine.addView(s)
        }

        if (Etat.parent) {
            racine.addView(Ui.section(this, "La maison"))
            val m = Ui.carte(this, Ui.CARTE_HAUTE)
            m.addView(Ui.texte(this, "Les appareils des enfants", 16f, Ui.TEXTE, gras = true))
            m.addView(Ui.marge(this, Ui.texte(this, "Qui est ouvert, ce qui est coupé, le planning. Accorder du temps ou fermer d'un geste.", 14f, Ui.TEXTE_2), haut = 6f))
            m.addView(Ui.marge(this, Ui.boutonPrimaire(this, "Ouvrir") { startActivity(Intent(this, ParentsActivity::class.java)) }, haut = 14f))
            racine.addView(m)
        }

        // L'accueil Vision et l'écran de veille : tout se règle sur l'appareil, dans un seul écran.
        racine.addView(Ui.section(this, "Accueil et écran de veille"))
        val acc = Ui.carte(this)
        acc.addView(Ui.texte(this, "Réglages de l'appareil", 16f, Ui.TEXTE, gras = true))
        acc.addView(Ui.marge(this, Ui.texte(this, "Tableaux de veille (et tableaux composés avec les entités Home Assistant), son, thème, couleurs, applications visibles, bulle.", 14f, Ui.TEXTE_2), haut = 6f))
        val r1 = Ui.rangee(this)
        r1.addView(Ui.boutonPrimaire(this, "Régler") { startActivity(Intent(this, ReglagesTvActivity::class.java)) })
        r1.addView(Ui.marge(this, Ui.boutonSecondaire(this, "Accueil Vision") { startActivity(Intent(this, LanceurActivity::class.java)) }, gauche = 8f))
        acc.addView(Ui.marge(this, r1, haut = 12f))
        racine.addView(acc)

        racine.addView(Ui.section(this, "Espace parent"))
        val parent = Ui.carte(this)
        zoneParent(parent)
        racine.addView(parent)
        racine.addView(Ui.espace(this, 24f))
    }

    private fun entete() {
        racine.addView(Ui.marque(this))
        val col = Ui.colonne(this)
        col.addView(Ui.titre(this, "Réglages"))
        col.addView(Ui.sousTitre(this, "Le contrôle parental de la maison"))
        racine.addView(Ui.marge(this, col, bas = 18f))
    }

    /** La grande carte : qui, ouvert ou fermé, et ce qui vient. */
    private fun carteEtat() {
        val horsLigne = Etat.horsLigne()
        val ferme = Etat.verrouilleEffectif()
        val couleur = when { horsLigne -> Ui.TEXTE_2; ferme -> Ui.ROUGE; else -> Ui.VERT }
        val libelle = when { horsLigne -> "Hors ligne"; ferme -> "Fermé"; cfg.modeParent -> "Pause parent"; else -> "Ouvert" }
        val c = Ui.carte(this, Ui.CARTE_HAUTE)
        val haut = Ui.rangee(this)
        val col = Ui.colonne(this)
        col.addView(Ui.texte(this, cfg.nom.ifEmpty { cfg.host }, 20f, Ui.TEXTE, gras = true))
        col.addView(Ui.texte(this, cfg.utilisateur.ifEmpty { "Appareil de la maison" }, 13f, Ui.TEXTE_2))
        haut.addView(Ui.poids(col))
        haut.addView(Ui.chip(this, libelle, couleur))
        c.addView(haut)
        val detail = when {
            horsLigne -> "Home Assistant est injoignable : les dernières règles restent appliquées."
            cfg.modeParent -> "Protection en pause jusqu'à ${Etat.heure(cfg.parentJusqua)}."
            ferme && Etat.prochainChangement > System.currentTimeMillis() ->
                "Réouverture à ${Etat.heure(Etat.prochainChangement)}."
            ferme -> Etat.message.ifEmpty { "La maison a fermé l'accès." }
            Etat.prochainChangement > System.currentTimeMillis() ->
                "Fermeture prévue à ${Etat.heure(Etat.prochainChangement)}."
            else -> "Aucune fermeture prévue."
        }
        c.addView(Ui.marge(this, Ui.texte(this, detail, 14f, Ui.TEXTE_2), haut = 12f))
        racine.addView(c)
    }

    private fun ligneProtection(titre: String, detail: String, ok: Boolean, action: () -> Unit, sans: String = "", possible: Boolean = true): View {
        val r = Ui.rangee(this)
        r.addView(Ui.pastille(this, ok))
        val col = Ui.colonne(this)
        col.addView(Ui.texte(this, titre, 15f, Ui.TEXTE, gras = true))
        col.addView(Ui.texte(this, detail, 12.5f, Ui.TEXTE_2))
        // Ce qu'on perd tant qu'elle manque, et si l'appareil sait l'accorder.
        if (!ok && sans.isNotEmpty()) col.addView(Ui.texte(this, sans, 12.5f, Ui.OR))
        if (!ok && !possible) col.addView(Ui.texte(this, "Cet appareil ne propose pas ce réglage.", 12.5f, Ui.TEXTE_3))
        r.addView(Ui.poids(col))
        if (!ok && possible) r.addView(Ui.marge(this, Ui.boutonSecondaire(this, "Activer", action), gauche = 10f))
        return r
    }

    private fun ligneInfo(cle: String, valeur: String): View {
        val r = Ui.rangee(this)
        // Le libellé garde sa largeur (jamais coupé en deux lignes) ; la valeur prend le reste.
        r.addView(Ui.texte(this, cle, 14f, Ui.TEXTE_2).apply { maxLines = 1; setPadding(0, 0, Ui.dp(this@SetupActivity, 12f), 0) })
        r.addView(Ui.texte(this, valeur, 14f, Ui.TEXTE, gras = true).apply {
            gravity = Gravity.END
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        })
        return Ui.marge(this, r, haut = 4f, bas = 4f)
    }

    // ------------------------------------------------- Connexion initiale

    private fun ecranConnexion() {
        // D'abord tout seul : Home Assistant s'annonce sur le réseau de la maison.
        val auto = Ui.carte(this, Ui.CARTE_HAUTE)
        auto.addView(Ui.texte(this, "Connexion automatique", 18f, Ui.TEXTE, gras = true))
        val suivi = Ui.texte(this, Decouverte.etat.ifEmpty { "Vision cherche Home Assistant sur le réseau de la maison." }, 14f, Ui.TEXTE_2)
        auto.addView(Ui.marge(this, suivi, haut = 6f))
        fun chercher() {
            cfg.sansCle = false
            Decouverte.inscrireSeul(this) { _ ->
                suivi.text = Decouverte.etat
                // L'inscription suit dans le service : on regarde quelques secondes si elle a abouti.
                var essais = 0
                val voir = object : Runnable { override fun run() {
                    if (isFinishing) return
                    if (cfg.inscrit) { dessiner(); return }
                    suivi.text = Decouverte.etat
                    if (++essais < 8) racine.postDelayed(this, 1500)
                } }
                racine.postDelayed(voir, 1500)
            }
            suivi.text = Decouverte.etat
        }
        auto.addView(Ui.marge(this, Ui.boutonSecondaire(this, "Chercher à nouveau") { chercher() }, haut = 12f))
        racine.addView(auto)
        if (!rechercheFaite) { rechercheFaite = true; chercher() }

        val c = Ui.carte(this)
        c.addView(Ui.texte(this, "Ou relier à la main", 18f, Ui.TEXTE, gras = true))
        c.addView(Ui.marge(this, Ui.sousTitre(this,
            "Dans Home Assistant, tableau Vision, onglet Ajouter : copie le bloc « adresse / clé » et colle-le ici."), bas = 8f))
        val bloc = Ui.champ(this, "Colle ici le bloc copié depuis Home Assistant", "").apply {
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE
            minLines = 3; gravity = Gravity.TOP
        }
        c.addView(bloc)
        val user = Ui.champ(this, "Prénom (facultatif, choisi ensuite dans la liste)", cfg.utilisateur)
        c.addView(user)
        c.addView(Ui.marge(this, Ui.boutonPrimaire(this, "Connecter") {
            val (externe, interne, cle) = analyserBloc(bloc.text.toString())
            if (externe.isEmpty() && interne.isEmpty() || cle.isEmpty()) {
                toast("Je n'ai pas trouvé d'adresse et de clé dans ce texte"); return@boutonPrimaire
            }
            cfg.urlExterne = externe.ifEmpty { interne }
            cfg.urlInterne = interne
            cfg.cleInscription = cle
            cfg.sansCle = false
            cfg.utilisateur = user.text.toString().trim()
            toast("Connexion…")
            AgentService.demarrer(this)
            racine.postDelayed({ dessiner() }, 2500)
        }, haut = 16f))
        racine.addView(c)
    }

    /**
     * Lit un texte collé : une ou deux adresses http(s) et une clé. Tolère le
     * bloc de Home Assistant (« adresse: … / cle: … / locale: … ») comme une
     * simple paire « url clé » tapée à la main.
     */
    private fun analyserBloc(t: String): Triple<String, String, String> {
        var externe = ""; var interne = ""
        for (m in Regex("https?://[^\\s\"'<>`]+").findAll(t)) {
            val url = m.value.trimEnd('.', ',', ';', ')')
            val hote = url.substringAfter("://").substringBefore('/').substringBefore(':')
            val prive = hote.startsWith("192.168.") || hote.startsWith("10.") || hote.endsWith(".local") ||
                Regex("^172\\.(1[6-9]|2[0-9]|3[01])\\.").containsMatchIn(hote) || hote == "localhost"
            if (prive) { if (interne.isEmpty()) interne = url } else if (externe.isEmpty()) externe = url
        }
        val cle = Regex("(?i)cl[ée]\\s*(?:d'inscription)?\\s*[:=]\\s*`?([A-Za-z0-9]{8,64})").find(t)?.groupValues?.get(1)
            ?: Regex("\\b[0-9a-f]{16,64}\\b").find(t)?.value ?: ""
        return Triple(externe, interne, cle)
    }

    /** Après l'inscription : qui tient cet appareil ? (liste des personnes de Home Assistant) */
    private fun choixPersonne() {
        val c = Ui.carte(this)
        c.addView(Ui.texte(this, "Qui utilise cet appareil ?", 18f, Ui.TEXTE, gras = true))
        c.addView(Ui.marge(this, Ui.sousTitre(this, "Les plages horaires et les règles de cette personne s'appliqueront ici."), bas = 6f))
        val liste = try { org.json.JSONArray(cfg.personnes) } catch (_: Exception) { org.json.JSONArray() }
        for (i in 0 until liste.length()) {
            val p = liste.optJSONObject(i) ?: continue
            val nom = p.optString("nom"); val id = p.optString("entity_id")
            if (nom.isEmpty() || id.isEmpty()) continue
            c.addView(Ui.marge(this, Ui.boutonSecondaire(this, nom) {
                cfg.personne = id; cfg.utilisateur = nom; cfg.personneAEnvoyer = true
                AgentService.demarrer(this)
                toast("Appareil de $nom")
                assistant = true; assistantDerniere = ""; avancerAssistant()
            }.apply { layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT) }, haut = 8f))
        }
        c.addView(Ui.marge(this, Ui.texte(this, "Personne d'autre ? Choisis-le plus tard dans Home Assistant.", 12f, Ui.TEXTE_3), haut = 10f))
        c.addView(Ui.marge(this, Ui.boutonSecondaire(this, "Passer") { cfg.personne = "-"; dessiner() }, haut = 6f))
        racine.addView(c)
    }

    // ---------------------------------------------------- Espace parent

    private fun zoneParent(c: LinearLayout) {
        if (!cfg.aUnCode) {
            c.addView(Ui.sousTitre(this, "Choisis un code parent : il protège ces réglages et la désinstallation."))
            val pin = Ui.champ(this, "Nouveau code (4 chiffres ou plus)", "", chiffres = true)
            c.addView(pin)
            c.addView(Ui.marge(this, Ui.boutonPrimaire(this, "Définir le code") {
                val code = pin.text.toString()
                if (code.length < 4) { toast("Au moins 4 chiffres"); return@boutonPrimaire }
                cfg.definirCode(code); toast("Code enregistré"); dessiner()
            }, haut = 12f))
            return
        }
        if (cfg.modeParent) {
            c.addView(ligneInfo("Mode parent", "jusqu'à ${Etat.heure(cfg.parentJusqua)}"))
            c.addView(Ui.marge(this, Ui.boutonPrimaire(this, "Reprendre la protection") { cfg.parentJusqua = 0; dessiner() }, haut = 12f))
            c.addView(Ui.marge(this, Ui.boutonDanger(this, "Désinstaller Vision") { desinstaller() }, haut = 10f))
            return
        }
        c.addView(Ui.sousTitre(this, "Mettre Vision en pause le temps d'un réglage ou d'une exception."))
        val pin = Ui.champ(this, "Code parent", "", chiffres = true)
        c.addView(pin)
        val r = Ui.rangee(this)
        listOf(15 to "Pause 15 min", 60 to "Pause 1 h").forEachIndexed { k, (min, lbl) ->
            r.addView(Ui.marge(this, Ui.poids(Ui.boutonSecondaire(this, lbl) {
                if (!cfg.verifierCode(pin.text.toString())) { toast("Code incorrect"); return@boutonSecondaire }
                cfg.parentJusqua = System.currentTimeMillis() + min * 60_000L
                toast(lbl); dessiner()
            }), gauche = if (k == 0) 0f else 8f))
        }
        c.addView(Ui.marge(this, r, haut = 12f))
    }

    private fun desinstaller() {
        // On retire d'abord l'administrateur, sinon le système refuse la désinstallation.
        if (AdminReceiver.estActif(this)) {
            val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
            try { dpm.removeActiveAdmin(AdminReceiver.composant(this)) } catch (_: Exception) {}
        }
        try {
            startActivity(Intent(Intent.ACTION_DELETE, Uri.parse("package:$packageName")))
        } catch (_: Exception) { toast("Ouvre les réglages pour désinstaller") }
    }

    // ---------------------------------------------------- Actions système

    private fun demanderOverlay() {
        if (Build.VERSION.SDK_INT >= 23)
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
    }

    private fun demanderVpn() {
        val i = VpnService.prepare(this)
        if (i != null) startActivityForResult(i, 1) else DnsVpnService.demarrer(this)
    }

    private fun demanderAdmin() {
        val i = Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN)
            .putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, AdminReceiver.composant(this))
            .putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, getString(R.string.admin_desc))
        try { startActivity(i) } catch (_: Exception) { toast("Indisponible sur cet appareil") }
    }

    private fun demanderBatterie() {
        if (Build.VERSION.SDK_INT >= 23) try {
            startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                Uri.parse("package:$packageName")))
        } catch (_: Exception) { ouvrir(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS) }
    }

    /** Réglage Android « Installer des applis inconnues », à accorder une fois à Vision. */
    private fun demanderInstallation() {
        if (Build.VERSION.SDK_INT >= 26) try {
            startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:$packageName")))
        } catch (_: Exception) { toast("Réglage introuvable") }
    }

    override fun onActivityResult(req: Int, res: Int, data: Intent?) {
        super.onActivityResult(req, res, data)
        if (req == 1 && res == RESULT_OK) DnsVpnService.demarrer(this)
    }

    private fun peutRecouvrir(): Boolean =
        Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this)

    private fun batterieIgnoree(): Boolean {
        if (Build.VERSION.SDK_INT < 23) return true
        val pm = getSystemService(Context.POWER_SERVICE) as android.os.PowerManager
        return pm.isIgnoringBatteryOptimizations(packageName)
    }

    private fun ouvrir(action: String) = try { startActivity(Intent(action)) }
        catch (_: Exception) { toast("Réglage introuvable") }

    private fun toast(t: String) = Toast.makeText(this, t, Toast.LENGTH_SHORT).show()

    companion object {
        /** Vrai quand l'écran de Vision est devant : l'écran du système peut alors s'ouvrir directement. */
        @Volatile var auPremierPlan = false
        const val EXTRA_BLOC = "bloc"
        const val EXTRA_UTILISATEUR = "utilisateur"
    }

}
