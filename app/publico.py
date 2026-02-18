"""Área pública (sem login) para clientes fazerem pedidos."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .db import get_db
from .asaas_service import create_or_get_customer, create_pix_payment, get_pix_qrcode
import os
from .utils import vencimento_do_pedido

bp = Blueprint("publico", __name__)


def _usuario_padrao_id() -> int | None:
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id FROM usuarios ORDER BY id ASC LIMIT 1")
    row = cur.fetchone()
    return int(row["id"]) if row else None


@bp.route("/loja", methods=["GET", "POST"])
def loja():
    uid = _usuario_padrao_id()
    if uid is None:
        return render_template("loja_sem_usuario.html")

    con = get_db()
    cur = con.cursor()

    cur.execute(
        "SELECT id, nome, preco FROM produtos WHERE usuario_id = ? ORDER BY nome",
        (uid,),
    )
    produtos = cur.fetchall()

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        telefone = (request.form.get("telefone") or "").strip()
        produto_id = request.form.get("produto_id")
        quantidade = request.form.get("quantidade")
        vencimento = (request.form.get("vencimento") or "").strip()
        hora_vencimento = (request.form.get("hora_vencimento") or "").strip() or "09:00"

        if not nome or not produto_id or not quantidade:
            flash("Preencha nome, produto e quantidade.", "error")
            return redirect(url_for("publico.loja"))

        try:
            produto_id_int = int(produto_id)
            qtd_int = int(quantidade)
            if qtd_int < 1:
                raise ValueError
        except ValueError:
            flash("Quantidade inválida.", "error")
            return redirect(url_for("publico.loja"))

        # valida vencimento (se não enviar, usa padrão)
        if vencimento:
            try:
                date.fromisoformat(vencimento)
            except ValueError:
                vencimento = ""
        if not vencimento:
            vencimento = vencimento_do_pedido(date.today()).isoformat()

        # garante que produto existe
        cur.execute(
            "SELECT 1 FROM produtos WHERE id = ? AND usuario_id = ?",
            (produto_id_int, uid),
        )
        if not cur.fetchone():
            flash("Produto inválido.", "error")
            return redirect(url_for("publico.loja"))

        # cria / reaproveita cliente por telefone (se vier)
        cliente_id = None
        if telefone:
            cur.execute(
                "SELECT id FROM clientes WHERE usuario_id = ? AND telefone = ? LIMIT 1",
                (uid, telefone),
            )
            row = cur.fetchone()
            if row:
                cliente_id = int(row["id"])

        if cliente_id is None:
            cur.execute(
                "INSERT INTO clientes (usuario_id, nome, telefone) VALUES (?, ?, ?)",
                (uid, nome, telefone),
            )
            cliente_id = cur.lastrowid

        hoje = date.today().isoformat()

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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (uid, cliente_id, produto_id_int, qtd_int, hoje, vencimento, hora_vencimento),
        )
        con.commit()

        return redirect(url_for("publico.sucesso"))

    

pedido_id = cur.lastrowid

# Cria cobrança PIX no Asaas (se configurado)
if os.getenv("ASAAS_API_KEY"):
    cur.execute(
        "SELECT nome, preco FROM produtos WHERE id = ? AND usuario_id = ?",
        (produto_id_int, uid),
    )
    pr = cur.fetchone()
    if pr:
        descricao = f"Pedido #{pedido_id} - {pr['nome']} x{qtd_int}"
        valor = float(pr["preco"]) * int(qtd_int)
        try:
            customer_id = create_or_get_customer(nome, telefone, external_reference=str(cliente_id))
            pay = create_pix_payment(
                customer_id=customer_id,
                value=valor,
                due_date_iso=vencimento,
                description=descricao,
                external_reference=str(pedido_id),
            )
            pay_id = pay.get("id")
            invoice_url = pay.get("invoiceUrl")

            pix_payload = None
            pix_qr = None
            if pay_id:
                qr = get_pix_qrcode(pay_id)
                pix_payload = (
                    qr.get("payload")
                    or qr.get("brCode")
                    or qr.get("copyPaste")
                    or qr.get("encodedText")
                )
                pix_qr = qr.get("encodedImage")

            cur.execute(
                """
                UPDATE pedidos
                SET asaas_customer_id = ?,
                    asaas_payment_id = ?,
                    asaas_invoice_url = ?,
                    pix_payload = ?,
                    pix_qr_code = ?,
                    asaas_status = ?
                WHERE id = ?
                """,
                (customer_id, pay_id, invoice_url, pix_payload, pix_qr, "PAYMENT_CREATED", pedido_id),
            )
        except Exception:
            pass
venc_padrao = vencimento_do_pedido(date.today()).isoformat()

    return render_template(
        "loja.html",
        produtos=produtos,
        venc_padrao=venc_padrao,
    )


@bp.route("/loja/sucesso")
def sucesso():
    return render_template("loja_sucesso.html")
