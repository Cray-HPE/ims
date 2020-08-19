# Image Management Services Version API
# Copyright 2018, 2019, Cray Inc. All Rights Reserved.

from flask import current_app as app
from flask_restful import Resource
from ims.helper import get_log_id

class Version(Resource):
    def __init__(self):
        pass

    def get(self):
        """Return service version"""

        log_id = get_log_id()
        app.logger.info("%s ++ version.GET", log_id)

        return_value = {
            'version': app.config["VERSION"],
        }

        app.logger.debug("%s Returning json response: %s", log_id, return_value)
        return return_value, 200
