import os


bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
capture_output = True
