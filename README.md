# 🚀 Brieflyy - AI-Powered Job Search Reasoning System

**Brieflyy** est une plateforme innovante conçue pour révolutionner la recherche d'emploi pour les étudiants et les jeunes professionnels. En utilisant une architecture multi-agents basée sur l'intelligence artificielle (Google Gemini), Brieflyy automatise la recherche d'offres, l'analyse de compatibilité (Fit Score) et l'adaptation de CV pour maximiser les chances de succès des candidats.

---

## 🌟 Fonctionnalités Clés

- **🤖 Pipeline Multi-Agents (Orchestration AI)** : Une suite de 6 agents spécialisés travaillant de concert pour automatiser le cycle complet de recherche d'emploi.
- **🔍 Agrégateur de Jobs Intelligent** : Recherche simultanée sur plus de 15 sources majeures (LinkedIn, Indeed, Glassdoor, Wellfound, Remote OK, etc.).
- **📊 Analyse de Fit (Reasoning Engine)** : Évaluation sémantique approfondie entre votre profil et les exigences du poste avec un score de compatibilité détaillé.
- **📄 CV Tailoring Automatique** : Génération de CV personnalisés au format PDF, optimisés avec les mots-clés ATS (Applicant Tracking System) spécifiques à chaque offre.
- **📈 Gestion des Candidatures** : Suivi centralisé des offres d'emploi, des CVs générés et du statut des candidatures.
- **🎯 Stratégie de Carrière Personnalisée** : Génération de plans d'action stratégiques basés sur votre profil et vos aspirations.
- **⚡ Performance Temps Réel** : Utilisation de Redis pour le suivi en direct de la progression du pipeline AI.

---

## 🛠️ Stack Technique

### Backend (Python)
- **Framework** : [FastAPI](https://fastapi.tixtl.com/) (Asynchrone, performant)
- **Base de données** : [PostgreSQL](https://www.postgresql.org/) avec [SQLAlchemy](https://www.sqlalchemy.org/) & [Alembic](https://alembic.sqlalchemy.org/)
- **Cache & Messaging** : [Redis](https://redis.io/) (Gestion des sessions et du cache)
- **IA & NLP** : [Google Gemini (Vertex AI)](https://cloud.google.com/vertex-ai), [FAISS](https://github.com/facebookresearch/faiss) (Vector search)
- **Parsing & PDF** : [PDFPlumber](https://github.com/jsvine/pdfplumber), [ReportLab](https://www.reportlab.com/)

### Frontend (TypeScript)
- **Framework** : [Angular 17](https://angular.io/)
- **UI/UX** : [Bootstrap 5](https://getbootstrap.com/), [Angular Material](https://material.angular.io/)
- **State Management** : Services RxJS réactifs

### Infrastructure & DevOps
- **Conteneurisation** : [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- **Cloud** : [Google Cloud Storage](https://cloud.google.com/storage) (Stockage des CVs)

---

## 🏗️ Architecture du Système

Le projet repose sur un **Orchestrateur de Pipeline** qui gère le cycle de vie des agents :

1.  **Agent 1 (Profile Parser)** : Extrait et structure les données de votre CV PDF.
2.  **Agent 2 (Job Searcher)** : Explore le web pour trouver des opportunités pertinentes.
3.  **Agent 3 (Job Analyzer)** : Analyse en profondeur les descriptions de poste.
4.  **Agent 4 (Fit Engine)** : Calcule le score de compatibilité et identifie les manques.
5.  **Agent 5 (Strategy Planner)** : Élabore une approche tactique pour postuler.
6.  **Agent 6 (CV Tailor)** : Réécrit dynamiquement le CV pour l'adapter à l'offre cible.

---

## 🚀 Installation et Démarrage

### Pré-requis
- Docker & Docker Compose
- Clé API Google Cloud (Vertex AI / Gemini)

### Lancement avec Docker (Recommandé)

1.  Cloner le dépôt :
    ```bash
    git clone https://github.com/votre-username/brieflyy.git
    cd brieflyy
    ```

2.  Configurer les variables d'environnement :
    Créez un fichier `.env` dans le dossier `backend/` en vous basant sur `backend/.env.example` (si disponible).

3.  Démarrer les services :
    ```bash
    docker-compose up --build
    ```

L'application sera accessible sur :
- Frontend : `http://localhost:4200`
- Backend API : `http://localhost:8000`
- Documentation API (Swagger) : `http://localhost:8000/docs`

---
*Développé avec passion dans le cadre du **USAII Hackathon**
