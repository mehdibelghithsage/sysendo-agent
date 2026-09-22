"""
Agent assistant métier — Sysendo
Spécialisé : Sage 100 & Facture Électronique

Installation :
    pip install anthropic

Usage :
    export ANTHROPIC_API_KEY="sk-ant-..."
    python agent_sysendo.py
"""

import os
import json
from datetime import datetime
import anthropic

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-opus-4-5"  # ou claude-sonnet-4-5, claude-haiku-3-5

SYSTEM_PROMPT = """Tu es l'assistant expert de la société Sysendo (mehdi.belghith@sysendo.fr),
intégrateur Sage 100.

Ta mission principale : répondre aux questions des clients relatives à la
**facture électronique** dans l'environnement Sage 100.

═══════════════════════════════════════════════════════════════
BASE DE CONNAISSANCES — FACTURE ÉLECTRONIQUE (France)
═══════════════════════════════════════════════════════════════

### Calendrier de la réforme (ordonnance 2021-1190 + loi Finance 2024)
- **1er septembre 2026** : obligation d'ÉMETTRE et RECEVOIR des factures
  électroniques pour les grandes entreprises et les ETI.
- **1er septembre 2027** : obligation étendue aux PME et micro-entreprises.
- Toutes les entreprises assujetties à la TVA en France sont concernées.

### Formats acceptés
| Format       | Description |
|--------------|-------------|
| Factur-X     | PDF enrichi d'un fichier XML embarqué (EN 16931). Format hybride lisible humain + machine. |
| UBL 2.1      | XML pur, standard européen. |
| CII (UN/CEFACT) | XML pur, norme internationale. |

### Architecture du dispositif
- **PPF** (Portail Public de Facturation, anciennement Chorus Pro) : portail
  d'État gratuit pour déposer/recevoir des factures.
- **PDP** (Plateforme de Dématérialisation Partenaire) : opérateurs privés
  immatriculés par la DGFIP (ex: Chorus Pro étendu, Yooz, Esker, Sage…).
  Les entreprises peuvent choisir une PDP plutôt que le PPF.
- **OD** (Opérateur de Dématérialisation) : prépare et transmet les factures
  vers une PDP ou le PPF mais ne les enregistre pas lui-même.

### Sage 100 & facture électronique
- Sage 100 Gestion Commerciale / Comptabilité : module de facturation
  électronique natif depuis la version **8.x** (mise à jour 2024-2025).
- **Paramétrage dans Sage 100** :
  1. Menu *Fichier > Paramètres société > Facture électronique*.
  2. Choisir le mode de transmission : PPF ou PDP partenaire.
  3. Configurer les identifiants SIRET et numéro de TVA.
  4. Activer le format de sortie (Factur-X recommandé par Sysendo).
- **Connecteur Sage → PDP** : Sage propose un connecteur natif vers
  Sage Network (PDP immatriculée Sage). Sysendo peut aussi interfacer
  d'autres PDP via API REST.
- **Archivage légal** : durée minimale 10 ans en France. Sage 100 génère
  une signature électronique qualifiée si l'option est activée.

### Questions fréquentes clients
- "Je ne sais pas si je suis concerné" → Oui si assujetti TVA France.
- "Puis-je continuer à envoyer des PDFs normaux après 2026 ?" → Non pour
  les B2B assujettis. Les PDF simples seront refusés.
- "Quelle est la différence entre PDP et PPF ?" → Le PPF est gratuit mais
  moins riche fonctionnellement. Une PDP offre des services à valeur
  ajoutée (rapprochement, suivi, archivage…).
- "Mon Sage 100 est-il à jour ?" → Vérifier la version en *Aide > À propos*.
  La version minimale pour la FE est 8.00.
- "J'ai une erreur de rejet sur le portail" → Causes fréquentes :
  SIRET invalide, TVA non renseignée, montants incohérents, format non
  conforme EN 16931.
═══════════════════════════════════════════════════════════════

Règles de conduite :
- Réponds toujours en français, de manière claire et professionnelle.
- Utilise les outils disponibles pour chercher des informations client
  ou créer un ticket si le problème nécessite une intervention technique.
- Si une question dépasse ta connaissance, propose d'ouvrir un ticket
  pour qu'un expert Sysendo rappelle le client.
- Mentionne systématiquement le numéro de TVA Sysendo (FR01938271749)
  dans les documents ou récapitulatifs officiels.
"""

# ──────────────────────────────────────────────
# Outils disponibles
# ──────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_current_datetime",
        "description": "Retourne la date et l'heure actuelles.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "recherche_client",
        "description": "Recherche un client Sysendo par nom ou email pour retrouver son contrat et sa version Sage 100.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Nom de la société ou adresse email du contact.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "verifier_version_sage",
        "description": "Vérifie si la version Sage 100 d'un client est compatible avec la facture électronique.",
        "input_schema": {
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Numéro de version Sage 100 du client (ex: 8.01, 7.50…).",
                }
            },
            "required": ["version"],
        },
    },
    {
        "name": "creer_ticket_support",
        "description": "Crée un ticket de support technique Sysendo pour une demande d'intervention ou un problème client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_email": {"type": "string", "description": "Email du client."},
                "titre": {"type": "string", "description": "Titre court du ticket."},
                "description": {"type": "string", "description": "Description détaillée du problème."},
                "priorite": {
                    "type": "string",
                    "enum": ["basse", "normale", "haute", "critique"],
                    "description": "Niveau de priorité.",
                },
                "categorie": {
                    "type": "string",
                    "enum": ["facture_electronique", "paramétrage_sage", "mise_a_jour", "autre"],
                    "description": "Catégorie du ticket.",
                },
            },
            "required": ["client_email", "titre", "description", "priorite", "categorie"],
        },
    },
    {
        "name": "planifier_formation",
        "description": "Planifie une session de formation ou démonstration sur la facture électronique Sage 100 pour un client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_email": {"type": "string", "description": "Email du client."},
                "sujet": {
                    "type": "string",
                    "enum": [
                        "introduction_facture_electronique",
                        "paramétrage_sage100_fe",
                        "connexion_pdp_ppf",
                        "archivage_legal",
                    ],
                    "description": "Sujet de la formation.",
                },
                "disponibilites": {
                    "type": "string",
                    "description": "Créneaux proposés par le client (texte libre).",
                },
            },
            "required": ["client_email", "sujet", "disponibilites"],
        },
    },
]


# ──────────────────────────────────────────────
# Logique des outils
# ──────────────────────────────────────────────
def get_current_datetime() -> dict:
    now = datetime.now()
    return {"date": now.strftime("%d/%m/%Y"), "heure": now.strftime("%H:%M")}


def recherche_client(query: str) -> dict:
    """Base démo — remplacez par un appel CRM/SQL réel."""
    clients_demo = {
        "acme": {
            "nom": "Acme SAS",
            "email": "compta@acme.fr",
            "siret": "12345678900012",
            "version_sage": "8.01",
            "contrat": "Maintenance Premium",
            "pdp": "Sage Network",
        },
        "btp2000": {
            "nom": "BTP2000",
            "email": "direction@btp2000.fr",
            "siret": "98765432100099",
            "version_sage": "7.50",
            "contrat": "Maintenance Standard",
            "pdp": None,
        },
    }
    q = query.lower()
    for key, c in clients_demo.items():
        if key in q or q in c["email"].lower() or q in c["nom"].lower():
            return {"trouvé": True, "client": c}
    return {"trouvé": False, "message": f"Aucun client trouvé pour « {query} »."}


def verifier_version_sage(version: str) -> dict:
    """Vérifie la compatibilité facture électronique."""
    try:
        major, minor = (float(x) for x in version.split(".")[:2])
        compatible = major >= 8
    except ValueError:
        return {"erreur": "Format de version non reconnu. Exemple attendu : 8.01"}

    if compatible:
        return {
            "version": version,
            "compatible_fe": True,
            "message": f"Sage 100 v{version} est compatible avec la facture électronique.",
            "action_recommandee": "Vérifier l'activation du module FE dans Paramètres société.",
        }
    else:
        return {
            "version": version,
            "compatible_fe": False,
            "message": f"Sage 100 v{version} n'est PAS compatible. Une mise à jour vers la v8.x est nécessaire.",
            "action_recommandee": "Contacter Sysendo pour planifier la mise à jour.",
        }


def creer_ticket_support(
    client_email: str, titre: str, description: str, priorite: str, categorie: str
) -> dict:
    """Crée un ticket — connectez votre ITSM ici (Zendesk, GLPI, Jira…)."""
    ticket_id = f"SYS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    print(f"\n  [TICKET] {ticket_id} | {priorite.upper()} | {categorie} | {titre}")
    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": (
            f"Ticket {ticket_id} créé. Un expert Sysendo va prendre en charge "
            f"votre demande dans les meilleurs délais."
        ),
    }


def planifier_formation(client_email: str, sujet: str, disponibilites: str) -> dict:
    """Planifie une formation — connectez votre agenda ici (Calendly, Google Calendar…)."""
    ref = f"FORM-{datetime.now().strftime('%Y%m%d')}"
    sujets_labels = {
        "introduction_facture_electronique": "Introduction à la facture électronique",
        "paramétrage_sage100_fe": "Paramétrage Sage 100 pour la FE",
        "connexion_pdp_ppf": "Connexion PDP / PPF",
        "archivage_legal": "Archivage légal des factures",
    }
    label = sujets_labels.get(sujet, sujet)
    print(f"\n  [FORMATION] {ref} | {label} | {client_email}")
    return {
        "success": True,
        "reference": ref,
        "message": (
            f"Demande de formation enregistrée ({label}). "
            f"Sysendo vous contactera sous 48h pour confirmer le créneau."
        ),
    }


def executer_outil(nom: str, parametres: dict) -> str:
    dispatch = {
        "get_current_datetime": lambda p: get_current_datetime(),
        "recherche_client": lambda p: recherche_client(**p),
        "verifier_version_sage": lambda p: verifier_version_sage(**p),
        "creer_ticket_support": lambda p: creer_ticket_support(**p),
        "planifier_formation": lambda p: planifier_formation(**p),
    }
    fn = dispatch.get(nom)
    if fn:
        return json.dumps(fn(parametres), ensure_ascii=False)
    return json.dumps({"erreur": f"Outil inconnu : {nom}"}, ensure_ascii=False)


# ──────────────────────────────────────────────
# Boucle agentique
# ──────────────────────────────────────────────
def run_agent(messages: list) -> str:
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  → {block.name}({json.dumps(block.input, ensure_ascii=False)})")
                    result_str = executer_outil(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            text = "".join(b.text for b in response.content if hasattr(b, "text"))
            return text
        else:
            return f"[Arrêt inattendu : {response.stop_reason}]"


# ──────────────────────────────────────────────
# Interface CLI
# ──────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  Sysendo — Assistant Facture Électronique & Sage 100")
    print("  Tapez 'quitter' pour terminer la session.")
    print("=" * 65)
    print("  Exemples de questions :")
    print("  • Mon Sage 100 est en version 7.50, suis-je à jour ?")
    print("  • Quelle est la différence entre PPF et PDP ?")
    print("  • Comment activer Factur-X dans Sage 100 ?")
    print("  • Je reçois une erreur de rejet sur le portail.")
    print("=" * 65)

    conversation: list = []

    while True:
        try:
            user_input = input("\nClient : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBonne journée !")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quitter", "quit", "exit", "bye"}:
            print("Bonne journée !")
            break

        conversation.append({"role": "user", "content": user_input})
        response = run_agent(conversation)
        print(f"\nAgent Sysendo : {response}")

        if not conversation or conversation[-1].get("role") != "assistant":
            conversation.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
