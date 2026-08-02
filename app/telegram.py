import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

def _token():
    return os.environ["TELEGRAM_BOT_TOKEN"]

def _chat_id():
    return os.environ["TELEGRAM_CHAT_ID"]

def enviar_mensagem(texto):
    try:
        r = requests.post(
            TELEGRAM_API.format(token=_token(), method="sendMessage"),
            json={"chat_id": _chat_id(), "text": texto, "parse_mode": "Markdown"},
            timeout=10
        )
        return r.ok
    except Exception as e:
        print(f"[Telegram] Erro: {e}")
        return False

def notificar_nova_reserva(uid, canal, check_in, check_out):
    texto = (
        f"🏠 *Suite Vila — Nova Entrada no iCal*\n\n"
        f"📋 Canal: *{canal}*\n"
        f"📅 Check-in: *{check_in.strftime('%d/%m/%Y')}*\n"
        f"📅 Check-out: *{check_out.strftime('%d/%m/%Y')}*\n"
        f"🌙 Diárias: *{(check_out - check_in).days}*"
    )
    teclado = {
        "inline_keyboard": [[
            {"text": "🔒 Bloqueio", "callback_data": f"BLOQUEIO:{uid[:8]}"},
            {"text": "✏️ Informar dados", "callback_data": f"DADOS:{uid[:8]}"},
        ]]
    }
    try:
        requests.post(
            TELEGRAM_API.format(token=_token(), method="sendMessage"),
            json={
                "chat_id": _chat_id(),
                "text": texto,
                "parse_mode": "Markdown",
                "reply_markup": teclado,
            },
            timeout=10
        )
    except Exception as e:
        print(f"[Telegram] Erro: {e}")
