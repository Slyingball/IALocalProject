# 🛡️ IALocalProject : Assistant Cyber & Multi-IA Local

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=flat&logo=flask&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-orange)
![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)

**Une interface web moderne pour orchestrer des LLMs locaux (via Ollama) avec des capacités d'exécution d'outils réels (Nmap).**

## 📖 Table des matières
- [Vue d'ensemble](#-vue-densemble)
- [Fonctionnalités Clés](#-fonctionnalités-clés)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [API REST](#-api-rest)
- [Structure du projet](#-structure-du-projet)
- [Sécurité & Limitations](#-sécurité--limitations)
- [Roadmap](#-roadmap)

---

## 🎯 Vue d'ensemble

Ce projet est une démonstration d'**Agent IA autonome** fonctionnant à 100% en local. Il connecte une interface web (Flask) à Ollama. Contrairement à un chat classique, les modèles compatibles peuvent exécuter des **outils** (Function Calling) pour interagir avec le système local, notamment pour effectuer des scans réseau via **Nmap**.

### ✨ Fonctionnalités Clés

* 🔄 **Multi-Modèles :** Basculez instantanément entre différents modèles (Llama 3 rapide, Llama 3.1 intelligent, Llama 2 non-censuré).
* 🛠️ **Support des "Tools" (Outils) :** Les modèles compatibles (ex: `llama3.1:8b`) peuvent lancer des scans Nmap réels et analyser les résultats.
*  **Modes Système :**
    *  **Cybersécurité :** Expert en OWASP, audit et pentest.
    *  **Général :** Assistant polyvalent et structuré.
*  **Interface Immersive :** Design sombre "Glassmorphism", responsive et adapté au workflow hacker/développeur.
*  **API REST :** Pilotage complet possible via API JSON (sans navigateur).
*  **Historique Intelligent :** Gestion de contexte (3 derniers échanges) et persistance en mémoire.

---

## ⚙️ Prérequis

Avant de lancer le projet, assurez-vous de disposer des éléments suivants :

1. **Python 3.10+** installé sur votre machine.
2. **Nmap** installé et accessible dans les variables d'environnement (`PATH` system). Vérifiez avec `nmap --version`.
3. **Ollama** installé et en cours d'exécution. Lancez le service avec `ollama serve`.

### 📦 Modèles Ollama Requis

Téléchargez les modèles nécessaires pour profiter de toutes les fonctionnalités :

```bash
# Pour le Function Calling et la polyvalence (Recommandé)
ollama pull llama3.1:8b

# Pour la vitesse d'exécution (Pas de support d'outils)
ollama pull llama3:latest

# Pour le mode sans filtre (Support d'outils variable)
ollama pull llama2-uncensored:latest
```

---

## 🏗️ Installation

1. **Cloner le répertoire :**
   ```bash
   git clone <votre-repo>
   cd IALocalProject
   ```

2. **Créer et activer un environnement virtuel :**
   ```bash
   python -m venv .venv

   # Sous Windows :
   .venv\Scripts\activate

   # Sous Linux/Mac :
   source .venv/bin/activate
   ```

3. **Installer les dépendances :**
   ```bash
   pip install -r requirements.txt
   ```
   *(Dépendances principales : `flask`, `requests`, `paramiko`)*

---

## 🚀 Utilisation

### Démarrage du serveur

Lancez l'application Flask :

```bash
python app.py
```

Accédez ensuite à l'interface via votre navigateur : **[http://localhost:5000](http://localhost:5000)**

### Guide de l'Interface

1. **Sélection du Modèle :** Utilisez la barre latérale pour choisir le LLM à utiliser.
   > ⚠️ **Note :** Choisissez `LLaMA 3.1 8B` pour utiliser les scans Nmap via Tool Calling. Le modèle `LLaMA 3` standard ne supporte pas cette fonctionnalité de manière native.
2. **Configuration :**
   * Activez **"Utiliser le contexte"** pour permettre à l'IA de se souvenir de vos derniers messages.
   * Basculez le **"Mode système"** sur **Cybersécurité** pour des réponses optimisées et techniques.
3. **Lancer un Scan Nmap (Tool Calling) :**
   Demandez simplement à l'IA de scanner une cible. Le modèle détectera l'intention et exécutera la commande adéquate.
   * *Exemple 1 :* "Scan l'hôte 192.168.1.15 rapidement."
   * *Exemple 2 :* "Fais un scan de versions sur scanme.nmap.org ports 80,443."
   * *Exemple 3 :* "Scan 10.0.0.5 sans ping."

---

## 🔌 API REST

Vous pouvez intégrer ce projet à vos propres scripts via les endpoints suivants :

* `POST /ask` : Poser une question à l'IA.
  ```json
  {
    "model": "llama3.1",
    "question": "Scan 192.168.1.1",
    "use_context": true,
    "system_mode": "cybersecurity"
  }
  ```
* `GET /history/<model_key>` : Récupérer l'historique des conversations pour un modèle donné.
* `POST /clear_history` : Effacer la mémoire d'un ou plusieurs modèles.
  ```json
  {"model": "llama3"} // ou {"model": "all"}
  ```

---

## 📁 Structure du projet

* `app.py` : Cœur de l'application (Serveur Flask, logique IA, Tool calling Nmap).
* `templates/index.html` : Interface chat (sidebar modèles, options, commandes).
* `static/style.css` : Thème sombre et styles responsifs.
* `requirements.txt` : Liste des dépendances.

---

## ⚠️ Sécurité & Limitations

* 🐛 **Mode Debug :** L'application tourne par défaut avec `debug=True`. **Ne pas l'exposer directement sur Internet.**
* 🛡️ **Exécution Nmap :** L'outil `run_nmap` est protégé par des expressions régulières (Regex) strictes (caractères alphanumériques uniquement pour les cibles) pour éviter les injections de commandes. Cependant, l'utilisation de scanners réseau doit toujours se faire sur des cibles pour lesquelles vous avez une autorisation explicite.
* ⏳ **Timeout :** Les scans Nmap sont limités à 40 secondes pour éviter de bloquer (geler) le serveur Flask.

---

## 🗺️ Roadmap (Idées futures)

- [ ] Intégration de `remote_executor.py` dans l'UI pour lancer des scans depuis un serveur distant (VPS).
- [ ] Ajout d'une base de données (SQLite/PostgreSQL) pour persister l'historique après redémarrage.
- [ ] Support d'outils supplémentaires (ex: requêtes HTTP/curl, analyse de logs, intégration Shodan).
- [ ] Interface d'administration pour la gestion fine des prompts systèmes.