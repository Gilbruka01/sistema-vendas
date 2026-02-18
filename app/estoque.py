"""Rotas de estoque (entrada/saída e mínimo)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request

from .db import get_db
from .utils import current_user_id, login_required

bp = Blueprint("estoque", __name__)


@bp.route("/estoque", methods=["GET", "POST"])
@login_required
def estoque():
    """Mostra e atualiza o estoque por produto."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    # Garante linha de estoque para todos os produtos do usuário
    cur.execute("SELECT id FROM produtos WHERE usuario_id = ?", (uid,))
    produtos_ids = [r[0] for r in cur.fetchall()]
    for pid in produtos_ids:
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
            (uid, pid),
        )
    con.commit()

    if request.method == "POST":
        try:
            produto_id = int(request.form["produto_id"])
            acao = request.form["acao"]  # add/sub
            qtd = int(request.form["qtd"])
            minimo_raw = request.form.get("minimo", "").strip()
            minimo_val = int(minimo_raw) if minimo_raw else None

            if acao not in ("add", "sub") or qtd < 1:
                raise ValueError
        except (KeyError, ValueError):
            flash("Dados inválidos.", "error")
            return redirect("/estoque")

        cur.execute(
            "SELECT 1 FROM produtos WHERE id = ? AND usuario_id = ?",
            (produto_id, uid),
        )
        if not cur.fetchone():
            flash("Produto inválido.", "error")
            return redirect("/estoque")

        cur.execute(
            "SELECT quantidade, minimo FROM estoque "
            "WHERE usuario_id = ? AND produto_id = ?",
            (uid, produto_id),
        )
        row = cur.fetchone()
        atual_qtd = row[0] if row else 0
        atual_min = row[1] if row else 0

        nova_qtd = atual_qtd + qtd if acao == "add" else atual_qtd - qtd
        nova_qtd = max(nova_qtd, 0)

        if minimo_val is None:
            minimo_val = atual_min

        cur.execute(
            """
            UPDATE estoque
            SET quantidade = ?, minimo = ?
            WHERE usuario_id = ? AND produto_id = ?
            """,
            (nova_qtd, minimo_val, uid, produto_id),
        )
        con.commit()

        flash("Estoque atualizado ✅", "success")
        return redirect("/estoque")

    cur.execute(
        """
        SELECT p.id, p.nome, p.preco, e.quantidade, e.minimo
        FROM produtos p
        LEFT JOIN estoque e
          ON e.produto_id = p.id AND e.usuario_id = p.usuario_id
        WHERE p.usuario_id = ?
        ORDER BY p.nome
        """,
        (uid,),
    )
    itens = cur.fetchall()
    return render_template("estoque.html", itens=itens)
