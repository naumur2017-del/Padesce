# Manuel de Reference - Systeme de Reporting et d'Analyse PADESCE

> Document de reference fonctionnel et technique pour les utilisateurs finaux, les consultants d'analyse et les administrateurs.
>
> Base de redaction : inspection du code applicatif Django, des vues de reporting, des dashboards d'analyse et des connecteurs Excel reseau.
>
> Version du referentiel analyse : 09/04/2026.

## Sommaire

1. [Introduction et vision](#1-introduction-et-vision)
2. [Perimetre et sources de donnees](#2-perimetre-et-sources-de-donnees)
3. [Architecture des pages](#3-architecture-des-pages)
4. [Methodologie de calcul et formules](#4-methodologie-de-calcul-et-formules)
5. [Guide d'utilisation generale](#5-guide-dutilisation-generale)
6. [Guide d'exploitation](#6-guide-dexploitation)
7. [Annexes fonctionnelles](#7-annexes-fonctionnelles)

\newpage

# 1. Introduction et vision

Le systeme **PADESCE** centralise le suivi des formations, les campagnes d'appels, les enquetes de satisfaction et la production de rapports d'exploitation. Sa finalite n'est pas seulement de compter des appels ou d'afficher des tableaux : il sert a **piloter la qualite reelle du dispositif de formation**, a **mesurer la couverture analytique** et a **orienter les actions correctives**.

## 1.1 Pourquoi ce systeme existe

Le systeme repond a quatre besoins metier majeurs :

- **Suivre l'execution operationnelle** des appels apprenants, formateurs et CGA.
- **Qualifier la fiabilite des analyses** en n'integrant que les reponses conformes aux regles de seuil et d'eligibilite.
- **Comparer les performances** par classe, prestation, prestataire, beneficiaire, ville, cohorte, fenetre et utilisateur.
- **Industrialiser le reporting** via des exports Word, Excel, CSV et un envoi journalier automatise.

## 1.2 Valeur ajoutee des analyses

La valeur ajoutee du dispositif repose sur trois principes :

- **Une vision unifiee** : les donnees d'appels, de questionnaires et de referentiels reseau sont rapprochees dans une meme interface.
- **Une logique de seuil** : une classe n'entre dans l'analyse que lorsqu'un volume minimal de retours est atteint, ce qui limite les lectures trompeuses.
- **Une logique d'action** : les pages "General", "Apprenants Manquants", "Consolidation" et "Rapport" servent directement a corriger les ecarts, completer les chargements et diffuser le resultat final.

## 1.3 Objectifs metier

Le systeme poursuit notamment les objectifs suivants :

- **Mesurer la satisfaction apprenants** sur 9 dimensions normalisees.
- **Mesurer la satisfaction formateurs** sur 3 dimensions quantitatives et 3 zones textuelles.
- **Suivre la progression d'appel** par source, par utilisateur et par segment de population.
- **Identifier les anomalies de qualite de donnees** : sans numero, faux nom, doublons, pas forme, exclusions manuelles.
- **Produire un rapport journalier exploitable** pour la coordination, le management et la diffusion mail.

> **Note importante**
>
> Les analyses visibles ne correspondent pas systematiquement a la totalite des enregistrements presents en base. Elles appliquent des **regles d'eligibilite**, des **filtres de fenetre** et, pour PADESCE, un **seuil analytique de 25 % par classe**.

\newpage

# 2. Perimetre et sources de donnees

## 2.1 Referentiels et tables principales

Les indicateurs sont alimentes principalement par les objets suivants :

- **`Appel`** : appels PADESCE apprenants.
- **`AppelAnswers`** : reponses Q1 a Q9 des appels apprenants.
- **`SatisfactionApprenant`** : enquete apprenant reliee a un appel.
- **`AppelFormateur`** : appels et reponses formateurs.
- **`SatisfactionFormateur`** : donnees d'enquete formateur.
- **`AppelCGA`** : appels du perimetre CGA.
- **`Classe`**, **`Prestation`**, **`Formation`**, **`Lieu`**, **`Formateur`** : referentiels pedagogiques.
- **`UserActivity`** : activite utilisateur exploitee dans le rapport d'application.
- **`Alarm`** et **`logs/app.log`** : incidents et traces utilises dans le reporting journalier si disponibles.

## 2.2 Sources Excel reseau

Le systeme exploite deux sources reseau principales :

- **`main`** : fichier consolide principal.
- **`cutoff`** : fichier consolide CutOff.

Le connecteur recherche le fichier selon l'ordre suivant :

1. **Chemin force par variable d'environnement**.
2. **Partage reseau**.
3. **Copie cachee locale**.
4. **Copie de secours embarquee** dans le projet.

Les feuilles pivots exploitees par les analyses sont :

- **`Apprenants`**
- **`Classes`**
- **`Prestations`**

Feuilles optionnelles :

- **`Inspecteurs`**
- **`ListesDV`**
- **`PATH Presence`**

La page de consolidation exploite en plus la feuille :

- **`Consolidation`**

## 2.3 Distinction entre source operationnelle et source analytique

Le systeme distingue :

- **La production d'appels** : pages d'appels et de saisie.
- **Le referentiel reseau** : structure theorique des apprenants, classes et prestations.
- **L'analyse** : sous-ensemble des donnees ayant satisfait les regles de prise en compte.

Cette distinction est essentielle : un appel peut exister en base sans etre **retenu dans les analyses**.

\newpage

# 3. Architecture des pages

## 3.1 Dashboard global - `/dashboard/`

### Role

Page de pilotage transversal. Elle donne une vue immediate de l'activite globale PADESCE, CGA et Formateurs, ainsi qu'un acces rapide aux espaces d'analyse.

### KPI affiches

- **Progression calendrier** de la campagne entre le **26/09/2025** et le **26/08/2026**.
- **Nombre total de classes**, **apprenants**, **presences**, **satisfactions apprenants**, **satisfactions formateurs**, **enquetes environnement**.
- **Nombre d'appels termines**.
- Pour **PADESCE**, **CGA** et **Formateurs** :
  - total d'enregistrements actifs ;
  - nombre d'appels effectues.
- Pour PADESCE sur les **24 dernieres heures** :
  - appels termines ;
  - repartition par utilisateur ;
  - repartition par classe/prestation ;
  - repartition par prestation.
- Classements par **prestataire**, **prestation**, **utilisateur** et **fenetre**.
- Classements equivalents pour **Formateurs** et **CGA**.

### Origine des donnees

- **`Appel`** pour PADESCE.
- **`AppelFormateur`** pour les appels formateurs.
- **`AppelCGA`** pour le bloc CGA.
- **`Classe`**, **`Apprenant`**, **`Presence`**, **`SatisfactionApprenant`**, **`SatisfactionFormateur`**, **`EnqueteEnvironnement`** pour les compteurs de volumetrie.

## 3.2 Enquête de satisfaction (Consultant) - `/consultant/`

### Role

Vue d'analyse qualitative des appels apprenants PADESCE. Elle sert a prioriser les dossiers disposant d'un **audio exploitable**, d'un **questionnaire complet** et relevant du **bon perimetre analytique**.

### KPI affiches

- **Prestations analysees**
- **Classes analysees**
- **Prestataires**
- **Beneficiaires**
- **Apprenants analyses**
- **Nombre d'audios**
- **Appels tentes**
- **Appels reussis**
- **Formulaires remplis**
- **Formulaires avec audio**
- **Audios enregistres**

### Origine des donnees

- **`Appel`**
- **`AppelAnswers`**
- **`SatisfactionApprenant`**
- Donnees de **classe / prestation / prestataire / beneficiaire** depuis les relations Django.
- Snapshot analytique issu du dashboard de satisfaction apprenants lorsque disponible.

### Particularites

- Le dashboard ne conserve que les appels :
  - hors statut **`en_attente`** ;
  - en **fenetre 2 ou 3** ;
  - **eligibles a l'analyse**.
- Les audios de **plus d'une minute** et les formulaires complets sont remontes en priorite.

## 3.3 Analyse detaillee d'une classe - `/classe/<code>/`

### Role

Page de synthese analytique pour une **classe** donnee. Elle rapproche les appels apprenants, les retours formateurs et les informations du referentiel source.

### KPI affiches

- **Appels tentes**
- **Appels reussis**
- **Formulaires remplis**
- **Formulaires avec audio**
- **Audios enregistres**
- **Formateurs analyses / total formateurs**
- Chapeau de satisfaction avec **moyennes Q1 a Q9**
- Chapeau contrôle de présence avec **Taux global**, **Participation** et **Personnes formees**

### Origine des donnees

- **`Appel`**
- **`AppelAnswers`**
- **`SatisfactionApprenant`**
- **`AppelFormateur`**
- **Source reseau** pour completer l'identification de la classe et le contexte formation

## 3.4 Analyse detaillee d'une prestation - `/prestation/<code>/`

### Role

Vue analytique consolidee a l'echelle d'une **prestation**. Elle sert a piloter la prestation entiere et a naviguer vers les classes qui la composent.

### KPI affiches

- **Appels tentes**
- **Appels reussis**
- **Formulaires remplis**
- **Formulaires avec audio**
- **Audios enregistres**
- **Classes liees**
- Donnees de synthese apprenants et formateurs

### Origine des donnees

- **`Appel`**
- **`AppelFormateur`**
- **`Classe`**
- **Referentiel reseau PADESCE**

## 3.5 Dashboard satisfaction apprenants - `/satisfaction-apprenants/analyse/`

### Role

C'est la page analytique principale du dispositif apprenants. Elle calcule les moyennes de satisfaction et les regroupements multi-axes sur le **perimetre retenu dans l'analyse**.

### KPI affiches

- **Appels tentes**
- **Appels reussis**
- **Formulaires remplis**
- **Formulaires avec audio**
- **Audios enregistres**
- **Nombre total de reponses analytiques**
- **Classes analysees**
- **Prestations analysees**
- **Prestataires analyses**
- **Beneficiaires analyses**
- **Cohortes analysees**
- **Fenetres analysees**
- **Nombre d'audios**
- **Indicateurs de présence** (Chapeau) : Taux global, Participation, Personnes formees
- Moyennes globales et par **classe**, **prestation**, **fenetre**, **ville**, **utilisateur**, **cohorte**, **prestataire**, **beneficiaire**

### Origine des donnees

- **`Appel`**
- **`AppelAnswers`**
- **`SatisfactionApprenant`**
- **Source Excel reseau** `main` ou `cutoff`

### Particularites

- Seules les **fenetres 2 et 3** sont eligibles.
- Une classe n'est visible sans filtre manuel que si son **seuil de 25 %** est atteint.
- Les apprenants sans numero exploitable, non formes ou exclus manuellement sont sortis du perimetre d'analyse.

## 3.6 Vue generale apprenants - `/satisfaction-apprenants/analyse/general/`

### Role

Vue de diagnostic exhaustive des apprenants PADESCE. Elle permet de comprendre **pourquoi** un dossier est ou non retenu dans les analyses.

### KPI affiches

- **Apprenants visibles**
- **Pris en compte**
- **Sans numero**
- **3 partout**
- **Masques**

### Origine des donnees

- **`Appel`**
- **`AppelAnswers`**
- **`SatisfactionApprenant`**
- **Source reseau** pour le contexte apprenant/classe/prestation

### Particularites

- Affiche le **statut d'analyse**, les **motifs d'exclusion**, les **commentaires**, les **recommandations** et les informations de reponse.
- Permet les actions de **masquage** et de **reintegration**.

## 3.7 Apprenants manquants - `/satisfaction-apprenants/analyse/apprenants-manquants/`

### Role

Page de rattrapage data. Elle identifie les prestations non encore qualifiees analytiquement et distingue les apprenants :

- a **importer** ;
- deja charges mais **sans telephone** ;
- sans action possible.

### KPI affiches

- **Total importable**
- **Total deja charge**
- **Total a synchroniser**
- **Total prestations manquantes**

### Origine des donnees

- **Feuille `Consolidation`**
- **Source reseau PADESCE**
- **`Appel`** deja presents en base

### Particularites

- Propose des actions de **synchronisation des telephones** et d'**import en lot**.

## 3.8 Dashboard satisfaction formateurs - `/satisfaction-formateurs/dashboard`

### Role

Vue analytique dediee a la satisfaction des formateurs.

### KPI affiches

- **Nombre total de fiches**
- **Nombre de questionnaires termines**
- **Nombre de fiches avec notes**
- Moyennes des 3 dimensions quantitatives :
  - **Prerequis apprenants**
  - **Interaction apprenants**
  - **Competences acquises**
- Ventilation par **prestataire**, **beneficiaire**, **cohorte** et **statut**

### Origine des donnees

- **`SatisfactionFormateur`**
- **`AppelFormateur`**
- **`Classe`**
- **`Formateur`**

## 3.9 Rapport d'application - `/reporting/rapport/`

### Role

Vue de production du **rapport journalier** de l'application. Elle consolide l'activite d'appel, l'activite utilisateur, les incidents, les anomalies et la couverture d'analyse.

### KPI affiches

- **Utilisateurs ayant appele**
- **Appels termines**
- **Classes analysees**
- **Prestataires analyses**
- **Heure la plus performante**
- Bloc **Appels** par source
- Bloc **Utilisateurs**
- Bloc **Analyse satisfaction**
- Bloc **Anomalie classe**
- Bloc **Bugs et incidents**
- Bloc **Appels par heure**
- Bloc **Diffusion mail**

### Origine des donnees

- **`Appel`**
- **`AppelFormateur`**
- **`UserActivity`**
- **`Classe`**
- **Logs applicatifs**
- **Alarmes**
- Resume analytique issu du dashboard de satisfaction apprenants

### Particularites

- Exports disponibles : **Word**, **Excel**, **CSV**.
- Peut etre diffuse par email lorsque la configuration SMTP est prete.

## 3.10 Consolidation - `/reporting/consolidation/`

### Role

Guichet technique d'analyse et d'integration du **fichier consolide**. Il sert a verifier la structure du fichier, visualiser les lignes et enregistrer la version de reference en base.

### KPI et informations affiches

- Apercu des **en-tetes mappes / manquants / supplementaires**
- **Previsualisation** des lignes
- **Apprenants** systeme
- **Appels termines**
- **Classement des prestataires**

### Origine des donnees

- Fichier Excel charge par l'utilisateur
- Table de **consolidation**
- **`Appel`** et referentiels systeme

### Particularites

- L'action **Valider et enregistrer** remplace integralement la table de consolidation.

> **Avertissement d'exploitation**
>
> La validation du fichier de consolidation n'est pas un simple ajout incremental. Le processus reinitialise la table cible puis recharge la nouvelle version.

## 3.11 Excel reseau - `/reporting/excel-reseau/`

### Role

Console de consultation du fichier Excel reseau dans une interface web a onglets.

### KPI et informations affiches

- **Fichier source**
- **Feuilles detectees**
- **Lignes repertoriees**
- **Pagination**

### Origine des donnees

- Partage reseau
- Cache local
- Copie embarquee de secours

### Particularites

- Permet un **rafraichissement depuis le reseau**.
- Sert de point de controle pour verifier la source analytique active.

## 3.12 Pages sources de production

Les analyses s'appuient aussi sur des pages de production qui ne sont pas des dashboards de synthese, mais qui alimentent les KPI :

- **`/appels/`** : production d'appels PADESCE.
- **`/appels-formateurs/`** : production d'appels formateurs.
- **`/cga/`** : production d'appels CGA.

Ces pages portent les compteurs de progression operationnelle et conditionnent les statuts exploites ensuite dans les analyses.

\newpage

# 4. Methodologie de calcul et formules

## 4.1 Dictionnaire des statuts utilises dans les KPI

### Appels apprenants et rapport d'application

- **Appel tente** : tout appel dont le statut est different de **`en_attente`**.
- **Appel reussi** : statut appartenant a **`appel_reussi`**, **`formulaire_rempli`**, **`formulaire_avec_audio`**, **`termine`**.
- **Appel termine pour seuil analytique PADESCE** : statut appartenant a **`formulaire_rempli`**, **`formulaire_avec_audio`**, **`termine`**.
- **Formulaire rempli** : statut **`formulaire_rempli`** ou **`formulaire_avec_audio`**.
- **Formulaire avec audio** : statut **`formulaire_avec_audio`**.

### Appels formateurs

- **Appel reussi** : statut dans le meme ensemble de succes.
- **Appel termine pour seuil formateur** : statut **`formulaire_rempli`** ou **`formulaire_avec_audio`**.

## 4.2 Progression calendrier du dashboard global

Le dashboard global affiche une progression temporelle fixe entre deux dates de campagne.

$$
Progression\ calendrier = \frac{Jours\ ecoules}{Jours\ totaux} \times 100
$$

Avec :

- **date de debut** = 26/09/2025
- **date de fin** = 26/08/2026
- **jours ecoules** bornee entre 0 et la duree totale

Le compte a rebours est calcule par :

$$
Jours\ restants = \max(0,\ DateFin - DateDuJour)
$$

## 4.3 KPI de progression operationnelle des appels PADESCE

Ces KPI sont utilises dans les pages de production d'appels et dans certains compteurs de synthese.

### Formules

$$
Appels\ tentes = \#\{appel \mid statut \neq en\_attente\}
$$

$$
Appels\ reussis = \#\{appel \mid statut \in CALL\_SUCCESS\_STATUSES\}
$$

$$
Formulaires\ remplis = \#\{appel \mid statut \in \{formulaire\_rempli,\ formulaire\_avec\_audio\}\}
$$

$$
Formulaires\ avec\ audio = \#\{appel \mid statut = formulaire\_avec\_audio\}
$$

$$
Audios\ enregistres = \#\{appel \mid audio\_file\ non\ vide\}
$$

Pour le widget de progression des pages d'appels :

$$
Taux\ de\ completion\ operationnelle = \frac{Termines}{Total\ filtre} \times 100
$$

avec :

$$
Termines = \#\{appel \mid statut \in \{formulaire\_rempli,\ formulaire\_avec\_audio,\ termine\}\}
$$

### Conditions de calcul

- Le calcul se declenche a chaque chargement de la page apres application des filtres actifs.
- Le **denominateur** est le **total de lignes du queryset filtre**, pas le total theorique reseau.

## 4.4 Seuil analytique PADESCE a 25 %

Ce seuil gouverne la prise en compte d'une classe dans les analyses de satisfaction apprenants.

### Regle

Une classe devient analytique lorsque le nombre d'appels **termines pour analyse** atteint **25 %** du volume **appelable**.

### Formule du seuil

$$
Seuil\_{classe} = \max\left(1,\left\lceil N\_{appelables} \times 0.25 \right\rceil\right)
$$

Avec :

- **`N_appelables`** = nombre d'apprenants de la classe disposant d'un numero exploitable.
- La source de ce total provient prioritairement du **referentiel reseau** ; a defaut, le systeme peut recalculer localement sur les appels actifs de la classe.

### Formule d'atteinte

$$
Classe\ analysee \iff N\_{termines\ analyse} \ge Seuil\_{classe}
$$

ou :

$$
N\_{termines\ analyse} = \#\{appel \mid statut \in \{formulaire\_rempli,\ formulaire\_avec\_audio,\ termine\}\}
$$

### Conditions de calcul

- Applique aux dashboards de satisfaction apprenants.
- Le calcul est realise **par classe**.
- Sans filtre manuel, seules les classes ayant atteint le seuil remontent dans le dashboard analytique principal.

> **Note importante**
>
> Le seuil analytique PADESCE n'est pas identique au widget de progression des pages d'appels. Le premier s'appuie sur le **potentiel appelable** par classe, alors que le second s'appuie sur le **queryset courant**.

## 4.5 Seuil analytique formateurs a 50 %

Les vues de progression formateurs utilisent un seuil distinct a **50 %**.

### Formule

$$
Seuil\_{formateurs} = \max\left(1,\left\lfloor N\_{total} \times 0.50 \right\rfloor\right)
$$

avec :

- **`N_total`** = nombre total de lignes formateurs dans le perimetre filtre.

### Condition d'atteinte

$$
Seuil\ atteint \iff N\_{termines} \ge Seuil\_{formateurs}
$$

ou :

$$
N\_{termines} = \#\{appelFormateur \mid statut \in \{formulaire\_rempli,\ formulaire\_avec\_audio\}\}
$$

### Message d'avancement

- Si le seuil est atteint : message de validation.
- Sinon : calcul du **nombre d'appels restants** pour atteindre 50 %.

## 4.6 Regles d'eligibilite et d'exclusion des apprenants

Un apprenant n'est pris en compte dans les analyses que s'il respecte simultanement les regles suivantes.

### Eligibilite de base

$$
Eligible = \neg Exclu\_manuel \land Numero\_utilisable \land \neg Pas\_suivi\_formation
$$

Les motifs d'exclusion explicites sont :

- **Exclu manuellement**
- **Sans numero**
- **Pas suivi formation**

### Perimetre analytique consultant et apprenants

$$
Perimetre\ analyse = Fenetre \in \{2, 3\}
$$

### Formulaire complet apprenant

Un formulaire est considere complet si les **9 notes** sont renseignees :

$$
Formulaire\ complet \iff \forall i \in [1,9],\ q_i \neq \varnothing
$$

### Prise en compte finale dans les analyses apprenants

$$
Pris\ en\ compte = Formulaire\ complet \land Eligible \land Seuil\_{classe}\ atteint
$$

### Cas particulier "3 partout"

La vue **General** signale les dossiers ou toutes les notes valent 3 :

$$
Trois\ partout \iff \forall i \in [1,9],\ q_i = 3
$$

## 4.7 Calcul des moyennes de satisfaction apprenants

Le systeme calcule les moyennes par question sur le sous-ensemble de lignes retenues.

### Formule generale par question

$$
Moyenne(q_i) = \frac{\sum_{k=1}^{n} score_{k,i}}{n}
$$

ou :

- **`n`** = nombre de reponses non nulles pour la question **`q_i`**
- **`score_{k,i}`** = score de la reponse **`k`** a la question **`i`**

### Questions analysees

- **Q1** : clarte des exposes
- **Q2** : interaction avec le formateur
- **Q3** : maitrise du contenu
- **Q4** : salle adequate
- **Q5** : materiel disponible
- **Q6** : organisation du temps
- **Q7** : utilite de la formation
- **Q8** : adequation aux besoins
- **Q9** : satisfaction globale

### Groupements disponibles

Les moyennes sont calculees globalement puis par :

- **classe**
- **prestation**
- **fenetre**
- **ville**
- **utilisateur**
- **cohorte**
- **prestataire**
- **beneficiaire**

### Conditions de calcul

- Le calcul se declenche a l'ouverture de la page et a chaque modification des filtres.
- Les lignes sont construites a partir de **`AppelAnswers`** ou, en repli, depuis **`SatisfactionApprenant`**.
- Seules les lignes **retenues dans l'analyse** alimentent les moyennes du dashboard principal.

## 4.8 Chapeau analytique d'une classe

Le chapeau de classe affiche les moyennes Q1 a Q9 sur les questionnaires complets eligibles de la classe.

### Formule

$$
Chapeau\_{classe}(q_i) = \frac{\sum score(q_i)}{Nombre\ de\ repondants\ retenus}
$$

Le nombre de repondants est dededoublonne par identifiant source lorsque possible.

## 4.9 Qualification analytique d'une prestation

Une prestation est consideree comme analysee lorsque **toutes ses classes appelables** satisfont les regles de terminaison et de seuil.

### Formule logique

$$
Prestation\ qualifiee \iff \forall Classe_j \in Prestation,\ Classe_j\ terminee \land Classe_j\ au\ seuil
$$

Avec :

$$
Classe_j\ terminee \iff N\_{termines\ analyse,\ j} \ge Seuil\_{classe_j}
$$

Ainsi, une prestation peut exister dans le referentiel sans apparaitre comme **prestation analysee** tant qu'une de ses classes reste sous le seuil.

## 4.10 Indicateurs du dashboard consultant

Le dashboard consultant reutilise les regles d'eligibilite, mais ses KPI de cartes sont calcules sur un **snapshot analytique** ou, a defaut, sur les appels eligibles.

### Formules principales

$$
Appels\ tentes = \#\{appel \mid statut \neq en\_attente\}
$$

$$
Appels\ reussis = \#\{appel \mid statut \in CALL\_SUCCESS\_STATUSES\}
$$

$$
Formulaires\ remplis = \#\{appel \mid Q1..Q9\ tous\ renseignes\ \lor\ SatisfactionApprenant\ existante\}
$$

$$
Formulaires\ avec\ audio = \#\{appel \mid Formulaire\ rempli \land audio\ present\}
$$

$$
Priorite\ consultant = Audio\ present \land Formulaire\ complet \land DureeAudio \ge 60s
$$

### Conditions de calcul

- Fenetres **2** et **3** uniquement.
- Exclusion des apprenants non eligibles a l'analyse.
- Les compteurs sont produits sur les classes connues du snapshot analytique.

## 4.11 Resume du rapport journalier d'application

Le rapport consolide l'activite PADESCE et Formateurs sur une plage de dates.

### Fenetre temporelle

$$
DateHeure\ debut = DateDebut\ a\ 00:00:00
$$

$$
DateHeure\ fin = DateFin\ a\ 23:59:59
$$

### KPI d'appels par source

Pour chaque source :

$$
Effectues = Total - En\ attente
$$

$$
Taux\ de\ completion = \frac{Appels\ termines}{Appels\ effectues} \times 100
$$

avec :

- **Total** = nombre total de lignes sur la periode
- **Termines** = statuts de succes
- **En attente** = statut **`en_attente`**
- **En cours** = statuts de tentative
- **Callbacks** = statut **`a_rappeler`**

### Heure la plus performante

Le systeme compte les appels termines par heure locale et retient l'heure maximisant :

$$
(\,Appels\ termines,\ Appels\ totaux,\ -Heure\,)
$$

Autrement dit :

- priorite au **plus grand nombre d'appels termines** ;
- puis au **plus grand volume total** ;
- puis a l'**heure la plus precoce** en cas d'egalite.

### Activite utilisateur

Pour chaque utilisateur ayant appele :

$$
Temps\ estime = DerniereActivite - PremiereActivite
$$

Le rapport affiche aussi :

- nombre d'**utilisateurs totaux**
- nombre d'**utilisateurs actifs**
- nombre de **staff**
- nombre de **superusers**
- nombre d'utilisateurs vus sur **24 h**
- nombre d'utilisateurs vus sur la **periode**
- nombre d'utilisateurs ayant **effectivement appele**

## 4.12 Resume analytique dans le rapport journalier

Le rapport journalier reutilise prioritairement le moteur du dashboard apprenants pour afficher :

- **classes analysees**
- **prestations analysees**
- **prestataires analyses**
- **beneficiaires analyses**

Si ce moteur n'est pas disponible, il bascule vers un calcul de secours base sur les appels termines et la qualification des prestations.

## 4.13 Anomalies de qualite de donnees

Le rapport journalier suit trois familles d'anomalies sur les appels PADESCE :

- **Pas forme**
- **Faux nom**
- **Doublon de numero**

### Formules de comptage

$$
Doublons = \#\{appel \mid flag\_numero\_double = vrai\}
$$

$$
FauxNoms = \#\{appel \mid flag\_faux\_nom = vrai\}
$$

$$
PasForme = \#\{appel \mid flag\_pas\_forme = vrai\}
$$

Le rapport suit egalement :

$$
Classes\ non\ terminees = \#\{classe\ active \mid statut \neq termine\}
$$

## 4.14 Satisfaction formateurs dans le rapport

Le rapport journalier calcule la satisfaction formateurs sur les dossiers termines de la periode.

### Formules

$$
Avec\ notes = \#\{fiche \mid Q1 \neq \varnothing \land Q2 \neq \varnothing \land Q3 \neq \varnothing\}
$$

$$
Moyenne\ formateurs(Q_i) = \frac{\sum score_{k,i}}{n}
$$

Les agregats sont produits :

- globalement ;
- par **prestataire**.

## 4.15 Indicateurs de presence et de formation (Chapeau)

Ces indicateurs sont affiches dans le "Chapeau contrôle de présence" de l'espace public et des fiches classes.

### Taux global de presence

Moyenne arithmetique des taux de presence individuels calcules sur les 4 contrôles (C1 a C4).

$$
Taux\ Global\ Presence = \frac{\sum_{k=1}^{n} TauxIndividual_k}{n}
$$

### Taux de participation

Pourcentage d'apprenants ayant ete marques presents (PR) au moins une fois sur les 4 sessions de contrôle.

$$
Taux\ Participation = \frac{\#\{apprenant \mid \exists i \in [1,4], C_i = PR\}}{n} \times 100
$$

### Taux de personne forme

Pourcentage d'apprenants dont l'appel est considere comme un succes (contact etabli et formation confirmee).

$$
Taux\ Personne\ Forme = \frac{\#\{appel \mid statut \in CALL\_SUCCESS\_STATUSES\}}{n} \times 100
$$

\newpage

# 5. Guide d'utilisation generale

## 5.1 Naviguer dans le systeme

1. Ouvrir le **dashboard global** pour obtenir une vue d'ensemble.
2. Acceder au **dashboard de satisfaction apprenants** pour la lecture analytique principale.
3. Utiliser le **dashboard consultant** pour les revues qualitatives avec audio et questionnaires complets.
4. Ouvrir une **classe** ou une **prestation** pour le detail de synthese.
5. Utiliser la vue **General** pour comprendre les exclusions.
6. Utiliser **Apprenants Manquants** pour corriger les trous de chargement.
7. Finaliser par le **Rapport d'application** pour l'export et la diffusion.

## 5.2 Filtrer les donnees

Les dashboards proposent plusieurs filtres, selon le contexte :

- **source** : `main` ou `cutoff`
- **classe**
- **prestation**
- **prestataire**
- **beneficiaire**
- **cohorte**
- **fenetre**
- **ville**
- **utilisateur**
- **statut**

### Bonnes pratiques de filtrage

- Commencer par choisir la **bonne source reseau**.
- Appliquer ensuite un filtre de **prestation** ou de **classe**.
- Ajouter seulement apres les filtres d'analyse fine : **fenetre**, **ville**, **utilisateur**, **statut**.

> **Conseil de lecture**
>
> Si une prestation n'apparait pas dans les analyses, cela ne signifie pas necessairement une absence d'appels. Le cas le plus frequent est un **seuil de 25 % non atteint** sur au moins une classe de la prestation.

## 5.3 Interpreter les cartes KPI

- **Appels tentes** mesurent la mobilisation operationnelle.
- **Appels reussis** mesurent la qualite de traitement.
- **Formulaires remplis** mesurent la matiere exploitable pour l'analyse.
- **Formulaires avec audio** mesurent le niveau de traçabilite qualitative.
- **Audios enregistres** mesurent la couverture de preuve sonore.
- **Classes / prestations analysees** mesurent la maturite analytique reelle.

## 5.4 Interpreter les resultats analytiques

- Une **moyenne elevee** sur **Q9 Satisfaction globale** traduit une perception favorable d'ensemble.
- Un ecart fort entre **Q9** et les questions logistiques (**Q4 a Q6**) peut signaler un bon contenu mais une execution terrain insuffisante.
- Une prestation avec de bons scores mais **peu de classes au seuil** doit etre interpretee avec prudence.
- La vue **General** doit etre consultee en cas de doute sur le perimetre retenu.

## 5.5 Explorer un cas depuis un resultat global

1. Identifier une **prestation** ou une **classe** dans le dashboard apprenants.
2. Ouvrir la page detaillee correspondante.
3. Verifier les **appels tentes**, les **formulaires complets** et les **audios**.
4. Consulter les **commentaires** et **recommandations**.
5. Revenir a **General** si des dossiers semblent manquer.

\newpage

# 6. Guide d'exploitation

## 6.1 Mettre a jour les donnees source

### Source reseau

Le systeme peut lire :

- le fichier reseau principal ;
- le fichier reseau CutOff ;
- ou, si besoin, une copie cachee / embarquee.

Pour actualiser la lecture reseau :

1. Ouvrir **Excel reseau**.
2. Selectionner la bonne source.
3. Utiliser **Actualiser depuis le reseau**.
4. Verifier la date de modification et le contenu de la feuille active.

### Consolidation

Pour mettre a jour la consolidation interne :

1. Ouvrir **Consolidation**.
2. Charger le fichier Excel.
3. Verifier les colonnes mappees, manquantes et supplementaires.
4. Lancer l'analyse si besoin.
5. Cliquer sur **Valider et enregistrer** seulement apres controle.

## 6.2 Generer le rapport final

Deux modes sont disponibles :

- **Mode interface** : via `/reporting/rapport/`
- **Mode commande** : via la commande Django dediee

### Commande de generation / diffusion

```bash
python manage.py send_daily_app_report
```

Options usuelles :

```bash
python manage.py send_daily_app_report --dry-run
python manage.py send_daily_app_report --start 2026-04-01 --end 2026-04-09
```

### Exports disponibles

- **Word** (Rapport d'application et Evaluation des classes)
- **Excel**
- **CSV**

## 6.3 Diffusion automatique

Le projet contient un script d'installation de tache planifiee Windows pour l'envoi quotidien :

- **script** : `scripts/install_daily_report_task.ps1`
- **nom de tache** : `NAUMUR_Daily_App_Report`
- **horaire configure** : `17:30`

## 6.4 Prerequis de diffusion mail

La page de rapport verifie notamment :

- **`REPORT_EMAIL_TO`**
- **`EMAIL_HOST`**
- **`DEFAULT_FROM_EMAIL`**

Si le backend mail est encore en mode console, le systeme tente une bascule vers SMTP lorsque les parametres sont complets.

## 6.5 Gerer les prestations non analysees

Lorsqu'une prestation reste absente des analyses :

1. Ouvrir **Apprenants Manquants**.
2. Identifier si le blocage vient :
   - d'un **manque d'import** ;
   - d'un **telephone manquant** ;
   - d'un **seuil non atteint** ;
   - d'un autre motif.
3. Lancer la synchronisation des telephones ou l'import des apprenants manquants.
4. Revenir au dashboard analytique pour verifier l'effet.

## 6.6 Precautions administrateur

- Ne pas recharger une consolidation sans avoir controle la structure du fichier.
- Verifier la **source active** (`main` ou `cutoff`) avant toute lecture comparative.
- Interpretrer les KPI d'analyse en tenant compte des **regles d'exclusion** et des **seuils**.
- Verifier periodiquement les **destinataires mail** et la **sante des logs**.

\newpage

# 7. Annexes fonctionnelles

## 7.1 Questions de satisfaction apprenants

- **Q1** : clarte des exposes
- **Q2** : interaction avec le formateur
- **Q3** : maitrise du contenu
- **Q4** : salle adequate
- **Q5** : materiel disponible
- **Q6** : organisation du temps
- **Q7** : utilite de la formation
- **Q8** : adequation aux besoins
- **Q9** : satisfaction globale

## 7.2 Questions de satisfaction formateurs

### Questions quantitatives

- **Q1** : prerequis apprenants
- **Q2** : interaction apprenants
- **Q3** : competences acquises

### Zones textuelles

- **Q4** : gestion administrative
- **Q5** : gestion financiere
- **Q6** : communication

## 7.3 Motifs d'exclusion analytique apprenant

- **Exclu manuellement**
- **Sans numero**
- **Pas suivi formation**
- **Fenetre hors analyse**
- **Seuil 25 % non atteint**

## 7.4 Lecture rapide des sources par page

- **Dashboard global** : base applicative temps reel
- **Consultant** : base applicative + snapshot analytique apprenant
- **Classe / Prestation** : base applicative + source reseau
- **Satisfaction apprenants** : base applicative + source reseau `main` ou `cutoff`
- **General** : base applicative + source reseau
- **Apprenants Manquants** : consolidation + source reseau + base applicative
- **Satisfaction formateurs** : base applicative
- **Rapport d'application** : base applicative + activite utilisateur + logs + anomalies
- **Consolidation** : fichier utilisateur + table de consolidation
- **Excel reseau** : partage reseau / cache / fallback embarque

## 7.5 Recommandation de format PDF

Pour un export PDF propre, conserver :

- les niveaux de titres **H1 / H2 / H3**
- les blocs de note en **citation Markdown**
- les formules LaTeX en mode bloc `$$ ... $$`
- les sauts de page `\newpage` entre sections majeures
