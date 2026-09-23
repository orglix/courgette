"""CLI de gestion du jardin (Phase 1).

Usage :
    uv run python cli.py init-db
    uv run python cli.py espece ajouter Tomate --exposition soleil --mois-semis 3,4 --mois-recolte 7,8,9
    uv run python cli.py espece lister
    uv run python cli.py plante ajouter 1 --emplacement exterieur --zone "potager nord"
    uv run python cli.py plante lister
"""

from datetime import date, datetime

import typer
import logging
from sqlmodel import Session, select

from courgette.db import create_db_and_tables, engine
from courgette.models import (
    Emplacement,
    Espece,
    Evenement,
    Exposition,
    PlanteJardin,
    StatutPlante,
    TypeEvenement,
)
# from courgette.rappels import taches_du_jour
from courgette.smart_todo import todays_tasks
from courgette.meteo_sync import synchroniser_meteo


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
 
app = typer.Typer(help="Assistant de gestion du jardin.")
espece_app = typer.Typer(help="Gérer le référentiel d'espèces.")
plante_app = typer.Typer(help="Gérer les plantes de ton jardin.")
evenement_app = typer.Typer(help="Gérer le journal d'événements (arrosage, taille, récolte...).")
rappel_app = typer.Typer(help="Voir les tâches dues.")
meteo_app = typer.Typer(help="Synchronisation météo.")
app.add_typer(espece_app, name="espece")
app.add_typer(plante_app, name="plante")
app.add_typer(evenement_app, name="evenement")
app.add_typer(rappel_app, name="rappel")
app.add_typer(meteo_app, name="meteo")
 
 
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
    date_plantation: str = typer.Option(None, help="Format AAAA-MM-JJ. Omis si date inconnue."),
    quantite: int = typer.Option(1, help="Nombre de pieds plantés ensemble."),
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
            date_plantation=date.fromisoformat(date_plantation) if date_plantation else None,
            quantite=quantite,
            statut=statut,
        )
        session.add(plante)
        session.commit()
        session.refresh(plante)
        nom_espece = espece.nom
 
    typer.echo(f"Plante ajoutée (id={plante.id}) — {quantite}x {nom_espece} en {emplacement.value}.")
 
 
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
            date_affichee = p.date_plantation if p.date_plantation else "date inconnue"
            typer.echo(
                f"[{p.id}] {p.quantite}x {espece.nom if espece else '?'} — {p.emplacement.value} "
                f"({p.zone or 'zone non précisée'}) — planté le {date_affichee} "
                f"— statut: {p.statut.value}"
            )
 
 
# --------------------------------------------------------------------------- #
# Evenement
# --------------------------------------------------------------------------- #
 
@evenement_app.command("ajouter")
def evenement_ajouter(
    plante_jardin_id: int,
    type: TypeEvenement = typer.Argument(..., help="arrosage, taille, traitement, recolte ou autre."),
    note: str = typer.Option(None, help="Note libre, ex. 'sol encore humide, arrosage léger'."),
    date_evenement: str = typer.Option(
        None, "--date", help="Format AAAA-MM-JJ HH:MM. Par défaut : maintenant."
    ),
):
    """Enregistre un événement (arrosage, taille, traitement, récolte) sur une plante."""
    with Session(engine) as session:
        plante = session.get(PlanteJardin, plante_jardin_id)
        if plante is None:
            typer.echo(
                f"Aucune plante avec l'id {plante_jardin_id}. Utilise 'plante lister' pour voir les id valides."
            )
            raise typer.Exit(code=1)
 
        evenement = Evenement(
            plante_jardin_id=plante_jardin_id,
            type=type,
            date=datetime.fromisoformat(date_evenement) if date_evenement else datetime.utcnow(),
            note=note,
        )
        session.add(evenement)
        session.commit()
        session.refresh(evenement)
 
    typer.echo(f"Événement '{type.value}' enregistré (id={evenement.id}) pour la plante {plante_jardin_id}.")
 
 
@evenement_app.command("lister")
def evenement_lister(plante_jardin_id: int):
    """Liste l'historique des événements d'une plante, du plus récent au plus ancien."""
    with Session(engine) as session:
        plante = session.get(PlanteJardin, plante_jardin_id)
        if plante is None:
            typer.echo(f"Aucune plante avec l'id {plante_jardin_id}.")
            raise typer.Exit(code=1)
 
        evenements = session.exec(
            select(Evenement)
            .where(Evenement.plante_jardin_id == plante_jardin_id)
            .order_by(Evenement.date.desc())
        ).all()
 
    if not evenements:
        typer.echo("Aucun événement enregistré pour cette plante.")
        raise typer.Exit()
 
    for e in evenements:
        note_suffixe = f" — {e.note}" if e.note else ""
        typer.echo(f"[{e.id}] {e.date:%Y-%m-%d %H:%M} — {e.type.value}{note_suffixe}")
 
 
# --------------------------------------------------------------------------- #
# Rappel — todo du jour
# --------------------------------------------------------------------------- #
 
@rappel_app.command("aujourdhui")
def rappel_aujourdhui():
    """Affiche les tâches dues aujourd'hui (arrosage + calendrier)."""
    with Session(engine) as session:
        taches = todays_tasks(session)
 
    if not taches:
        typer.echo("Rien à faire aujourd'hui.")
        raise typer.Exit()
 
    for t in taches:
        typer.echo(
            f"[plante {t['plante_jardin_id']}] {t['type']} — {t['quantite']}x {t['espece_nom']} "
            f"({t['zone'] or t['emplacement']})"
        )
 
 
# --------------------------------------------------------------------------- #
# Météo
# --------------------------------------------------------------------------- #
 
@meteo_app.command("sync")
def meteo_sync_command():
    """Récupère la météo manquante et crée les arrosages automatiques (pluie).
 
    À lancer une fois par jour (ex. via le planificateur de tâches Windows).
    """
    with Session(engine) as session:
        jours = synchroniser_meteo(session)
    typer.echo(f"Synchro météo terminée ({len(jours)} jours récupérés).")
 
 
if __name__ == "__main__":
    app()
