#
# MIT License
#
# (C) Copyright 2023 Hewlett Packard Enterprise Development LP
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
Remote Build Nodes API
"""

import http.client
from flask import jsonify, request, current_app
from flask_restful import Resource

from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
    generate_resource_not_found_response
from src.server.helper import get_log_id
from src.server.models.remote_build_nodes import V3RemoteBuildNodeRecordInputSchema, V3RemoteBuildNodeRecordSchema, V3RemoteBuildNodeRecord
from src.server.v3.models import PATCH_OPERATION_UNDELETE

remote_build_node_user_input_schema = V3RemoteBuildNodeRecordInputSchema()
remote_build_node_schema = V3RemoteBuildNodeRecordSchema()

class V3RemoteBuildNodeCollection(Resource):
    """
    Class representing the operations that can be taken on a collection of remote builds nodes
    """

    def get(self):
        """ retrieve a list/collection of remote build nodes """
        log_id = get_log_id()
        current_app.logger.info("%s ++ remote_build_nodes.v3.GET", log_id)
        return_json = remote_build_node_schema.dump(iter(current_app.data['remote_build_nodes'].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def post(self):
        """ Add a new remote build node to the IMS Service.

        A new remote build node is created from values that passed in via the request body. If the remote build
        node already exists, then a 400 is returned. If the remote build node is created successfully then a 201
        is returned.

        """
        log_id = get_log_id()
        current_app.logger.info("%s ++ remote_build_nodes.v3.POST", log_id)

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No post data accompanied the POST request.", log_id)
            return generate_missing_input_response()

        current_app.logger.info("%s json_data = %s", log_id, json_data)

        # Validate input
        errors = remote_build_node_user_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the post data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        # Create a remote build node record if the user input data was valid
        new_remote_build_node = remote_build_node_schema.load(json_data)

        # Save to datastore
        current_app.data['remote_build_nodes'][str(new_remote_build_node.xname)] = new_remote_build_node

        return_json = remote_build_node_schema.dump(new_remote_build_node)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Delete all remote build nodes. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ remote_build_nodes.v3.DELETE", log_id)

        try:
            del current_app.data['remote_build_nodes']
            current_app.data['remote_build_nodes'] = {}
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting remote build nodes. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V3RemoteBuildNodeResource(Resource):
    """ Endpoint for the remote-build-nodes/{remote_build_node_xname} resource. """

    def get(self, remote_build_node_xname):
        """ Retrieve a remote build node. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ remote_build_nodes.v3.GET %s", log_id, remote_build_node_xname)

        if remote_build_node_xname not in current_app.data['remote_build_nodes']:
            current_app.logger.info("%s no IMS remote bild node matches xname=%s", log_id, remote_build_node_xname)
            return generate_resource_not_found_response()

        return_json = remote_build_node_schema.dump(current_app.data['remote_build_nodes'][remote_build_node_xname])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, remote_build_node_xname):
        """ Delete a remote build node. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ remote_build_nodes.v3.DELETE %s", log_id, remote_build_node_xname)

        try:
            del current_app.data['remote_build_nodes'][remote_build_node_xname]
        except KeyError:
            current_app.logger.info("%s no remote build node record matches xname=%s", log_id, remote_build_node_xname)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204
