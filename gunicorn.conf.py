import os

# Configuração de binding dinâmico para Railway / PaaS
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# 1 worker com threads para manter cache em memória compartilhado e baixo consumo de RAM
workers = 1
threads = 4

# Timeout estendido para evitar que downloads pesados derrubem o worker
timeout = 120
keepalive = 5
