# Migration SQLite vers PostgreSQL

## Objectif
Passer l'application de SQLite vers PostgreSQL tout en recopiant les donnees existantes et les relations entre tables.

## Prerequis
- Une base PostgreSQL vide accessible depuis l'application.
- Les dependances Python installees (`pip install -r requirements.txt`).
- Une sauvegarde du fichier SQLite source (`db.sqlite3`).

## Configuration
Dans `.env`, renseigner au minimum :

```env
DB_ENGINE=postgresql
POSTGRES_DB=padesce
POSTGRES_USER=postgres
POSTGRES_PASSWORD=motdepasse
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Alternative :

```env
DB_ENGINE=postgresql
DATABASE_URL=postgresql://postgres:motdepasse@localhost:5432/padesce
```

La base SQLite source reste le fichier local `db.sqlite3`, ou un autre chemin passe via `--source`.

## Procedure
1. Sauvegarder SQLite :
   ```bash
   copy db.sqlite3 db.sqlite3.backup
   ```
2. Creer le schema PostgreSQL avec les migrations Django :
   ```bash
   python manage.py migrate
   ```
3. Copier toutes les donnees SQLite vers PostgreSQL :
   ```bash
   python manage.py migrate_sqlite_to_postgres --source db.sqlite3
   ```

## Options utiles
- Limiter la copie a certains modeles :
  ```bash
  python manage.py migrate_sqlite_to_postgres --source db.sqlite3 --model formations.formation --model apprenants.apprenant
  ```
- Ne pas rejouer les migrations :
  ```bash
  python manage.py migrate_sqlite_to_postgres --source db.sqlite3 --skip-migrate
  ```
- Conserver le contenu deja present dans PostgreSQL :
  ```bash
  python manage.py migrate_sqlite_to_postgres --source db.sqlite3 --skip-flush
  ```

## Ce que fait la commande
- Verifie que la cible configuree dans Django est bien PostgreSQL.
- Cree le schema cible via `migrate` (sauf `--skip-migrate`).
- Vide les tables ciblees dans PostgreSQL (sauf `--skip-flush`).
- Copie les donnees dans l'ordre des dependances entre modeles.
- Recale les sequences PostgreSQL apres import.
- Verifie les comptes source/cible par table, pour detecter une copie incomplete.

## Recommandation apres migration
Executer ensuite :

```bash
python manage.py check
```

Puis lancer l'application normalement :

```bash
python manage.py runserver
```
