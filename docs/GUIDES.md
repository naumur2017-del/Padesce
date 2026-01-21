# Guides utilisateurs et technique

## Profils utilisateurs (parcours rapides)
- **Admin système** : crée les utilisateurs, affecte les groupes, gère les référentiels (formations, prestations, classes, apprenants, formateurs, inspecteurs, lieux). Accède à tout, y compris reporting et export.
- **Inspecteur/Enquêteur** : saisie des enquêtes (présence, satisfactions, environnement), consultation des classes, envoi de campagnes (si autorisé).
- **Prestataire/Bénéficiaire** : lecture sur ses formations/classes/enquêtes (selon droits), accès reporting.
- **Consultation** : lecture globale (reporting/tableaux de bord).

## Guide utilisateur (actions clés)
- Accueil `/` : consulter les compteurs + naviguer vers classes, données traitées, formations, export.
- Formations `/formations/` : voir les formations et statuts.
- Classes `/formations/classes/` : lister, puis créer via `/formations/classes/nouveau/` (code auto CLA###, cohorte auto). Dans la fiche classe, accéder aux enquêtes et gestion des apprenants.
- Import apprenants `/apprenants/import/<classe_id>/` : charger un CSV (colonnes : nom, genre, âge, fonction, qualification, années exp, ville, téléphone), vérifier doublons, génération de codes.
- Présences `/presences/` : saisir PR/AB (code ou papier), filtrer par classe, exporter CSV.
- Satisfactions `/satisfaction-apprenants/` et `/satisfaction-formateurs/` : saisir Q1–Q9, commentaires, exporter CSV.
- Environnement `/environnement/` : cocher les indicateurs, ajouter commentaires, exporter CSV.
- Messages `/messages/` : gérer contacts (filtres prestataire/ville/fenêtre, export CSV). `/messages/campagnes/` : enregistrer une campagne (texte, cible, envois/rejets en JSON).
- Reporting `/reporting/` : voir compteurs, top listes, exporter CSV/XLS.

## Guide technique
- Installation dev : `pip install -r requirements.txt` puis `python manage.py migrate` et `python manage.py runserver`.
- Variables d’environnement : configurer `.env` (voir `.env.example`) pour `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`.
- Sécurité prod : mettre `DJANGO_DEBUG=False`, définir `ALLOWED_HOSTS`, activer HTTPS (HSTS, cookies secure déjà gérés). Prévoir certificat côté reverse-proxy.
- Sauvegarde/restauration SQLite :  
  - Bash : `./scripts/backup_sqlite.sh db.sqlite3 backups` ; `./scripts/restore_sqlite.sh backups/db-<timestamp>.sqlite3 db.sqlite3`.  
  - PowerShell : `.\scripts\backup_sqlite.ps1 -SourceDb db.sqlite3 -DestinationDir backups` ; `.\scripts\restore_sqlite.ps1 -BackupFile backups\db-<timestamp>.sqlite3 -TargetDb db.sqlite3`.
- Collectstatic : `python manage.py collectstatic --noinput` (cible `staticfiles/`).
- Audit : middleware + signaux actifs ; consulter `logs/app.log` et `logs/access.log` après requêtes.

## Tests à exécuter
- Sanity : `python manage.py check`
- Migrations : `python manage.py migrate`
- Création données test : via admin ou formulaires (présence/satisfactions/environnement), vérifier `AuditLog`.
- Exports : télécharger les CSV/XLS des modules et vérifier ouverture.
- Pagination : vérifier navigation sur les pages listes (présences, satisfactions, environnement, contacts).
