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
