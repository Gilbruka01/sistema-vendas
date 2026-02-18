"""Rotas de cobranças (fiado em aberto) + baixa de pagamento.

Neste sistema, "cobrança automática" significa:
- O valor exibido é sempre recalculado automaticamente (principal + juros por atraso).
- Ao registrar o pagamento (botão "Dar baixa"), o pedido é marcado como pago e sai da lista.

Para baixa 100% automática via PIX/Boleto/Cartão, é preciso integrar um provedor
(Mercado Pago, Asaas, etc.) e receber um "webhook" de confirmação de pagamento.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote
import re

from flask import Blueprint, redirect, render_template, request, url_for

from .db import get_db
from .utils import (
    apenas_numeros,
    current_user_id,
    login_required,
    vencimento_do_pedido,
)

bp = Blueprint("cobrancas", __name__)

TAXA_JUROS_DIA = 0.03  # 3% ao dia


def _dias_atraso(hoje: date, vencimento: date) -> int:
    """Retorna dias de atraso (nunca negativo)."""
    return max((hoje - vencimento).days, 0)


def _calcular_juros(principal: float, dias_atraso: int) -> float:
    """Calcula juros simples por dia de atraso."""
    if dias_atraso <= 0:
        return 0.0
    return float(principal) * float(TAXA_JUROS_DIA) * int(dias_atraso)


def _vencimento(data_pedido_iso: str, vencimento_iso: str | None) -> date:
    """Resolve vencimento: usa campo vencimento se existir, senão calcula pelo padrão do sistema."""
    if vencimento_iso:
        return date.fromisoformat(vencimento_iso)
    return vencimento_do_pedido(date.fromisoformat(data_pedido_iso))


@bp.route("/cobrancas")
@login_required
def cobrancas():
    """Lista pedidos em aberto, calcula juros e oferece link WhatsApp + baixa manual."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT
            pedidos.id           AS pedido_id,
            clientes.id          AS cliente_id,
            clientes.nome        AS cliente_nome,
            clientes.telefone    AS cliente_telefone,
            pedidos.data         AS data_pedido,
            pedidos.vencimento   AS vencimento,
            pedidos.hora_vencimento AS hora_vencimento,
            produtos.nome        AS produto_nome,
            produtos.preco       AS produto_preco,
            pedidos.quantidade   AS quantidade
        FROM pedidos
        JOIN clientes ON clientes.id = pedidos.cliente_id
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.pago = 0 AND pedidos.usuario_id = ?
        ORDER BY clientes.nome, pedidos.data
        """,
        (uid,),
    )
    linhas = cur.fetchall()

    hoje = date.today()

    por_cliente: dict[int, dict] = {}

    for row in linhas:
        pedido_id = int(row["pedido_id"])
        cliente_id = int(row["cliente_id"])
        nome = row["cliente_nome"]
        telefone_raw = row["cliente_telefone"] or ""
        data_pedido = row["data_pedido"]
        vencimento_raw = row["vencimento"]
        hora_vencimento = row["hora_vencimento"] or "09:00"
        produto = row["produto_nome"]
        preco = float(row["produto_preco"])
        qtd = int(row["quantidade"])

        if cliente_id not in por_cliente:
            por_cliente[cliente_id] = {
                "cliente_id": cliente_id,
                "nome": nome,
                "telefone": telefone_raw,
                "pedidos": [],
                "principal": 0.0,
                "juros": 0.0,
            }

        principal_item = preco * qtd
        venc = _vencimento(data_pedido, vencimento_raw)
        dias = _dias_atraso(hoje, venc)
        juros_item = _calcular_juros(principal_item, dias)
        total_item = principal_item + juros_item

        por_cliente[cliente_id]["principal"] += principal_item
        por_cliente[cliente_id]["juros"] += juros_item
        por_cliente[cliente_id]["pedidos"].append(
            {
                "pedido_id": pedido_id,
                "produto": produto,
                "qtd": qtd,
                "preco": preco,
                "principal": principal_item,
                "vencimento": venc.isoformat(),
                "dias": dias,
                "juros": juros_item,
                "total": total_item,
            }
        )

    clientes: list[dict] = []

    for info in por_cliente.values():
        telefone = apenas_numeros(info["telefone"])
        principal = float(info["principal"])
        juros = float(info["juros"])
        total_final = principal + juros

        # Link WhatsApp só se existir telefone válido
        link = None
        if telefone:
            msg: list[str] = [
                f"Olá {info['nome']}! 👋",
                "",
                "Resumo do seu fiado (em aberto):",
            ]
            for it in info["pedidos"]:
                linha = (
                    f"- {it['produto']} x{it['qtd']} = R$ {it['principal']:.2f} | "
                    f"atraso: {it['dias']}d | juros: R$ {it['juros']:.2f} | "
                    f"total: R$ {it['total']:.2f}"
                )
                msg.append(linha)

            msg.extend(
                [
                    "",
                    f"Subtotal: R$ {principal:.2f}",
                    f"Juros (3% ao dia): R$ {juros:.2f}",
                    f"Total atualizado: R$ {total_final:.2f}",
                    "",
                    "Quando puder, me confirma o pagamento 🙂",
                ]
            )
            texto = chr(10).join(msg)
            link = f"https://wa.me/55{telefone}?text={quote(texto)}"

        clientes.append(
            {
                "cliente_id": info["cliente_id"],
                "nome": info["nome"],
                "total": total_final,
                "principal": principal,
                "juros": juros,
                "link_whatsapp": link,
                "pedidos": info["pedidos"],
            }
        )

    return render_template(
        "cobrancas.html",
        clientes=clientes,
        hoje=hoje.isoformat(),
        taxa_juros_dia=TAXA_JUROS_DIA,
    )



@bp.route("/cobrancas/editar/<int:pedido_id>", methods=["POST"])
@login_required
def editar_cobranca(pedido_id: int):
    """Edita data e horário da cobrança (vencimento) de um pedido em aberto."""
    uid = current_user_id()
    nova_data = (request.form.get("vencimento") or "").strip()
    nova_hora = (request.form.get("hora_vencimento") or "").strip() or "09:00"

    # validação simples de data (YYYY-MM-DD)
    try:
        date.fromisoformat(nova_data)
    except ValueError:
        return redirect(url_for("cobrancas.cobrancas"))

    # validação simples de hora (HH:MM)
    if not re.match(r"^\d{2}:\d{2}$", nova_hora):
        nova_hora = "09:00"

    con = get_db()
    cur = con.cursor()
    cur.execute(
        """
        UPDATE pedidos
        SET vencimento = ?, hora_vencimento = ?
        WHERE id = ? AND usuario_id = ? AND pago = 0
        """,
        (nova_data, nova_hora, pedido_id, uid),
    )
    con.commit()
    return redirect(url_for("cobrancas.cobrancas"))


@bp.route("/cobrancas/pagar/<int:pedido_id>", methods=["POST"])
@login_required
def pagar_pedido(pedido_id: int):
    """Dá baixa em um pedido: marca como pago e registra valor + data."""
    uid = current_user_id()
    con = get_db()
    cur = con.cursor()

    cur.execute(
        """
        SELECT
            pedidos.id         AS pedido_id,
            pedidos.data       AS data_pedido,
            pedidos.vencimento AS vencimento,
            pedidos.quantidade AS quantidade,
            produtos.preco     AS preco
        FROM pedidos
        JOIN produtos ON produtos.id = pedidos.produto_id
        WHERE pedidos.id = ? AND pedidos.usuario_id = ? AND pedidos.pago = 0
        """,
        (pedido_id, uid),
    )
    row = cur.fetchone()
    if row is None:
        return redirect(url_for("cobrancas.cobrancas"))

    hoje = date.today()
    data_pedido = row["data_pedido"]
    vencimento_raw = row["vencimento"]
    qtd = int(row["quantidade"])
    preco = float(row["preco"])

    principal = preco * qtd
    venc = _vencimento(data_pedido, vencimento_raw)
    dias = _dias_atraso(hoje, venc)
    juros = _calcular_juros(principal, dias)
    total = principal + juros

    cur.execute(
        """
        UPDATE pedidos
        SET pago = 1,
            juros = ?,
            data_pagamento = ?,
            valor_pago = ?
        WHERE id = ? AND usuario_id = ?
        """,
        (juros, hoje.isoformat(), total, pedido_id, uid),
    )
    con.commit()

    return redirect(url_for("cobrancas.cobrancas"))
