"""Calcul de la todo du jour.

Deux familles de tâches :
- Arrosage : récurrent, basé sur frequence_arrosage_jours + dernier événement d'arrosage
  (ou date_plantation si aucun arrosage encore enregistré, ou immédiatement due si ni l'un ni l'autre).
- Semis / plantation / récolte / taille : basées sur le calendrier de l'Espece (mois_xxx),
  dues tant qu'aucun événement du même type n'a déjà été enregistré cette année pour cette plante.
"""

from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from courgette.models import Espece, Evenement, PlanteJardin, TypeEvenement

# Correspondance entre un type de tâche calendaire et le champ de mois de l'Espece.
TACHES_CALENDAIRES = {
    TypeEvenement.SEMIS: "mois_semis",
    TypeEvenement.PLANTATION: "mois_plantation",
    TypeEvenement.RECOLTE: "mois_recolte",
    TypeEvenement.TAILLE: "mois_taille",
}
 
 
def taches_du_jour(session: Session, aujourdhui: date | None = None) -> list[dict]:
    """Retourne la liste des tâches dues aujourd'hui, tous jardins confondus."""
    aujourdhui = aujourdhui or date.today()
    taches: list[dict] = []
 
    plantes = session.exec(select(PlanteJardin)).all()
 
    # Tous les événements de l'année en cours, pour savoir ce qui a déjà été fait.
    debut_annee = datetime(aujourdhui.year, 1, 1)
    evenements_annee = session.exec(select(Evenement).where(Evenement.date >= debut_annee)).all()
    deja_fait_cette_annee = {(e.plante_jardin_id, e.type) for e in evenements_annee}
 
    # Dernier arrosage par plante, toutes années confondues.
    tous_arrosages = session.exec(select(Evenement).where(Evenement.type == TypeEvenement.ARROSAGE)).all()
    dernier_arrosage: dict[int, datetime] = {}
    for e in tous_arrosages:
        if e.plante_jardin_id not in dernier_arrosage or e.date > dernier_arrosage[e.plante_jardin_id]:
            dernier_arrosage[e.plante_jardin_id] = e.date
 
    for plante in plantes:
        espece = session.get(Espece, plante.espece_id)
        if espece is None:
            continue
 
        base = {
            "plante_jardin_id": plante.id,
            "espece_nom": espece.nom,
            "quantite": plante.quantite,
            "zone": plante.zone,
            "emplacement": plante.emplacement.value,
        }
 
        # --- Arrosage (récurrent) ---
        frequence = plante.frequence_arrosage_jours_override or espece.frequence_arrosage_jours
        if frequence:
            reference = dernier_arrosage.get(plante.id)
            if reference is None and plante.date_plantation:
                reference = datetime.combine(plante.date_plantation, datetime.min.time())
 
            if reference is None:
                du = True  # Ni arrosage ni date de plantation connue : tâche due par défaut.
            else:
                prochaine_echeance = reference.date() + timedelta(days=frequence)
                du = prochaine_echeance <= aujourdhui
 
            if du:
                taches.append({**base, "type": TypeEvenement.ARROSAGE.value})
 
        # --- Tâches calendaires (semis, plantation, récolte, taille) ---
        for type_tache, champ_mois in TACHES_CALENDAIRES.items():
            mois_liste = getattr(espece, champ_mois) or []
            if aujourdhui.month in mois_liste and (plante.id, type_tache) not in deja_fait_cette_annee:
                taches.append({**base, "type": type_tache.value})
 
    return taches
 
 
def prochaine_echeance_arrosage(session: Session, plante: PlanteJardin, aujourdhui: date | None = None) -> dict:
    """Detail helper for the per-plant view: current watering rule and next due date.
 
    Not used by taches_du_jour() (which recomputes this inline for all plants
    at once) — this is the single-plant version for display purposes.
    """
    aujourdhui = aujourdhui or date.today()
    espece = session.get(Espece, plante.espece_id)
    frequence = plante.frequence_arrosage_jours_override or (espece.frequence_arrosage_jours if espece else None)
 
    if not frequence:
        return {"frequence_jours": None, "dernier_arrosage": None, "prochaine_echeance": None, "due": False}
 
    dernier = session.exec(
        select(Evenement)
        .where(Evenement.plante_jardin_id == plante.id, Evenement.type == TypeEvenement.ARROSAGE)
        .order_by(Evenement.date.desc())
    ).first()
 
    if dernier is not None:
        reference = dernier.date.date()
    elif plante.date_plantation:
        reference = plante.date_plantation
    else:
        return {"frequence_jours": frequence, "dernier_arrosage": None, "prochaine_echeance": None, "due": True}
 
    prochaine = reference + timedelta(days=frequence)
    return {
        "frequence_jours": frequence,
        "dernier_arrosage": reference.isoformat(),
        "prochaine_echeance": prochaine.isoformat(),
        "due": prochaine <= aujourdhui,
    }
 