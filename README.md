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

Scénario : montée progressive de 10 à 100 utilisateurs simulés sur 3 minutes, requêtes sur `GET /services` (lecture réelle en base à chaque appel), contre l'URL publique.

| Indicateur | Résultat |
|---|---|
| Requêtes totales | 7 822 |
| Taux d'erreur | 0.00% |
| Latence moyenne | 15.84 ms |
| Latence p95 | 21.75 ms |
| Latence max | 205.35 ms |

Aucune erreur sur l'ensemble du test, latence stable même proche de 100 utilisateurs simultanés. Le nombre de conteneurs n'a pas augmenté pendant ce test : l'application étant légère, le seuil CPU d'auto-scaling n'a pas été atteint sur cette charge. La politique d'auto-scaling est en place (1 à 2 conteneurs, déclenchement sur CPU) et se déclencherait sous une charge plus soutenue ou plus consommatrice de CPU.

## Scénario de panne

Un conteneur en cours d'exécution a été arrêté manuellement (`aws ecs stop-task`) pendant que le service tournait avec 1 seul conteneur actif (`minTaskCount: 1`). Une sonde a interrogé `/health` toutes les secondes pendant 60 secondes après l'arrêt : **60/60 réponses `200`, aucune coupure visible.** ECS a détecté l'arrêt et démarré un conteneur de remplacement suffisamment vite pour qu'aucune requête n'échoue sur cette fenêtre d'observation.

## Sécurité

- Aucun secret en dur dans le code ou le dépôt (`.env` gitignored, mot de passe RDS uniquement dans Secrets Manager).
- Authentification GitHub Actions → AWS par OIDC, sans clé d'accès statique.
- Base de données non accessible publiquement, uniquement depuis le groupe de sécurité du conteneur applicatif.
- Stockage RDS chiffré au repos ; scan de vulnérabilités automatique sur chaque image poussée vers ECR.
- Protection SSRF sur les URL de services ajoutées par l'utilisateur.

## Limitations connues / améliorations possibles

- **Pas d'authentification sur l'API** (dashboard et `/docs` publics) — acceptable pour cet exercice, à ajouter en production.
- **Un seul conteneur minimum** (`minTaskCount: 1`) — en production on fixerait au moins 2 conteneurs sur plusieurs zones de disponibilité.
- **Rôle IAM `servicepulse-ci` aux droits volontairement larges** pour l'exercice — en production, détaillés action par action.
- **Pas de sauvegarde étendue sur RDS** (rétention 1 jour, pas de multi-AZ) — suffisant pour une démonstration.
- **Requêtes N+1** sur la liste des services — acceptable pour un petit nombre de services, à optimiser si ça grandit.
- **Pas de CDN/WAF** devant le load balancer.
