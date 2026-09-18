"""Connexion à la base de données et gestion des sessions SQLModel.

Usage :
    from db import get_session, create_db_and_tables

    create_db_and_tables()  # à lancer une fois, ou via une migration Alembic plus tard

    with next(get_session()) as session:
        session.add(une_espece)
        session.commit()
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

# Charge les variables du fichier .env (DATABASE_URL notamment) dans l'environnement.
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL manquante. Copie .env.example en .env et renseigne la valeur "
        "(ex. postgresql+psycopg://jardin:change-moi@localhost:5432/jardin)."
    )

# echo=True affiche les requêtes SQL générées — pratique en développement,
# à mettre à False (ou piloter via une variable d'env) une fois l'app plus mature.
engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables() -> None:
    """Crée les tables manquantes à partir des modèles SQLModel.

    Suffisant en Phase 1 (pas encore de vraies migrations). À remplacer par
    Alembic dès que le schéma commence à évoluer avec des données existantes
    à préserver.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Fournit une session SQLModel, à utiliser avec `with` ou via injection (FastAPI)."""
    with Session(engine) as session:
        yield session