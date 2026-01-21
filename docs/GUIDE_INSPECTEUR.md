# Guide utilisateur - Inspecteur / Enqueteur

## Acces
- Connexion avec le groupe `inspecteur_enqueteur`.
- Menus principaux : Accueil `/`, Classes `/formations/classes/`, Presences `/presences/`, Satisfaction apprenants `/satisfaction-apprenants/`, Satisfaction formateurs `/satisfaction-formateurs/`, Environnement `/environnement/`, Reporting `/reporting/`.

## Taches quotidiennes
- Reperer la classe cible puis saisir les enquetes (presence, satisfactions, environnement).
- Consulter et exporter les enquetes saisies.
- Eventuellement enregistrer une campagne de messages (si autorisé).

## Flows detaillees
1) Identifier la classe  
   - `/formations/classes/` : cliquer sur la classe (voir code, prestation, fenetre, cohorte, lieu).
2) Saisie presence  
   - `/presences/` : choisir la classe, renseigner apprenant/inspecteur, date/horaires, PR/AB, moyen (Code ou Papier), remarques.  
   - Enregistrer ; verifier dans la liste et exporter CSV si besoin.
3) Satisfaction apprenants  
   - `/satisfaction-apprenants/` : choisir classe/apprenant, date/heure, notes Q1-Q9 (1-5), commentaire/recommandations ; enregistrer puis voir dans la liste.  
   - Export CSV disponible.
4) Satisfaction formateurs  
   - `/satisfaction-formateurs/` : choisir classe/formateur, date/heure, notes Q1-Q9 (1-5), commentaires/recommandations ; enregistrer.  
   - Export CSV disponible.
5) Enquete environnement  
   - `/environnement/` : choisir classe, inspecteur, date/heure, cocher les equipements/commodites/securite, ajouter commentaires ; enregistrer puis voir dans la liste.  
   - Export CSV disponible.
6) Reporting  
   - `/reporting/` : consulter les compteurs et top listes, exporter CSV/XLS.
7) Messages (si autorisé)  
   - Contacts : `/messages/` (filtrer prestataire/ville/fenetre, ajouter un contact, export CSV).  
   - Campagnes : `/messages/campagnes/` (enregistrer texte + cible + envois/rejets JSON).

## Controles / tests rapides
- Verifier chaque saisie dans la liste correspondante et tester l’export CSV.  
- S’assurer que les notes sont bien entre 1 et 5 pour les satisfactions.  
- Consulter AuditLog (via un admin) en cas de besoin de traçabilité.  
- Télécharger les exports et ouvrir dans Excel pour valider les colonnes.
