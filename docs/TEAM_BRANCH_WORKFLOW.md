# Branches equipe et releases

## About du repository

Description courte recommandee pour GitHub :

`Plateforme Django PADESCE pour le suivi des formations, appels, enquetes, reporting et deploiement Gandi automatise avec GitHub Actions.`

## Branches dediees a l'equipe

Chaque membre a sa branche de travail dediee :

- `feature/tana`
- `feature/marcel`
- `feature/eyoum`
- `feature/koulou`

Ces branches servent de base de travail personnelle. Chacun developpe et pousse sur sa branche.

## Regle simple de travail

1. recuperer la derniere version
2. travailler sur sa branche
3. formatter et verifier
4. commit
5. push
6. ouvrir une PR vers `main` ou laisser le owner ouvrir la PR

## Commandes a utiliser par chaque membre

Exemple pour `tana` :

```bash
git fetch origin
git checkout feature/tana
git pull origin feature/tana
```

Faire les changements, puis lancer la qualite :

```bash
python -m black .
python -m ruff check .
```

Si tout est bon :

```bash
git add .
git commit -m "feat: decrire clairement le changement"
git push origin feature/tana
```

Les autres membres remplacent simplement `feature/tana` par :

- `feature/marcel`
- `feature/eyoum`
- `feature/koulou`

## Regle de merge

- personne ne pousse directement sur `main`
- `main` est reservee au code pret pour la production
- le owner controle la PR finale et merge sur `main`
- le merge sur `main` declenche le deploiement Gandi

## PR et controles automatiques

Sur chaque branche et chaque PR vers `main`, GitHub Actions verifie :

1. le nom de branche
2. `black --check` sur les fichiers Python modifies
3. le lint Python sur les fichiers Python modifies
4. `python manage.py check`
5. les tests du pipeline de deploiement

## Workflow Git Flow simple

- `main` : production
- `feature/*` : travail des membres
- `hotfix/*` : correction urgente
- `release/*` : preparation d'une livraison si necessaire
- `v...` : tag de release

## Comment faire un release tag

Quand vous avez merge les PR voulues sur `main` :

```bash
git checkout main
git pull origin main
git tag -a v2026.03.31-01 -m "Release v2026.03.31-01"
git push origin v2026.03.31-01
```

Exemple de tags :

- `v2026.03.31-01`
- `v2026.04.02-01`
- `v1.0.0`

## Conseil de commit

Utilisez des messages simples et lisibles :

- `feat: ajout du tableau de bord appels`
- `fix: correction du calcul de presence`
- `docs: mise a jour du guide equipe`
- `chore: nettoyage du workflow github`

## Ce que fait le owner

Le owner :

1. relit la PR
2. valide les checks GitHub Actions
3. merge sur `main`
4. pose le tag de release
5. laisse GitHub Actions deployer sur Gandi
6. verifie le mail et la page [https://call.naumur.com/deploiement/](https://call.naumur.com/deploiement/)
