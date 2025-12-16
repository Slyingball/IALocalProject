Voici une version "parfaite" et complète du README, basée sur l'analyse de tous les fichiers de ton projet (notamment `app.py` pour la logique, `style.css` pour l'identité visuelle, et `remote_executor.py` pour les fonctionnalités latentes).

Ce README est structuré pour être professionnel, clair et orienté utilisateur.

-----

# IALocalProject : Assistant Cyber & Multi-IA Local

**Une interface web moderne pour orchestrer des LLMs locaux (via Ollama) avec des capacités d'exécution d'outils réels (Nmap).**

  

## 📋 Vue d'ensemble

Ce projet est une démonstration d'**Agent IA autonome** tournant 100% en local. Il connecte une interface web (Flask) à Ollama. Contrairement à un chat classique, les modèles compatibles peuvent exécuter des **outils** (Function Calling) pour interagir avec le système, notamment pour effectuer des scans réseau via **Nmap**.

### 🔑 Fonctionnalités Clés

  * **Multi-Modèles :** Basculez instantanément entre différents modèles (Llama 3 rapide, Llama 3.1 intelligent, Llama 2 non-censuré).
  * **Support des "Tools" (Outils) :** Les modèles compatibles (ex: `llama3.1:8b`) peuvent lancer des scans Nmap réels et analyser les résultats.
  * **Modes Système :**
      * 🛡️ **Cybersécurité :** Expert en OWASP, audit et pentest.
      * 🧠 **Général :** Assistant polyvalent et structuré.
  * **Interface Immersive :** Design sombre "Glassmorphism", responsive et adapté au workflow hacker/développeur.
  * **API REST :** Pilotage complet possible via API JSON (sans navigateur).
  * **Historique Intelligent :** Gestion de contexte (3 derniers échanges) et persistance en mémoire.

-----

## 🛠️ Prérequis

Avant de lancer le projet, assurez-vous d'avoir :

1.  **Python 3.10+** installé.
2.  **Nmap** installé et accessible dans le PATH système (`nmap --version`).
3.  **Ollama** installé et en cours d'exécution (`ollama serve`).

### Modèles Ollama Requis

Tirez les modèles nécessaires pour profiter de toutes les fonctionnalités :

```bash
# Pour les outils et la polyvalence (Recommandé)
ollama pull llama3.1:8b

# Pour la vitesse (Pas de support d'outils)
ollama pull llama3:latest

# Pour le mode sans filtre (Support outils variable)
ollama pull llama2-uncensored:latest
```

-----

## 🏗️ Installation

1.  **Cloner le projet :**

    ```bash
    git clone <votre-repo>
    cd IALocalProject
    ```

2.  **Créer un environnement virtuel :**

    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Installer les dépendances :**

    ```bash
    pip install -r requirements.txt
    ```

    *(Dépendances principales : `flask`, `requests`, `paramiko`)*

-----

## 🖥️ Utilisation

### Démarrage

Lancez le serveur Flask :

```bash
python app.py
```

Accédez à l'interface via : **http://localhost:5000**

### Guide de l'Interface

1.  **Sélection du Modèle :** Utilisez la barre latérale pour choisir votre modèle.
      * ⚠️ *Note :* Choisissez `LLaMA 3.1 8B` si vous voulez utiliser les scans Nmap. `LLaMA 3` standard ne supporte pas les outils dans cette configuration.
2.  **Configuration :**
      * Activez "Utiliser le contexte" pour une conversation suivie.
      * Basculez le "Mode système" sur **Cybersécurité** pour des réponses techniques.
3.  **Lancer un Scan Nmap (Tool Calling) :**
    Demandez simplement à l'IA de scanner une cible. Le modèle détectera l'intention et exécutera la commande.
      * *Exemple 1 :* "Scan l'hôte 192.168.1.15 rapidement."
      * *Exemple 2 :* "Fais un scan de versions sur scanme.nmap.org ports 80,443."
      * *Exemple 3 :* "Scan 10.0.0.5 sans ping."

### API JSON

Vous pouvez intégrer ce projet dans vos scripts via les endpoints suivants :

  * `POST /ask` : Poser une question.
    ```json
    {
      "model": "llama3.1",
      "question": "Scan 192.168.1.1",
      "use_context": true,
      "system_mode": "cybersecurity"
    }
    ```
  * `GET /history/<model_key>` : Récupérer l'historique.
  * `POST /clear_history` : Effacer la mémoire (`{"model": "llama3"}` ou `{"model": "all"}`).

-----

## 📂 Structure du Projet

  * **`app.py`** : Cœur de l'application. Gère le serveur Web, la logique de discussion, et l'exécution sécurisée de `subprocess` pour Nmap.
  * **`templates/index.html`** : L'interface utilisateur. Intègre la sidebar dynamique et la fenêtre de chat.
  * **`static/style.css`** : Feuille de style complète (thème sombre, animations, layout responsive).
  * **`remote_executor.py`** : *[Expérimental]* Module utilitaire contenant une classe `RemoteCommandExecutor` pour exécuter des commandes via SSH (Paramiko). Non connecté à l'UI pour l'instant.
  * **`chat_llama.py`** : Script minimaliste pour tester la connexion Ollama en ligne de commande.

-----

## ⚠️ Sécurité & Limitations

  * **Mode Debug :** L'application tourne par défaut avec `debug=True`. Ne pas exposer directement sur Internet.
  * **Exécution Nmap :** L'outil `run_nmap` est sécurisé par des Regex strictes (caractères alphanumériques uniquement pour les cibles) pour éviter les injections de commandes, mais l'utilisation de scanners réseau doit toujours se faire sur des cibles autorisées.
  * **Timeout :** Les scans Nmap sont limités à 40 secondes pour ne pas geler le serveur.

-----

## 🔭 Roadmap (Idées futures)

  * [ ] Intégration de `remote_executor.py` dans l'UI pour lancer des scans depuis un serveur distant (VPS).
  * [ ] Ajout d'une base de données (SQLite) pour persister l'historique après redémarrage.