"""Camada de banco: conexão SQLite e inicialização/migração simples."""

from __future__ import annotations

import os
import sqlite3

from flask import g

DB_NAME = "database.db"


def get_db() -> sqlite3.Connection:
    """Retorna a conexão SQLite para a request atual."""
    if "db" not in g:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, DB_NAME)
        g.db = sqlite3.connect(db_path, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exception=None) -> None:
    """Fecha a conexão do banco ao final da request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def coluna_existe(cursor: sqlite3.Cursor, tabela: str, coluna: str) -> bool:
    """Verifica se uma coluna existe na tabela (SQLite)."""
    cursor.execute(f"PRAGMA table_info({tabela})")
    cols = [row[1] for row in cursor.fetchall()]
    return coluna in cols


def init_db() -> None:
    """Cria tabelas e aplica migrações simples."""
    con = get_db()
    cur = con.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha_hash BLOB NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            nome TEXT NOT NULL,
            telefone TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            nome TEXT NOT NULL,
            preco REAL NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            cliente_id INTEGER,
            produto_id INTEGER,
            quantidade INTEGER,
            data TEXT,
            vencimento TEXT,
            hora_vencimento TEXT,
            pago INTEGER DEFAULT 0,
            juros REAL DEFAULT 0,
            data_pagamento TEXT,
            valor_pago REAL,
            asaas_customer_id TEXT,
            asaas_payment_id TEXT,
            asaas_invoice_url TEXT,
            pix_payload TEXT,
            pix_qr_code TEXT,
            asaas_status TEXT,
            whatsapp_enviado INTEGER DEFAULT 0,
            whatsapp_enviado_em TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            minimo INTEGER NOT NULL DEFAULT 0,
            UNIQUE(usuario_id, produto_id)
        )
        """
    )

    migracoes = [
        ("clientes", ["usuario_id"]),
        ("produtos", ["usuario_id"]),
        ("pedidos", ["usuario_id", "vencimento", "hora_vencimento", "juros", "data_pagamento", "valor_pago", "asaas_customer_id", "asaas_payment_id", "asaas_invoice_url", "pix_payload", "pix_qr_code", "asaas_status", "whatsapp_enviado", "whatsapp_enviado_em"]),
        ("estoque", ["usuario_id", "produto_id", "quantidade", "minimo"]),
    ]

    for tabela, colunas in migracoes:
        try:
            for col in colunas:
                if coluna_existe(cur, tabela, col):
                    continue

                if col == "vencimento":
                    cur.execute(
                        f"ALTER TABLE {tabela} ADD COLUMN {col} TEXT"
                    )
                elif col in ("juros", "valor_pago"):
                    cur.execute(
                        f"ALTER TABLE {tabela} ADD COLUMN {col} REAL"
                    )
                elif col in (
                    "quantidade", "minimo", "usuario_id", "produto_id", "whatsapp_enviado"
                ):
                    cur.execute(
                        f"ALTER TABLE {tabela} ADD COLUMN {col} INTEGER"
                    )
                else:
                    cur.execute(
                        f"ALTER TABLE {tabela} ADD COLUMN {col} TEXT"
                    )
        except sqlite3.OperationalError:
            # Se algo não existir (banco antigo), seguimos sem quebrar.
            pass

    con.commit()