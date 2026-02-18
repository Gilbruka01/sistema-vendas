"""Rotas de pedidos (criar, listar e marcar como pago)."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request

from .db import get_db
from .utils import current_user_id, login_required, vencimento_do_pedido

bp = Blueprint("pedidos", __name__)


@bp.route("/pedidos", methods=["GET", "POST"])
@login_required
def pedidos():
    """Tela de criação de pedidos."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT id, nome, telefone FROM clientes "
        "WHERE usuario_id = ? ORDER BY nome",
        (uid,),
    )
    clientes = cur.fetchall()

    cur.execute(
        "SELECT id, nome, preco FROM produtos "
        "WHERE usuario_id = ? ORDER BY nome",
        (uid,),
    )
    produtos = cur.fetchall()

    if request.method == "POST":
        try:
            cliente_id = int(request.form["cliente_id"])
            produto_id = int(request.form["produto_id"])
            quantidade = int(request.form["quantidade"])
            if quantidade < 1:
                raise ValueError
        except (KeyError, ValueError):
            flash("Dados inválidos!", "error")
            return redirect("/pedidos")

        cur.execute(
            "SELECT 1 FROM clientes WHERE id = ? AND usuario_id = ?",
            (cliente_id, uid),
        )
        if not cur.fetchone():
            flash("Cliente inválido!", "error")
            return redirect("/pedidos")

        cur.execute(
            "SELECT 1 FROM produtos WHERE id = ? AND usuario_id = ?",
            (produto_id, uid),
        )
        if not cur.fetchone():
            flash("Produto inválido!", "error")
            return redirect("/pedidos")

        hoje = date.today()
        venc = vencimento_do_pedido(hoje)

        cur.execute(
            """
            INSERT INTO pedidos (
                usuario_id,
                cliente_id,
                produto_id,
                quantidade,
                data,
                vencimento,
                hora_vencimento,
                pago
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                uid,
                cliente_id,
                produto_id,
                quantidade,
                hoje.isoformat(),
                venc.isoformat(),
                '09:00',
            ),
        )
        con.commit()

        flash("Pedido criado ✅", "success")
        return redirect("/listar_pedidos")

    return render_template(
        "pedidos.html",
        clientes=clientes,
        produtos=produtos,
    )


@bp.route("/listar_pedidos")
@login_required
def listar_pedidos():
    """Lista pedidos do usuário."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT
            pedidos.id,
            pedidos.data,
            clientes.nome,
            produtos.nome,
            produtos.preco,
            pedidos.quantidade,
            (produtos.preco * pedidos.quantidade) AS total,
            pedidos.pago
        FROM pedidos
        JOIN clientes ON clientes.id = pedidos.cliente_id
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.usuario_id = ?
        ORDER BY pedidos.id DESC
        """,
        (uid,),
    )

    lista = cur.fetchall()
    return render_template("listar_pedidos.html", pedidos=lista)


@bp.route("/marcar_pago/<int:pedido_id>", methods=["POST"])
@login_required
def marcar_pago(pedido_id: int):
    """Marca um pedido como pago."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        "UPDATE pedidos SET pago = 1 WHERE id = ? AND usuario_id = ?",
        (pedido_id, uid),
    )
    con.commit()

    flash("Pedido marcado como pago ✅", "success")
    return redirect("/listar_pedidos")
