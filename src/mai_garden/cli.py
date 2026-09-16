"""CLI de gestion du jardin (Phase 1).

Usage :
    uv run python cli.py init-db
    uv run python cli.py espece ajouter Tomate --exposition soleil --mois-semis 3,4 --mois-recolte 7,8,9
    uv run python cli.py espece lister
    uv run python cli.py plante ajouter 1 --emplacement exterieur --zone "potager nord"
    uv run python cli.py plante lister
"""

from datetime import date

import typer
from sqlmodel import Session, select

from mai_garden.db import create_db_and_tables, engine
from mai_garden.models import Emplacement, Espece, Exposition, PlanteJardin, StatutPlante

app = typer.Typer(help="Assistant de gestion du jardin.")
espece_app = typer.Typer(help="Gérer le référentiel d'espèces.")
plante_app = typer.Typer(help="Gérer les plantes de ton jardin.")
app.add_typer(espece_app, name="espece")
app.add_typer(plante_app, name="plante")


def _parse_mois(valeur: str | None) -> list[int]:
    """Parse une liste de mois séparés par des virgules, ex. '3,4,5' -> [3, 4, 5]."""
    if not valeur:
        return []
    return [int(m.strip()) for m in valeur.split(",") if m.strip()]


@app.command("init-db")
def init_db():
    """Crée les tables en base si elles n'existent pas encore."""
    create_db_and_tables()
    typer.echo("Tables créées (ou déjà existantes).")


# --------------------------------------------------------------------------- #
# Espece
# --------------------------------------------------------------------------- #

@espece_app.command("ajouter")
def espece_ajouter(
    nom: str,
    famille: str = typer.Option(None, help="Ex. Solanacées."),
    exposition: Exposition = typer.Option(Exposition.SOLEIL),
    frequence_arrosage_jours: int = typer.Option(None, help="Ex. 3 pour un arrosage tous les 3 jours."),
    mois_semis: str = typer.Option(None, help="Mois séparés par des virgules, ex. '3,4'."),
    mois_plantation: str = typer.Option(None, help="Ex. '4,5'."),
    mois_recolte: str = typer.Option(None, help="Ex. '7,8,9'."),
    duree_recolte_jours: int = typer.Option(None),
    source: str = typer.Option(None, help="D'où vient l'info : livre, site, IA..."),
):
    """Ajoute une nouvelle espèce au référentiel (saisie manuelle pour l'instant)."""
    espece = Espece(
        nom=nom,
        famille=famille,
        exposition=exposition,
        frequence_arrosage_jours=frequence_arrosage_jours,
        mois_semis=_parse_mois(mois_semis),
        mois_plantation=_parse_mois(mois_plantation),
        mois_recolte=_parse_mois(mois_recolte),
        duree_recolte_jours=duree_recolte_jours,
        source=source,
    )
    with Session(engine) as session:
        session.add(espece)
        session.commit()
        session.refresh(espece)
    typer.echo(f"Espèce '{espece.nom}' ajoutée (id={espece.id}).")


@espece_app.command("lister")
def espece_lister():
    """Liste toutes les espèces du référentiel."""
    with Session(engine) as session:
        especes = session.exec(select(Espece)).all()
    if not especes:
        typer.echo("Aucune espèce enregistrée. Utilise 'espece ajouter' pour commencer.")
        raise typer.Exit()
    for e in especes:
        typer.echo(
            f"[{e.id}] {e.nom} — exposition: {e.exposition.value if e.exposition else '?'} "
            f"— arrosage tous les {e.frequence_arrosage_jours or '?'} j "
            f"— semis: {e.mois_semis or '?'} — récolte: {e.mois_recolte or '?'}"
        )


# --------------------------------------------------------------------------- #
# PlanteJardin
# --------------------------------------------------------------------------- #

@plante_app.command("ajouter")
def plante_ajouter(
    espece_id: int,
    emplacement: Emplacement = typer.Option(Emplacement.EXTERIEUR),
    zone: str = typer.Option(None, help="Ex. 'potager nord', 'salon'."),
    date_plantation: str = typer.Option(str(date.today()), help="Format AAAA-MM-JJ."),
    statut: StatutPlante = typer.Option(StatutPlante.SEMIS),
):
    """Ajoute une plante à ton jardin, liée à une espèce existante du référentiel."""
    with Session(engine) as session:
        espece = session.get(Espece, espece_id)
        if espece is None:
            typer.echo(f"Aucune espèce avec l'id {espece_id}. Utilise 'espece lister' pour voir les id valides.")
            raise typer.Exit(code=1)

        plante = PlanteJardin(
            espece_id=espece_id,
            emplacement=emplacement,
            zone=zone,
            date_plantation=date.fromisoformat(date_plantation),
            statut=statut,
        )
        session.add(plante)
        session.commit()
        session.refresh(plante)
        nom_espece = espece.nom

    typer.echo(f"Plante ajoutée (id={plante.id}) — {nom_espece} en {emplacement.value}.")


@plante_app.command("lister")
def plante_lister():
    """Liste les plantes du jardin avec le nom de leur espèce."""
    with Session(engine) as session:
        plantes = session.exec(select(PlanteJardin)).all()
        if not plantes:
            typer.echo("Aucune plante enregistrée. Utilise 'plante ajouter' pour commencer.")
            raise typer.Exit()
        for p in plantes:
            espece = session.get(Espece, p.espece_id)
            typer.echo(
                f"[{p.id}] {espece.nom if espece else '?'} — {p.emplacement.value} "
                f"({p.zone or 'zone non précisée'}) — planté le {p.date_plantation} "
                f"— statut: {p.statut.value}"
            )


if __name__ == "__main__":
    app()