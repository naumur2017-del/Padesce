# Guide utilisateur - Prestataire / Beneficiaire

## Acces
- Compte rattaché au groupe `prestataire_beneficiaire` (lecture privilégiée).
- Menus : Accueil `/`, Formations `/formations/`, Classes `/formations/classes/`, Reporting `/reporting/`, Messages `/messages/` (consultation/creation contact si autorisé).

## Taches principales
- Consulter les formations/classes qui vous concernent.
- Visualiser les enquetes (presence, satisfactions, environnement) liées à vos classes.
- Exporter les données (CSV/XLS) pour analyse.
- Gérer ou consulter les contacts liés à vos formations (si autorisé).

## Flows detaillees
1) Consulter formations et classes  
   - `/formations/` pour voir les formations et leurs statuts.  
   - `/formations/classes/` pour voir les classes (prestation, lieu, cohorte, fenetre).
2) Consulter les enquetes  
   - Présences : `/presences/` filtrer par classe.  
   - Satisfaction apprenants : `/satisfaction-apprenants/` filtrer par classe.  
   - Satisfaction formateurs : `/satisfaction-formateurs/` filtrer par classe.  
   - Environnement : `/environnement/` filtrer par classe.
3) Exports  
   - Chaque page d’enquete possède un export CSV.  
   - Reporting : `/reporting/` pour export CSV/XLS global.
4) Contacts (option)  
   - `/messages/` : filtrer prestataire/ville/fenetre, ajouter un contact si habilitation, exporter CSV.

## Controles / tests rapides
- Verifier que les classes affichées correspondent à vos prestations.  
- Télécharger un CSV (presence ou satisfaction) et ouvrir dans Excel.  
- Consulter le reporting et valider les compteurs/exports.  
- Si droits accordés, tester l’ajout d’un contact sur `/messages/` et vérifier sa présence dans la liste.
