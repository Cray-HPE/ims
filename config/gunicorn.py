# Copyright 2020, Cray Inc.
# Gunicorn settings for IMS
import os

bind = "0.0.0.0:80"
# workers = int(os.environ.get('WORKERS', 1))

# Worker
# http://docs.gunicorn.org/en/stable/settings.html#worker-class
# worker_class = os.environ.get('WORKER_CLASS', 'gevent')
# timeout = int(os.environ.get('WORKER_TIMEOUT', 3600))  # seconds

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()
