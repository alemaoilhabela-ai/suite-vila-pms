from flask import Blueprint, jsonify, request, render_template, Response
from app.database import get_client
from app.auth import login_required, tem_permissao
from agent.ical_agent import verificar_feeds, processar_resposta_whatsapp, processar_bloqueio_telegram
from datetime import date, timedelta
import calendar

bp = Blueprint("main", __name__)

@bp.get("/")
@login_required
def index():
    return render_template("index.html")

@bp.get("/api/reservas")
def listar_reservas():
    db = get_client()
    ano = request.args.get("ano", date.today().year)
    # inclui qualquer reserva que CRUZA o ano (não apenas as que começam nele)
    res = db.table("reservas").select("*").lte("check_in", f"{ano}-12-31").gte("check_out", f"{ano}-01-01").order("check_in", desc=True).execute()
    return jsonify(res.data)

@bp.get("/api/config")
def get_config():
    db = get_client()
    res = db.table("configuracoes").select("*").execute()
    return jsonify({r["chave"]: r["valor"] for r in res.data})

@bp.post("/api/config")
def set_config():
    db = get_client()
    data = request.json
    for chave, valor in data.items():
        db.table("configuracoes").upsert({"chave": chave, "valor": valor}).execute()
    # quando data_corte muda: cria/atualiza bloqueio de vendas
    if "data_corte_vendas" in data:
        from datetime import datetime, timedelta
        inicio = data["data_corte_vendas"]
        fim_dt = datetime.strptime(inicio, "%Y-%m-%d") + timedelta(days=730)
        fim = fim_dt.strftime("%Y-%m-%d")
        # remove bloqueios anteriores de venda (uid especial)
        db.table("reservas").delete().eq("uid", "bloqueio-vendas").execute()
        db.table("reservas").insert({
            "uid": "bloqueio-vendas",
            "canal": "Bloqueio",
            "status": "Bloqueado",
            "check_in": inicio,
            "check_out": fim,
            "hospede": "Bloqueado — Fora de venda",
            "aguardando_detalhes": False,
            "status_financeiro": "Paga",
        }).execute()
    return jsonify({"ok": True})

@bp.get("/api/reservas/pendentes")
def pendentes():
    db = get_client()
    res = db.table("reservas").select("*").eq("aguardando_detalhes", True).order("check_in").execute()
    return jsonify(res.data)

@bp.post("/api/reservas")
def criar_reserva():
    db = get_client()
    data = request.json
    required = ["check_in", "check_out", "canal"]
    if not all(k in data for k in required):
        return jsonify({"error": "Campos obrigatórios: check_in, check_out, canal"}), 400
    res = db.table("reservas").insert(data).execute()
    return jsonify(res.data[0]), 201

@bp.put("/api/reservas/<int:rid>")
def atualizar_reserva(rid):
    db = get_client()
    data = request.json
    data.pop("id", None)
    res = db.table("reservas").update(data).eq("id", rid).execute()
    return jsonify(res.data[0])

@bp.delete("/api/reservas/<int:rid>")
def deletar_reserva(rid):
    db = get_client()
    db.table("reservas").delete().eq("id", rid).execute()
    return jsonify({"ok": True})

@bp.get("/api/relatorios/mensal")
def relatorio_mensal():
    db = get_client()
    ano = int(request.args.get("ano", date.today().year))
    # busca reservas que cruzam o ano (check_in <= 31/dez E check_out >= 01/jan)
    res = db.table("reservas").select("check_in,check_out,valor_total,canal,diarias,adr").lte("check_in", f"{ano}-12-31").gte("check_out", f"{ano}-01-02").neq("status", "Bloqueado").execute()

    COMISSOES = {"Booking": 0.13, "Airbnb": 0.03, "Direta": 0.0, "Vrbo": 0.0}
    meses = {i: {"diarias": 0, "faturamento": 0.0, "faturamento_real": 0.0, "reservas": 0} for i in range(1, 13)}
    reservas_contadas = set()

    for r in res.data:
        if not r["valor_total"]:
            continue
        ci = date.fromisoformat(r["check_in"])
        co = date.fromisoformat(r["check_out"])
        total_noites = (co - ci).days
        if total_noites <= 0:
            continue

        valor      = float(r["valor_total"])
        comissao   = COMISSOES.get(r["canal"], 0)
        valor_real = valor * (1 - comissao)
        valor_noite      = valor / total_noites
        valor_noite_real = valor_real / total_noites

        # percorre cada noite da reserva e distribui proporcionalmente
        d = ci
        noites_no_ano = {i: 0 for i in range(1, 13)}
        while d < co:
            if d.year == ano:
                noites_no_ano[d.month] += 1
            d += timedelta(days=1)

        chave_reserva = (r["check_in"], r["check_out"], r["canal"])
        for mes, noites in noites_no_ano.items():
            if noites == 0:
                continue
            meses[mes]["diarias"]          += noites
            meses[mes]["faturamento"]      += valor_noite * noites
            meses[mes]["faturamento_real"] += valor_noite_real * noites
            # conta a reserva apenas no mês do check-in (evita duplicar contagem)
            if mes == ci.month and ci.year == ano and chave_reserva not in reservas_contadas:
                meses[mes]["reservas"] += 1
                reservas_contadas.add(chave_reserva)

    resultado = []
    for m, dados in meses.items():
        dias_no_mes = calendar.monthrange(ano, m)[1]
        occ = round(dados["diarias"] / dias_no_mes, 4) if dias_no_mes else 0
        adr = round(dados["faturamento"] / dados["diarias"], 2) if dados["diarias"] else 0
        resultado.append({"mes": m, "occ": occ, "adr": adr, **dados})
    return jsonify(resultado)

@bp.post("/api/admin/marcar-todos-pago")
def marcar_todos_pago():
    db = get_client()
    db.table("reservas").update({"status_financeiro": "Paga"}).neq("canal", "Bloqueio").execute()
    return jsonify({"ok": True, "msg": "Todas as reservas marcadas como Paga"})

@bp.route("/api/agent/run", methods=["GET","POST"])
def rodar_agente():
    try:
        verificar_feeds()
        return jsonify({"ok": True, "msg": "Agente iCal executado com sucesso"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/api/webhook/whatsapp")
def webhook_whatsapp():
    data = request.json or {}
    texto = data.get("text", "") or data.get("message", "")
    if texto.upper().startswith("BLOQUEIO "):
        uid_prefix = texto[9:].strip()
        ok, msg = processar_bloqueio_telegram(uid_prefix)
        return jsonify({"ok": ok, "msg": msg})
    if texto.upper().startswith("RESERVA "):
        ok, msg = processar_resposta_whatsapp(texto)
        return jsonify({"ok": ok, "msg": msg})
    return jsonify({"ok": False, "msg": "Mensagem ignorada"})

@bp.get("/api/calendar/export.ics")
def exportar_ical():
    db = get_client()
    res = db.table("reservas").select("uid,check_in,check_out,hospede,canal,status").gte("check_out", str(date.today())).execute()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Suite Vila PMS//PT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Suite Vila",
    ]
    for r in res.data:
        uid = r.get("uid") or f"{r['check_in']}-{r['check_out']}@suitevila"
        ci  = r["check_in"].replace("-", "")
        co  = r["check_out"].replace("-", "")
        hospede = r.get("hospede") or "Reservado"
        canal   = r.get("canal") or ""
        summary = "Bloqueado" if r.get("status") == "Bloqueado" else f"{hospede} ({canal})"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;VALUE=DATE:{ci}",
            f"DTEND;VALUE=DATE:{co}",
            f"SUMMARY:{summary}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines), mimetype="text/calendar", headers={
        "Content-Disposition": "attachment; filename=suite-vila.ics"
    })

@bp.post("/api/webhook/telegram")
def webhook_telegram():
    data = request.json or {}
    msg = data.get("message") or data.get("channel_post") or {}
    texto = msg.get("text", "").strip()
    if not texto:
        return jsonify({"ok": True})
    if texto.upper().startswith("BLOQUEIO "):
        uid_prefix = texto[9:].strip()
        ok, msg_resp = processar_bloqueio_telegram(uid_prefix)
    elif texto.upper().startswith("RESERVA "):
        ok, msg_resp = processar_resposta_whatsapp(texto)
    else:
        return jsonify({"ok": True})
    return jsonify({"ok": ok, "msg": msg_resp})
