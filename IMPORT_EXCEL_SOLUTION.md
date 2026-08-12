# Solution Import Excel - Padesce Call App

## Problème Identifié

### Erreur Initiale
```
Impossible de lire le fichier : Colonnes requises manquantes : Code. 
Colonnes trouvées dans le fichier : N° / No, Nom et prénom / Name & First Name, ...
```

### Causes
1. **Colonnes bilingues non reconnues** : Le fichier source utilise un format "Label Français / Label Anglais" (ex: "N° / No", "Nom et prénom / Name & First Name")
2. **Codes invalides** : Lors des premiers tests, les codes (1, 2, 3...) correspondaient à des appels existants mais n'étaient pas affichés
3. **Exigence stricte du code** : Le système Django requiert absolument une colonne "Code" valide pour chaque ligne

## Modifications Apportées

### 1. Fichier views.py - Reconnaissance des colonnes bilingues

**Ajout des variantes multilingues pour les clés de colonne :**

```python
_NOM_KEYS = [
    "nom et prenom / name & first name",  # NOUVEAU - Format bilingue
    "nom et prénom / name & first name",  # NOUVEAU
    "nom et prenom 0 name & first name",
    "nom et prénom 0 name & first name",
    "nom et prenom",
    "nom et prénom",
    "nom complet",
    "nom",
]

_CODE_KEYS = ["code", "apprenant id", "n / no", "no"]  # NOUVEAU : "n / no"
```

**Amélioration des autres colonnes :**

```python
prestataire = get(row, "prestataire / training provider", "prestataire")
beneficiaire = get(row, "beneficiaires / beneficiary", "bénéficiaires / beneficiary", ...)
fenetre = get(row, "fenêtre / window", "fenetre", "window")
```

### 2. Génération des Codes Uniques

**Format utilisé :** `APP####` (ex: APP0001, APP0002, APP0031)

**Logique :**
- Le système génère automatiquement des codes séquentiels
- Chaque import génère des codes uniques qui n'existent pas encore
- Permet d'éviter les conflits avec les appels existants

## Fichier test_import.xlsx - Structure

| Code  | N° / No | Nom et prénom / Name & First Name | ... | 
|-------|---------|----------------------------------|-----|
| APP0001 | 1 | AHMADOU BABBA | ... |
| APP0002 | 2 | ISMAIL A | ... |
| ... | ... | ... | ... |

**Caractéristiques :**
- 26 colonnes au total
- 30 lignes de données réelles
- Codes générés automatiquement (APP0001-APP0031)
- Format Excel (.xlsx) compatible

## Instructions d'Importation

1. **Accéder à :** `https://call.naumur.com/appels/`
2. **Sélectionner :** `Importer un fichier Excel (.xlsx/.xlsm)`
3. **Charger :** `test_import.xlsx`
4. **Mode :** Choisir "Ajouter/combiner" (append) ou "Remplacer" (replace)
5. **Importer :** Cliquer sur "Importer"

## Résultat Attendu

```
Fichier importe. 30 nouveau(x) appel(s), 0 appel(s) mis à jour.
Affichage remplacé. 0 doublon(s) désactivé(s).
```

Les 30 appels apparaîtront dans les tables avec :
- Code : APP0001 à APP0031
- Nom : Données réelles du fichier source
- Prestataire : IFP 2ITP, etc.
- Et autres informations du fichier source

## Fichiers Générés

- **test_import.xlsx** : Fichier Excel prêt à l'importation avec codes uniques
- **IMPORT_EXCEL_SOLUTION.md** : Ce document (backup de la solution)

## Notes Techniques

### Normalisation des En-têtes

La fonction `_normalize_header()` transforme :
- "N° / No" → "n / no"
- "Nom et prénom / Name & First Name" → "nom et prenom / name & first name"
- "Fenêtre / Window" → "fenetre / window"

Cela permet une correspondance flexible des colonnes indépendamment de la casse et des accents.

### Support Multilingue

Le système supporte maintenant :
- Colonnes en français uniquement
- Colonnes en anglais uniquement  
- Colonnes bilingues (Français / English)
- Variantes avec "/" ou "0" comme séparateur

## Problèmes Évités

✅ Colonnes bilingues non reconnues  
✅ Codes numériques simples en conflit avec appels existants  
✅ Lignes ignorées par manque de colonne "Code"  
✅ Données non affichées après importation  

---

**Dernière mise à jour:** 2026-08-12  
**Fichier:** `test_import.xlsx` (30 appels, codes APP0001-APP0031)
