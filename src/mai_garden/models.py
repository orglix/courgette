"""Modèles de données du jardin — Phase 1 (MVP sans IA).

Quatre entités :
- Espece      : référentiel, indépendant du jardin (peuplé à la main pour l'instant,
                par l'IA plus tard — la table ne change pas selon la source).
- PlanteJardin: une plante concrète présente dans le jardin, liée à une Espece.
- Evenement   : le journal (arrosage, taille, traitement, récolte...).
- Rappel      : prochaine échéance d'une action sur une PlanteJardin.
"""

from datetime import date, datetime
from enum import Enum

from sqlalchemy import ARRAY, Integer
from sqlmodel import Column, Field, Relationship, SQLModel


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class Exposition(str, Enum):
    SOLEIL = "soleil"
    MI_OMBRE = "mi_ombre"
    OMBRE = "ombre"


class Emplacement(str, Enum):
    INTERIEUR = "interieur"
    EXTERIEUR = "exterieur"


class StatutPlante(str, Enum):
    SEMIS = "semis"
    CROISSANCE = "croissance"
    RECOLTE = "recolte"
    TERMINEE = "terminee"


class TypeEvenement(str, Enum):
    ARROSAGE = "arrosage"
    TAILLE = "taille"
    TRAITEMENT = "traitement"
    RECOLTE = "recolte"
    AUTRE = "autre"


# --------------------------------------------------------------------------- #
# Espece — référentiel
# --------------------------------------------------------------------------- #

class Espece(SQLModel, table=True):
    """Fiche de référence d'une espèce de plante.

    Modifiable librement, sans historique de versions : en cas de mise à jour,
    on écrase avec la donnée la plus fiable disponible (peu importe la source :
    saisie manuelle, recherche web, photo de paquet de graines...).
    """

    id: int | None = Field(default=None, primary_key=True)

    nom: str = Field(index=True)
    famille: str | None = None
    exposition: Exposition | None = None

    frequence_arrosage_jours: int | None = Field(
        default=None, description="Nombre de jours recommandé entre deux arrosages."
    )

    # Mois stockés en entiers 1-12, en tableau natif Postgres (indexable en GIN,
    # bien plus efficace à filtrer en masse qu'un JSON une fois le référentiel volumineux).
    mois_semis: list[int] = Field(
        default_factory=list, sa_column=Column(ARRAY(Integer), nullable=False, server_default="{}")
    )
    mois_plantation: list[int] = Field(
        default_factory=list, sa_column=Column(ARRAY(Integer), nullable=False, server_default="{}")
    )
    mois_recolte: list[int] = Field(
        default_factory=list, sa_column=Column(ARRAY(Integer), nullable=False, server_default="{}")
    )
    mois_taille: list[int] = Field(
        default_factory=list, sa_column=Column(ARRAY(Integer), nullable=False, server_default="{}")
    )
    mois_bouturage: list[int] | None = Field(
        default=None,
        sa_column=Column(ARRAY(Integer), nullable=True),
        description="Mois où le bouturage est possible. None si non applicable à l'espèce.",
    )

    duree_recolte_jours: int | None = Field(
        default=None, description="Durée approximative entre plantation et récolte."
    )

    source: str | None = Field(
        default=None, description="D'où vient l'information la plus récente (livre, site, IA...)."
    )
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    plantes: list["PlanteJardin"] = Relationship(back_populates="espece")


# --------------------------------------------------------------------------- #
# PlanteJardin — instance dans le jardin
# --------------------------------------------------------------------------- #

class PlanteJardin(SQLModel, table=True):
    """Une plante concrètement présente dans le jardin (ou en intérieur)."""

    id: int | None = Field(default=None, primary_key=True)

    espece_id: int = Field(foreign_key="espece.id", index=True)
    emplacement: Emplacement
    zone: str | None = Field(default=None, description="Ex. 'potager nord', 'salon'.")
    date_plantation: date
    statut: StatutPlante = Field(default=StatutPlante.SEMIS)

    espece: Espece = Relationship(back_populates="plantes")
    evenements: list["Evenement"] = Relationship(back_populates="plante_jardin")
    rappels: list["Rappel"] = Relationship(back_populates="plante_jardin")


# --------------------------------------------------------------------------- #
# Evenement — journal
# --------------------------------------------------------------------------- #

class Evenement(SQLModel, table=True):
    """Une entrée de journal sur une PlanteJardin donnée."""

    id: int | None = Field(default=None, primary_key=True)

    plante_jardin_id: int = Field(foreign_key="plantejardin.id", index=True)
    type: TypeEvenement
    date: datetime = Field(default_factory=datetime.utcnow)
    note: str | None = None

    plante_jardin: PlanteJardin = Relationship(back_populates="evenements")


# --------------------------------------------------------------------------- #
# Rappel
# --------------------------------------------------------------------------- #

class Rappel(SQLModel, table=True):
    """Prochaine échéance d'une action à faire sur une PlanteJardin."""

    id: int | None = Field(default=None, primary_key=True)

    plante_jardin_id: int = Field(foreign_key="plantejardin.id", index=True)
    type_action: TypeEvenement
    prochaine_echeance: date
    recurrence_jours: int | None = Field(
        default=None, description="Si récurrent, nombre de jours entre deux échéances."
    )

    plante_jardin: PlanteJardin = Relationship(back_populates="rappels")