from flask import Flask, render_template, request, jsonify

import requests

import json

from remote_executor import (
    RemoteCommandExecutor,
    CommandValidationError,
    RemoteExecutionError,
    sanitize_and_split,
)

app = Flask(__name__)

# Configuration des modèles IA locaux

MODELS = {

    "llama3.1": {

        "name": "LLaMA 3.1 8B",

        "url": "http://localhost:11434/api/generate",

        "model_id": "llama3.1:8b",

        "description": "Modèle équilibré et polyvalent",

        "icon": "🦙"

    },

    "llama2-uncensored": {

        "name": "LLaMA 2 Uncensored",

        "url": "http://localhost:11434/api/generate",

        "model_id": "llama2-uncensored:latest",

        "description": "Modèle sans filtres",

        "icon": "🔓"

    }

}

# Prompts système spécialisés

SYSTEM_PROMPTS = {

    "cybersecurity": """Tu es un expert en cybersécurité avec une expertise approfondie en :

- Sécurité des applications web (OWASP Top 10)

- Tests d'intrusion et audit de sécurité

- Cryptographie et gestion des secrets

- Analyse de vulnérabilités (CVE)

- Forensic et réponse aux incidents

- Conformité (RGPD, ISO 27001)

Réponds de manière claire, technique et pédagogique.""",

    "general": """Tu es un assistant IA intelligent et serviable. Réponds de manière claire, précise et structurée."""

}

# Historique des conversations par modèle

conversation_history = {

    "llama3.1": [],

    "llama2-uncensored": []

}


remote_executor_client = RemoteCommandExecutor()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", models=MODELS)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()

    model_key = data.get("model", "llama3.1")

    question = data.get("question", "").strip()

    use_context = data.get("use_context", True)

    system_mode = data.get("system_mode", "general")

    if not question:
        return jsonify({"error": "Aucune question fournie"}), 400

    if model_key not in MODELS:
        return jsonify({"error": f"Modèle {model_key} inconnu"}), 400

    model_info = MODELS[model_key]

    # Construire le prompt avec contexte si activé

    if use_context and conversation_history[model_key]:

        context = "\n".join([

            f"Q: {item['question']}\nR: {item['answer']}"

            for item in conversation_history[model_key][-3:]  # Garder les 3 derniers échanges

        ])

        full_prompt = f"{SYSTEM_PROMPTS[system_mode]}\n\nContexte:\n{context}\n\nQuestion actuelle: {question}"

    else:

        full_prompt = f"{SYSTEM_PROMPTS[system_mode]}\n\n{question}"

    payload = {

        "model": model_info["model_id"],

        "prompt": full_prompt,

        "stream": False,

        "options": {

            "temperature": 0.7,

            "top_p": 0.9,

            "top_k": 40

        }

    }

    try:

        response = requests.post(model_info["url"], json=payload, timeout=120)

        if response.status_code != 200:
            return jsonify({

                "error": f"Erreur du modèle ({response.status_code})",

                "details": response.text

            }), 500

        result = response.json()

        answer = result.get("response", "Pas de réponse")

        # Sauvegarder dans l'historique

        conversation_history[model_key].append({

            "question": question,

            "answer": answer

        })

        # Limiter l'historique à 10 échanges

        if len(conversation_history[model_key]) > 10:
            conversation_history[model_key] = conversation_history[model_key][-10:]

        return jsonify({

            "answer": answer,

            "model_used": model_info["name"],

            "history_length": len(conversation_history[model_key])

        })

    except requests.exceptions.Timeout:

        return jsonify({"error": "Timeout - Le modèle met trop de temps à répondre"}), 504

    except requests.exceptions.ConnectionError:

        return jsonify({"error": "Impossible de se connecter à Ollama. Est-il lancé ?"}), 503

    except Exception as e:

        return jsonify({"error": f"Erreur: {str(e)}"}), 500


@app.route("/clear_history", methods=["POST"])
def clear_history():
    data = request.get_json()

    model_key = data.get("model")

    if model_key == "all":

        for key in conversation_history:
            conversation_history[key] = []

        return jsonify({"message": "Tout l'historique a été effacé"})

    elif model_key in conversation_history:

        conversation_history[model_key] = []

        return jsonify({"message": f"Historique de {MODELS[model_key]['name']} effacé"})

    else:

        return jsonify({"error": "Modèle inconnu"}), 400


@app.route("/history/<model_key>", methods=["GET"])
def get_history(model_key):
    if model_key not in conversation_history:
        return jsonify({"error": "Modèle inconnu"}), 400

    return jsonify({

        "model": MODELS[model_key]["name"],

        "history": conversation_history[model_key]

    })


@app.route("/api/execute_command", methods=["POST"])
def execute_command():
    data = request.get_json() or {}
    target_host = data.get("target_ip") or data.get("target") or data.get("host")
    command = (data.get("command") or "").strip()

    if not target_host:
        return jsonify({"error": "Adresse IP ou hôte cible manquant"}), 400

    try:
        command_parts = sanitize_and_split(command)
    except CommandValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        result = remote_executor_client.execute(
            host=target_host,
            command_parts=command_parts,
            username=data.get("username"),
            password=data.get("password"),
            key_filename=data.get("key_path"),
            port=data.get("port"),
        )
    except RemoteExecutionError as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "target": target_host,
        "command": " ".join(command_parts),
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result["exit_code"],
    })


if __name__ == "__main__":

    print("🚀 Serveur Flask démarré sur http://localhost:5000")

    print("📋 Modèles disponibles:")

    for key, info in MODELS.items():
        print(f"   {info['icon']} {info['name']} - {info['description']}")

    app.run(host="0.0.0.0", port=5000, debug=True)