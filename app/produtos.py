"""Rotas de produtos (CRUD)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request

from .db import get_db
from .utils import current_user_id, login_required

bp = Blueprint("produtos", __name__)


@bp.route("/produtos", methods=["GET", "POST"])
@login_required
def produtos():
    """Lista e cria produtos."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        preco_raw = request.form.get("preco", "").strip().replace(",", ".")

        if not nome:
            flash("Nome inválido!", "warning")
            return redirect("/produtos")

        try:
            preco = float(preco_raw)
            if preco <= 0:
                raise ValueError
        except ValueError:
            flash("Preço inválido!", "warning")
            return redirect("/produtos")

        cur.execute(
            "INSERT INTO produtos (usuario_id, nome, preco) VALUES (?, ?, ?)",
            (uid, nome, preco),
        )
        con.commit()

        # Cria linha de estoque para o produto
        produto_id = cur.lastrowid
        cur.execute(
            """
            INSERT OR IGNORE INTO estoque (
                usuario_id,
                produto_id,
                quantidade,
                minimo
            )
            VALUES (?, ?, 0, 0)
            """,
            (uid, produto_id),
        )
        con.commit()

        flash("Produto cadastrado ✅", "success")
        return redirect("/produtos")

    cur.execute(
        "SELECT id, nome, preco FROM produtos "
        "WHERE usuario_id = ? ORDER BY nome",
        (uid,),
    )
    lista = cur.fetchall()
    return render_template("produtos.html", produtos=lista)


@bp.route("/produtos/editar/<int:produto_id>", methods=["GET", "POST"])
@login_required
def editar_produto(produto_id: int):
    """Edita um produto."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT id, nome, preco FROM produtos "
        "WHERE id = ? AND usuario_id = ?",
        (produto_id, uid),
    )
    produto = cur.fetchone()

    if not produto:
        flash("Produto não encontrado.", "warning")
        return redirect("/produtos")

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        preco_raw = request.form.get("preco", "").strip().replace(",", ".")

        if not nome:
            flash("Informe o nome do produto.", "warning")
            return render_template("produto_editar.html", produto=produto)

        try:
            preco = float(preco_raw)
        except ValueError:
            flash("Preço inválido.", "warning")
            return render_template("produto_editar.html", produto=produto)

        cur.execute(
            "UPDATE produtos SET nome = ?, preco = ? "
            "WHERE id = ? AND usuario_id = ?",
            (nome, preco, produto_id, uid),
        )
        con.commit()
        flash("Produto atualizado ✅", "success")
        return redirect("/produtos")

    return render_template("produto_editar.html", produto=produto)


@bp.route("/produtos/excluir/<int:produto_id>", methods=["POST"])
@login_required
def excluir_produto(produto_id: int):
    """Exclui um produto."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "DELETE FROM produtos WHERE id = ? AND usuario_id = ?",
        (produto_id, uid),
    )
    con.commit()
    flash("Produto excluído ✅", "success")
    return redirect("/produtos")
