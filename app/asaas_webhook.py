"""Webhook do Asaas para dar baixa automática no pagamento.

Segurança:
- Configure um token no Asaas e coloque em ASAAS_WEBHOOK_TOKEN.
  O Asaas envia esse token no header `asaas-access-token`.
"""

from __future__ import annotations

import os
from datetime import datetime

from flask import Blueprint, jsonify, request

from .db import get_db

bp = Blueprint("asaas_webhook", __name__)

def _token_ok() -> bool:
    expected = (os.getenv("ASAAS_WEBHOOK_TOKEN") or "").strip()
    if not expected:
        # se não configurou token, aceitamos (não recomendado)
        return True
    got = (request.headers.get("asaas-access-token") or "").strip()
    return got == expected

@bp.route("/webhook/asaas", methods=["POST"])
def webhook_asaas():
    if not _token_ok():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    event = (payload.get("event") or "").upper()
    payment = payload.get("payment") or {}
    payment_id = payment.get("id")

    # Eventos mais úteis para baixa:
    # PAYMENT_CONFIRMED e PAYMENT_RECEIVED
    if event not in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
        return jsonify({"ok": True, "ignored": event}), 200

    if not payment_id:
        return jsonify({"ok": False, "error": "missing payment id"}), 400

    con = get_db()
    cur = con.cursor()

    # Procura o pedido associado
    cur.execute(
        "SELECT id, valor_pago FROM pedidos WHERE asaas_payment_id = ? LIMIT 1",
        (payment_id,),
    )
    row = cur.fetchone()
    if not row:
        return jsonify({"ok": True, "note": "payment not linked"}), 200

    pedido_id = int(row["id"])
    valor = payment.get("value") or payment.get("netValue") or payment.get("originalValue")
    data_pag = payment.get("paymentDate") or payment.get("clientPaymentDate") or payment.get("confirmedDate")

    # Atualiza baixa
    cur.execute(
        """
        UPDATE pedidos
        SET pago = 1,
            data_pagamento = ?,
            valor_pago = ?,
            asaas_status = ?
        WHERE id = ?
        """,
        (
            (data_pag or datetime.now().isoformat(timespec="seconds")),
            float(valor) if valor is not None else None,
            event,
            pedido_id,
        ),
    )
    con.commit()

    return jsonify({"ok": True, "pedido_id": pedido_id, "event": event}), 200
