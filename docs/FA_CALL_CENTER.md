# FA : mise en service et vérification

Le module FA (« Fond d’amortissement », nom demandé) reprend le questionnaire NAUMUR/APME consacré aux fonds d’amorçage : 36 questions, six sections et une déclaration orale du répondant. Les réponses conditionnelles et les choix d’accompagnement de la question 27 sont repris. Les champs nécessaires à un questionnaire complet sont signalés ; les autres résultats d’appel acceptent un brouillon.

## Parcours

- `/fa/` : entreprises, recherche, filtres de statut, ville, secteur, opérateur, dates de tentative et présence d’audio ; pagination de 50 lignes.
- Le bouton ouvre la fiche et le questionnaire dans une modale. Le téléphone peut être corrigé avant le démarrage, notamment pour les contacts absents du registre.
- Le microphone doit fonctionner et un premier audio doit parvenir au serveur avant la création d’un appel. La composition du numéro devient disponible ensuite. Une source audio partagée peut compléter le microphone pour capter l’autre interlocuteur ; l’application ne passe pas elle-même d’appel téléphonique et ne dispose pas d’un fournisseur de téléphonie.
- Les sauvegardes audio intermédiaires sont cumulatives, lisibles et conservées avec leur séquence. Le navigateur garde temporairement les uploads non acquittés dans IndexedDB et les réessaie après reconnexion. Les sauvegardes réussies sont retirées du stockage local.
- La fermeture de la modale est bloquée pendant l’enregistrement. Une navigation forcée ou un arrêt brutal du navigateur peut perdre les dernières secondes depuis la dernière sauvegarde. Le serveur conserve la tentative ouverte et les audios déjà reçus ; aucun mécanisme navigateur ne garantit une capture après fermeture forcée ou coupure matérielle.
- La clôture exige un résultat explicite et le dernier fichier audio marqué final. Un rappel exige une date future. Un questionnaire complet exige ses réponses applicables et la confirmation de la déclaration. Le serveur vérifie ces règles indépendamment du JavaScript.
- L’historique conserve les tentatives et les enregistrements. Un seul appel peut être ouvert par entreprise. L’opérateur propriétaire et le superadmin peuvent modifier la tentative ; l’écoute est limitée au propriétaire et aux responsables d’analyse autorisés.
- `/fa/analyses/` et `/fa/export/` : accès superadmin, managers PADESCE/CGA/FA et consultants. Les analyses de financement portent sur les questionnaires complets ; le nombre d’entreprises constitue le dénominateur du taux de complétion. Les répartitions multichoix indiquent leur nombre de répondants.

## Importer les 70 entreprises fournies

Le registre préparé localement se trouve dans `data/fa/enterprises.json`. Il contient des coordonnées et des chiffres d’affaires : le garder dans le stockage privé du déploiement, sans le publier dans un dépôt public. Le fichier Excel original peut également être importé directement depuis l’interface FA par un superadmin.

```sh
python manage.py import_fa_enterprises /chemin/prive/entreprises.xlsx --dry-run
python manage.py import_fa_enterprises /chemin/prive/entreprises.xlsx
```

Le même import accepte le registre JSON préparé. Les références `FA-001` à `FA-070` proviennent des numéros source. L’import est additif et réexécutable : réponses, appels, audios et corrections de téléphone effectuées dans le questionnaire sont conservés. Il signale quatre téléphones absents et trois numéros de huit chiffres à vérifier. Les numéros partagés ne provoquent ni fusion ni suppression.

## Déploiement

Intégrer les modifications sur la branche courante de production avec revue, puis exécuter dans l’environnement de production :

```sh
python manage.py check
python manage.py migrate --plan
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Le pipeline Gandi du dépôt applique ensuite le rechargement habituel. Ne pas envoyer les bases locales de test ou remplacer la base de production. Sauvegarder la base et les médias avec les outils existants avant les migrations. La migration `appels.0045_cga_navigation_index` ajoute un index ; `fa.0001_initial` crée uniquement les nouvelles tables FA.

Prévoir un stockage média durable et les limites proxy nécessaires aux uploads audio (jusqu’à 64 Mo par fichier), HTTPS et l’accès microphone. Les deux interlocuteurs ne sont captés que si la source d’entrée les contient ou si l’opérateur partage l’audio de l’outil d’appel. Faire un essai réel avec l’équipement des opérateurs avant la campagne.

Le navigateur crée des copies intermédiaires complètes pour permettre la reprise sans fichier WebM illisible. Cela augmente l’espace média utilisé ; conserver ces fichiers conformément aux règles de la campagne. Aucun nettoyage automatique des enregistrements n’est introduit.

## Optimisations de navigation

Les listes PADESCE, CGA et formateurs et les détails d’analyse demandent les audios uniquement à la lecture (`preload="none"`). Les scripts du widget partagé sont différés. Le suivi d’activité désactivé ne charge plus de script ; les mises à jour d’activité sont limitées à une par minute. Les vérifications des groupes partagent leur requête pendant la même requête HTTP.

La liste CGA affiche 50 lignes par défaut, évite les comptages redondants, récupère les valeurs de filtres distinctes dans SQL et garde uniquement les libellés de filtres 30 secondes. Les lignes, statuts et verrous restent lus à chaque chargement. Le contexte agrégé des analyses CGA est conservé 15 secondes et invalidé après sauvegarde/suppression d’une ligne. Le HTML, l’identité et les jetons CSRF ne sont pas partagés par ce nouveau cache.

Mesures de rendu serveur local du 29 octobre 2026, sans réseau ni rendu navigateur :

| Page | Première mesure | Mesures suivantes |
| --- | ---: | ---: |
| FA, liste de 70 entreprises | 689 ms | 25–26 ms |
| FA, questionnaire en modale | 91 ms | 56–93 ms |
| FA, analyses | 34 ms | 21–47 ms |
| CGA, copie de 251 052 lignes | 2 434 ms | 694–852 ms |
| Analyses CGA, même copie | 862 ms | 7–9 ms |

Ces mesures ne constituent pas une garantie de chargement en production. Le premier accès CGA dépasse encore une seconde. La copie SQLite fournie a perdu plusieurs contraintes/index historiques et n’est pas représentative à elle seule d’un PostgreSQL de production. Aucune réparation destructive de cette base n’a été effectuée. Le réseau de production, le proxy, la concurrence et le premier chargement doivent être mesurés sur place ; un objectif de 1 ms de chargement réseau n’est pas réaliste.

## Validation et limites constatées

Les tests ciblés couvrent l’authentification, les droits audio, la première capture obligatoire, les conflits d’opérateurs, les retries idempotents, les sauvegardes finales, les rappels, les questionnaires conditionnels, l’import et les analyses. Quatre simulations JavaScript sur DOM couvrent les branches imbriquées, le microphone refusé, le retry d’audio après coupure et la séquence d’une session reprise. Les trois gabarits FA sont rendus par Django sans erreur.

Le contrôle du navigateur a refusé l’ouverture de l’aperçu local : la vérification visuelle et l’essai réel microphone/son distant restent à effectuer. Une suite élargie rencontre aussi deux problèmes préexistants : `core.tests` importe `_build_formateur_stats`, absent de `public_views`, et un ancien test CGA exige la suppression du premier audio alors que le module conserve déjà un historique. Ces problèmes ne sont pas masqués et ne sont pas traités comme des tests réussis.
