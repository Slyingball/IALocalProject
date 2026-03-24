import os
import json
import re
import shutil
import subprocess
import requests
import platform
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://localhost:4173"])

# --- Configuration ---
# Utilisation de variables d'environnement avec valeurs par défaut
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

# Configuration de l'historique
MAX_HISTORY_STORED = 10   # Nombre d'échanges gardés en mémoire
MAX_HISTORY_CONTEXT = 3   # Nombre d'échanges envoyés à l'IA pour le contexte

# Optimisation: Session persistante pour les requêtes HTTP (Keep-Alive)
http_session = requests.Session()

DEFAULT_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
}

MODELS = {
    "llama3": {
        "name": "LLaMA 3 Instruct",
        "url": OLLAMA_GENERATE_URL,
        "model_id": "llama3:latest",
        "description": "Modèle plus léger et rapide",
        "icon": "L3S",
        "supports_tools": False,
    },
    "llama3.1": {
        "name": "LLaMA 3.1 8B",
        "url": OLLAMA_GENERATE_URL,
        "model_id": "llama3.1:8b",
        "description": "Modèle équilibré et polyvalent",
        "icon": "L3",
        "supports_tools": True,
    },
    "llama2-uncensored": {
        "name": "LLaMA 2 Uncensored",
        "url": OLLAMA_GENERATE_URL,
        "model_id": "llama2-uncensored:latest",
        "description": "Modèle sans filtres",
        "icon": "L2",
        "supports_tools": False,
    },
}

SYSTEM_PROMPTS = {
    "cybersecurity": (
        "Tu es un expert en cybersécurité avec une expertise approfondie en:\n"
        "- Sécurité des applications web (OWASP Top 10)\n"
        "- Tests d'intrusion et audit de sécurité\n"
        "- Cryptographie et gestion des secrets\n"
        "- Analyse de vulnérabilités (CVE)\n"
        "- Forensic et réponse aux incidents\n"
        "- Conformité (RGPD, ISO 27001)\n"
        "Réponds de manière claire, technique et pédagogique."
    ),
    "general": (
        "Tu es un assistant IA intelligent et serviable. "
        "Réponds de manière claire, précise et structurée."
    ),
}

conversation_history = {key: [] for key in MODELS.keys()}

TOOL_INSTRUCTIONS = (
    "Tu disposes de l'outil 'run_nmap' (appel de fonction) pour réaliser un "
    "scan réseau cible. Utilise-le quand on te demande explicitement de lancer "
    "un nmap ou de faire un scan. Fournis ensuite un court résumé du résultat."
)

NMAP_TOOL = {
    "type": "function",
    "function": {
        "name": "run_nmap",
        "description": "Lance un scan nmap limité et retourne stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Nom d'hôte ou IP à scanner (ex: 192.168.0.10 ou scanme.nmap.org).",
                },
                "ports": {
                    "type": "string",
                    "description": "Liste de ports optionnelle, ex: '22,80,443'.",
                },
                "fast_scan": {
                    "type": "boolean",
                    "description": "Activer le scan rapide (-F).",
                },
                "service_versions": {
                    "type": "boolean",
                    "description": "Détecter les versions des services (-sV).",
                },
                "skip_ping": {
                    "type": "boolean",
                    "description": "Ne pas ping avant le scan (-Pn).",
                },
            },
            "required": ["target"],
        },
    },
}

PING_TOOL = {
    "type": "function",
    "function": {
        "name": "run_ping",
        "description": "Teste la connectivité vers une machine (Ping ICMP).",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Adresse IP ou nom de domaine à pinger.",
                }
            }, 
            "required": ["target"],
        },
    },
}

TOOLS = [NMAP_TOOL, PING_TOOL]

def build_messages(model_key: str, question: str, system_mode: str, use_context: bool):
    system_prompt = SYSTEM_PROMPTS.get(system_mode, SYSTEM_PROMPTS["general"])
    system_with_tools = f"{system_prompt}\n\n{TOOL_INSTRUCTIONS}"
    messages = [{"role": "system", "content": system_with_tools}]

    if use_context and conversation_history.get(model_key):
        # On ne prend que les X derniers échanges pour le contexte
        for item in conversation_history[model_key][-MAX_HISTORY_CONTEXT:]:
            messages.append({"role": "user", "content": item["question"]})
            messages.append({"role": "assistant", "content": item["answer"]})

    messages.append({"role": "user", "content": question})
    return messages


def safe_json_loads(raw_arguments):
    if not raw_arguments:
        return {}
    try:
        return json.loads(raw_arguments)
    except Exception:
        return {}


def run_nmap_tool(arguments: dict):
    target = (arguments.get("target") or "").strip()
    ports = (arguments.get("ports") or "").strip()
    fast_scan = bool(arguments.get("fast_scan", True))
    service_versions = bool(arguments.get("service_versions", False))
    skip_ping = bool(arguments.get("skip_ping", False))

    if not target:
        return {"error": "Cible manquante pour nmap."}

    if not re.fullmatch(r"[A-Za-z0-9_.:/-]+", target):
        return {"error": "Cible invalide (caractères non autorisés)."}

    if ports and not re.fullmatch(r"[0-9,\-]+", ports):
        return {"error": "Format de ports invalide. Ex: 22,80,443 ou 1-1024."}

    if shutil.which("nmap") is None:
        return {"error": "nmap introuvable sur le serveur."}

    cmd = ["nmap"]
    if fast_scan:
        cmd.append("-F")
    if service_versions:
        cmd.append("-sV")
    if skip_ping:
        cmd.append("-Pn")
    if ports:
        cmd.extend(["-p", ports])
    cmd.append(target)

    try:
        # Note: subprocess.run est bloquant. 
        # Pour une V2, envisager Celery ou un Threading asynchrone.
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        return {
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"error": "nmap a dépassé le délai autorisé (timeout)."}
    except Exception as exc:
        return {"error": f"Erreur lors de l'exécution de nmap: {exc}"}

def run_ping_tool(arguments: dict):
    target = (arguments.get("target") or "").strip()

    if not target:
        return {"error": "Cible manquante pour ping."}

    if not re.fullmatch(r"[A-Za-z0-9_.:/-]+", target):
        return {"error": "Cible invalide (caracteres non autorises)."}

    param = "-n" if platform.system().lower() == "windows" else "-c"
    cmd = ["ping", param, "4", target]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout= 10,
            check=False,
        )
        return {
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Le ping a dépassé le delai autorise (timeout)."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Erreur lors de l'execution de ping: {exc}"}

def call_ollama_chat(model_info, messages, include_tools=True):
    payload = {
        "model": model_info["model_id"],
        "messages": messages,
        "stream": False,
        "options": DEFAULT_OPTIONS,
    }
    if include_tools and model_info.get("supports_tools", True):
        payload["tools"] = TOOLS

    # Utilisation de la session persistante
    response = http_session.post(OLLAMA_CHAT_URL, json=payload, timeout=120)
    
    if response.status_code == 404:
        raise ValueError(
            f"Modèle {model_info['model_id']} introuvable dans Ollama (404). "
            "Vérifie qu'il est bien téléchargé (ollama pull ...)."
        )
    if response.status_code != 200:
        raise ValueError(f"Erreur du modèle ({response.status_code}): {response.text}")

    data = response.json()
    return data.get("message", {})


def handle_tool_calls(model_info, base_messages, assistant_message, tool_calls):
    messages_with_tools = list(base_messages)
    messages_with_tools.append(
        {
            "role": "assistant",
            "content": assistant_message.get("content", ""),
            "tool_calls": tool_calls,
        }
    )

    tool_results = []
    for call in tool_calls:
        function_data = call.get("function", {})
        name = function_data.get("name")
        args = safe_json_loads(function_data.get("arguments"))
        
        # --- DÉBUT DES MODIFICATIONS ---
        result = {}
        
        # On vérifie quel outil est demandé par l'IA
        if name == "run_nmap":
            result = run_nmap_tool(args)
        elif name == "run_ping":       # <--- Nouveau cas pour le ping
            result = run_ping_tool(args)
        else:
            # Si l'outil est inconnu, on l'ignore ou on log une erreur
            print(f"Outil inconnu demandé: {name}")
            continue
        # --- FIN DES MODIFICATIONS ---

        tool_results.append(
            {
                "role": "tool",
                "name": name,
                "tool_call_id": call.get("id"),
                "content": json.dumps(result),
            }
        )

    if not tool_results:
        return assistant_message.get("content", "")

    messages_with_tools.extend(tool_results)

    # Appel récursif (sans tools cette fois pour éviter une boucle infinie)
    follow_up_message = call_ollama_chat(
        model_info, messages_with_tools, include_tools=False
    )
    return follow_up_message.get("content", tool_results[0]["content"])


def chat_with_tools(model_info, messages):
    use_tools = model_info.get("supports_tools", True)
    assistant_message = call_ollama_chat(model_info, messages, include_tools=use_tools)
    
    if not use_tools:
        return assistant_message.get("content", "Pas de réponse")
    
    tool_calls = assistant_message.get("tool_calls") or []

    if tool_calls:
        return handle_tool_calls(model_info, messages, assistant_message, tool_calls)

    return assistant_message.get("content", "Pas de réponse")


@app.route("/models", methods=["GET"])
def get_models():
    models_list = {}
    for key, info in MODELS.items():
        models_list[key] = {
            "name": info["name"],
            "description": info["description"],
            "icon": info["icon"],
            "supports_tools": info["supports_tools"],
        }
    return jsonify(models_list)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", models=MODELS)


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    model_key = data.get("model", "llama3")
    question = (data.get("question", "") or "").strip()
    use_context = bool(data.get("use_context", True))
    system_mode = data.get("system_mode", "general")

    if not question:
        return jsonify({"error": "Aucune question fournie"}), 400

    if model_key not in MODELS:
        return jsonify({"error": f"Modèle {model_key} inconnu"}), 400

    model_info = MODELS[model_key]
    messages = build_messages(model_key, question, system_mode, use_context)

    try:
        answer = chat_with_tools(model_info, messages)

        # Mise à jour de l'historique
        conversation_history[model_key].append({"question": question, "answer": answer})
        # On garde les X derniers en mémoire
        if len(conversation_history[model_key]) > MAX_HISTORY_STORED:
            conversation_history[model_key] = conversation_history[model_key][-MAX_HISTORY_STORED:]

        return jsonify(
            {
                "answer": answer,
                "model_used": model_info["name"],
                "history_length": len(conversation_history[model_key]),
            }
        )

    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout - Le modèle met trop de temps à répondre"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Impossible de se connecter à Ollama. Est-il lancé ?"}), 503
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"error": f"Erreur: {exc}"}), 500


@app.route("/clear_history", methods=["POST"])
def clear_history():
    data = request.get_json()
    model_key = data.get("model")

    if model_key == "all":
        for key in conversation_history:
            conversation_history[key] = []
        return jsonify({"message": "Tout l'historique a été effacé"})

    if model_key in conversation_history:
        conversation_history[model_key] = []
        return jsonify({"message": f"Historique de {MODELS[model_key]['name']} effacé"})

    return jsonify({"error": "Modèle inconnu"}), 400


@app.route("/history/<model_key>", methods=["GET"])
def get_history(model_key):
    if model_key not in conversation_history:
        return jsonify({"error": "Modèle inconnu"}), 400

    return jsonify({"model": MODELS[model_key]["name"], "history": conversation_history[model_key]})


if __name__ == "__main__":
    print("Serveur Flask démarré sur http://localhost:5000")
    print("Modèles disponibles:")
    for key, info in MODELS.items():
        print(f"   {info['icon']} {info['name']} - {info['description']}")
    
    # Gestion sécurisée du mode debug via variable d'environnement
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)