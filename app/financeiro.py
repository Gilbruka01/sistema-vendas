"""Painel financeiro simples."""

from __future__ import annotations

from flask import Blueprint, render_template
from .auth import login_required
from .db import get_db

bp = Blueprint("financeiro", __name__)

@bp.route("/financeiro")
@login_required
def financeiro():
    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT COALESCE(SUM(valor_pago),0) AS total_recebido FROM pedidos WHERE pago = 1")
    total_recebido = float(cur.fetchone()["total_recebido"] or 0)

    cur.execute("SELECT COUNT(*) AS qtd_abertos FROM pedidos WHERE pago = 0")
    qtd_abertos = int(cur.fetchone()["qtd_abertos"] or 0)

    cur.execute("""
        SELECT
            p.id,
            p.data_pagamento,
            p.valor_pago,
            c.nome AS cliente,
            pr.nome AS produto
        FROM pedidos p
        JOIN clientes c ON c.id = p.cliente_id
        JOIN produtos pr ON pr.id = p.produto_id
        WHERE p.pago = 1
        ORDER BY p.data_pagamento DESC
        LIMIT 20
    """)
    ultimos = cur.fetchall()

    return render_template(
        "financeiro.html",
        total_recebido=total_recebido,
        qtd_abertos=qtd_abertos,
        ultimos=ultimos,
    )
