# ServicePulse

Plateforme de monitoring de services web/API : ajout de services à surveiller, vérification de leur disponibilité et de leur latence, historique des checks.

## Stack

| Composant | Techno |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy |
| Frontend | HTML / CSS / JavaScript (à venir) |
| Base de données | MySQL 8 (conteneur en local, RDS en prod) |
| Tests | pytest (contre SQLite en mémoire) |
| CI/CD | GitHub Actions (à venir) |
| Cloud | AWS (à venir) |

## Lancer le projet en local

```bash
cp .env.example .env
docker compose up --build
```

- API : http://localhost:8000
- Documentation interactive (Swagger) : http://localhost:8000/docs
- Health check : http://localhost:8000/health

## Lancer les tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

## Architecture

```
INTERNET
   │
   ▼
[à compléter avec App Runner / ALB]
   │
   ▼
Conteneur unique : FastAPI sert l'API (/services, /health)
ET le dashboard statique (/, /css, /js) ──► MySQL (RDS en prod / conteneur en local)
```

## Décisions d'ingénierie

- **Config par variables d'environnement, jamais en dur** (`DATABASE_URL`, etc.) — la même image tourne en local, en CI et en prod sans modification de code.
- **Tests contre SQLite en mémoire plutôt que contre MySQL** : tests rapides, sans dépendance réseau, exécutables en CI sans provisionner de base. MySQL n'est utilisé qu'en local (conteneur) et en prod (RDS) — le code ne connaît que l'URL SQLAlchemy, pas le moteur.
- **Retry de connexion DB au démarrage** (5 tentatives, 2s d'intervalle) : tolère que le conteneur MySQL / l'instance RDS ne soit pas encore prête au premier démarrage, plutôt que de crasher.
- **Endpoint `/health` dédié**, distinct des routes métier : utilisé par Docker `HEALTHCHECK` en local et par le health check de la plateforme cloud en prod pour décider du routage et du redémarrage automatique.
- **Frontend servi directement par FastAPI** (`StaticFiles`) plutôt que par un conteneur séparé (nginx, etc.) : un seul conteneur à construire, tester et déployer. Plus simple à opérer et cohérent avec la contrainte des 4h — le seul point de complexité en plus serait justifié si le frontend devait scaler indépendamment du backend, ce qui n'est pas le cas ici.
- **Protection SSRF sur l'URL des services surveillés** : `/check` fait une requête HTTP sortante vers l'URL fournie par l'utilisateur — sans validation, ce serait un vecteur classique pour sonder le réseau interne (ex: l'endpoint de métadonnées cloud `169.254.169.254`). Les URL sont donc rejetées (422) si le schéma n'est pas http/https ou si l'hôte résout vers une IP privée/loopback/link-local. Un hôte qui ne résout simplement pas n'est pas rejeté : c'est un cas légitime (service mal configuré ou pas encore déployé) que l'outil doit pouvoir suivre comme DOWN.

## Limitations connues / améliorations possibles

- La liste des services fait plusieurs requêtes SQL par service (dernier check, disponibilité, historique récent) — acceptable pour un petit nombre de services, à optimiser avec des agrégations SQL si ça grandit.
- (à compléter à la fin de l'exercice)

## Ce qui reste à faire

- [x] Frontend (dashboard : recherche, disponibilité %, mini-graphique de latence)
- [ ] CI/CD (GitHub Actions)
- [ ] Déploiement AWS (ECR + App Runner + RDS)
- [ ] Load testing (k6)
- [ ] Scénario de panne documenté
- [ ] Sécurité (secrets, validation, éventuelle auth)
