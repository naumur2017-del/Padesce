# Workflow Git pour Projet Django + Gandi

## Objectif
Protéger la branche `main` tout en permettant un développement agile et des déploiements sécurisés.

## Branches Structure

```
main                    # Production (protégée)
  |
  |-- feature/*        # Développement de nouvelles fonctionnalités
  |-- hotfix/*         # Corrections urgentes en production
  |-- release/*        # Préparation de déploiement
  |
  |-- develop          # Intégration continue (optionnel)
```

## Workflow Complet

### 1. Développement (Feature Branch)

```bash
# Créer une branche feature depuis main
git checkout main
git pull origin main
git checkout -b feature/NOM_FONCTIONNALITE

# Développer et committer
git add .
git commit -m "feat: Description de la fonctionnalité

- Implémentation de X
- Modification de Y
- Tests ajoutés

Closes #123"

# Pousser la branche
git push origin feature/NOM_FONCTIONNALITE
```

### 2. Review et Merge

```bash
# Après review et validation
git checkout main
git pull origin main
git merge feature/NOM_FONCTIONNALITE
git push origin main

# Supprimer la branche locale et distante
git branch -d feature/NOM_FONCTIONNALITE
git push origin --delete feature/NOM_FONCTIONNALITE
```

### 3. Hotfix (Urgence Production)

```bash
# Créer branche hotfix depuis main
git checkout main
git pull origin main
git checkout -b hotfix/CORRECTION_URGENTE

# Correction rapide
git add .
git commit -m "hotfix: Correction urgente de X

Fixe le problème Y en production"

# Merge direct dans main
git checkout main
git merge hotfix/CORRECTION_URGENTE
git tag -a v1.x.x -m "Version patch 1.x.x"
git push origin main --tags
git push origin --delete hotfix/CORRECTION_URGENTE
```

## Conventions de Commits

### Format
```
type(scope): description

body (optionnel)

footer (optionnel)
```

### Types
- `feat`: Nouvelle fonctionnalité
- `fix`: Correction de bug
- `docs`: Documentation
- `style`: Formatage (sans impact fonctionnel)
- `refactor`: Refactoring
- `test`: Tests
- `chore`: Maintenance, dépendances

### Exemples
```bash
feat(appels): Nouvelle logique de statuts d'appels
fix(auth): Correction de la validation des tokens
docs(readme): Mise à jour des instructions d'installation
```

## Protection de Main

### GitHub Branch Protection Rules
```yaml
# .github/branch-protection.yml (via interface GitHub)
main:
  required_reviews: 1
  dismiss_stale_reviews: true
  require_up_to_date_branch: true
  required_status_checks:
    - "Deploy to Gandi (workflow)"
  enforce_admins: true
  restrictions:
    users: []
    teams: ["core-developers"]
```

### Workflow Actions
```yaml
# .github/workflows/branch-protection.yml
name: Branch Protection
on:
  pull_request:
    branches: [main]

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Django Checks
        run: python manage.py check
      - name: Run Tests
        run: python manage.py test
      - name: Lint Code
        run: flake8 App_PADESCE/
```

## Workflow Spécifique Django + Gandi

### 1. Environnement de Développement
```bash
# Cloner le projet
git clone https://github.com/naumur2017-del/Padesce.git
cd Padesce

# Configurer l'environnement
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec les clés de développement
```

### 2. Cycle de Développement
```bash
# 1. Mettre à jour main
git checkout main
git pull origin main

# 2. Créer branche feature
git checkout -b feature/MA_FONCTION

# 3. Développer
# ... modifications ...

# 4. Tests locaux
python manage.py check
python manage.py test
python manage.py runserver

# 5. Commiter
git add .
git commit -m "feat: Description"

# 6. Pousser
git push origin feature/MA_FONCTION
```

### 3. Déploiement sur Gandi
```bash
# Après merge dans main
git checkout main
git pull origin main

# Le workflow GitHub Actions se déclenche automatiquement:
# - Tests Django
# - Build assets
# - Déploiement sur Gandi
# - Vérification post-déploiement
```

## Bonnes Pratiques

### Avant de Committer
```bash
# 1. Vérifier les fichiers modifiés
git status

# 2. Formater et vérifier le code
black App_PADESCE/
isort App_PADESCE/
flake8 App_PADESCE/ --max-line-length=100

# 3. Vérifier la syntaxe Django
python manage.py check

# 4. Lancer les tests
python manage.py test --failfast

# 5. Vérifier le formatage (optionnel)
black --check --diff App_PADESCE/
```

### Messages de Commits
- **Précis**: Décrire ce qui change, pas pourquoi
- **Concis**: Maximum 72 caractères pour le titre
- **Impératif**: "Ajoute" au lieu de "Ajouté"
- **Contexte**: Inclure le scope (appels, auth, etc.)

### Branches
- **Courte vie**: Merge et supprimer rapidement
- **Descriptives**: `feature/appels-statuts` au lieu de `feature/fix`
- **Syncées**: `git pull origin main` avant de commencer

### Déploiement
- **Jamais directement sur main**: Toujours via PR
- **Tests obligatoires**: Le workflow doit passer
- **Rollback rapide**: Tags et backups disponibles

## Workflow d'Urgence

### Si Main est Cassé
```bash
# 1. Identifier le dernier commit stable
git log --oneline main

# 2. Revenir à la version stable
git checkout main
git reset --hard <commit_stable_hash>
git push --force-with-lease origin main

# 3. Créer hotfix
git checkout -b hotfix/ROLLBACK
# ... correction ...
git checkout main
git merge hotfix/ROLLBACK
git push origin main
```

### Si Déploiement Échoue
```bash
# 1. Vérifier les logs GitHub Actions
# 2. Corriger localement
git checkout main
git pull origin main
# ... corrections ...

# 3. Commiter et pousser
git add .
git commit -m "fix: Correction déploiement Gandi"
git push origin main
```

## Black et Formatage de Code

### Configuration Black
Le projet utilise Black avec les paramètres suivants :
- **Line length**: 100 caractères
- **Target version**: Python 3.13
- **Exclusions**: `.git`, `.venv`, `logs`, `media`, `staticfiles`, `migrations`

### Installation et Configuration
```bash
# Installer les dépendances
pip install black flake8 isort pre-commit

# Installer les hooks pre-commit
pre-commit install

# Formater le code
black App_PADESCE/
isort App_PADESCE/

# Vérifier le formatage
black --check --diff App_PADESCE/
flake8 App_PADESCE/ --max-line-length=100
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black
        language_version: python3.13
        args: [--line-length=100]
```

### GitHub Actions Integration
Le workflow GitHub Actions inclut maintenant :
- **Black**: Vérification du formatage
- **Flake8**: Analyse statique du code
- **isort**: Tri des imports
- **Django Check**: Validation Django
- **Django Tests**: Tests automatiques

## Outils Recommandés

### Git Hooks
```bash
# .git/hooks/pre-commit
#!/bin/sh
black App_PADESCE/
isort App_PADESCE/
flake8 App_PADESCE/ --max-line-length=100
python manage.py check
python manage.py test --failfast
```

### Git Aliases
```bash
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.st status
git config --global alias.unstage 'reset HEAD --'
git config --global alias.last 'log -1 HEAD'
```

## Résumé du Workflow Actuel

1. **feature/KEMAYOU** : Nouvelle logique de statuts d'appels
2. **Tests** : Vérifier localement
3. **Review** : Validation par l'équipe
4. **Merge** : Intégration dans main
5. **Déploiement** : Automatique via GitHub Actions
6. **Monitoring** : Vérification post-déploiement

Ce workflow garantit la qualité du code tout en permettant des déploiements rapides et sécurisés.
