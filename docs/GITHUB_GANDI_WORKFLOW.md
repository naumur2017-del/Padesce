# Workflow GitHub et Gandi

Ce projet est connecte a GitHub via le depot `origin` :

- `https://github.com/naumur2017-del/Padesce.git`

## Objectif

Donner a l'equipe un flux simple :

1. le code vit sur GitHub
2. les secrets restent hors Git
3. le deploiement vers Gandi se fait depuis la page de deploiement
4. le pipeline confirme que le serveur Python a bien recharge la nouvelle version

## Fichiers a ne jamais versionner

Les fichiers suivants restent locaux et ne doivent pas partir sur GitHub :

- `.env`
- `.env.local`
- `db.sqlite3`
- `media/`
- `logs/`
- `staticfiles/`

Le fichier `.env.example` sert uniquement de modele sans secret.

## Preparation d'un nouveau poste

1. Cloner le depot GitHub.
2. Copier `.env.example` vers `.env` ou `.env.local`.
3. Renseigner les cles et acces reels.
4. Installer les dependances avec `pip install -r requirements.txt`.
5. Lancer les migrations avec `python manage.py migrate`.

## Flux de collaboration

1. Partir de `main`.
2. Creer une branche de travail.
3. Developper et tester localement.
4. Pousser la branche sur GitHub.
5. Faire valider puis fusionner dans `main`.

## Convention d'equipe

Chaque membre travaille sur sa propre branche, par exemple :

- `feature/nom-court`
- `fix/nom-court`
- `chore/nom-court`
- `docs/nom-court`
- `hotfix/nom-court`

Le proprietaire du depot reste le validateur final avant fusion sur `main`.

## GitHub Actions pour les PR

Le depot contient maintenant :

- `.github/workflows/pr-checks.yml`
- `.github/CODEOWNERS`
- `.github/pull_request_template.md`

Sur chaque branche poussee et sur chaque PR vers `main`, GitHub Actions verifie :

1. le nom de branche
2. l'absence de travail direct sur `main`
3. `python manage.py check`
4. la suite de tests du pipeline de deploiement

## GitHub Actions pour le deploiement

Le depot contient aussi :

- `.github/workflows/deploy-gandi.yml`

Quand une PR est fusionnee sur `main`, GitHub Actions :

1. recupere le code fusionne
2. installe Python et les dependances
3. valide la configuration Django
4. lance `python manage.py gandi_deploy --mode deploy`
5. envoie le mail de resultat via le pipeline existant
6. archive les logs du run dans GitHub Actions

## Flux de deploiement Gandi

Une fois le code a jour sur la machine de deploiement :

1. Ouvrir [https://call.naumur.com/deploiement/](https://call.naumur.com/deploiement/).
2. Lancer `Previsualiser` pour voir les ajouts, modifications et suppressions.
3. Verifier le journal et les controles.
4. Lancer `Deployer maintenant`.
5. Attendre la fin du pipeline.

## Comment on sait que Python est bien a jour

Le pipeline ne se contente pas d'envoyer les fichiers.

Il fait aussi ces controles :

1. verification du transfert des fichiers
2. demande de rafraichissement du processus Python sur Gandi
3. verification publique sur [https://call.naumur.com/deploiement/live/](https://call.naumur.com/deploiement/live/)
4. envoi d'un rapport par email avec les checks et les logs

Si le rechargement Python n'est pas confirme, le deploiement doit etre considere comme incomplet.

## Regle d'equipe recommandee

GitHub devient la source de verite pour le code.

Le serveur Gandi doit recevoir :

- soit une version deja fusionnee sur GitHub
- soit une branche explicitement choisie pour un test

Ainsi, l'equipe sait toujours quelle version du code est en ligne.

## Reglages GitHub a activer

Dans GitHub, sur la branche `main`, activez aussi :

1. `Require a pull request before merging`
2. `Require approvals`
3. `Require review from Code Owners`
4. `Require status checks to pass before merging`
5. l'interdiction des pushes directs sur `main`

Checks a selectionner dans la protection de branche :

- `Branch Policy`
- `Django Check`
- `Deployment Tests`

## Secrets GitHub a renseigner

Ajoutez dans `Settings > Secrets and variables > Actions` :

- `DJANGO_SECRET_KEY`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `DEPLOYMENT_REPORT_EMAIL_TO`
- `GANDI_SFTP_HOST`
- `GANDI_SFTP_PORT`
- `GANDI_SFTP_USERNAME`
- `GANDI_SFTP_TOKEN`
- `GANDI_SFTP_REMOTE_PATH`
