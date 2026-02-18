import time
import os
from app import create_app

# Força habilitação do scheduler neste processo
os.environ.setdefault("WHATSAPP_AUTOMATICO", "1")

app = create_app()

if __name__ == "__main__":
    # Mantém o processo vivo (scheduler roda em background)
    while True:
        time.sleep(60)
