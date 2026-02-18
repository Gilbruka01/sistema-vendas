"""Rotas de clientes (CRUD)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request

from .db import get_db
from .utils import apenas_numeros, current_user_id, login_required

bp = Blueprint("clientes", __name__)


@bp.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    """Lista e cria clientes."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = apenas_numeros(request.form.get("telefone", ""))

        if not nome:
            flash("Nome inválido!", "warning")
            return redirect("/clientes")

        cur.execute(
            "INSERT INTO clientes (usuario_id, nome, telefone) "
            "VALUES (?, ?, ?)",
            (uid, nome, telefone),
        )
        con.commit()
        flash("Cliente cadastrado ✅", "success")
        return redirect("/clientes")

    cur.execute(
        "SELECT id, nome, telefone FROM clientes "
        "WHERE usuario_id = ? ORDER BY nome",
        (uid,),
    )
    lista = cur.fetchall()
    return render_template("clientes.html", clientes=lista)


@bp.route("/clientes/<int:cliente_id>/editar", methods=["GET", "POST"])
@login_required
def editar_cliente(cliente_id: int):
    """Edita um cliente."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT id, nome, telefone FROM clientes "
        "WHERE id = ? AND usuario_id = ?",
        (cliente_id, uid),
    )
    cliente = cur.fetchone()

    if not cliente:
        flash("Cliente não encontrado.", "warning")
        return redirect("/clientes")

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = apenas_numeros(request.form.get("telefone", ""))

        if not nome:
            flash("Informe o nome do cliente.", "warning")
            return render_template("cliente_editar.html", cliente=cliente)

        cur.execute(
            "UPDATE clientes SET nome = ?, telefone = ? "
            "WHERE id = ? AND usuario_id = ?",
            (nome, telefone, cliente_id, uid),
        )
        con.commit()
        flash("Cliente atualizado ✅", "success")
        return redirect("/clientes")

    return render_template("cliente_editar.html", cliente=cliente)


@bp.route("/clientes/<int:cliente_id>/excluir", methods=["POST"])
@login_required
def excluir_cliente(cliente_id: int):
    """Exclui um cliente."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "DELETE FROM clientes WHERE id = ? AND usuario_id = ?",
        (cliente_id, uid),
    )
    con.commit()
    flash("Cliente excluído ✅", "success")
    return redirect("/clientes")
