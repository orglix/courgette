# Spec — App IA d'aide au jardinage

## 1. Objectif du projet

Application personnelle d'aide à la gestion du jardin/plantes, combinant règles classiques (calendrier, arrosage) et IA (analyse photo, recherche automatique d'infos, conseils contextualisés). Projet à double vocation : outil utile au quotidien, et projet d'apprentissage progressif (CRUD → RAG → vision → agents) dans le cadre d'un retour vers des missions Python/IA.

## 2. Fonctionnalités envisagées

### Catalogue & suivi
- Fiche par espèce de plante (référentiel)
- Fiche par plante réellement présente dans le jardin (instance)
- Journal de bord (arrosages, tailles, traitements, engrais, récoltes)
- Suivi visuel dans le temps (photos horodatées, comparaison avant/après)

### Diagnostic & conseil (IA)
- Identification d'espèce par photo (paquet de graines ou plante elle-même)
- Détection de maladies/carences/parasites par photo
- Chatbot conversationnel sur les questions de jardinage (RAG)

### Planification
- Calendrier de semis/plantation/récolte selon les mois et la saison
- Génération de plan de potager avec compagnonnage
- Rotation des cultures d'une année sur l'autre

### Météo-dépendant
- Arrosage ajusté à la pluie prévue/passée
- Alertes gel/canicule/grêle avec actions recommandées
- Suggestion du meilleur moment pour une tâche selon la météo

### Post-récolte
- Guide de conservation/stockage selon le légume/fruit
- Idées de recettes ou conservation selon la récolte du moment

### Transverse
- Rappels/notifications proactifs
- Mode "débutant" (pédagogique) vs mode "expert" (condensé)

## 3. Feuille de route (par phase de développement)

**Phase 1 — MVP sans IA**
Catalogue de plantes (CRUD), calendrier de référence statique, règles d'arrosage simples par espèce, rappels basiques.
*Objectifs d'apprentissage : modélisation de données, CRUD, Python 3 moderne.*

**Phase 2 — Météo + premier usage LLM**
Intégration météo (Open-Meteo), chatbot LLM avec RAG sur base de connaissances jardinage, génération de liste de travaux du mois croisant saison + météo + localisation.
*Objectifs d'apprentissage : RAG, prompt engineering, appels d'API météo.*

**Phase 3 — Multimodal (photo)**
Identification de plante par photo (API externe), diagnostic maladie/carence par photo, suivi de croissance par comparaison de photos.
*Objectifs d'apprentissage : vision, modèles multimodaux.*

**Phase 4 — Agentique**
Agent autonome croisant météo + historique + photo pour décider des actions, génération de plan de potager avec compagnonnage, extension capteurs/domotique en option.
*Objectifs d'apprentissage : agents, tool-calling, orchestration multi-source.*

## 4. Modèle de données (Phase 1)

- **Espèce** (référentiel) : nom, famille, exposition idéale, fréquence d'arrosage type, mois de semis/plantation/récolte, durée avant récolte.
  - Modifiable à tout moment, sans historique des modifications.
  - En cas de mise à jour, privilégier la source la plus "solide" disponible (pas nécessairement la première trouvée).
  - Pensée pour être peuplée aussi bien manuellement que plus tard via l'IA (photo de paquet de graines, recherche automatique) — même point d'entrée dans la table quelle que soit la source.
- **PlanteJardin** (instance) : lien vers une Espèce, emplacement (intérieur/extérieur, zone du jardin), date de plantation, statut (semis/en croissance/récolté).
- **Evenement** (journal) : lien vers PlanteJardin, type (arrosage/taille/traitement/récolte), date, note libre.
- **Rappel** : lien vers PlanteJardin, type d'action, prochaine échéance, récurrence.

Séparation Espèce/PlanteJardin volontaire : évite la duplication des infos de référence, centralise les corrections, et prépare le branchement de sources IA en Phase 3 sans changer le schéma.

## 5. Stack technique

- **Python 3.12+**, typage statique partout
- **uv** pour la gestion du projet et des dépendances
- **SQLModel** (SQLAlchemy + Pydantic) pour l'ORM et la validation
- **PostgreSQL + pgvector** (via Docker, image `pgvector/pgvector`) comme base de données, choisi dès la Phase 1 pour éviter une migration de moteur quand les besoins vectoriels (RAG) arriveront en Phase 2
- **psycopg[binary]** comme driver Postgres
- **FastAPI** pour l'API REST (ajoutée après la validation du CLI)
- **Typer** pour le CLI (première interface utilisable, en Phase 1)
- **pytest** pour les tests
- **python-dotenv** pour la configuration (`.env`, non commité)
- **Docker Desktop** pour faire tourner Postgres en local

## 6. Références externes identifiées (recherche GitHub)

Projets existants étudiés pour inspiration, sans qu'aucun ne couvre l'ensemble des besoins :
- **plant-it** (MDeLuise) — modèle de données plante/événement/rappel
- **jadu** (komalali) — assistant CLI Claude, tool-calling écrit à la main, référence d'architecture agent sans framework
- **gardenailocal** (magnusseptim) — LLM local (Ollama) + météo Open-Meteo
- **Demeter / Demetra.AI** — combinaison météo + base botanique (Trefle) + LLM
- **monty** (auto-d) — pattern agent/gatekeeper avec AutoGen

APIs/bases externes à réutiliser plutôt que réinventer :
- **Pl@ntNet** pour l'identification de plante par photo (Phase 3)
- **Open-Meteo** pour la météo (gratuit, sans clé)
- **Trefle** / **OpenFarm** comme bases botaniques existantes, en appui de la table Espèce

## 7. Décisions actées

- Table Espèce sans historique de versions, mise à jour libre à tout moment.
- Priorité à la source la plus fiable lors du remplissage/mise à jour d'une Espèce, quelle que soit son origine (saisie manuelle, photo, recherche web).
- PostgreSQL + pgvector retenu dès la Phase 1 plutôt que SQLite, pour éviter une migration ultérieure et développer une compétence plus transférable sur le marché de l'emploi.
- CLI (Typer) développé avant l'API REST (FastAPI), pour valider le modèle de données et la logique métier sans complexité additionnelle.

## 8. Points en attente

- Décider si le `docker-compose.yml` et un `.env.example` sont committés dans le dépôt GitHub public du projet.