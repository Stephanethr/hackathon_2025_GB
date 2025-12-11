# Gbook

Application de gestion d'espace de travail intelligente (NLP + Booking Engine).

## Installation

1.  **Prérequis**: Python 3.11+
2.  **Installation des dépendances**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configuration**:
    Créer un fichier `.env` à la racine contenant :
    ```env
    OPENAI_API_KEY=votre_cle_api_openai
    SECRET_KEY=votre_secret_key_securise
    DATABASE_URL=sqlite:///gbook.db
    ```

4.  **Initialisation de la Base de Données**:
    ```bash
    # Crée la DB et un admin (admin/password) + salles de démo
    python seed.py
    ```

## Démarrage

Lancer le serveur de développement :
```bash
python run.py
```
Accéder à l'application via : `http://localhost:5000`

## Tests

Lancer les tests unitaires (vérification des règles métier) :
```bash
pytest
```

## Architecture & DevOps

### Structure
- `app/services`: Logique métier (NLP via ChatGPT, Booking System).
- `app/api/routes`: Endpoints API (Auth, Chat, Bookings).
- `app/models`: Schémas de base de données.
- `app/utils`: Fonctions utilitaires et décorateurs.
- `app/static` & `app/templates`: Frontend simple.

### Déploiement (Production)
- Utiliser **Gunicorn** comme serveur WSGI :
  ```bash
  gunicorn -w 4 -b 0.0.0.0:8000 run:app
  ```
- **Base de données**: Passer de SQLite à PostgreSQL via `DATABASE_URL` env var.
- **Docker**: Utiliser une image `python:3.11-slim`.

### Sécurité
- [x] JWT Auth (Token Based)
- [x] Password Hashing (PBKDF2)
- [x] Input Validation (Basic regex + Type checking)

## API Documentation
Voir le fichier `openapi.yaml` pour la spécification Swagger des endpoints.
