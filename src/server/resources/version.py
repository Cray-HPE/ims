"""
# Image Management Services Version API
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
"""

from flask import current_app as app
from flask_restful import Resource
from src.server.helper import get_log_id


class Version(Resource):
    """ Return IMS version information """

    def get(self):
        """ Return IMS version information """

        log_id = get_log_id()
        app.logger.info("%s ++ version.GET", log_id)

        return_value = {
            'version': app.config["VERSION"],
        }

        app.logger.debug("%s Returning json response: %s", log_id, return_value)
        return return_value, 200
