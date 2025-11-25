# IALocalProject

Interface Flask servant d'orchestrateur entre Ollama (LLM local) et une machine distante sur laquelle exécuter des commandes réseau/système ciblées.

## Architecture recommandée pour l'exécution distante
- **Génération** : Ollama produit une commande structurée (JSON) via un prompt système strict.
- **Validation locale** : Flask reçoit la commande, vérifie une liste blanche et exécute `which <cmd>` via `subprocess.run(..., shell=False)` pour s'assurer que le binaire est présent localement avant d'orchestrer l'appel distant.
- **Transport sécurisé** : l'API utilise Paramiko (SSH) pour ouvrir une session courte et non interactive sur l'hôte cible (VM ou machine physique). SSH reste le standard le plus sûr pour un POC car il offre chiffrement, contrôle d'identité, gestion native des clés et compatibilité multi-plateforme sans déployer d'agent propriétaire. Pour un déploiement avancé, on peut placer un « agent » REST minimal sur l'hôte cible, mais SSH+Paramiko offre le meilleur compromis simplicité/sécurité pour démarrer.
- **Exécution distante** : la commande validée est transférée telle quelle (quotée argument par argument) au serveur distant via `exec_command`. Les identifiants sont fournis via le JSON de la requête (usage POC) ou des variables d'environnement/gestionnaire de secrets en production.

### Bonnes pratiques secrets
- Définir `REMOTE_SSH_USERNAME`, `REMOTE_SSH_PASSWORD`, `REMOTE_SSH_KEY_PATH`, `REMOTE_SSH_PORT` dans un fichier `.env` ignoré par Git ou dans un coffre-fort (Vault, AWS Secrets Manager…).
- Ne jamais consigner les mots de passe dans le code ou les journaux.
- Préférer les clés SSH protégées par mot de passe dès que possible.

## API Flask utile au POC
### `POST /api/execute_command`
Payload attendu :
```json
{
  "target_ip": "192.168.1.15",
  "command": "nmap -oX -p 22,80 192.168.1.15",
  "username": "sysadmin",          // optionnel si REMOTE_SSH_USERNAME défini
  "password": "monSecret",          // pour un POC ; en prod utiliser une clé ou un secret store
  "key_path": "/chemin/id_rsa",    // optionnel, priorité sur password si fourni
  "port": 22                         // optionnel (par défaut 22)
}
```
Réponse : stdout/stderr/exit_code du serveur distant + rappel de la cible.

### Contrôles de sécurité intégrés
- **Liste blanche stricte** (`remote_executor.ALLOWED_COMMANDS`) : `nmap`, `ping`, `ip`, `df`, `ps`, `netstat`, `curl`, `ss`, `lsof`, `top`.
- **Liste noire de jetons** : interdit `;`, `&&`, `||`, `|`, `` ` ``, `$(`, redirections, `sudo`, `rm`, `kill`, etc.
- **Validation locale** : si la commande n'existe pas sur l'hôte Flask (`which` via `subprocess.run(..., shell=False)`), elle est rejetée avant même l'ouverture SSH.
- **Quotage systématique** : chaque argument est échappé côté Flask avant envoi à Paramiko pour éviter les injections.
- **Gestion des erreurs** : toutes les erreurs de validation renvoient HTTP 400, les erreurs SSH 500 avec un message générique.

## System Prompt strict pour Ollama
```
Tu es "Sentinel", un générateur spécialisé de commandes Linux/réseau à destination d'un hôte CIBLE distant.
Ton unique rôle est de proposer des commandes d'observation (réseau, process, disque) non destructives.

Contraintes :
- Sort uniquement du JSON valide, une seule ligne, format exact :
  {
    "target_ip": "<IPv4 ou hostname>",
    "command": "<commande>"
  }
- Commandes autorisées : nmap, ping, ip, df, ps, netstat, curl, ss, lsof, top.
- Bannir toute commande dangereuse (sudo, rm, kill, :(){:|:&};:, redirections, opérateurs `;`, `&&`, `||`, `|`, backticks, $()).
- Ne jamais manipuler de fichiers sensibles, utilisateurs ou services critiques.
- La cible doit toujours être incluse comme dernier argument si pertinent (ex: `nmap ... <IP>`).
- Pas de texte additionnel, excuses ou commentaires.
- Si la demande de l'utilisateur est incompatible avec les règles ci-dessus, renvoie uniquement :
  {
    "target_ip": "",
    "command": ""
  }
```

## Commandes recommandées pour un SysAdmin
- ✅ `nmap -oX <plage>` : la sortie XML facilite une analyse ultérieure automatique (XSLT, parsing Python) pour détecter ports/services exposés.
- ✅ `ps aux --sort=-%cpu` : classe immédiatement les processus les plus gourmands en CPU, utile pour diagnostiquer des pics de charge.
- `ss -tuln` : inventorie rapidement sockets TCP/UDP ouverts et ports en écoute avec un format tabulaire stable.
- `lsof -i` : relie chaque socket réseau à son processus PID/commande, pratique pour retrouver le binaire responsable d'un port.
- `top -n 1 -b` : capture instantanée complète des ressources (CPU/RAM) dans un format brut exploitable par un parser.

## Mise en route
1. Créer et activer un environnement virtuel Python 3.11+.
2. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Exporter les variables d'environnement SSH (`REMOTE_SSH_*`).
4. Lancer Flask :
   ```bash
   flask --app app run --host 0.0.0.0 --port 5000
   ```
5. Côté client (UI ou script), appeler `/api/execute_command` avec une commande JSON issue d'Ollama.

## Tests rapides
- `curl -X POST http://localhost:5000/api/execute_command -H "Content-Type: application/json" -d '{"target_ip": "192.168.1.10", "command": "ping -c 1 192.168.1.10"}'`
- Vérifier que les commandes hors liste blanche retournent HTTP 400.

## Aller plus loin
- Remplacer `AutoAddPolicy` par un stockage de clés connues (`known_hosts`) pour les environnements sensibles.
- Centraliser la configuration (whitelist, hôtes approuvés) dans un fichier YAML signé.
- Ajouter une couche d'analyse IA côté Flask pour résumer la sortie avant affichage à l'utilisateur.
