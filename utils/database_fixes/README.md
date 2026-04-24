# Scripts de récupération base de données

Ce dossier contient des scripts **critiques** pour la récupération et la maintenance de la base de données PADESCE.

## 🚨 Scripts critiques

### fix_migrations.py
**Utilité** : Résout les problèmes de migration avec clés étrangères  
**Quand utiliser** : Erreurs de migration, conflits de clés étrangères  
**Fonctionnalités** : `disable_foreign_key_checks()`, réparation migrations  

### fix_missing_columns.py
**Utilité** : Crée les colonnes manquantes après fake migrations  
**Quand utiliser** : Colonnes manquantes dans apprenants_apprenant  
**Fonctionnalités** : Ajout colonnes c1-c4, validation schéma DB  

### fix_formateur_ids.py
**Utilité** : Corrige les formateurs avec IDs manquants/invalides  
**Quand utiliser** : Erreur TEL698065452, IDs formateurs corrompus  
**Fonctionnalités** : Suppression formateurs problématiques, réassignation IDs  

### fix_formateur_column.py
**Utilité** : Ajoute la colonne nom manquante dans formations_formateur  
**Quand utiliser** : Colonne nom manquante après migration  

### fix_formateur_ids_direct.py
**Utilité** : Correction directe des IDs de formateurs  
**Quand utiliser** : Alternative à fix_formateur_ids.py  

### fix_production_stats.py
**Utilité** : Correction des statistiques en production  
**Quand utiliser** : Stats incorrectes en environnement de production  

### fix_real_prestation_mapping.py
**Utilité** : Correction du mapping des prestations réelles  
**Quand utiliser** : Mapping prestations corrompu  

## ⚠️ Instructions d'utilisation

1. **Toujours faire un backup** avant d'exécuter ces scripts
2. **Tester en environnement de staging** avant la production
3. **Exécuter avec Python 3.13** : `python script_name.py`
4. **Vérifier les logs** pour les erreurs éventuelles

## 📋 Conditions préalables

- Django configuré avec `DJANGO_SETTINGS_MODULE`
- Accès à la base de données
- Permissions d'écriture sur les tables concernées

## 🚨 ATTENTION

Ces scripts modifient directement la base de données. Utilisez-les avec **extrême prudence** et **uniquement si nécessaire**.
