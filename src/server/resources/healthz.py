"""
Kubernetes Health and Liveness functions
Copyright 2020 Hewlett Packard Enterprise Development LP
"""

from flask import current_app as app
from flask_restful import Resource

from src.server.helper import get_log_id


class Ready(Resource):
    """Return k8s readiness check"""
    def get(self):
        """Return k8s readiness check"""
        log_id = get_log_id()
        app.logger.debug("%s ++ healthz/ready.GET", log_id)
        return {}, 200


class Live(Resource):
    """Return k8s liveness check"""
    def get(self):
        """Return k8s liveness check"""
        log_id = get_log_id()
        app.logger.debug("%s ++ healthz/live.GET", log_id)
        return {}, 200
