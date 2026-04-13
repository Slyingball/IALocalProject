# IALocalProject — Assistant Cyber & Multi-IA Local

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=flat&logo=flask&logoColor=white)
![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?style=flat&logo=vue.js&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-orange)
![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)

**Une plateforme web mutualisée (Vue.js + Flask) pour orchestrer des LLMs locaux via Ollama, avec des capacités d'exécution d'outils système réels (Nmap, Ping, audit réseau).**

---

## Table des matières

- [Vue d'ensemble](#-vue-densemble)
- [Architecture](#-architecture)
- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#%EF%B8%8F-prérequis)
- [Installation](#%EF%B8%8F-installation)
- [Utilisation](#-utilisation)
- [API REST](#-api-rest)
- [Structure du projet](#-structure-du-projet)
- [Sécurité & Limitations](#%EF%B8%8F-sécurité--limitations)
- [Roadmap](#%EF%B8%8F-roadmap)

---

## Vue d'ensemble

Ce projet est une démonstration d'**Agent IA autonome** fonctionnant à 100% en local. Il connecte un frontend moderne (Vue.js 3 / TypeScript) à un backend API (Flask) qui orchestre les modèles Ollama. Les modèles compatibles peuvent exécuter des **outils** (Function Calling / Tool Use) pour interagir avec le système local : scans réseau Nmap, diagnostics système, audits de sécurité, et découverte de réseau.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Client                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Vue.js 3 + TypeScript (ViewerIALocalProject)         │  │
│  │  ├── App.vue          (State management)              │  │
│  │  ├── AppSidebar.vue   (Modèles, options, commandes)   │  │
│  │  ├── ChatWindow.vue   (Messages, topbar)              │  │
│  │  ├── ChatInput.vue    (Saisie avec auto-resize)       │  │
│  │  ├── MessageBubble.vue(Rendu des messages)            │  │
│  │  ├── PromptAdminModal.vue (CRUD prompts système)      │  │
│  │  └── useApi.ts        (Composable HTTP/API)           │  │
│  └─────────────────────┬──────────────────────────────────┘  │
│                        │  npm run build-only                 │
│                        ▼                                     │
│            static/vue/ (index.html + assets)                 │
└──────────────────────────┬───────────────────────────────────┘
                           │  HTTP (port 5000)
┌──────────────────────────▼───────────────────────────────────┐
│                    Serveur Flask (app.py)                     │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Routes API REST                                      │  │
│  │  GET  /           → Sert le build Vue.js              │  │
│  │  GET  /models     → Liste des modèles disponibles     │  │
│  │  POST /ask        → Envoi d'une question à l'IA       │  │
│  │  GET  /history/<m>→ Historique par modèle             │  │
│  │  POST /clear_history → Effacement historique          │  │
│  │  CRUD /prompts    → Gestion des prompts système       │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │  Tool Calling Engine                                  │  │
│  │  ├── run_nmap          (Scan réseau)                  │  │
│  │  ├── run_ping          (Test connectivité ICMP)       │  │
│  │  ├── get_network_interfaces (Interfaces réseau)       │  │
│  │  ├── get_system_status (CPU, RAM, disque)             │  │
│  │  ├── run_reconnaissance_rapide (Bundle: Ping+Nmap+HTTP│  │
│  │  ├── run_local_discovery (Bundle: Discovery LAN)      │  │
│  │  └── run_port_audit   (Bundle: Audit ports admin)     │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │  Persistance                                          │  │
│  │  ├── data/history.json  (Historique conversations)    │  │
│  │  └── data/prompts.json  (Prompts personnalisés)       │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │  HTTP (port 11434)
                    ┌───────▼────────┐
                    │  Ollama (LLMs) │
                    │  ├── llama3    │
                    │  ├── llama3.1  │
                    │  └── llama2    │
                    └────────────────┘
```

**Principes d'architecture :**

- **Separation of Concerns** : Frontend (Vue.js) ↔ Backend API (Flask) ↔ LLM (Ollama), chaque couche est indépendante.
- **API REST stateless** : Le backend expose une API JSON pure, le frontend est un SPA autonome.
- **Build-time integration** : Le build Vite dépose les assets dans `static/vue/`, Flask les sert de manière transparente. Un seul serveur à déployer.

---

## Fonctionnalités

### Multi-Modèles
Basculez instantanément entre différents modèles LLM (Llama 3 rapide, Llama 3.1 avec Tool Calling, Llama 2 non-censuré).

###  Tool Calling (7 outils)
Les modèles compatibles (ex: `llama3.1:8b`) peuvent exécuter des outils réels :

| Outil | Description | Protection |
|-------|-------------|------------|
| `run_nmap` | Scan réseau ciblé (ports, versions, -F, -sV, -Pn) | Regex + timeout 40s |
| `run_ping` | Test de connectivité ICMP | Regex + timeout 10s |
| `get_network_interfaces` | Interfaces réseau et IP locale | Lecture seule |
| `get_system_status` | État système (OS, CPU, RAM, disque) | Lecture seule (psutil) |
| `run_reconnaissance_rapide` | Bundle : Ping + Nmap rapide + HTTP check | Regex + timeouts |
| `run_local_discovery` | Bundle : Auto-détection IP + Ping Sweep LAN | timeout 60s |
| `run_port_audit` | Bundle : Audit ports admin sensibles + alertes sécu | Regex + timeout 90s |

### Prompts Système (CRUD)
Interface d'administration complète pour créer, modifier, dupliquer et supprimer des profils de comportement IA (Général, Cybersécurité, personnalisés).

### Interface Immersive
Design sombre "Glassmorphism", responsive, avec commandes rapides, sidebar collapsible, et animations fluides.

### Persistance
Historique et prompts sauvegardés avec écriture atomique (fichier temporaire → backup → rename) pour éviter la corruption.

---

## Prérequis

1. **Python 3.10+** installé.
2. **Node.js 20+** (uniquement pour modifier le frontend).
3. **Nmap** installé et dans le `PATH`. Vérifiez avec `nmap --version`.
4. **Ollama** en cours d'exécution (`ollama serve`).

### Modèles Ollama requis

```bash
# Tool Calling + polyvalence (Recommandé)
ollama pull llama3.1:8b

# Vitesse d'exécution (pas de Tool Calling)
ollama pull llama3:latest

# Mode sans filtre
ollama pull llama2-uncensored:latest
```

---

## Installation

### Backend (Flask)

```bash
git clone https://github.com/Slyingball/IALocalProject.git
cd IALocalProject

python -m venv .venv
# Windows : .venv\Scripts\activate
# Linux/Mac : source .venv/bin/activate

pip install -r requirements.txt
```

### Frontend (Vue.js) — uniquement si vous modifiez l'interface

```bash
cd ../ViewerIALocalProject
npm install
```

---

## Utilisation

### Démarrage

```bash
cd IALocalProject
python app.py
# → http://localhost:5000
```

### Développement frontend (hot-reload)

```bash
cd ViewerIALocalProject
npm run dev        # Vite dev server sur :5173 (proxy auto vers Flask :5000)
```

### Re-build du frontend

```bash
cd ViewerIALocalProject
npm run build-only  # Build dans IALocalProject/static/vue/
```

### Guide de l'interface

1. **Sélection du modèle** : Sidebar gauche → Cliquez sur un modèle.
   > ⚠️ Choisissez **LLaMA 3.1 8B** pour les outils (scans, audits). Les autres modèles ne supportent pas le Tool Calling.
2. **Mode système** : Sélecteur dans la sidebar → Général ou Cybersécurité.
3. **Commandes rapides** : 6 cartes dans la sidebar pour pré-remplir des scans courants.
4. **Gestion des Prompts** : Bouton ⚙️ en bas de la sidebar → Modal CRUD.
5. **Lancer un scan** : Demandez simplement à l'IA, ex : *"Scan l'hôte 192.168.1.15 rapidement."*

---

## API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/models` | Liste des modèles disponibles |
| `POST` | `/ask` | Poser une question à l'IA |
| `GET` | `/history/<model_key>` | Historique d'un modèle |
| `POST` | `/clear_history` | Effacer l'historique |
| `GET` | `/prompts` | Lister les prompts système |
| `POST` | `/prompts` | Créer/modifier un prompt |
| `DELETE` | `/prompts/<id>` | Supprimer un prompt |
| `POST` | `/prompts/<id>/duplicate` | Dupliquer un prompt |

### Exemple — Poser une question

```bash
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1",
    "question": "Scan 192.168.1.1 rapidement",
    "use_context": true,
    "system_mode": "cybersecurity"
  }'
```

---

## Structure du projet

```
IALocalProject/
├── app.py                  # Backend Flask (API, Tool Calling, persistance)
├── requirements.txt        # Dépendances Python (flask, flask-cors, requests, psutil)
├── data/
│   ├── history.json        # Historique des conversations (auto-généré)
│   └── prompts.json        # Prompts personnalisés (auto-généré)
├── static/
│   └── vue/                # Build de production Vue.js (auto-généré)
│       ├── index.html
│       └── assets/         # JS + CSS bundlés
└── templates/              # (Legacy — remplacé par Vue.js)

ViewerIALocalProject/       # Code source du frontend
├── src/
│   ├── App.vue             # Composant racine + state management
│   ├── main.ts             # Point d'entrée
│   ├── assets/main.css     # Design system complet
│   ├── components/
│   │   ├── AppSidebar.vue      # Sidebar (modèles, options, commandes)
│   │   ├── ChatWindow.vue      # Zone de chat principale
│   │   ├── ChatInput.vue       # Barre de saisie
│   │   ├── MessageBubble.vue   # Bulle de message
│   │   └── PromptAdminModal.vue # Administration des prompts
│   └── composables/
│       └── useApi.ts           # Couche HTTP (API calls)
├── vite.config.ts          # Config build (output → IALocalProject/static/vue/)
└── package.json            # Dépendances Node.js
```

---

## Sécurité & Limitations

### Protections implémentées

- **Validation d'entrée** : Toutes les cibles (IP/hostname) sont filtrées par regex stricte (`[A-Za-z0-9_.:/-]+`), empêchant l'injection de commandes shell.
- **Timeouts** : Chaque outil a un timeout dédié (Ping: 10s, Nmap: 40s, Discovery: 60s, Audit: 90s) pour éviter de bloquer le serveur.
- **Écriture atomique** : Les fichiers JSON (historique, prompts) sont écrits via fichier temporaire → backup → `os.replace()` pour éviter la corruption.
- **CORS restreint** : Seuls `localhost:5173` et `localhost:4173` sont autorisés.
- **Debug désactivé** : Le mode debug est contrôlé par variable d'environnement (`FLASK_DEBUG`), désactivé par défaut.
- **Sauvegarde automatique** : Backup `.backup.json` avant chaque écriture.

### Limitations connues

- **Pas de base de données** : La persistance utilise des fichiers JSON. Pour de la production, migrer vers SQLite/PostgreSQL.
- **Exécution synchrone** : Les outils (Nmap, Ping) bloquent le thread Flask. Pour de la charge, envisager Celery ou asyncio.
- **Usage local uniquement** : Ne pas exposer directement sur Internet (serveur WSGI requis pour la production).
- **Nmap requiert des droits** : Certains scans nécessitent des privilèges administrateur.

---

## Roadmap

- [x] Multi-modèles LLM avec basculement instantané
- [x] Tool Calling (Nmap, Ping, 5 bundles métier)
- [x] Interface Glassmorphism responsive
- [x] Administration des prompts système (CRUD)
- [x] Migration frontend vers Vue.js 3 + TypeScript
- [ ] Base de données (SQLite/PostgreSQL) pour la persistance
- [ ] Exécution asynchrone des outils (Celery/asyncio)
- [ ] Support d'outils supplémentaires (curl, Shodan, analyse de logs)
- [ ] Authentification et gestion des utilisateurs
- [ ] Déploiement Docker (Flask + Ollama conteneurisés)