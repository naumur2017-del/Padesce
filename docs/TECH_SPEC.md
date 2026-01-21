# Spécifications techniques PADESCE

## Modèle de données (vue synthétique)
- Référentiels : Formation, Prestation (avec Prestataire + Bénéficiaire, durées prévues/réelles, jalons contractuels), Lieu, Inspecteur, Formateur, Classe (statut, cohorte auto, code unique), Apprenant (contraintes unicité nom/classe et téléphone/formation, région/département/arrondissement, appartenance_beneficiaire), Contact.
- Enquêtes : Presence (PR/AB, code/papier, unique par classe-apprenant-date), SatisfactionApprenant (Q1–Q9 notes 1-5), SatisfactionFormateur (Q1–Q9 notes 1-5), EnqueteEnvironnement (booléens équipement/sécurité/commodités).
- Messaging : CampagneMessage (JSON d’envoi/rejet, enquêteur, datation).
- Audit : AuditLog (actor, model_name, object_pk, action created/updated/deleted, timestamp).

Indices/contraintes clés :
- Apprenant : unique (classe, nom_complet) ; unique (formation, telephone1) ; index sur (classe, formation).
- Presence : unique (classe, apprenant, date) ; index (classe, date).
- Satisfaction/Environnement : index sur classe.

## Sécurité / Configuration
- Auth Django + groupes créés par migration core 0002 (admin_systeme, inspecteur_enqueteur, prestataire_beneficiaire, consultation).
- Middleware `CurrentUserMiddleware` pour l’audit (audit des CRUD sur présences/satisfactions/environnement).
- Production : variables env (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`), HTTPS forcé si DEBUG=False (HSTS, SECURE_SSL_REDIRECT, cookies secure).
- Logs : fichiers `logs/app.log` et `logs/access.log` (créés après requêtes).
- Statics : `static/` (dev), `collectstatic` vers `staticfiles/`.

## Endpoints principaux (routes)
- Accueil : `/`
- Formations : `/formations/`
- Classes : `/formations/classes/`, création : `/formations/classes/nouveau/`, détail : `/formations/classes/<id>/`
- Apprenants : `/apprenants/`, import CSV : `/apprenants/import/<classe_id>/`, API codes : `/apprenants/api/codes/`
- Présences : `/presences/`, export CSV : `/presences/export/csv/`
- Satisfaction apprenants : `/satisfaction-apprenants/`, export CSV idem `/export/csv/`
- Satisfaction formateurs : `/satisfaction-formateurs/`, export CSV idem `/export/csv/`
- Environnement : `/environnement/`, export CSV idem `/export/csv/`
- Messaging : contacts `/messages/`, export CSV `/messages/export/csv/`, campagnes `/messages/campagnes/`
- Reporting : `/reporting/`, exports `/reporting/export/csv`, `/reporting/export/excel`

## Front / UX
- Templates Django + JS léger (preview CSV, pagination simple).
- Pages clés : accueil, formations, classes (listing/détail), création classe avec import CSV apprenants, enquêtes (présence/sat/appr/form/env), contacts/campagnes, reporting.

## Sauvegarde / restauration SQLite
- Scripts : `scripts/backup_sqlite.sh` / `.ps1`, `scripts/restore_sqlite.sh` / `.ps1`.
- Usage (bash) : `./scripts/backup_sqlite.sh db.sqlite3 backups` ; restauration : `./scripts/restore_sqlite.sh backups/db-<timestamp>.sqlite3 db.sqlite3`.
- Usage (PowerShell) : `.\scripts\backup_sqlite.ps1 -SourceDb db.sqlite3 -DestinationDir backups` ; restauration : `.\scripts\restore_sqlite.ps1 -BackupFile backups\db-<timestamp>.sqlite3 -TargetDb db.sqlite3`.

## Tests recommandés
- Santé : `python manage.py check`
- Migrations : `python manage.py migrate`
- Audit : créer/supprimer une présence puis `python manage.py shell -c "from App_PADESCE.core.models import AuditLog; print(AuditLog.objects.filter(model_name__icontains('presence')).order_by('-timestamp')[:1])"`
- Exports : appeler les endpoints CSV/XLS (présences, satisfactions, environnement, messages, reporting).
- Pagination : parcourir les listes paginées (présences, satisfactions, environnement, contacts).

## Déploiement / collecte statique
- Définir `.env` (copie de `.env.example`).
- `python manage.py collectstatic --noinput` (cible `staticfiles/`).
- Production : servir les fichiers statiques via le serveur web (nginx/whitenoise à configurer si besoin).
