import os

# Railway injeta a porta em $PORT. Lemos direto do ambiente em Python,
# assim nao dependemos de expansao de shell (que estava falhando no deploy).
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
graceful_timeout = 30
keepalive = 5
