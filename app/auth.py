from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template
from werkzeug.security import check_password_hash, generate_password_hash
from app.database import get_client
from functools import wraps

auth_bp = Blueprint("auth", __name__)

TELAS = ["calendario", "reservas", "relatorio", "config"]

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("usuario_id"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Não autenticado"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("papel") != "admin":
            return jsonify({"error": "Acesso negado"}), 403
        return f(*args, **kwargs)
    return decorated

def tem_permissao(tela):
    if session.get("papel") == "admin":
        return True
    perms = session.get("permissoes", [])
    return tela in perms

@auth_bp.get("/login")
def login_page():
    if session.get("usuario_id"):
        return redirect("/")
    return render_template("login.html")

@auth_bp.post("/api/auth/login")
def do_login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    senha = data.get("senha", "")
    db = get_client()
    res = db.table("usuarios").select("*").eq("email", email).eq("ativo", True).execute()
    if not res.data:
        return jsonify({"error": "Usuário ou senha inválidos"}), 401
    user = res.data[0]
    if not check_password_hash(user["senha_hash"], senha):
        return jsonify({"error": "Usuário ou senha inválidos"}), 401
    # carrega permissões
    perms_res = db.table("permissoes_usuario").select("tela").eq("usuario_id", user["id"]).eq("permitido", True).execute()
    perms = [p["tela"] for p in perms_res.data]
    session.permanent = True
    session["usuario_id"] = user["id"]
    session["nome"] = user["nome"]
    session["email"] = user["email"]
    session["papel"] = user["papel"]
    session["permissoes"] = perms
    return jsonify({"ok": True, "nome": user["nome"], "papel": user["papel"], "permissoes": perms})

@auth_bp.post("/api/auth/logout")
def do_logout():
    session.clear()
    return jsonify({"ok": True})

@auth_bp.get("/api/auth/me")
def me():
    if not session.get("usuario_id"):
        return jsonify({"autenticado": False}), 401
    return jsonify({
        "autenticado": True,
        "nome": session.get("nome"),
        "papel": session.get("papel"),
        "permissoes": session.get("permissoes", []),
    })

# --- Admin: gerenciar usuários ---

@auth_bp.get("/api/admin/usuarios")
@login_required
@admin_required
def listar_usuarios():
    db = get_client()
    users = db.table("usuarios").select("id,nome,email,papel,ativo,criado_em").order("id").execute()
    perms = db.table("permissoes_usuario").select("*").execute()
    perms_map = {}
    for p in perms.data:
        perms_map.setdefault(p["usuario_id"], {})[p["tela"]] = p["permitido"]
    for u in users.data:
        u["permissoes"] = perms_map.get(u["id"], {})
    return jsonify(users.data)

@auth_bp.post("/api/admin/usuarios")
@login_required
@admin_required
def criar_usuario():
    data = request.json
    db = get_client()
    senha_hash = generate_password_hash(data["senha"], method="pbkdf2:sha256")
    res = db.table("usuarios").insert({
        "nome": data["nome"],
        "email": data["email"].lower(),
        "senha_hash": senha_hash,
        "papel": data.get("papel", "visitante"),
        "ativo": True,
    }).execute()
    uid = res.data[0]["id"]
    # salva permissões
    for tela in TELAS:
        db.table("permissoes_usuario").upsert({
            "usuario_id": uid,
            "tela": tela,
            "permitido": data.get("permissoes", {}).get(tela, False),
        }).execute()
    return jsonify(res.data[0]), 201

@auth_bp.put("/api/admin/usuarios/<int:uid>")
@login_required
@admin_required
def atualizar_usuario(uid):
    data = request.json
    db = get_client()
    upd = {"nome": data["nome"], "email": data["email"].lower(), "papel": data["papel"], "ativo": data.get("ativo", True)}
    if data.get("senha"):
        upd["senha_hash"] = generate_password_hash(data["senha"], method="pbkdf2:sha256")
    db.table("usuarios").update(upd).eq("id", uid).execute()
    for tela in TELAS:
        db.table("permissoes_usuario").upsert({
            "usuario_id": uid,
            "tela": tela,
            "permitido": data.get("permissoes", {}).get(tela, False),
        }).execute()
    return jsonify({"ok": True})

@auth_bp.delete("/api/admin/usuarios/<int:uid>")
@login_required
@admin_required
def deletar_usuario(uid):
    if uid == session.get("usuario_id"):
        return jsonify({"error": "Não pode excluir a si mesmo"}), 400
    db = get_client()
    db.table("usuarios").delete().eq("id", uid).execute()
    return jsonify({"ok": True})
