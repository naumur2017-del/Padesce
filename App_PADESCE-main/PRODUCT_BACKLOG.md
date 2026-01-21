# Product Backlog – Application PADESCE

## Base technique & sécurité
- Config env/prod séparées (DEBUG off, ALLOWED_HOSTS, SECURE_SSL_REDIRECT, HSTS), gestion secrets (.env), collectstatic, logs.
- Auth & rôles : groupes (admin système, inspecteur, prestataire, consultation) avec permissions par modèle et par vue.
- Audit : journal des créations/mises à jour/suppressions d’enquêtes et présences ; logs d’accès serveur.
- Sauvegarde/restauration SQLite (script, planification, doc).

## Référentiels
- CRUD + filtres/export : Formations, Prestataires, Bénéficiaires, Lieux, Formateurs, Inspecteurs.
- Génération codes (FORMA###, INS###, PREST###, LIEU###, BEN###).
- Import CSV/Excel des référentiels (prestataires, lieux, formateurs) avec validations.

## Formations / Classes
- Liste formations avec statuts modifiables (non démarré, en cours, terminé) et filtres (prestataire, fenêtre, région).
- Création classe : code CLA###, cohorte auto par prestation, auto-remplissage formation via prestation, lieu auto si connu, saisie géo.
- Page classe : bandeau infos (prestation, lieu, cohorte, fenêtre), KPIs (apprenants, enquêtes), actions contextuelles.
- Import apprenants CSV par classe : validation doublons noms/tél, génération codes APP###, mise à jour statut formation -> en cours, prévisualisation avant enregistrement.
- Suppression/édition apprenants avec confirmation, statuts SMS par apprenant.

## Apprenants
- Tableau apprenants filtrable (classe, prestataire, fenêtre, ville), sélection multiple, édition modale, suppression sécurisée.
- Export CSV/Excel apprenants (classe/prestataire/fenêtre).
- Contrainte unicité téléphone par formation (persistée).

## Module Présence
- Saisie par classe : sélection enqueteur/inspecteur, dates prévues, bouton “présent par code” + “présent par papier”, horodatage auto.
- Validation unicité présence par apprenant/jour, statut PR/AB, moyen C/P, remarques.
- Calculs taux de présence (séance, classe, prestataire, fenêtre) et graphiques TDB.
- Export CSV/Excel par filtres (classe, période, prestataire) ; désactivation actions si formation terminée.

## Satisfaction Apprenants
- Formulaire Q1–Q9 (1–5) + commentaires/recommandations ; option anonyme ou par apprenant identifié.
- Calcul moyennes par question/classe et score global par classe/prestataire/fenêtre.
- Tableau des enquêtes par classe ; export CSV/Excel.

## Satisfaction Formateurs
- Formulaire Q1–Q9 (1–5) par formateur/classe/prestataire + commentaires/recommandations.
- Calcul satisfaction moyenne formateur par classe/prestataire ; export CSV/Excel ; tableau des enquêtes.

## Environnement
- Formulaire booléens équipements/sécurité/commodités + commentaires ; inspecteur/enquêteur, date/heure.
- Scores optionnels (équipement/sécurité/confort) calculés depuis les booléens.
- Export CSV/Excel ; tableau des enquêtes.

## Messages (Contacts & campagnes)
- Référentiel contacts (issu de TEL) avec filtres (prestataire, classe, ville, fenêtre, type formation).
- Listes de diffusion et export CSV/Excel ; stockage campagnes (date, texte, cible, ids envoyés/rejetés, motif).
- Prévoir intégration API SMS/WhatsApp/email ultérieure (interface prête à brancher).

## Reporting / TDB
- Accueil : cartes stats (nb classes, nb enquêtes par type, nb apprenants), % avancement annuel.
- Données traitées : graphes TDB PADESCE (taux présence 40 graphes, moyennes satisfactions, état environnement).
- Exports agrégés CSV/Excel (taux présence, satisfactions, environnement par région/prestataire/fenêtre).
- Performance : pagination, index filtres, select_related/prefetch.

## UX/UI
- Layout responsive FR (toggle EN futur), navigation par modules, alertes/toasts pour feedbacks, états désactivés si formation terminée.
- Accessibilité de base (labels, focus, contrastes).

## Tests & CI
- Tests modèles (contraintes unicité, génération codes), vues import/présence/satisfactions/environnement, exports CSV/Excel.
- Tests permissions par rôle ; pipeline CI (lint, tests).

## Documentation
- Guide installation/configuration, .env.example, requirements, procédures backup/restore.
- Guides utilisateurs par rôle (admin, inspecteur, prestataire).
