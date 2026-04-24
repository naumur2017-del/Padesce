# Scripts de diagnostics

Ce dossier contient des scripts **utiles** pour le diagnostic et l'analyse des données PADESCE.

## 🔍 Scripts de diagnostic

### Scripts de vérification (check_*)
- **check_prestation_names.py** : Vérifie les vrais noms/titres des prestations avec jointures complexes
- **check_classes.py** : Compte et vérifie les classes CLA* dans la base de données
- **check_db.py** : Vérification simple de la base de données SQLite
- **check_db_simple.py** : Diagnostic DB simplifié
- **check_excel_columns.py** : Vérification des colonnes dans fichiers Excel
- **check_excel_sheets.py** : Analyse des feuilles Excel
- **check_local_db.py** : Diagnostic base de données locale
- **check_long_phone_numbers.py** : Vérification des numéros de téléphone
- **check_presta008.py** : Validation spécifique pour la prestation 008
- **check_prestation_structure.py** : Analyse structure des prestations

### Scripts de test et validation
- **test_new_logic.py** : Test la nouvelle logique de combinaison prestataire-bénéficiaire

## 📊 Utilisation

### Pour vérifier les prestations
```bash
python check_prestation_names.py
```

### Pour analyser les classes
```bash
python check_classes.py
```

### Pour tester la nouvelle logique métier
```bash
python test_new_logic.py
```

## 🎯 Cas d'usage

- **Debugging** : Identifier des anomalies dans les données
- **Validation** : Vérifier la cohérence des informations
- **Reporting** : Extraire des statistiques spécifiques
- **Development** : Tester de nouvelles fonctionnalités

## ⚠️ Notes

- Ces scripts sont **read-only** : ils ne modifient pas les données
- Utilisent Django ORM pour l'accès aux données
- Peuvent nécessiter des variables d'environnement configurées
