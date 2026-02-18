"""Funções utilitárias (auth, datas e validações)."""

from __future__ import annotations

from datetime import date, timedelta
from functools import wraps

from flask import flash, redirect, session, url_for


def apenas_numeros(texto: str) -> str:
    """Remove tudo que não for dígito."""
    return "".join(ch for ch in (texto or "") if ch.isdigit())


def login_required(func):
    """Decorator: exige usuário logado."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Faça login para acessar o sistema.", "warning")
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)

    return wrapper


def current_user_id() -> int:
    """Retorna o id do usuário logado."""
    return int(session["user_id"])


def primeiro_dia_util(ano: int, mes: int) -> date:
    """Retorna o primeiro dia útil do mês (seg-sex)."""
    dia = date(ano, mes, 1)
    while dia.weekday() >= 5:  # 5=sábado, 6=domingo
        dia += timedelta(days=1)
    return dia


def vencimento_do_pedido(data_pedido: date) -> date:
    """Vencimento padrão: primeiro dia útil do próximo mês."""
    ano = data_pedido.year
    mes = data_pedido.month

    if mes == 12:
        return primeiro_dia_util(ano + 1, 1)

    return primeiro_dia_util(ano, mes + 1)
