# ServicePulse

Plateforme de monitoring de services web/API : ajout de services à surveiller, vérification de leur disponibilité et de leur latence, historique des checks, disponibilité (%) et tendance de latence.

> **Contexte** : ce dépôt démarre avec un prototype (backend FastAPI, dashboard, tests, Dockerfile) préparé avant le lancement du chronomètre de 4h, avec l'accord explicite du recruteur. Le premier commit reflète ce point de départ. Tout ce qui suit dans l'historique (CI/CD complet, base RDS, test de charge, scénario de panne) a été réalisé pendant la fenêtre de 4h, démarrée au push du premier commit.

## URL publique

**https://se-cb38813f3aca4a9b8c391d482fea4411.ecs.eu-west-3.on.aws**

## Stack

| Composant | Techno |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy |
| Frontend | HTML / CSS / JavaScript (servi par le backend) |
| Base de données | MySQL 8 (conteneur en local, Amazon RDS en prod) |
| Tests | pytest (contre SQLite en mémoire) |
| CI/CD | GitHub Actions (tests, build, push ECR, déploiement ECS) |
| Registre d'images | Amazon ECR |
| Cloud | Amazon ECS Express Mode (Fargate, load balancer, autoscaling) |
| Secrets | AWS Secrets Manager (mot de passe RDS) |

## Lancer le projet en local

```bash
cp .env.example .env
docker compose up --build
```
- Dashboard : http://localhost:8000
- API interactive (Swagger) : http://localhost:8000/docs
- Health check : http://localhost:8000/health

## Lancer les tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

## Architecture

    INTERNET
       │
       ▼
    Application Load Balancer (créé automatiquement par ECS Express Mode)
       │
       ▼
    Conteneur Fargate : FastAPI sert l'API (/services, /health) ET le dashboard statique
       │
       ▼
    Amazon RDS MySQL (accès réseau limité au groupe de sécurité du conteneur uniquement,
    mot de passe injecté depuis Secrets Manager, jamais en variable d'environnement en clair)

Déploiement :

    git push
       │
       ▼
    GitHub Actions
       ├─ Tests (pytest)
       ├─ Build de l'image Docker
       ├─ Authentification AWS par OIDC (aucune clé stockée dans GitHub)
       ├─ Push vers Amazon ECR
       └─ Déploiement automatique sur ECS (rolling update, zéro coupure)

## Comment c'est construit et déployé

- **CI/CD (GitHub Actions, 3 jobs séquentiels)** : `test` → `build-and-push` → `deploy`. Le déploiement ne se déclenche que sur un push, et seulement si les jobs précédents ont réussi.
- **Authentification GitHub → AWS par OIDC** : aucune clé d'accès AWS stockée comme secret GitHub. AWS accepte le jeton uniquement pour ce dépôt et la branche `main`.
- **Permissions IAM au plus juste** : le rôle du pipeline ne peut que pousser des images vers ECR `servicepulse` et déployer le service ECS `servicepulse`.
- **Amazon ECS Express Mode** plutôt qu'une configuration manuelle ECS + Load Balancer + Auto Scaling : provisionne et connecte automatiquement ces briques (ALB, health checks, scaling par CPU, rollback automatique sur erreurs 5XX), réduisant le risque de blocage sous contrainte de temps.
- **Amazon RDS MySQL**, non accessible publiquement, chiffré au repos, mot de passe géré par AWS Secrets Manager.

## Décisions d'ingénierie

- **Config par variables d'environnement, jamais en dur** (`DATABASE_URL` ou ses composants séparés) — la même image tourne en local, en CI et en prod sans modification de code.
- **Tests contre SQLite en mémoire plutôt que contre MySQL** : tests rapides, sans dépendance réseau, exécutables en CI sans provisionner de base.
- **Retry de connexion DB au démarrage** (5 tentatives, 2s d'intervalle) : tolère que le conteneur MySQL / l'instance RDS ne soit pas encore prête au premier démarrage.
- **Endpoint `/health` dédié** : utilisé par Docker `HEALTHCHECK` en local et par le health check ECS/ALB en prod pour décider du routage et du redémarrage automatique.
- **Frontend servi directement par FastAPI** (`StaticFiles`) plutôt que par un conteneur séparé : un seul conteneur à construire, tester et déployer — plus simple, cohérent avec la contrainte des 4h.
- **Protection SSRF** sur l'URL des services surveillés : `/check` fait une requête HTTP sortante vers une URL fournie par l'utilisateur ; sans validation, ce serait un vecteur pour sonder le réseau interne (ex: l'endpoint de métadonnées cloud `169.254.169.254`). Les URL sont rejetées (422) si le schéma n'est pas http/https ou si l'hôte résout vers une IP privée/loopback/link-local. Un hôte qui ne résout simplement pas n'est pas rejeté : c'est un cas légitime (service mal configuré) que l'outil doit pouvoir suivre comme DOWN.
- **Mot de passe DB jamais assemblé en clair** : `config.py` construit `DATABASE_URL` à partir de morceaux séparés (hôte/utilisateur en variable d'environnement classique, mot de passe injecté à part par ECS depuis Secrets Manager).
- **CI en jobs séparés et dépendants** (`needs: test`, puis `needs: build-and-push`) : si les tests cassent, ni l'image n'est construite, ni rien n'est déployé.

## Comportement sous charge (test k6)

Scénario : montée progressive de 10 à 100 utilisateurs simulés sur 3 minutes, requêtes sur `GET /services` (lecture réelle en base MySQL/RDS à chaque appel), contre l'URL publique.

| Indicateur | Résultat |
|---|---|
| Requêtes totales | 7 270 |
| Taux d'erreur | 0.00% |
| Latence moyenne | 92.6 ms |
| Latence p95 | 199.38 ms |
| Latence max | 789.27 ms |

CPU du conteneur (Amazon CloudWatch, métrique `AWS/ECS CPUUtilization`) sur la fenêtre du test :

| Heure (UTC+1) | CPU moyen | CPU max |
|---|---|---|
| 23:08 (avant le test) | 0.11% | 0.13% |
| 23:09 (montée en charge) | 0.45% | 2.15% |
| 23:10 (charge croissante) | 6.57% | 19.54% |
| 23:11 (proche du pic, ~100 VUs) | 18.65% | 47.64% |

Aucune erreur sur l'ensemble du test. La latence augmente avec la charge (attendu : chaque requête déclenche une vraie lecture réseau vers RDS), mais reste sous 800ms même au pic. Le CPU suit clairement la montée en charge (multiplié par plus de 150 entre le début et le pic), sans toutefois franchir le seuil de déclenchement du scale-out sur cette fenêtre de 3 minutes — un test plus long ou plus intensif le déclencherait, comme le montre la tendance nette de cette courbe.

## Scénario de panne

Un conteneur en cours d'exécution a été arrêté manuellement (`aws ecs stop-task`) pendant que le service tournait avec 1 seul conteneur actif (`minTaskCount: 1`). Une sonde a interrogé `/health` toutes les secondes pendant 60 secondes après l'arrêt : **60/60 réponses `200`, aucune coupure visible.** ECS a détecté l'arrêt et démarré un conteneur de remplacement suffisamment vite pour qu'aucune requête n'échoue sur cette fenêtre d'observation.

## Sécurité

- Aucun secret en dur dans le code ou le dépôt (`.env` gitignored, mot de passe RDS uniquement dans Secrets Manager).
- Authentification GitHub Actions → AWS par OIDC, sans clé d'accès statique.
- Base de données non accessible publiquement, uniquement depuis le groupe de sécurité du conteneur applicatif.
- Stockage RDS chiffré au repos ; scan de vulnérabilités automatique sur chaque image poussée vers ECR.
- Protection SSRF sur les URL de services ajoutées par l'utilisateur.

## Test de résistance : trouver le point de rupture

Un second test, volontairement plus agressif que le premier, a été lancé pour tenter de déclencher un vrai scale-out : 150 utilisateurs simulés soutenus pendant 3 minutes (au lieu d'une montée progressive), avec un temps d'attente réduit entre requêtes.

| Indicateur | Résultat |
|---|---|
| Requêtes totales | 5 723 |
| Taux d'erreur | 8.28% |
| Latence moyenne | 5.13 s |
| Latence p95 | 60 s (timeout k6) |

CPU du conteneur sur cette fenêtre :

| Heure (UTC+1) | CPU moyen | CPU max |
|---|---|---|
| 23:50 (avant le test) | 0.15% | 0.21% |
| 23:51 (charge appliquée) | 12.13% | 71.79% |
| 23:52 | 0.40% | 2.46% |
| 23:53 | 17.56% | 92.16% |
| 23:54 | 0.71% | 2.80% |
| 23:55 (fin du test) | 0.93% | 2.87% |

**Résultat inattendu, contrairement à l'hypothèse émise après le premier test** : malgré un pic CPU à 92%, aucun scale-out ne s'est déclenché (le nombre de conteneurs actifs est resté à 1 pendant tout le test, confirmé par une surveillance en parallèle). L'hypothèse la plus probable : le vrai goulot d'étranglement n'était pas le CPU mais le pool de connexions MySQL de SQLAlchemy (5 connexions par défaut), saturé par les requêtes N+1 déjà identifiées comme limitation ci-dessous — une requête qui attend une connexion libre n'utilise pas de CPU, elle attend, d'où l'alternance entre pics brefs et calme plutôt qu'une charge CPU soutenue capable de déclencher l'auto-scaling.

Le service s'est intégralement rétabli après le test (`/health` de nouveau à 100% en quelques secondes), sans intervention manuelle. Cette limite est corrigible en production par un pool de connexions plus grand et/ou un correctif des requêtes N+1 — volontairement non corrigée ici pour garder une trace honnête du comportement observé sous charge réelle.

## Limitations connues / améliorations possibles

- **Pas d'authentification sur l'API** (dashboard et `/docs` publics) — acceptable pour cet exercice, à ajouter en production.
- **Un seul conteneur minimum** (`minTaskCount: 1`) — en production on fixerait au moins 2 conteneurs sur plusieurs zones de disponibilité.
- **Rôle IAM `servicepulse-ci` aux droits volontairement larges** pour l'exercice — en production, détaillés action par action.
- **Pas de sauvegarde étendue sur RDS** (rétention 1 jour, pas de multi-AZ) — suffisant pour une démonstration.
- **Requêtes N+1** sur la liste des services — acceptable pour un petit nombre de services, à optimiser si ça grandit.
- **Pas de CDN/WAF** devant le load balancer.
