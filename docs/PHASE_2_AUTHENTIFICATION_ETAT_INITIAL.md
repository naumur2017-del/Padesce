# PADESCE — Phase 2 : état initial de l'authentification

Date d'analyse : 2026-08-25. Ce document décrit uniquement ce qui a été
vérifié dans le dépôt. Il ne prétend pas décrire les données de production,
qui doivent être auditées séparément.

## Décision à ce stade

L'identifiant réellement utilisé par le formulaire de connexion est le champ
Django `auth.User.username`. Il est donc le candidat provisoire à
l'identifiant officiel. Aucun passage au nouveau backend ou ajout de
contrainte de base de données ne doit avoir lieu avant le rapport
`audit_operator_accounts` exécuté sur une copie PostgreSQL.

Règle de normalisation proposée pour le diagnostic et l'audit : NFKC Unicode,
suppression des caractères de format invisibles, réduction des espaces,
suppression des espaces périphériques et `casefold()` Unicode. Les accents sont
conservés. Cette règle n'est pas encore utilisée pour authentifier en
production : elle peut révéler des collisions qui requièrent une décision
humaine.

## Parcours actuel

```text
Utilisateur
  -> /login/ (template registration/login.html, username + password)
  -> SQLiteSafeLoginView
  -> AuthenticationForm / authenticate()
  -> backend Django
       SQLite : SQLiteSafeModelBackend, recherche exacte du username
       PostgreSQL : ModelBackend Django par défaut
  -> auth_user (PostgreSQL en production)
  -> is_active
  -> création/rotation de session
  -> redirection Django
```

Une voie séparée existait dans `LoginRequiredMiddleware` : des chemins
d'analyse pouvaient ouvrir automatiquement une session. Elle est maintenant
désactivée par défaut via `PUBLIC_ANALYSIS_AUTO_LOGIN=False`; elle reste un
feature flag exceptionnel, à activer uniquement par décision explicite et
avec des secrets hors du dépôt.

## Modèles et identifiants vérifiés

| Élément | Constat dans le code | Risque / conséquence |
| --- | --- | --- |
| Utilisateur | `django.contrib.auth.models.User` standard ; aucun `AUTH_USER_MODEL` configuré | Le champ de connexion est `username`. |
| Profil opératrice | Aucun modèle `Operatrice`, `Agent`, `Consultant` ou `Profile` trouvé | Un rôle est principalement porté par les groupes Django. |
| Identifiant de connexion | `username` dans `AuthenticationForm` et les backends | Les e-mails, téléphones, matricules et codes ne sont pas acceptés par le login actuel. |
| Groupes détectés | `admin_systeme`, `inspecteur_enqueteur`, `prestataire_beneficiaire`, `consultation`, `manager_padesce`, `manager_cga`, `consultant` | Les contrôles ne sont pas encore tous centralisés. |
| Base de données | PostgreSQL si les variables sont définies ; SQLite sinon | Les tests ciblés actuels s'exécutent avec SQLite : PostgreSQL doit être ajouté au pipeline avant les contraintes. |

## Divergences et causes de refus probables

1. **Critique — contournement par auto-connexion publique.** Il était activé
   par défaut et dépendait d'identifiants codés dans la configuration. Le
   défaut est désormais désactivé ; déployer ce changement impose de vérifier
   que les pages d'analyse ont bien le niveau d'accès attendu.
2. **Élevée — normalisation incohérente.** Le login recherche un `username`
   exact, alors que l'ancien diagnostic supprimait les espaces et utilisait une
   comparaison insensible à la casse. Une espace, une majuscule ou un caractère
   invisible peut donc faire échouer la connexion.
3. **Élevée — collisions inconnues.** Une normalisation future peut rapprocher
   deux identifiants existants. Le backend ne devra jamais choisir le premier
   compte : l'audit doit d'abord identifier les collisions.
4. **Élevée — rôles hétérogènes.** Des décorateurs/fonctions existent dans
   `core/access.py`, mais des tests de groupes et de superutilisateur sont
   encore écrits directement dans des vues.
5. **Moyenne — sessions multi-workers.** PostgreSQL utilise `cached_db`, mais
   le cache par défaut est local (`LocMemCache`) sans Redis configuré. Il faut
   confirmer un cache partagé en production.
6. **Moyenne — paramètres de proxy/cookies.** Les cookies sécurisés et le
   proxy HTTPS sont activés seulement lorsque `DEBUG=False`; la configuration
   effective de production doit être contrôlée.

## Commandes de diagnostic introduites

La commande suivante est strictement en lecture :

```bash
python manage.py audit_operator_accounts --format json --dry-run --output /tmp/padesce-auth-audit.json
```

Elle ne contient ni mot de passe, ni hash, ni token, ni identifiant brut. Elle
signale notamment les valeurs vides, espaces et caractères invisibles,
collisions après normalisation, comptes inactifs, mots de passe inutilisables,
groupes absents/inconnus et valeurs qui ressemblent à un e-mail ou un
téléphone.

Pour examiner un identifiant de manière non destructive :

```bash
python manage.py diagnose_operator_login --identifier 'valeur saisie'
```

## Vérifications PostgreSQL requises avant la suite

À exécuter sur une copie restaurée ou avec un compte SQL en lecture seule :

```sql
SELECT
  COUNT(*) FILTER (WHERE username IS NULL OR btrim(username) = '') AS usernames_vides,
  COUNT(*) FILTER (WHERE username <> btrim(username)) AS usernames_avec_espaces,
  COUNT(*) FILTER (WHERE NOT is_active) AS comptes_inactifs,
  COUNT(*) FILTER (WHERE password LIKE '!%') AS mots_de_passe_inutilisables
FROM auth_user;

SELECT
  COUNT(*) AS groupes_de_collision,
  COALESCE(SUM(nombre), 0) AS comptes_concernes
FROM (
  SELECT lower(btrim(username)) AS identifiant_normalise, COUNT(*) AS nombre
  FROM auth_user
  GROUP BY lower(btrim(username))
  HAVING COUNT(*) > 1
) collisions;
```

## Déploiement et retour arrière

1. Déployer d'abord les deux commandes et observer les logs/rapports ; ne pas
   activer le backend normalisé.
2. Exécuter l'audit contre une copie PostgreSQL et faire valider humainement
   chaque collision.
3. Ajouter les tests PostgreSQL et un backend sous feature flag.
4. Activer le feature flag seulement après validation, puis surveiller les
   codes techniques agrégés.
5. Ajouter une migration/contrainte seulement lorsque toutes les collisions
   sont résolues.

Les trois commits initiaux sont indépendants et réversibles :

- `441082c` : fonction de normalisation et audit non destructif ;
- `ad464aa` : diagnostic aligné sur la normalisation ;
- `e84c12a` : auto-connexion publique désactivée par défaut.

Pour revenir en arrière, effectuer un `git revert` du commit concerné. Aucun
de ces commits ne modifie les comptes, les mots de passe ou le schéma de la
base de données.
