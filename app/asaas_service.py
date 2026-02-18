"""Integração com Asaas (Pix) + Webhook.

Requer variáveis de ambiente:
- ASAAS_API_KEY: chave de API (produção ou sandbox)
- ASAAS_BASE_URL: opcional (default produção). Ex.: https://api.asaas.com
  Para sandbox: https://api-sandbox.asaas.com
"""

from __future__ import annotations

import os
import re
import requests

DEFAULT_BASE_URL = "https://api.asaas.com"

def _base_url() -> str:
    return (os.getenv("ASAAS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

def _headers() -> dict:
    api_key = os.getenv("ASAAS_API_KEY", "").strip()
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": api_key,
    }

def _clean_phone_br(phone: str) -> str:
    # Asaas aceita telefone sem máscara. Mantemos apenas dígitos.
    digits = re.sub(r"\D+", "", phone or "")
    # Se vier sem DDI, adiciona 55 (Brasil)
    if digits and not digits.startswith("55"):
        digits = "55" + digits
    return digits

def create_or_get_customer(nome: str, telefone: str | None, external_reference: str | None = None) -> str:
    """Cria cliente no Asaas e retorna o customerId.

    Para simplificar, sempre cria (evita busca complexa). Em produção, dá pra
    buscar por CPF/CNPJ/email e reutilizar.
    """
    payload = {
        "name": (nome or "").strip()[:200] or "Cliente",
    }
    phone = _clean_phone_br(telefone or "")
    if phone:
        payload["phone"] = phone
        payload["mobilePhone"] = phone

    if external_reference:
        payload["externalReference"] = external_reference

    r = requests.post(f"{_base_url()}/v3/customers", headers=_headers(), json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("id")

def create_pix_payment(customer_id: str, value: float, due_date_iso: str, description: str, external_reference: str | None = None) -> dict:
    """Cria cobrança PIX e retorna o JSON da cobrança."""
    payload = {
        "customer": customer_id,
        "billingType": "PIX",
        "value": float(value),
        "dueDate": due_date_iso,
        "description": description[:250],
    }
    if external_reference:
        payload["externalReference"] = external_reference

    r = requests.post(f"{_base_url()}/v3/payments", headers=_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def get_pix_qrcode(payment_id: str) -> dict:
    """Obtém QR Code do PIX para uma cobrança.
    Endpoint: GET /v3/payments/{id}/pixQrCode
    """
    r = requests.get(f"{_base_url()}/v3/payments/{payment_id}/pixQrCode", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()
