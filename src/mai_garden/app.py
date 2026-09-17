"""API FastAPI + page unique pour gérer les plantes et le journal d'événements.

Espece reste géré en CLI (usage technique). Ici : consultation des especes
(pour peupler un menu déroulant), gestion des plantes du jardin, et journal.

Lancement :
    uv run uvicorn mai_garden.app:app --reload
Puis ouvrir http://localhost:8000
"""

from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from mai_garden.db import create_db_and_tables, get_session
from mai_garden.models import (
    Emplacement,
    Espece,
    Evenement,
    PlanteJardin,
    StatutPlante,
    TypeEvenement,
)

from mai_garden.rappels import taches_du_jour
 
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
    zone: str | None = None
    date_plantation: date | None = None
    quantite: int = 1
    statut: StatutPlante = StatutPlante.SEMIS
 
 
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
        zone=payload.zone,
        date_plantation=payload.date_plantation,
        quantite=payload.quantite,
        statut=payload.statut,
    )
    session.add(plante)
    session.commit()
    session.refresh(plante)
    return {"id": plante.id}
 
 
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
    return taches_du_jour(session)
 
 
# --------------------------------------------------------------------------- #
# Page unique
# --------------------------------------------------------------------------- #
 
@app.get("/", response_class=HTMLResponse)
def page_accueil():
    chemin = Path(__file__).parent / "static" / "index.html"
    return chemin.read_text(encoding="utf-8")
