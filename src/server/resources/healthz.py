#
# MIT License
#
# (C) Copyright 2020-2022 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""
Kubernetes Health and Liveness functions
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
