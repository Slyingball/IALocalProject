import os
import json
import re
import shutil
import copy
from datetime import datetime, timezone
import subprocess
import requests
import platform
import socket
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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
MAX_HISTORY_STORED = 50   # Nombre d'échanges gardés en mémoire
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

# --- Prompts systèmes par défaut (fallback) ---
DEFAULT_PROMPTS = {
    "general": {
        "name": "Général",
        "icon": "💬",
        "content": (
            "Tu es un assistant IA intelligent et serviable. "
            "Réponds de manière claire, précise et structurée."
        ),
        "is_default": True,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    },
    "cybersecurity": {
        "name": "Cybersécurité",
        "icon": "🛡️",
        "content": (
            "Tu es un expert en cybersécurité avec une expertise approfondie en:\n"
            "- Sécurité des applications web (OWASP Top 10)\n"
            "- Tests d'intrusion et audit de sécurité\n"
            "- Cryptographie et gestion des secrets\n"
            "- Analyse de vulnérabilités (CVE)\n"
            "- Forensic et réponse aux incidents\n"
            "- Conformité (RGPD, ISO 27001)\n"
            "Réponds de manière claire, technique et pédagogique."
        ),
        "is_default": True,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    },
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")
PROMPTS_BACKUP = os.path.join(DATA_DIR, "prompts.backup.json")


# --- Utilitaire : écriture atomique avec backup ---
def _atomic_save(filepath, data, backup_path=None):
    """Sauvegarde atomique : écrit dans un fichier temporaire puis renomme.
    Crée un backup du fichier existant si backup_path est fourni."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    tmp_path = filepath + ".tmp"
    try:
        # Écriture dans un fichier temporaire
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # Backup de l'ancien fichier si il existe
        if backup_path and os.path.exists(filepath):
            shutil.copy2(filepath, backup_path)
        # Remplacement atomique
        os.replace(tmp_path, filepath)
    except Exception as e:
        # Nettoyage du fichier temporaire en cas d'erreur
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e


# --- Gestion des prompts systèmes ---
def load_prompts():
    """Charge les prompts depuis le fichier JSON, avec fallback sur les défauts."""
    prompts = copy.deepcopy(DEFAULT_PROMPTS)
    if os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Fusion : les prompts sauvegardés écrasent les défauts
            for key, value in saved.items():
                prompts[key] = value
            # S'assurer que les défauts existent toujours
            for key, default in DEFAULT_PROMPTS.items():
                if key not in prompts:
                    prompts[key] = copy.deepcopy(default)
        except Exception as e:
            print(f"⚠️ Erreur au chargement des prompts ({e}). Utilisation des défauts.")
    return prompts


def save_prompts(prompts_data):
    """Sauvegarde les prompts avec écriture atomique et backup."""
    try:
        _atomic_save(PROMPTS_FILE, prompts_data, backup_path=PROMPTS_BACKUP)
    except Exception as e:
        print(f"❌ Erreur à la sauvegarde des prompts : {e}")
        raise


# Variable globale des prompts (chargée au démarrage)
system_prompts = load_prompts()


# Propriété de compatibilité : SYSTEM_PROMPTS renvoie {id: content}
def get_system_prompts_flat():
    """Retourne un dict {id: content} compatible avec l'ancien format."""
    return {key: p["content"] for key, p in system_prompts.items()}

SYSTEM_PROMPTS = get_system_prompts_flat()


# --- Gestion de l'historique de conversation ---
def load_history():
    history = {key: [] for key in MODELS.keys()}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for key in saved:
                    if key in history:
                        history[key] = saved[key]
        except Exception as e:
            print(f"Erreur au chargement de l'historique : {e}")
    return history


def save_history(history_data):
    """Sauvegarde l'historique avec écriture atomique et backup."""
    try:
        _atomic_save(HISTORY_FILE, history_data,
                     backup_path=os.path.join(DATA_DIR, "history.backup.json"))
    except Exception as e:
        print(f"Erreur à la sauvegarde de l'historique : {e}")


conversation_history = load_history()

TOOL_INSTRUCTIONS = (
    "Tu disposes de plusieurs outils (appels de fonctions) :\n"
    "- 'run_nmap' : Scan réseau ciblé (ports, versions, etc.)\n"
    "- 'run_ping' : Test de connectivité ICMP vers une machine\n"
    "- 'get_network_interfaces' : Récupérer les interfaces réseau et l'IP locale de cette machine\n"
    "- 'get_system_status' : État du système (OS, CPU, RAM, disque)\n"
    "- 'run_reconnaissance_rapide' : Bundle métier qui effectue Ping + Nmap rapide + vérification HTTP en une seule commande\n"
    "- 'run_local_discovery' : Bundle métier qui détecte l'IP locale, calcule le sous-réseau et découvre toutes les machines du réseau\n"
    "- 'run_port_audit' : Bundle métier qui audite les ports d'administration sensibles (FTP, SSH, Telnet, RDP, SMB...) et génère des alertes de sécurité\n"
    "Utilise ces outils quand l'utilisateur te le demande explicitement ou quand c'est pertinent. "
    "Pour les bundles, fournis une synthèse claire et structurée du rapport retourné."
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

GET_NETWORK_INTERFACES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_network_interfaces",
        "description": "Récupère les interfaces réseau de la machine locale avec leurs adresses IP. Utile pour connaître l'IP locale et le sous-réseau.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

GET_SYSTEM_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_system_status",
        "description": "Récupère l'état du système local : OS, CPU, RAM, espace disque. Utile pour diagnostiquer la machine.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

RECON_RAPIDE_TOOL = {
    "type": "function",
    "function": {
        "name": "run_reconnaissance_rapide",
        "description": (
            "Bundle d'analyse complète : effectue un Ping, un scan Nmap rapide (-F), "
            "et une vérification HTTP (headers serveur + titre de la page) sur une cible. "
            "Renvoie une synthèse structurée en 3 étapes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Adresse IP ou nom de domaine de la cible.",
                },
            },
            "required": ["target"],
        },
    },
}

LOCAL_DISCOVERY_TOOL = {
    "type": "function",
    "function": {
        "name": "run_local_discovery",
        "description": (
            "Bundle de découverte réseau local : détecte automatiquement l'IP locale, "
            "calcule le sous-réseau, et effectue un Ping Sweep (nmap -sn) pour lister "
            "toutes les machines connectées au réseau local."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

PORT_AUDIT_TOOL = {
    "type": "function",
    "function": {
        "name": "run_port_audit",
        "description": (
            "Bundle d'audit de sécurité : scanne les ports d'administration sensibles "
            "(21 FTP, 22 SSH, 23 Telnet, 3389 RDP, 445 SMB, 3306 MySQL, 5432 PostgreSQL) "
            "avec détection de versions (-sV). Signale les services dangereux exposés "
            "avec des alertes de sécurité détaillées."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Adresse IP ou nom de domaine de la cible à auditer.",
                },
            },
            "required": ["target"],
        },
    },
}

TOOLS = [
    NMAP_TOOL, PING_TOOL,
    GET_NETWORK_INTERFACES_TOOL, GET_SYSTEM_STATUS_TOOL,
    RECON_RAPIDE_TOOL, LOCAL_DISCOVERY_TOOL, PORT_AUDIT_TOOL,
]

def build_messages(model_key: str, question: str, system_mode: str, use_context: bool):
    # Lecture dynamique depuis les prompts chargés en mémoire
    prompt_entry = system_prompts.get(system_mode, system_prompts.get("general", {}))
    system_prompt = prompt_entry.get("content", "") if isinstance(prompt_entry, dict) else str(prompt_entry)
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


def get_network_interfaces_tool():
    """Récupère les interfaces réseau de la machine locale."""
    try:
        import psutil
        interfaces = {}
        for name, addrs in psutil.net_if_addrs().items():
            iface_info = []
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    iface_info.append({
                        "ip": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast,
                    })
            if iface_info:
                interfaces[name] = iface_info

        hostname = socket.gethostname()
        # IP principale (celle utilisée pour sortir vers Internet)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            main_ip = s.getsockname()[0]
            s.close()
        except Exception:
            main_ip = socket.gethostbyname(hostname)

        return {
            "hostname": hostname,
            "main_ip": main_ip,
            "interfaces": interfaces,
        }
    except ImportError:
        hostname = socket.gethostname()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            main_ip = s.getsockname()[0]
            s.close()
        except Exception:
            main_ip = socket.gethostbyname(hostname)
        return {
            "hostname": hostname,
            "main_ip": main_ip,
            "note": "Module psutil non installé — informations limitées. pip install psutil",
        }
    except Exception as e:
        return {"error": f"Erreur lors de la récupération des interfaces : {e}"}


def get_system_status_tool():
    """Récupère l'état du système (OS, CPU, RAM, disque)."""
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk_path = "C:\\" if platform.system().lower() == "windows" else "/"
        disk = psutil.disk_usage(disk_path)

        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "cpu": {
                "usage_percent": cpu_percent,
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
            },
            "ram": {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "usage_percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "usage_percent": round(disk.percent, 1),
            },
        }
    except ImportError:
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "note": "Module psutil non installé — infos limitées. pip install psutil",
        }
    except Exception as e:
        return {"error": f"Erreur : {e}"}


def run_reconnaissance_rapide_tool(arguments: dict):
    """Bundle métier : Ping + Nmap rapide + vérification HTTP."""
    target = (arguments.get("target") or "").strip()

    if not target:
        return {"error": "Cible manquante."}
    if not re.fullmatch(r"[A-Za-z0-9_.:/-]+", target):
        return {"error": "Cible invalide (caractères non autorisés)."}

    report = {
        "target": target,
        "etape_1_ping": {},
        "etape_2_nmap": {},
        "etape_3_http": {},
        "synthese": "",
    }

    # --- Étape 1 : Ping ---
    ping_result = run_ping_tool({"target": target})
    is_up = ping_result.get("returncode", 1) == 0
    report["etape_1_ping"] = {
        "status": "UP" if is_up else "DOWN / Filtre ICMP",
        "detail": ping_result.get("stdout", ping_result.get("error", "")),
    }

    # --- Étape 2 : Nmap rapide ---
    nmap_result = run_nmap_tool({"target": target, "fast_scan": True, "skip_ping": True})
    report["etape_2_nmap"] = {
        "command": nmap_result.get("command", ""),
        "stdout": nmap_result.get("stdout", ""),
        "error": nmap_result.get("error", ""),
    }

    # Extraire les ports ouverts du résultat nmap
    open_ports = []
    nmap_stdout = nmap_result.get("stdout", "")
    for line in nmap_stdout.splitlines():
        if "/tcp" in line and "open" in line:
            open_ports.append(line.strip())

    # --- Étape 3 : Vérification HTTP si ports 80 ou 443 ouverts ---
    http_info = {"checked": False}
    has_http = any("80/tcp" in p for p in open_ports)
    has_https = any("443/tcp" in p for p in open_ports)

    if has_http or has_https:
        protocol = "https" if has_https else "http"
        url = f"{protocol}://{target}"
        http_info["checked"] = True
        http_info["url"] = url
        try:
            resp = http_session.get(url, timeout=5, verify=False, allow_redirects=True)
            http_info["status_code"] = resp.status_code
            http_info["server_header"] = resp.headers.get("Server", "Non renseigné")
            http_info["x_powered_by"] = resp.headers.get("X-Powered-By", "Non renseigné")
            title_match = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
            http_info["page_title"] = title_match.group(1).strip() if title_match else "Aucun titre"
        except Exception as e:
            http_info["error"] = str(e)

    report["etape_3_http"] = http_info

    report["synthese"] = (
        f"Hôte {target} : {'UP' if is_up else 'DOWN/Filtré'}. "
        f"{len(open_ports)} port(s) ouvert(s) détecté(s). "
        f"{'Service web détecté.' if http_info.get('checked') else 'Aucun service web standard détecté.'}"
    )

    return report


def run_local_discovery_tool():
    """Bundle métier : Découverte automatique du réseau local."""
    report = {
        "etape_1_detection_ip": {},
        "etape_2_ping_sweep": {},
        "synthese": "",
    }

    # --- Étape 1 : Détecter l'IP locale ---
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = socket.gethostbyname(socket.gethostname())

    # Calculer le sous-réseau /24
    parts = local_ip.rsplit(".", 1)
    subnet = f"{parts[0]}.0/24"

    report["etape_1_detection_ip"] = {
        "ip_locale": local_ip,
        "sous_reseau": subnet,
    }

    # --- Étape 2 : Ping Sweep ---
    if shutil.which("nmap") is None:
        report["etape_2_ping_sweep"] = {"error": "nmap introuvable sur le serveur."}
        report["synthese"] = f"IP locale : {local_ip}. Nmap non disponible pour le scan réseau."
        return report

    cmd = ["nmap", "-sn", subnet]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)

        # Parser les hôtes découverts
        hosts = []
        current_host = {}
        for line in result.stdout.splitlines():
            if "Nmap scan report for" in line:
                if current_host:
                    hosts.append(current_host)
                ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                hostname_match = re.search(r"for\s+(\S+)\s+\(", line)
                current_host = {
                    "ip": ip_match.group(1) if ip_match else line,
                    "hostname": hostname_match.group(1) if hostname_match else "",
                }
            elif "MAC Address:" in line:
                mac_match = re.search(r"MAC Address:\s+(\S+)\s+\((.+?)\)", line)
                if mac_match:
                    current_host["mac"] = mac_match.group(1)
                    current_host["vendor"] = mac_match.group(2)
        if current_host:
            hosts.append(current_host)

        report["etape_2_ping_sweep"] = {
            "command": " ".join(cmd),
            "hosts_discovered": hosts,
            "total": len(hosts),
            "raw_output": result.stdout,
        }

        report["synthese"] = (
            f"IP locale : {local_ip} | Sous-réseau scanné : {subnet} | "
            f"{len(hosts)} hôte(s) actif(s) détecté(s) sur le réseau."
        )
    except subprocess.TimeoutExpired:
        report["etape_2_ping_sweep"] = {"error": "Le scan a dépassé le délai autorisé (60s)."}
        report["synthese"] = f"IP locale : {local_ip}. Le Ping Sweep a expiré."
    except Exception as e:
        report["etape_2_ping_sweep"] = {"error": str(e)}
        report["synthese"] = f"IP locale : {local_ip}. Erreur lors du scan : {e}"

    return report


def run_port_audit_tool(arguments: dict):
    """Bundle métier : Audit des ports d'administration sensibles."""
    target = (arguments.get("target") or "").strip()

    if not target:
        return {"error": "Cible manquante."}
    if not re.fullmatch(r"[A-Za-z0-9_.:/-]+", target):
        return {"error": "Cible invalide (caractères non autorisés)."}

    if shutil.which("nmap") is None:
        return {"error": "nmap introuvable sur le serveur."}

    # Ports d'administration sensibles
    admin_ports = "21,22,23,25,445,1433,3306,3389,5432,5900,8080,8443"

    report = {
        "target": target,
        "ports_audites": admin_ports,
        "scan_result": {},
        "alertes": [],
        "synthese": "",
    }

    cmd = ["nmap", "-sV", "-Pn", "-p", admin_ports, target]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)

        # Parser les services détectés
        services = []
        for line in result.stdout.splitlines():
            if "/tcp" in line:
                parts_line = line.split()
                port_proto = parts_line[0] if len(parts_line) > 0 else ""
                state = parts_line[1] if len(parts_line) > 1 else ""
                service_name = parts_line[2] if len(parts_line) > 2 else ""
                version_info = " ".join(parts_line[3:]) if len(parts_line) > 3 else ""

                service_entry = {
                    "port": port_proto,
                    "state": state,
                    "service": service_name,
                    "version": version_info,
                }
                services.append(service_entry)

                # Détecter les alertes de sécurité
                if state == "open":
                    if "23/tcp" in port_proto:
                        report["alertes"].append(
                            "⚠️ CRITIQUE : Telnet (port 23) est OUVERT ! Protocole non chiffré, à désactiver immédiatement."
                        )
                    if "21/tcp" in port_proto:
                        report["alertes"].append(
                            "⚠️ ATTENTION : FTP (port 21) est OUVERT. Préférer SFTP (port 22). Vérifier si l'accès anonyme est activé."
                        )
                    if "3389/tcp" in port_proto:
                        report["alertes"].append(
                            "🔒 INFO : RDP (port 3389) est OUVERT. S'assurer que NLA est activé et accès restreint par pare-feu/VPN."
                        )
                    if "445/tcp" in port_proto:
                        report["alertes"].append(
                            "🔒 INFO : SMB (port 445) est OUVERT. Vérifier que SMBv1 est désactivé (vulnérabilité EternalBlue)."
                        )
                    if "5900/tcp" in port_proto:
                        report["alertes"].append(
                            "⚠️ ATTENTION : VNC (port 5900) est OUVERT. Le trafic VNC n'est souvent pas chiffré."
                        )
                    if "25/tcp" in port_proto:
                        report["alertes"].append(
                            "🔒 INFO : SMTP (port 25) est OUVERT. Vérifier que le relais ouvert (open relay) est désactivé."
                        )

        report["scan_result"] = {
            "command": " ".join(cmd),
            "services": services,
            "raw_output": result.stdout,
        }

        nb_open = sum(1 for s in services if s["state"] == "open")
        nb_alertes = len(report["alertes"])

        report["synthese"] = (
            f"Audit de {target} : {nb_open} port(s) d'administration ouvert(s) "
            f"sur {len(services)} scannés. "
            f"{nb_alertes} alerte(s) de sécurité générée(s)."
        )

    except subprocess.TimeoutExpired:
        report["scan_result"] = {"error": "Le scan a dépassé le délai autorisé (90s)."}
        report["synthese"] = "Le scan a expiré avant de terminer."
    except Exception as e:
        report["scan_result"] = {"error": str(e)}
        report["synthese"] = f"Erreur lors de l'audit : {e}"

    return report


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
        
        # --- Dispatch des outils ---
        result = {}

        if name == "run_nmap":
            result = run_nmap_tool(args)
        elif name == "run_ping":
            result = run_ping_tool(args)
        elif name == "get_network_interfaces":
            result = get_network_interfaces_tool()
        elif name == "get_system_status":
            result = get_system_status_tool()
        elif name == "run_reconnaissance_rapide":
            result = run_reconnaissance_rapide_tool(args)
        elif name == "run_local_discovery":
            result = run_local_discovery_tool()
        elif name == "run_port_audit":
            result = run_port_audit_tool(args)
        else:
            print(f"Outil inconnu demandé: {name}")
            continue
        # --- Fin dispatch ---

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
    return render_template("index.html", models=MODELS, prompts=system_prompts)


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
        
        save_history(conversation_history)

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
        save_history(conversation_history)
        return jsonify({"message": "Tout l'historique a été effacé"})

    if model_key in conversation_history:
        conversation_history[model_key] = []
        save_history(conversation_history)
        return jsonify({"message": f"Historique de {MODELS[model_key]['name']} effacé"})

    return jsonify({"error": "Modèle inconnu"}), 400


@app.route("/history/<model_key>", methods=["GET"])
def get_history(model_key):
    if model_key not in conversation_history:
        return jsonify({"error": "Modèle inconnu"}), 400

    return jsonify({"model": MODELS[model_key]["name"], "history": conversation_history[model_key]})


# ========================================
# --- API CRUD : Gestion des Prompts ---
# ========================================

@app.route("/prompts", methods=["GET"])
def get_prompts():
    """Retourne tous les prompts systèmes avec leurs métadonnées."""
    return jsonify(system_prompts)


@app.route("/prompts", methods=["POST"])
def create_or_update_prompt():
    """Crée ou met à jour un prompt système."""
    global SYSTEM_PROMPTS
    data = request.get_json()

    prompt_id = (data.get("id") or "").strip().lower()
    name = (data.get("name") or "").strip()
    content = (data.get("content") or "").strip()
    icon = (data.get("icon") or "💬").strip()

    if not prompt_id:
        return jsonify({"error": "L'identifiant (id) du prompt est requis."}), 400
    if not re.fullmatch(r"[a-z0-9_-]+", prompt_id):
        return jsonify({"error": "L'identifiant ne doit contenir que des lettres minuscules, chiffres, tirets et underscores."}), 400
    if not name:
        return jsonify({"error": "Le nom du prompt est requis."}), 400
    if not content:
        return jsonify({"error": "Le contenu du prompt est requis."}), 400
    if len(content) > 5000:
        return jsonify({"error": "Le contenu du prompt est trop long (max 5000 caractères)."}), 400

    now = datetime.now(timezone.utc).isoformat()
    is_update = prompt_id in system_prompts

    if is_update:
        # Mise à jour : on conserve created_at et is_default
        system_prompts[prompt_id]["name"] = name
        system_prompts[prompt_id]["content"] = content
        system_prompts[prompt_id]["icon"] = icon
        system_prompts[prompt_id]["updated_at"] = now
    else:
        # Création
        system_prompts[prompt_id] = {
            "name": name,
            "icon": icon,
            "content": content,
            "is_default": False,
            "created_at": now,
            "updated_at": now,
        }

    try:
        save_prompts(system_prompts)
        SYSTEM_PROMPTS = get_system_prompts_flat()
        action = "mis à jour" if is_update else "créé"
        return jsonify({
            "message": f"Prompt '{name}' {action} avec succès.",
            "prompt": system_prompts[prompt_id],
            "id": prompt_id,
        })
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la sauvegarde : {e}"}), 500


@app.route("/prompts/<prompt_id>", methods=["DELETE"])
def delete_prompt(prompt_id):
    """Supprime un prompt système (les prompts par défaut ne peuvent pas être supprimés)."""
    global SYSTEM_PROMPTS

    if prompt_id not in system_prompts:
        return jsonify({"error": f"Prompt '{prompt_id}' introuvable."}), 404

    if system_prompts[prompt_id].get("is_default", False):
        return jsonify({"error": "Les prompts par défaut ne peuvent pas être supprimés. Vous pouvez les modifier."}), 403

    name = system_prompts[prompt_id].get("name", prompt_id)
    del system_prompts[prompt_id]

    try:
        save_prompts(system_prompts)
        SYSTEM_PROMPTS = get_system_prompts_flat()
        return jsonify({"message": f"Prompt '{name}' supprimé avec succès."})
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la sauvegarde : {e}"}), 500


@app.route("/prompts/<prompt_id>/duplicate", methods=["POST"])
def duplicate_prompt(prompt_id):
    """Duplique un prompt existant."""
    global SYSTEM_PROMPTS

    if prompt_id not in system_prompts:
        return jsonify({"error": f"Prompt '{prompt_id}' introuvable."}), 404

    # Générer un nouvel ID
    base_id = f"{prompt_id}-copy"
    new_id = base_id
    counter = 1
    while new_id in system_prompts:
        new_id = f"{base_id}-{counter}"
        counter += 1

    now = datetime.now(timezone.utc).isoformat()
    original = system_prompts[prompt_id]

    system_prompts[new_id] = {
        "name": f"{original['name']} (copie)",
        "icon": original.get("icon", "💬"),
        "content": original["content"],
        "is_default": False,
        "created_at": now,
        "updated_at": now,
    }

    try:
        save_prompts(system_prompts)
        SYSTEM_PROMPTS = get_system_prompts_flat()
        return jsonify({
            "message": f"Prompt dupliqué sous l'ID '{new_id}'.",
            "prompt": system_prompts[new_id],
            "id": new_id,
        })
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la sauvegarde : {e}"}), 500


if __name__ == "__main__":
    print("Serveur Flask démarré sur http://localhost:5000")
    print("Modèles disponibles:")
    for key, info in MODELS.items():
        print(f"   {info['icon']} {info['name']} - {info['description']}")
    print(f"Prompts systèmes chargés: {len(system_prompts)}")
    for pid, pinfo in system_prompts.items():
        default_tag = " [défaut]" if pinfo.get("is_default") else ""
        print(f"   {pinfo.get('icon', '')} {pinfo['name']}{default_tag}")
    
    # Gestion sécurisée du mode debug via variable d'environnement
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)