"""Scheduler de cobranças automáticas.

Como funciona:
- A cada 1 minuto, busca pedidos em aberto (pago=0) que já chegaram no vencimento (data + hora)
  e ainda não tiveram WhatsApp enviado.
- Envia a mensagem e marca whatsapp_enviado=1.

IMPORTANTE:
- Isso só roda se o sistema estiver EXECUTANDO num servidor ligado 24/7.
  Se você fechar o programa, ele não consegue enviar mensagens.
"""

from __future__ import annotations

from datetime import datetime
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from .db import get_db
from .whatsapp_service import enviar_whatsapp

TAXA_JUROS_DIA = 0.03  # 3% ao dia


def _agora_local() -> datetime:
    return datetime.now()


def _parse_data_hora(data_iso: str | None, hora_hhmm: str | None) -> datetime | None:
    if not data_iso:
        return None
    try:
        hora = (hora_hhmm or "09:00").strip()
        if len(hora) == 5:
            dt = datetime.fromisoformat(f"{data_iso}T{hora}:00")
        else:
            dt = datetime.fromisoformat(f"{data_iso}T09:00:00")
        return dt
    except Exception:
        return None


def _calcular_total(preco: float, qtd: int, venc_dt: datetime, agora: datetime) -> tuple[float, float, int]:
    principal = float(preco) * int(qtd)
    dias_atraso = max((agora.date() - venc_dt.date()).days, 0)
    juros = principal * TAXA_JUROS_DIA * dias_atraso if dias_atraso > 0 else 0.0
    total = principal + juros
    return total, juros, dias_atraso


def _job_enviar_cobrancas(app: Flask) -> None:
    with app.app_context():
        con = get_db()
        cur = con.cursor()

        # Seleciona pedidos em aberto e ainda não enviados
        cur.execute(
            """
            SELECT
                p.id              AS pedido_id,
                p.usuario_id      AS usuario_id,
                p.vencimento      AS vencimento,
                p.hora_vencimento AS hora_vencimento,
                p.data            AS data_pedido,
                p.quantidade      AS quantidade,
                p.whatsapp_enviado AS whatsapp_enviado,
                p.asaas_invoice_url AS asaas_invoice_url,
                p.pix_payload AS pix_payload,
                c.nome            AS cliente_nome,
                c.telefone        AS cliente_telefone,
                pr.nome           AS produto_nome,
                pr.preco          AS produto_preco
            FROM pedidos p
            JOIN clientes c ON c.id = p.cliente_id
            JOIN produtos pr ON pr.id = p.produto_id
            WHERE p.pago = 0 AND (p.whatsapp_enviado IS NULL OR p.whatsapp_enviado = 0)
            """
        )
        rows = cur.fetchall()
        agora = _agora_local()

        for r in rows:
            venc_dt = _parse_data_hora(r["vencimento"], r["hora_vencimento"])
            if venc_dt is None:
                continue

            # Só dispara quando chegou a data+hora
            if agora < venc_dt:
                continue

            telefone = r["cliente_telefone"] or ""
            if not telefone:
                continue

            total, juros, dias = _calcular_total(
                float(r["produto_preco"]),
                int(r["quantidade"] or 0),
                venc_dt,
                agora,
            )

            nome = r["cliente_nome"]
            produto = r["produto_nome"]
            pedido_id = int(r["pedido_id"])

            msg = (
                f"Olá {nome}! 👋\n\n"
                f"Sua cobrança chegou agora ({venc_dt.strftime('%d/%m/%Y %H:%M')}).\n"
                f"Pedido #{pedido_id}: {produto} x{int(r['quantidade'])}\n"
                f"Total atualizado: R$ {total:.2f}\n"
            )
            if dias > 0:
                msg += f"Inclui juros de R$ {juros:.2f} (3% ao dia, {dias} dia(s) de atraso).\n"
            
# Se houver PIX, inclui link e código copia-e-cola
if r.get("asaas_invoice_url"):
    msg += f"\nLink do pagamento (Pix): {r['asaas_invoice_url']}\n"
if r.get("pix_payload"):
    msg += f"\nPix Copia e Cola:\n{r['pix_payload']}\n"

msg += "\nResponda aqui confirmando o pagamento 🙂"

            ok = enviar_whatsapp(telefone, msg)

            if ok:
                cur.execute(
                    """
                    UPDATE pedidos
                    SET whatsapp_enviado = 1,
                        whatsapp_enviado_em = ?
                    WHERE id = ?
                    """,
                    (agora.isoformat(timespec="seconds"), pedido_id),
                )
                con.commit()


def start_scheduler(app: Flask) -> None:
    """Inicia o scheduler em background, se habilitado por env var."""
    if os.getenv("WHATSAPP_AUTOMATICO", "0") != "1":
        return

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(lambda: _job_enviar_cobrancas(app), "interval", minutes=1, id="cobrancas_whatsapp")
    sched.start()

    # guarda referência para evitar GC
    app.extensions["apscheduler"] = sched
