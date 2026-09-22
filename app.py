"""
Sysendo — Agent Facture Électronique Sage 100
API Backend (FastAPI) + interface web intégrée

Installation :
    pip install anthropic fastapi uvicorn python-dotenv

Lancement :
    uvicorn app:app --reload --port 8000
    → Ouvrir http://localhost:8000
"""

import os
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"

app = FastAPI(title="Sysendo — Assistant FE Sage 100")

# ── Prompt système ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es l'assistant expert de la société Sysendo (mehdi.belghith@sysendo.fr),
intégrateur Sage 100.

Ta mission principale : répondre aux questions des clients relatives à la
**facture électronique** dans l'environnement Sage 100.

═══════════════════════════════════════════════════════════════
BASE DE CONNAISSANCES — FACTURE ÉLECTRONIQUE (France)
═══════════════════════════════════════════════════════════════

### Calendrier de la réforme
- **1er septembre 2026** : grandes entreprises et ETI.
- **1er septembre 2027** : PME et micro-entreprises.
- Toutes les entreprises assujetties à la TVA en France sont concernées.

### Formats acceptés
- **Factur-X** : PDF enrichi d'un XML (EN 16931). Format hybride recommandé.
- **UBL 2.1** : XML pur, standard européen.
- **CII (UN/CEFACT)** : XML pur, norme internationale.

### Architecture
- **PPF** (Portail Public de Facturation) : portail d'État gratuit.
- **PDP** (Plateforme Dématérialisation Partenaire) : opérateurs privés immatriculés DGFIP.
- **OD** (Opérateur de Dématérialisation) : prépare et transmet vers PDP/PPF.

### Sage 100 & facture électronique
- Compatible depuis la version **8.x** (mise à jour 2024-2025).
- Paramétrage : *Fichier > Paramètres société > Facture électronique*.
- Connecteur natif vers **Sage Network** (PDP immatriculée).
- Format recommandé par Sysendo : **Factur-X**.
- Archivage légal 10 ans avec signature électronique qualifiée.

### Erreurs courantes
- Rejet portail : SIRET invalide, TVA manquante, montants incohérents,
  format non conforme EN 16931.
- Version trop ancienne : mettre à jour vers v8.x.
═══════════════════════════════════════════════════════════════

Règles :
- Réponds en français, de manière claire et professionnelle.
- Si un problème nécessite une intervention, propose d'ouvrir un ticket.
- Mentionne le N° TVA Sysendo (FR01938271749) dans les documents officiels.
"""

# ── Outils ────────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_current_datetime",
        "description": "Retourne la date et l'heure actuelles.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "verifier_version_sage",
        "description": "Vérifie si une version Sage 100 est compatible avec la facture électronique.",
        "input_schema": {
            "type": "object",
            "properties": {
                "version": {"type": "string", "description": "Numéro de version (ex: 8.01, 7.50)."}
            },
            "required": ["version"],
        },
    },
    {
        "name": "creer_ticket_support",
        "description": "Crée un ticket de support Sysendo pour une intervention technique.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_email": {"type": "string"},
                "titre": {"type": "string"},
                "description": {"type": "string"},
                "priorite": {"type": "string", "enum": ["basse", "normale", "haute", "critique"]},
                "categorie": {
                    "type": "string",
                    "enum": ["facture_electronique", "paramétrage_sage", "mise_a_jour", "autre"],
                },
            },
            "required": ["client_email", "titre", "description", "priorite", "categorie"],
        },
    },
]


def executer_outil(nom: str, params: dict) -> str:
    if nom == "get_current_datetime":
        now = datetime.now()
        result = {"date": now.strftime("%d/%m/%Y"), "heure": now.strftime("%H:%M")}

    elif nom == "verifier_version_sage":
        version = params.get("version", "")
        try:
            major = float(version.split(".")[0])
            compatible = major >= 8
        except (ValueError, IndexError):
            return json.dumps({"erreur": "Format de version non reconnu."})
        result = {
            "version": version,
            "compatible_fe": compatible,
            "message": (
                f"Sage 100 v{version} est {'compatible' if compatible else 'NON compatible'} "
                f"avec la facture électronique."
            ),
            "action": (
                "Vérifier l'activation du module FE dans Paramètres société."
                if compatible
                else "Mise à jour vers la v8.x requise — contacter Sysendo."
            ),
        }

    elif nom == "creer_ticket_support":
        ticket_id = f"SYS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = {
            "success": True,
            "ticket_id": ticket_id,
            "message": f"Ticket {ticket_id} créé. Un expert Sysendo vous contactera sous 24h.",
        }
    else:
        result = {"erreur": f"Outil inconnu : {nom}"}

    return json.dumps(result, ensure_ascii=False)


# ── Logique agentique ──────────────────────────────────────────────────────────
def run_agent(messages: list) -> str:
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": executer_outil(block.name, block.input),
                    })
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            return "".join(b.text for b in response.content if hasattr(b, "text"))
        else:
            return f"[Erreur : {response.stop_reason}]"


# ── Modèles Pydantic ──────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    messages: list  # [{"role": "user"|"assistant", "content": "..."}]


# ── Routes API ─────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Point d'entrée de l'agent. Accepte un historique de messages et retourne la réponse."""
    try:
        reply = run_agent(req.messages.copy())
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"Erreur serveur : {str(e)}", "error": True}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Sysendo FE Agent", "tva": "FR01938271749"}


# ── Interface web intégrée ─────────────────────────────────────────────────────
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sysendo — Assistant Facture Électronique</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --brand: #1a56db;
      --brand-dark: #1040b0;
      --surface: #f8fafc;
      --card: #ffffff;
      --border: #e2e8f0;
      --text: #1e293b;
      --muted: #64748b;
      --user-bg: #1a56db;
      --bot-bg: #f1f5f9;
      --shadow: 0 4px 24px rgba(0,0,0,.08);
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--surface);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Header */
    header {
      background: var(--brand);
      color: #fff;
      padding: 16px 24px;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 2px 12px rgba(26,86,219,.3);
    }
    .logo {
      width: 40px; height: 40px;
      background: rgba(255,255,255,.2);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 20px;
    }
    header h1 { font-size: 18px; font-weight: 700; }
    header p  { font-size: 12px; opacity: .8; margin-top: 2px; }
    .badge {
      margin-left: auto;
      background: rgba(255,255,255,.2);
      border-radius: 20px;
      padding: 4px 12px;
      font-size: 11px;
      font-weight: 600;
    }

    /* Suggestions rapides */
    .suggestions {
      padding: 12px 24px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      background: var(--card);
      border-bottom: 1px solid var(--border);
    }
    .sugg {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 6px 14px;
      font-size: 13px;
      cursor: pointer;
      color: var(--brand);
      transition: background .15s, border-color .15s;
    }
    .sugg:hover { background: #e8f0fe; border-color: var(--brand); }

    /* Zone de chat */
    #chat {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      max-width: 860px;
      width: 100%;
      margin: 0 auto;
    }

    .message {
      display: flex;
      gap: 10px;
      animation: fadeIn .2s ease;
    }
    @keyframes fadeIn { from { opacity:0; transform: translateY(6px) } to { opacity:1; transform:none } }

    .message.user  { flex-direction: row-reverse; }

    .avatar {
      width: 36px; height: 36px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 16px; flex-shrink: 0;
    }
    .message.bot  .avatar { background: var(--brand); color:#fff; }
    .message.user .avatar { background: #334155; color:#fff; }

    .bubble {
      max-width: 72%;
      padding: 12px 16px;
      border-radius: 18px;
      font-size: 14px;
      line-height: 1.65;
      white-space: pre-wrap;
    }
    .message.bot  .bubble { background: var(--bot-bg); border-bottom-left-radius: 4px; }
    .message.user .bubble {
      background: var(--user-bg);
      color: #fff;
      border-bottom-right-radius: 4px;
    }

    /* Indicateur de frappe */
    .typing .bubble { background: var(--bot-bg); padding: 14px 18px; }
    .dot { display:inline-block; width:7px; height:7px; border-radius:50%;
           background: var(--muted); animation: bounce 1.2s infinite; }
    .dot:nth-child(2) { animation-delay:.2s; }
    .dot:nth-child(3) { animation-delay:.4s; }
    @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }

    /* Ticket / succès */
    .ticket-card {
      background: #f0fdf4;
      border: 1px solid #86efac;
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 13px;
      color: #166534;
      margin-top: 8px;
    }

    /* Zone de saisie */
    .input-area {
      background: var(--card);
      border-top: 1px solid var(--border);
      padding: 16px 24px;
    }
    .input-wrap {
      max-width: 860px;
      margin: 0 auto;
      display: flex;
      gap: 10px;
    }
    #userInput {
      flex: 1;
      border: 1.5px solid var(--border);
      border-radius: 12px;
      padding: 12px 16px;
      font-size: 14px;
      font-family: inherit;
      outline: none;
      resize: none;
      transition: border-color .2s;
      min-height: 48px;
      max-height: 140px;
    }
    #userInput:focus { border-color: var(--brand); }

    #sendBtn {
      width: 48px; height: 48px;
      border: none;
      border-radius: 12px;
      background: var(--brand);
      color: #fff;
      font-size: 20px;
      cursor: pointer;
      transition: background .15s;
      flex-shrink: 0;
    }
    #sendBtn:hover { background: var(--brand-dark); }
    #sendBtn:disabled { background: #94a3b8; cursor: not-allowed; }

    /* Scrollbar */
    #chat::-webkit-scrollbar { width: 5px; }
    #chat::-webkit-scrollbar-track { background: transparent; }
    #chat::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }
  </style>
</head>
<body>

<header>
  <div class="logo">🧾</div>
  <div>
    <h1>Assistant Sysendo</h1>
    <p>Facture Électronique &amp; Sage 100</p>
  </div>
  <span class="badge">🟢 En ligne</span>
</header>

<div class="suggestions">
  <button class="sugg" onclick="ask('Mon Sage 100 est en version 7.50, suis-je compatible ?')">Version 7.50 compatible ?</button>
  <button class="sugg" onclick="ask('Quelle est la différence entre PPF et PDP ?')">PPF vs PDP</button>
  <button class="sugg" onclick="ask('Quand entre en vigueur la réforme pour les PME ?')">Calendrier PME</button>
  <button class="sugg" onclick="ask('Comment activer Factur-X dans Sage 100 ?')">Activer Factur-X</button>
  <button class="sugg" onclick="ask(\"J'ai une erreur de rejet sur le portail, que faire ?\")">Erreur de rejet</button>
</div>

<div id="chat">
  <!-- Message d'accueil -->
  <div class="message bot">
    <div class="avatar">🤖</div>
    <div class="bubble">Bonjour ! Je suis l'assistant Sysendo, expert en <strong>facture électronique et Sage 100</strong>.<br><br>Comment puis-je vous aider aujourd'hui ?</div>
  </div>
</div>

<div class="input-area">
  <div class="input-wrap">
    <textarea id="userInput" placeholder="Posez votre question…" rows="1"></textarea>
    <button id="sendBtn" onclick="sendMessage()">➤</button>
  </div>
</div>

<script>
  const chat = document.getElementById('chat');
  const input = document.getElementById('userInput');
  const sendBtn = document.getElementById('sendBtn');
  let history = [];

  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
  });

  // Envoi sur Entrée (Shift+Entrée = nouvelle ligne)
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  function ask(text) {
    input.value = text;
    sendMessage();
  }

  function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `
      <div class="avatar">${role === 'bot' ? '🤖' : '👤'}</div>
      <div class="bubble">${text.replace(/</g,'&lt;').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>')}</div>
    `;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'message bot typing';
    div.id = 'typing';
    div.innerHTML = `<div class="avatar">🤖</div><div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>`;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById('typing');
    if (el) el.remove();
  }

  async function sendMessage() {
    const text = input.value.trim();
    if (!text || sendBtn.disabled) return;

    // Afficher le message utilisateur
    addMessage('user', text);
    history.push({ role: 'user', content: text });
    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;
    showTyping();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history }),
      });
      const data = await res.json();
      hideTyping();

      addMessage('bot', data.reply || 'Erreur sans message.');
      history.push({ role: 'assistant', content: data.reply || '' });
    } catch (err) {
      hideTyping();
      addMessage('bot', '⚠️ Impossible de joindre le serveur. Vérifiez que le backend est lancé.');
    }

    sendBtn.disabled = false;
    input.focus();
  }
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML_PAGE)


# ── Lancement direct ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
