# Utilitaires PADESCE

Ce dossier contient les scripts utilitaires organisés par catégorie pour la maintenance et le développement du projet PADESCE.

## 📁 Structure des dossiers

### 🗄️ database_fixes/
Scripts **critiques** pour la récupération et la maintenance de la base de données.
- **fix_*.py** : Scripts de réparation DB
- **ATTENTION** : Modifient directement les données
- **Usage** : Uniquement en cas de problèmes critiques

### 🔍 diagnostics/
Scripts **utiles** pour le diagnostic et l'analyse des données.
- **check_*.py** : Scripts de vérification
- **test_*.py** : Tests de logique métier
- **Usage** : Read-only, debugging, validation

### 🌐 external_tests/
Scripts qui dépendent de **serveurs externes**.
- **test_formateur_stats.py** : Test HTTP externe
- **Dépendances** : Serveurs externes, internet
- **Usage** : Validation d'intégrations externes

## 🚨 Instructions générales

### Avant d'exécuter un script
1. **Vérifier la catégorie** : database_fixes = ⚠️ danger, diagnostics = ✅ safe
2. **Lire le README** spécifique au dossier
3. **Faire un backup** pour les scripts database_fixes
4. **Configurer l'environnement** Django si nécessaire

### Exécution
```bash
# Scripts database_fixes (avec prudence)
cd utils/database_fixes
python fix_migrations.py

# Scripts diagnostics (safe)
cd utils/diagnostics  
python check_prestation_names.py

# Scripts external_tests (dépendances externes)
cd utils/external_tests
python test_formateur_stats.py
```

## 📋 Maintenance

- **Documentation** : Maintenir les README à jour
- **Tests** : Vérifier régulièrement que les scripts fonctionnent
- **Nettoyage** : Supprimer les scripts obsolètes
- **Organisation** : Ajouter de nouveaux scripts dans les bons dossiers

## 🔗 Liens utiles

- [Documentation principale](../docs/)
- [Guide d'installation](../docs/Guide_Installation_Configuration.md)
- [Audit DevOps](../AUDIT_DEVOPS_COMPLET.md)
