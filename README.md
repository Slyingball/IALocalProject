# IALocalProject

Interface web locale multi-IA construite avec Flask, propulsee par Ollama, avec support d'appels d'outils (nmap) selon le modele choisi.

## Vue d'ensemble
- Choix du modele en colonne gauche, zone de chat plein ecran.
- Options: contexte (3 derniers echanges), mode systeme (general, cybersecurity).
- Tableau des commandes disponibles (scans nmap) integre dans l'UI.
- Historique par modele (effacement cible ou global).
- API JSON simple pour piloter sans l'UI.

## Modeles et support des outils
- `llama3:latest` (LLaMA 3 Instruct) : plus leger/rapide, **ne supporte pas** les tools (nmap desactive).
- `llama3.1:8b` (LLaMA 3.1 8B) : support tools.
- `llama2-uncensored:latest` : support tools (si modele Ollama le permet).

Pour les scans nmap, utilisez un modele compatible tools. Si vous voyez "does not support tools", changez de modele ou desactivez l'envoi des tools pour ce modele.

## Prerequis
- Python 3.10+ et `pip`.
- Ollama installe et lance (`http://localhost:11434`).
- Modeles telecharges:
  - `ollama pull llama3:latest`
  - `ollama pull llama3.1:8b`
  - `ollama pull llama2-uncensored:latest` (optionnel)
- nmap installe sur la machine (dans le PATH).

## Installation
```bash
pip install -r requirements.txt
```

## Lancement
```bash
python app.py
# UI: http://localhost:5000
```

## Utilisation (UI)
1) Choisir un modele (en haut a gauche).
2) Optionnel: decocher le contexte pour aller plus vite, choisir le mode systeme.
3) Saisir la requete en bas. Ctrl+Enter pour envoyer.
4) Pour un scan nmap, formuler explicitement:  
   - "scanme.nmap.org ports 80,443 sV" (scan rapide + detection versions)  
   - "192.168.0.10 ports 22,80" (scan rapide)  
   - "192.168.0.10 ports 1-1024 no-ping" (plage plus large, -Pn)
5) Les boutons "Effacer historique" agissent sur le modele courant ou sur tout.

## API
- `POST /ask`  
  JSON: `{ "model": "llama3.1", "question": "ta requete", "use_context": true, "system_mode": "general" }`
- `GET /history/<model_key>`
- `POST /clear_history`  
  JSON: `{ "model": "<key>" }` ou `{ "model": "all" }`

## Fichiers utiles
- `app.py` : server Flask, routes et logique tools (nmap).
- `templates/index.html` : UI (sidebar modeles, commandes, chat plein ecran).
- `static/style.css` : styles sombres type chat moderne.
- `chat_llama.py` : exemple d'appel direct Ollama.

## Depannage
- "does not support tools" : le modele selectionne ne gere pas les tools. Choisir `llama3.1:8b` ou autre modele compatible.
- 404 modele introuvable : verifier `ollama list` et tirer le modele (`ollama pull ...`).
- nmap introuvable : installer nmap et ajouter au PATH, puis relancer le terminal.
- Timeout Ollama : modeles lourds -> patienter ou choisir le modele leger.

## Production et securite
- Application en `debug=True` par defaut (ne pas exposer telle quelle).
- Pas d'authentification integree; ajouter proxy/ACL avant exposition reseau.
