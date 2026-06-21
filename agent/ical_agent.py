import os
import requests
from datetime import date
from icalendar import Calendar
from app.database import get_client
from app.telegram import notificar_nova_reserva

FEEDS = {
    "Booking": os.environ.get("BOOKING_ICAL", ""),
    "Airbnb":  os.environ.get("AIRBNB_ICAL", ""),
}

def parse_ical(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    cal = Calendar.from_ical(r.content)
    eventos = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        summary = str(component.get("SUMMARY", ""))
        if "not available" not in summary.lower() and "closed" not in summary.lower():
            continue
        dt_start = component.get("DTSTART").dt
        dt_end   = component.get("DTEND").dt
        if hasattr(dt_start, "date"):
            dt_start = dt_start.date()
        if hasattr(dt_end, "date"):
            dt_end = dt_end.date()
        if dt_end <= date.today():
            continue
        eventos.append({
            "uid": str(component.get("UID")),
            "check_in": dt_start,
            "check_out": dt_end,
        })
    return eventos

def verificar_feeds():
    db = get_client()
    for canal, url in FEEDS.items():
        if not url:
            continue
        try:
            eventos = parse_ical(url)
        except Exception as e:
            print(f"[{canal}] Erro ao buscar iCal: {e}")
            continue

        for ev in eventos:
            uid = ev["uid"]
            existente = db.table("reservas").select("id").eq("uid", uid).execute()
            if existente.data:
                continue

            db.table("reservas").insert({
                "uid": uid,
                "canal": canal,
                "check_in": str(ev["check_in"]),
                "check_out": str(ev["check_out"]),
                "aguardando_detalhes": True,
                "status": "Reserva Confirmada",
            }).execute()

            db.table("mensagens_pendentes").insert({
                "uid": uid,
                "canal": canal,
                "check_in": str(ev["check_in"]),
                "check_out": str(ev["check_out"]),
            }).execute()

            notificar_nova_reserva(uid, canal, ev["check_in"], ev["check_out"])
            print(f"[{canal}] Nova reserva registrada: {uid} ({ev['check_in']} → {ev['check_out']})")

def processar_resposta_whatsapp(texto):
    """
    Formato esperado: RESERVA <uid8> | Nome | Valor | Obs
    """
    partes = [p.strip() for p in texto.split("|")]
    if len(partes) < 3:
        return False, "Formato inválido. Use: RESERVA <id> | Nome | Valor | Obs"

    uid_prefix = partes[0].replace("RESERVA", "").strip()
    hospede    = partes[1]
    try:
        valor  = float(partes[2].replace(",", "."))
    except ValueError:
        return False, "Valor inválido."
    obs = partes[3] if len(partes) > 3 else ""

    db = get_client()
    res = db.table("reservas").select("id,uid,check_in,check_out,canal").ilike("uid", f"{uid_prefix}%").eq("aguardando_detalhes", True).execute()
    if not res.data:
        return False, f"Reserva {uid_prefix} não encontrada ou já preenchida."

    row = res.data[0]
    db.table("reservas").update({
        "hospede": hospede,
        "valor_total": valor,
        "observacoes": obs,
        "aguardando_detalhes": False,
    }).eq("id", row["id"]).execute()

    db.table("mensagens_pendentes").update({"respondido": True}).eq("uid", row["uid"]).execute()

    return True, f"✅ Reserva registrada: {hospede} | {row['check_in']} → {row['check_out']} | R$ {valor:.2f}"
