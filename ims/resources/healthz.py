# Image Management Services Version API
# Copyright 2020, Cray Inc.

from flask import current_app as app
from flask_restful import Resource

from ims.helper import get_log_id


class Ready(Resource):
    """Return k8s readiness check"""
    def get(self):
        log_id = get_log_id()
        app.logger.debug("%s ++ healthz/ready.GET", log_id)
        return {}, 200


class Live(Resource):
    """Return k8s liveness check"""
    def get(self):
        log_id = get_log_id()
        app.logger.debug("%s ++ healthz/live.GET", log_id)
        return {}, 200
