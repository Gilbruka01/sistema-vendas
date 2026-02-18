"""Dashboard do sistema (totais e gráfico)."""

from __future__ import annotations

from flask import Blueprint, render_template

from .db import get_db
from .utils import current_user_id, login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def home():
    """Tela inicial com resumo e dados para gráfico."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT SUM(produtos.preco * pedidos.quantidade)
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.pago = 0 AND pedidos.usuario_id = ?
        """,
        (uid,),
    )
    total_aberto = cur.fetchone()[0] or 0

    cur.execute(
        """
        SELECT SUM(produtos.preco * pedidos.quantidade)
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.pago = 1 AND pedidos.usuario_id = ?
        """,
        (uid,),
    )
    total_pago = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM clientes WHERE usuario_id = ?", (uid,))
    total_clientes = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM pedidos WHERE usuario_id = ?", (uid,))
    total_pedidos = cur.fetchone()[0] or 0

    cur.execute(
        """
        SELECT substr(pedidos.data, 1, 7) AS mes,
               SUM(produtos.preco * pedidos.quantidade) AS total
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.usuario_id = ?
        GROUP BY mes
        ORDER BY mes DESC
        LIMIT 6
        """,
        (uid,),
    )
    meses = list(reversed(cur.fetchall()))

    chart_labels = [m[0] for m in meses]
    chart_values = [float(m[1] or 0) for m in meses]

    return render_template(
        "dashboard.html",
        total_aberto=total_aberto,
        total_pago=total_pago,
        total_clientes=total_clientes,
        total_pedidos=total_pedidos,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )
