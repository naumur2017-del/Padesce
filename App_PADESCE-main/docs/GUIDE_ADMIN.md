# Guide utilisateur - Admin systeme

## Acces
- Connexion (compte admin) puis navigation barre haute : Accueil `/`, Formations `/formations/`, Classes `/formations/classes/`, Reporting `/reporting/`, Messages `/messages/`.

## Taches principales
- Gestion utilisateurs/roles : attribuer les groupes (`admin_systeme`, `inspecteur_enqueteur`, `prestataire_beneficiaire`, `consultation`) via l’admin Django.
- Referentiels : creer/modifier/désactiver Formations, Prestataires, Beneficiaires, Prestations, Lieux, Formateurs, Inspecteurs, Classes.
- Import apprenants par classe.
- Suivi/audit : consulter les journaux (admin AuditLog) et exports CSV.
- Sauvegarde/restauration SQLite.

## Flows detaillees
1) Creer une formation/prestation/lieu/formateur/inspecteur  
   - Admin Django ou formulaires (Formations `/formations/` -> admin pour creation).  
   - Prestations via admin (lier Prestataire + Formation + Beneficiaire).
2) Creer une classe  
   - `/formations/classes/nouveau/` : code CLA### auto, cohorte auto, choisir prestation -> formation auto.  
   - Completer fenetre/statut/lieu/formateur.  
   - Enregistrer pour creer la classe.
3) Importer les apprenants de la classe  
   - `/apprenants/import/<classe_id>/` : charger CSV (nom, genre, age, fonction, qualification, annees exp, ville, telephone).  
   - Verifier l’absence de doublons nom/tel, generer les codes puis valider.
4) Superviser les enquetes  
   - Presence : `/presences/` (filtrer par classe, saisir PR/AB, export CSV).  
   - Satisfaction apprenants : `/satisfaction-apprenants/` (Q1-Q9, export CSV).  
   - Satisfaction formateurs : `/satisfaction-formateurs/` (Q1-Q9, export CSV).  
   - Environnement : `/environnement/` (checkbox equipements/ securite/ commodites, export CSV).
5) Messaging  
   - Contacts : `/messages/` (filtres prestataire/ville/fenetre, creation contact, export CSV).  
   - Campagnes : `/messages/campagnes/` (enregistrer texte + cibles + envois/rejets JSON).
6) Reporting  
   - `/reporting/` : compteurs, top listes, exports CSV/XLS.
7) Sauvegarde/restauration SQLite  
   - Backup : `./scripts/backup_sqlite.sh db.sqlite3 backups` ou `.\scripts\backup_sqlite.ps1 -SourceDb db.sqlite3 -DestinationDir backups`.  
   - Restore : `./scripts/restore_sqlite.sh backups/db-<ts>.sqlite3 db.sqlite3` ou `.\scripts\restore_sqlite.ps1 -BackupFile backups\db-<ts>.sqlite3 -TargetDb db.sqlite3`.

## Controles / tests rapides
- `python manage.py check` ; `python manage.py migrate`.  
- Import CSV apprenants sur une classe test puis verifier codes generes.  
- Exporter CSV (presences/sat/env/messages/reporting) et ouvrir dans Excel.  
- Consulter admin AuditLog pour voir les traces apres une saisie/suppression.
