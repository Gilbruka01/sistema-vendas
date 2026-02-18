"""Rotas e funções de autenticação (register/login/logout)."""

from __future__ import annotations

import sqlite3

import bcrypt
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .db import get_db
from .utils import login_required

bp = Blueprint("auth", __name__)


def criar_usuario(username: str, senha: str) -> None:
    """Cria um usuário com senha armazenada em hash (bcrypt)."""
    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())
    con = get_db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO usuarios (username, senha_hash) VALUES (?, ?)",
        (username, senha_hash),
    )
    con.commit()


def autenticar_usuario(username: str, senha: str) -> int | None:
    """Valida usuário/senha e retorna o id do usuário quando válido."""
    con = get_db()
    cur = con.cursor()
    cur.execute(
        "SELECT id, senha_hash FROM usuarios WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    if not row:
        return None

    user_id, senha_hash = row["id"], row["senha_hash"]
    if isinstance(senha_hash, str):
        senha_hash = senha_hash.encode("utf-8")

    if bcrypt.checkpw(senha.encode("utf-8"), senha_hash):
        return int(user_id)

    return None


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Tela e ação de cadastro."""
    if request.method != "POST":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    senha = request.form.get("senha", "")
    senha2 = request.form.get("senha2", "")

    erro: str | None = None
    if not username or len(username) < 3:
        erro = "Usuário inválido (mínimo 3 caracteres)."
    elif not senha or not senha2:
        erro = "Preencha senha e confirmação."
    elif senha != senha2:
        erro = "As senhas não conferem."
    elif len(senha) < 6:
        erro = "Senha fraca (mínimo 6 caracteres)."

    if erro:
        flash(erro, "warning")
        return redirect(url_for("auth.register"))

    try:
        criar_usuario(username, senha)
    except sqlite3.IntegrityError:
        flash("Esse usuário já existe.", "warning")
        return redirect(url_for("auth.register"))

    flash("Conta criada! Faça login ✅", "success")
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Tela e ação de login."""
    if request.method != "POST":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    senha = request.form.get("senha", "")

    if not username or not senha:
        flash("Preencha usuário e senha.", "warning")
        return redirect(url_for("auth.login"))

    user_id = autenticar_usuario(username, senha)
    if not user_id:
        flash("Usuário ou senha inválidos.", "error")
        return redirect(url_for("auth.login"))

    session["user_id"] = user_id
    session["username"] = username
    flash("Login realizado ✅", "success")
    return redirect("/")


@bp.route("/logout")
@login_required
def logout():
    """Encerra sessão do usuário."""
    session.clear()
    flash("Você saiu da conta.", "info")
    return redirect(url_for("auth.login"))
