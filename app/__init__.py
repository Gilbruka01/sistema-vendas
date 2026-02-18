"""Criação e configuração da aplicação Flask (factory)."""

from __future__ import annotations

import os

from flask import Flask, render_template

from .auth import bp as auth_bp
from .clientes import bp as clientes_bp
from .cobrancas import bp as cobrancas_bp
from .dashboard import bp as dashboard_bp
from .db import close_db, init_db
from .estoque import bp as estoque_bp
from .financeiro import bp as financeiro_bp
from .pedidos import bp as pedidos_bp
from .produtos import bp as produtos_bp
from .publico import bp as publico_bp
from .scheduler import start_scheduler
from .asaas_webhook import bp as asaas_webhook_bp


def create_app() -> Flask:
    """Cria e configura a aplicação Flask."""

    # Caminho raiz do projeto (onde ficam /templates e /static)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )

    # SECRET_KEY por variável de ambiente (fallback só para dev)
    app.secret_key = os.getenv("SECRET_KEY", "dev-key")

    # Cookies de sessão mais seguros (ative SECURE quando estiver em HTTPS)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    )

    # Inicia/cria tabelas
    with app.app_context():
        init_db()

    # Fecha conexão no fim de cada request
    app.teardown_appcontext(close_db)

    # Registra módulos (blueprints)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(produtos_bp)
    app.register_blueprint(pedidos_bp)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(cobrancas_bp)
    app.register_blueprint(financeiro_bp)
    app.register_blueprint(publico_bp)
    app.register_blueprint(asaas_webhook_bp)

    # Inicia scheduler (WhatsApp automático), se WHATSAPP_AUTOMATICO=1
    start_scheduler(app)

    @app.errorhandler(404)
    def pagina_nao_encontrada(_error):
        """Renderiza página 404."""
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def erro_interno(_error):
        """Renderiza página 500."""
        return render_template("500.html"), 500

    return app
