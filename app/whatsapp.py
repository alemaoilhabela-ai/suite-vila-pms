import os
import requests

def enviar_mensagem(texto):
    url = f"{os.environ['EVOLUTION_API_URL']}/message/sendText/{os.environ['EVOLUTION_INSTANCE']}"
    headers = {"apikey": os.environ["EVOLUTION_API_KEY"], "Content-Type": "application/json"}
    payload = {
        "number": os.environ["WHATSAPP_OWNER"],
        "text": texto
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        return r.ok
    except Exception as e:
        print(f"[WhatsApp] Erro: {e}")
        return False

def notificar_nova_reserva(uid, canal, check_in, check_out):
    texto = (
        f"🏠 *Suite Vila — Nova Reserva Detectada*\n\n"
        f"📋 Canal: *{canal}*\n"
        f"📅 Check-in: *{check_in.strftime('%d/%m/%Y')}*\n"
        f"📅 Check-out: *{check_out.strftime('%d/%m/%Y')}*\n"
        f"🌙 Diárias: *{(check_out - check_in).days}*\n\n"
        f"Para registrar, responda com:\n"
        f"`RESERVA {uid[:8]} | Nome do Hóspede | Valor Total | Observações`\n\n"
        f"_Exemplo: RESERVA {uid[:8]} | João Silva | 850.00 | 2 pessoas_"
    )
    return enviar_mensagem(texto)
