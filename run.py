import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG") == "1"
    # Se o WhatsApp automático estiver ligado, desativamos o reloader para não duplicar o scheduler
    use_reloader = False if os.getenv("WHATSAPP_AUTOMATICO", "0") == "1" else debug
    app.run(debug=debug, use_reloader=use_reloader)
