from flask import Blueprint, jsonify, request, render_template
from app.database import get_client
from agent.ical_agent import verificar_feeds, processar_resposta_whatsapp
from datetime import date

bp = Blueprint("main", __name__)

@bp.get("/")
def index():
    return render_template("index.html")

@bp.get("/api/reservas")
def listar_reservas():
    db = get_client()
    ano = request.args.get("ano", date.today().year)
    res = db.table("reservas").select("*").gte("check_in", f"{ano}-01-01").lte("check_in", f"{ano}-12-31").order("check_in", desc=True).execute()
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
    ano = request.args.get("ano", date.today().year)
    res = db.table("reservas").select("check_in,check_out,valor_total,canal,diarias,adr").gte("check_in", f"{ano}-01-01").lte("check_in", f"{ano}-12-31").neq("status", "Bloqueado").execute()

    COMISSOES = {"Booking": 0.13, "Airbnb": 0.03, "Direta": 0.0, "Vrbo": 0.0}
    meses = {i: {"diarias": 0, "faturamento": 0.0, "faturamento_real": 0.0, "reservas": 0} for i in range(1, 13)}

    for r in res.data:
        if not r["valor_total"]:
            continue
        mes = int(r["check_in"][5:7])
        comissao = COMISSOES.get(r["canal"], 0)
        meses[mes]["diarias"] += r["diarias"] or 0
        meses[mes]["faturamento"] += float(r["valor_total"])
        meses[mes]["faturamento_real"] += float(r["valor_total"]) * (1 - comissao)
        meses[mes]["reservas"] += 1

    dias_mes = [31,28,31,30,31,30,31,31,30,31,30,31]
    resultado = []
    for m, dados in meses.items():
        occ = round(dados["diarias"] / dias_mes[m-1], 4) if dias_mes[m-1] else 0
        adr = round(dados["faturamento"] / dados["diarias"], 2) if dados["diarias"] else 0
        resultado.append({"mes": m, "occ": occ, "adr": adr, **dados})
    return jsonify(resultado)

@bp.post("/api/agent/run")
def rodar_agente():
    try:
        verificar_feeds()
        return jsonify({"ok": True, "msg": "Agente executado com sucesso"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/api/webhook/whatsapp")
def webhook_whatsapp():
    data = request.json or {}
    texto = data.get("text", "") or data.get("message", "")
    if texto.upper().startswith("RESERVA "):
        ok, msg = processar_resposta_whatsapp(texto)
        return jsonify({"ok": ok, "msg": msg})
    return jsonify({"ok": False, "msg": "Mensagem ignorada"})
