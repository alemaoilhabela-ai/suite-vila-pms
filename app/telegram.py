import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

def enviar_mensagem(texto):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    try:
        r = requests.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"},
            timeout=10
        )
        return r.ok
    except Exception as e:
        print(f"[Telegram] Erro: {e}")
        return False

def notificar_nova_reserva(uid, canal, check_in, check_out):
    texto = (
        f"🏠 *Suite Vila — Nova Reserva*\n\n"
        f"📋 Canal: *{canal}*\n"
        f"📅 Check-in: *{check_in.strftime('%d/%m/%Y')}*\n"
        f"📅 Check-out: *{check_out.strftime('%d/%m/%Y')}*\n"
        f"🌙 Diárias: *{(check_out - check_in).days}*\n\n"
        f"Para registrar, responda com:\n"
        f"`RESERVA {uid[:8]} | Nome do Hóspede | Valor Total | Observações`\n\n"
        f"_Exemplo: RESERVA {uid[:8]} | João Silva | 850.00 | 2 pessoas_"
    )
    return enviar_mensagem(texto)
