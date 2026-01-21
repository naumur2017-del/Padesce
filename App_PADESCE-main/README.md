# PADESCE - Suivi des formations et enquêtes

Prototype Django pour centraliser les présences, enquêtes (satisfaction apprenants/formateurs, environnement), gestion des contacts/campagnes et reporting.

## Installation rapide (dev)
1. Créer un environnement virtuel puis installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
2. Appliquer les migrations et lancer le serveur :
   ```bash
   python manage.py migrate
   python manage.py createsuperuser  # pour accéder à l'admin
   python manage.py runserver
   ```

## Applications
- `formations` : formations, prestataires, bénéficiaires, prestations, lieux, classes, formateurs, inspecteurs.
- `apprenants` : référentiel apprenants, import CSV (à implémenter), codes APP###, contraintes d'unicité.
- `presences` : saisie des présences (code/papier), calculs futurs.
- `satisfaction_apprenants` / `satisfaction_formateurs` : enquêtes Q1..Q9.
- `environnement` : enquêtes équipement/sécurité/commodités.
- `messaging` : contacts, campagnes (stockage JSON, pas d'envoi SMS pour l'instant).
- `reporting` : tableau de bord et exports (placeholder).

## Prochaines étapes
- Formulaires/vues en cours : creation classe (`/formations/classes/nouveau/`) avec code auto `CLA###` et cohorte auto par prestation ; import CSV apprenants par classe (`/apprenants/import/<classe_id>/`) avec validations de doublons et génération de codes `APP###`.
- A venir : workflows détaillés des enquêtes (présence, satisfactions, environnement), envoi SMS, graphes TDB PADESCE et exports CSV/Excel.
- Sécuriser les rôles via groupes Django et permissions par module.
