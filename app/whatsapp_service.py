"""Envio de mensagens WhatsApp via provedor.

Implementação principal: Twilio WhatsApp.
- Requer variáveis de ambiente:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_WHATSAPP_FROM  (ex: whatsapp:+14155238886 ou seu número aprovado no Twilio)

Observações:
- Para enviar para clientes, o número deve estar em formato E.164 e, no WhatsApp do Twilio,
  geralmente precisa estar como: whatsapp:+55XXXXXXXXXXX
"""

from __future__ import annotations

import os
import re
from typing import Optional

import requests


def normalizar_telefone_br(telefone: str) -> Optional[str]:
    """Normaliza telefone BR para E.164 (sem espaços). Retorna apenas dígitos com DDI 55.

    Ex:
    - (11) 91234-5678 -> 5511912345678
    """
    if not telefone:
        return None
    digits = re.sub(r"\D+", "", telefone)
    if not digits:
        return None
    # Se já começar com 55, mantemos; caso contrário, adiciona
    if digits.startswith("55"):
        return digits
    return "55" + digits


def enviar_whatsapp_twilio(telefone_e164_sem_sinal: str, mensagem: str) -> bool:
    """Envia mensagem WhatsApp pelo Twilio. Retorna True/False."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()

    if not (account_sid and auth_token and from_whatsapp):
        return False

    to_whatsapp = f"whatsapp:+{telefone_e164_sem_sinal}"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    data = {
        "From": from_whatsapp,
        "To": to_whatsapp,
        "Body": mensagem,
    }

    resp = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=30)
    return 200 <= resp.status_code < 300


def enviar_whatsapp(telefone: str, mensagem: str) -> bool:
    """Ponto único de envio (por enquanto Twilio)."""
    tel = normalizar_telefone_br(telefone)
    if not tel:
        return False
    return enviar_whatsapp_twilio(tel, mensagem)
