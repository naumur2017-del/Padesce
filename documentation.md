# Documentation d'utilisation PADESCE (Django)

## Acces et roles
- Acces prive par defaut : page de login sur `/`. Groupes : admin systeme, inspecteur/enqueteur, prestataire/beneficiaire, consultation.
- Portail public beneficiaire : `/beneficiaire/` (upload CSV/Excel, verification doublons/qualification/genre, preview + enregistrement des erreurs).
- Toujours utiliser un compte ayant le role attendu pour chaque module (enquetes, reporting, messaging).

## Navigation principale
- Tableau de bord : `/dashboard/` (boutons Classe / Donnee traitee / Formation / Export global).
- Formations (End) : `/formations/` liste des prestations avec objectifs (effectif/femmes) et leurs classes; bouton ON/OFF par classe bascule le statut en cours/termine. Une prestation est consideree terminee si toutes ses classes sont terminees et l’effectif atteint.
- Liste des classes : `/formations/classes/` (cartes cliquables). Creation classe : `/formations/classes/nouveau/`.
- Detail classe : `/formations/classes/<id>/` (entete classe/prestation/lieu/cohorte, tableau apprenants, actions SMS, import, liens vers enquetes Presence/Satisfaction/Environnement, bouton “Rapports enquetes”).

## Gestion des apprenants
- Import CSV apres creation de classe : redirection vers `/apprenants/import/<classe_id>/` avec previsualisation, controle unicite, generation codes APP###.
- Edition appartenance beneficiaire via cases a cocher dans la classe. Suppression et envoi SMS en masse via boutons du tableau.

## Module Presence
- Saisie et listing : `/presences/`. Filtre par classe, formulaire PR/AB (code/papier), export CSV, audit actif.
- Module d’appel (seuil de presence) : `/presences/appels/`. Curseur de seuil (%), liste des apprenants de classes terminees sous le seuil, boutons Enregistrer (audio local navigateur) et Play/Pause.

## Modules Satisfaction
- Satisfaction apprenants : `/satisfaction-apprenants/` (formulaire Q1-Q9 note 1-5, commentaires/recommandations, export CSV, audit).
- Satisfaction formateurs : `/satisfaction-formateurs/` (questions Q1-Q9 dont Q9 satisfaction prestataire, commentaires, export CSV, audit).
- Identification rapide : saisie code ou telephone pour pre-remplir, upload audio d’appel si besoin, lecture des reponses IA non modifiables.

## Module Environnement
- Saisie/listing : `/environnement/`. Arrivee directe depuis une classe via le bouton correspondant avec classe/lieu preselectionnes. Booleens equipements/securite/commodites + commentaires, export CSV, audit.

## Rapports d’enquetes par classe
- Depuis une classe, bouton “Rapports enquetes” (`/formations/classes/<id>/rapports/`) montrant :
  - Presence : cartes par date (total/presents/absents) cliquables vers `/formations/classes/<id>/rapports/presences/<date>/` affichant apprenants presents/absents + totaux (actifs/presents/absents).
  - Satisfaction apprenants : liste antichronologique (inspecteur/enqueteur, Q9 globale).
  - Satisfaction formateurs : liste antichronologique (inspecteur/enqueteur, Q9 globale prestataire).
  - Environnement : liste antichronologique avec commentaire global.

## Messaging
- Contacts et filtres (prestataire/classe/ville/fenetre/type formation), export CSV. Campagnes : creation, historique (date/texte/cible/nombre/echecs) via `/messages/` et `/messages/campagnes/`.

## Reporting / TDB PADESCE
- `/reporting/` : compteurs classes/apprenants/formateurs/enquetes, taux presence, moyennes satisfaction, etat environnement, ~40 graphes. Exports CSV/XLS, boutons CSV/image, iframes tables/graphes.

## Operations techniques
- Installation deps : `pip install -r requirements.txt` (Python 3).
- Variables `.env` (exemple `.env.example`). Base SQLite par defaut (`db.sqlite3`).
- Commandes utiles : `python manage.py migrate`, `python manage.py createsuperuser`, `python manage.py runserver`.
- Sauvegarde/restauration SQLite : `scripts/backup_sqlite.ps1|sh` et `scripts/restore_sqlite.ps1|sh <backup>`.
- Collectstatic / logs : verifier `logs/` pour `app.log` et `access.log`.
- Deploiement : `DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=... python manage.py check --deploy` pour valider securite.

## Exports / imports
- Exports CSV : Presence, Satisfaction apprenants/formateurs, Environnement, Messaging (contacts/campagnes), Reporting (CSV/XLS simples).
- Imports CSV : referentiels via admin; apprenants via CreateClass -> import.

## Rappels de conformite et audit
- Groupes/permissions configures (admin systeme, inspecteur/enqueteur, prestataire/beneficiaire, consultation).
- Audit actif sur presences et enquetes; logs d’acces serveur. Toujours operer avec un compte authentifie hors portail public.

## Parcours recommande (inspecteur/enqueteur)
1) Se connecter puis ouvrir `/dashboard`.
2) Aller sur `/formations/` puis entrer dans une classe via `/formations/classes/` ou cartes.
3) Importer/gerer les apprenants; envoyer SMS si besoin.
4) Saisir presences `/presences/`, satisfactions `/satisfaction-apprenants/` et `/satisfaction-formateurs/`, environnement `/environnement/`.
5) Consulter les rapports par classe via “Rapports enquetes”.
6) Suivre les indicateurs globaux sur `/reporting/`.
