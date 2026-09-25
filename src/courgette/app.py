"""API FastAPI + page unique pour gérer les plantes et le journal d'événements.

Espece reste géré en CLI (usage technique). Ici : consultation des especes
(pour peupler un menu déroulant), gestion des plantes du jardin, et journal.

Lancement :
    uv run uvicorn courgette.app:app --reload
Puis ouvrir http://localhost:8000
"""

from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from courgette.db import create_db_and_tables, get_session
from courgette.models import (
    Contenant,
    Emplacement,
    Espece,
    Evenement,
    PlanteJardin,
    StatutPlante,
    TypeEvenement,
)

from courgette.smart_todo import todays_tasks
from courgette import alertes, fiche_plante, weather, rappels
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Jardin Assistant")
 
 
@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
 
 
# --------------------------------------------------------------------------- #
# Schémas de requête
# --------------------------------------------------------------------------- #
 
class NouvellePlante(BaseModel):
    espece_id: int
    emplacement: Emplacement
    contenant: Contenant = Contenant.PLEINE_TERRE
    zone: str | None = None
    date_plantation: date | None = None
    quantite: int = 1
    statut: StatutPlante = StatutPlante.SEMIS
 
 
class ModificationPlante(BaseModel):
    """Tous les champs sont optionnels : seuls ceux fournis sont modifiés."""
 
    statut: StatutPlante | None = None
    emplacement: Emplacement | None = None
    contenant: Contenant | None = None
    zone: str | None = None
    frequence_arrosage_jours_override: int | None = None
 
 
class NouvelleBouture(BaseModel):
    emplacement: Emplacement = Emplacement.INTERIEUR
    contenant: Contenant = Contenant.POT
    zone: str | None = None
    frequence_arrosage_jours_override: int | None = None
    note: str | None = None
 
 
class NouvelEvenement(BaseModel):
    type: TypeEvenement
    note: str | None = None
 
 
# --------------------------------------------------------------------------- #
# API — especes (lecture seule ici, création réservée au CLI)
# --------------------------------------------------------------------------- #
 
@app.get("/api/especes")
def lister_especes(session: Session = Depends(get_session)):
    especes = session.exec(select(Espece)).all()
    return [{"id": e.id, "nom": e.nom} for e in especes]
 
 
# --------------------------------------------------------------------------- #
# API — plantes
# --------------------------------------------------------------------------- #
 
@app.get("/api/plantes")
def lister_plantes(session: Session = Depends(get_session)):
    plantes = session.exec(select(PlanteJardin)).all()
    resultat = []
    for p in plantes:
        espece = session.get(Espece, p.espece_id)
        resultat.append(
            {
                "id": p.id,
                "espece_nom": espece.nom if espece else "?",
                "emplacement": p.emplacement.value,
                "contenant": p.contenant.value,
                "zone": p.zone,
                "date_plantation": p.date_plantation.isoformat() if p.date_plantation else None,
                "quantite": p.quantite,
                "statut": p.statut.value,
            }
        )
    return resultat
 
 
@app.post("/api/plantes")
def ajouter_plante(payload: NouvellePlante, session: Session = Depends(get_session)):
    espece = session.get(Espece, payload.espece_id)
    if espece is None:
        raise HTTPException(status_code=404, detail="Espèce introuvable.")
 
    plante = PlanteJardin(
        espece_id=payload.espece_id,
        emplacement=payload.emplacement,
        contenant=payload.contenant,
        zone=payload.zone,
        date_plantation=payload.date_plantation,
        quantite=payload.quantite,
        statut=payload.statut,
    )
    session.add(plante)
    session.commit()
    session.refresh(plante)
    return {"id": plante.id}
 
 
@app.patch("/api/plantes/{plante_id}")
def modifier_plante(
    plante_id: int, payload: ModificationPlante, session: Session = Depends(get_session)
):
    """Change l'état d'une plante existante (ex. bouture -> croissance après
    plantation finale). Ne crée rien — contrairement à /bouturer.
    """
    plante = session.get(PlanteJardin, plante_id)
    if plante is None:
        raise HTTPException(status_code=404, detail="Plante introuvable.")
 
    updates = payload.model_dump(exclude_unset=True)
    for champ, valeur in updates.items():
        setattr(plante, champ, valeur)
 
    session.add(plante)
    session.commit()
    return {"id": plante.id}
 
 
@app.post("/api/plantes/{plante_id}/bouturer")
def bouturer_plante(
    plante_id: int, payload: NouvelleBouture, session: Session = Depends(get_session)
):
    """Prend une bouture : crée une nouvelle PlanteJardin (statut 'bouture')
    liée à la plante mère, et enregistre l'événement sur la plante mère.
    """
    parent = session.get(PlanteJardin, plante_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Plante introuvable.")
 
    enfant = PlanteJardin(
        espece_id=parent.espece_id,
        emplacement=payload.emplacement,
        contenant=payload.contenant,
        zone=payload.zone,
        statut=StatutPlante.BOUTURE,
        quantite=1,
        frequence_arrosage_jours_override=payload.frequence_arrosage_jours_override,
        plante_parent_id=parent.id,
    )
    session.add(enfant)
    session.commit()
    session.refresh(enfant)
    enfant_id = enfant.id
 
    session.add(
        Evenement(
            plante_jardin_id=parent.id,
            type=TypeEvenement.BOUTURAGE,
            plante_creee_id=enfant_id,
            note=payload.note,
        )
    )
    session.commit()
    return {"id": enfant_id}
 
 
@app.get("/api/plantes/{plante_id}/detail")
def detail_plante(plante_id: int, session: Session = Depends(get_session)):
    """Full identity card for one plant: current state, watering status,
    lineage (bouture), and the species fiche (Trefle/Wikipedia).
    """
    plante = session.get(PlanteJardin, plante_id)
    if plante is None:
        raise HTTPException(status_code=404, detail="Plante introuvable.")
 
    espece = session.get(Espece, plante.espece_id)
    arrosage = rappels.prochaine_echeance_arrosage(session, plante)
 
    enfants = session.exec(
        select(PlanteJardin).where(PlanteJardin.plante_parent_id == plante_id)
    ).all()
 
    return {
        "id": plante.id,
        "espece_nom": espece.nom if espece else "?",
        "emplacement": plante.emplacement.value,
        "contenant": plante.contenant.value,
        "zone": plante.zone,
        "quantite": plante.quantite,
        "statut": plante.statut.value,
        "date_plantation": plante.date_plantation.isoformat() if plante.date_plantation else None,
        "plante_parent_id": plante.plante_parent_id,
        "boutures_filles": [e.id for e in enfants],
        "arrosage": arrosage,
        "fiche_espece": fiche_plante.get_fiche(espece.nom) if espece else None,
    }
 
 
# --------------------------------------------------------------------------- #
# API — evenements
# --------------------------------------------------------------------------- #
 
@app.get("/api/plantes/{plante_id}/evenements")
def lister_evenements(plante_id: int, session: Session = Depends(get_session)):
    evenements = session.exec(
        select(Evenement)
        .where(Evenement.plante_jardin_id == plante_id)
        .order_by(Evenement.date.desc())
    ).all()
    return [
        {"id": e.id, "type": e.type.value, "date": e.date.isoformat(), "note": e.note}
        for e in evenements
    ]
 
 
@app.post("/api/plantes/{plante_id}/evenements")
def ajouter_evenement(
    plante_id: int, payload: NouvelEvenement, session: Session = Depends(get_session)
):
    plante = session.get(PlanteJardin, plante_id)
    if plante is None:
        raise HTTPException(status_code=404, detail="Plante introuvable.")
 
    evenement = Evenement(
        plante_jardin_id=plante_id,
        type=payload.type,
        note=payload.note,
        date=datetime.utcnow(),
    )
    session.add(evenement)
    session.commit()
    session.refresh(evenement)
    return {"id": evenement.id}
 
 
# --------------------------------------------------------------------------- #
# API — todo du jour
# --------------------------------------------------------------------------- #
 
@app.get("/api/todo")
def todo_du_jour(session: Session = Depends(get_session)):
    return todays_tasks(session)
 
 
# --------------------------------------------------------------------------- #
# API — alertes gel/canicule (jardin entier, pas liées à une plante précise)
# --------------------------------------------------------------------------- #
 
@app.get("/api/alertes")
def alertes_meteo():
    return alertes.get_alerts()
 
 
# --------------------------------------------------------------------------- #
# API — météo brute (debug)
# --------------------------------------------------------------------------- #
 
@app.get("/api/meteo")
def meteo_debug():
    """Raw weather data for troubleshooting: past 15 days + next 48h forecast.
 
    Read-only — unlike the sync job (meteo_sync.synchroniser_meteo), this
    never creates automatic watering events, so it's safe to refresh anytime.
    """
    jours = weather.get_weather(past_days=15, forecast_days=2)
    aujourdhui = date.today()
    return [
        {
            "date": j.day.isoformat(),
            "precipitation_mm": j.precipitation_mm,
            "temp_min_c": j.temp_min_c,
            "temp_max_c": j.temp_max_c,
            "periode": "passe" if j.day < aujourdhui else ("aujourdhui" if j.day == aujourdhui else "prevision"),
        }
        for j in jours
    ]
 
 
# --------------------------------------------------------------------------- #
# Page unique
# --------------------------------------------------------------------------- #
 
@app.get("/", response_class=HTMLResponse)
def page_accueil():
    chemin = Path(__file__).parent / "static" / "index.html"
    return chemin.read_text(encoding="utf-8")
 
 
@app.get("/meteo", response_class=HTMLResponse)
def page_meteo():
    """Standalone debug page: raw weather data, separate from the main app page."""
    chemin = Path(__file__).parent / "static" / "meteo.html"
    return chemin.read_text(encoding="utf-8")
 
 
@app.get("/plante/{plante_id}", response_class=HTMLResponse)
def page_plante(plante_id: int):
    """Per-plant identity card page. The id is read client-side from the URL."""
    chemin = Path(__file__).parent / "static" / "plante.html"
    return chemin.read_text(encoding="utf-8")
