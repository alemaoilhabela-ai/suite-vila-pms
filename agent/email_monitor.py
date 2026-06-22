import os
import json
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from agent.ical_agent import verificar_feeds
from app.telegram import enviar_mensagem

REMETENTES = ["booking.com", "airbnb.com", "airbnb.com.br"]

def extrair_id_reserva(assunto):
    m = re.search(r'\b(\d{8,12})\b', assunto)
    return m.group(1) if m else None

def get_gmail_service():
    creds_data = json.loads(os.environ["GMAIL_TOKEN_JSON"])
    creds = Credentials(
        token=creds_data["token"],
        refresh_token=creds_data["refresh_token"],
        token_uri=creds_data["token_uri"],
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=creds_data["scopes"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

def verificar_emails_novos():
    try:
        service = get_gmail_service()
        query = "from:(booking.com OR airbnb.com OR airbnb.com.br) is:unread newer_than:1d"
        results = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = results.get("messages", [])

        if not messages:
            return 0

        novos = 0
        for msg in messages:
            detail = service.users().messages().get(userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            remetente = headers.get("From", "").lower()
            assunto = headers.get("Subject", "")

            if any(r in remetente for r in REMETENTES):
                id_reserva = extrair_id_reserva(assunto)
                print(f"[Email] Novo email: {assunto} | ID extraído: {id_reserva}")
                # Salva o ID da reserva na reserva correspondente se encontrar
                if id_reserva:
                    from app.database import get_client
                    db = get_client()
                    db.table("reservas").update({"numero_reserva": id_reserva}).eq("numero_reserva", "").is_("numero_reserva", "null").execute()
                novos += 1

        if novos > 0:
            print(f"[Email] {novos} email(s) detectado(s) — verificando iCal...")
            verificar_feeds()

        return novos

    except Exception as e:
        print(f"[Email Monitor] Erro: {e}")
        return 0
