# Jardin Assistant

Application personnelle d'aide au jardinage : catalogue de plantes, calendrier de semis/plantation/récolte, suivi d'arrosage, et (à terme) analyse de plantes par photo et conseils via IA.

> 🚧 Projet en cours de développement — Phase 1 (MVP sans IA). Voir [`spec.md`](./spec.md) pour la feuille de route complète.

## Fonctionnalités (Phase 1)

- Gestion d'un catalogue d'espèces de plantes (exposition, arrosage, mois de semis/récolte)
- Suivi des plantes présentes dans le jardin (emplacement, date de plantation, statut)
- Journal d'événements (arrosage, taille, traitement, récolte)
- Rappels simples basés sur la fréquence d'arrosage de chaque espèce

Les fonctionnalités à venir (météo, chatbot IA, identification par photo, agents) sont détaillées dans [`spec.md`](./spec.md).

## Stack technique

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — gestion du projet et des dépendances
- [SQLModel](https://sqlmodel.tiangolo.com/) — ORM (SQLAlchemy + Pydantic)
- PostgreSQL + [pgvector](https://github.com/pgvector/pgvector) — base de données
- [Typer](https://typer.tiangolo.com/) — interface en ligne de commande
- pytest — tests

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installé

## Installation

1. Cloner le dépôt :
   ```bash
   git clone <url-du-depot>
   cd jardin-assistant
   ```

2. Copier le fichier d'environnement et adapter si besoin :
   ```bash
   cp .env.example .env
   ```

3. Lancer la base de données :
   ```bash
   docker compose up -d
   ```

4. Installer les dépendances Python :
   ```bash
   uv sync
   ```

5. Appliquer les migrations (à venir une fois configurées) :
   ```bash
   uv run alembic upgrade head
   ```

## Utilisation

```bash
# Creation base de donnée
uv run courgette init-db

# Ajouter une espèce au référentiel
uv run courgette espece ajouter

# Lister les plantes de son jardin
uv run courgette plante liste

# Enregistrer un arrosage
uv run courgette evenement ajouter

# Voir les rappels du jour
uv run courgette rappel liste
```

*(Commandes indicatives — à ajuster une fois le CLI implémenté.)*

## Tests

```bash
uv run pytest
```

## Documentation

- [`spec.md`](./spec.md) — objectifs, feuille de route par phase, modèle de données, décisions techniques

## Licence

À définir.