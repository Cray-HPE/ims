# Copyright 2018-2021 Hewlett Packard Enterprise Development LP
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# (MIT License)
"""
Public Keys API
"""

import http.client
from flask import jsonify, request, current_app
from flask_restful import Resource

from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
    generate_resource_not_found_response
from src.server.helper import get_log_id
from src.server.models.publickeys import V2PublicKeyRecordInputSchema, V2PublicKeyRecordSchema

public_key_user_input_schema = V2PublicKeyRecordInputSchema()
public_key_schema = V2PublicKeyRecordSchema()


class V2PublicKeyCollection(Resource):
    """
    Class representing the operations that can be taken on a collection of public keys
    """

    def get(self):
        """ retrieve a list/collection of public keys """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v2.GET", log_id)
        return_json = public_key_schema.dump(iter(current_app.data["public_keys"].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def post(self):
        """ Add a new public key to the IMS Service.

        A new public key is created from values that passed in via the request body. If the public key already
        exists, then a 400 is returned. If the public key is created successfully then a 201 is returned.

        """

        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v2.POST", log_id)

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No post data accompanied the POST request.", log_id)
            return generate_missing_input_response()

        current_app.logger.info("%s json_data = %s", log_id, json_data)

        # Validate input
        errors = public_key_user_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the post data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        # Create a public key record if the user input data was valid
        new_public_key = public_key_schema.load(json_data)

        # Save to datastore
        current_app.data['public_keys'][str(new_public_key.id)] = new_public_key

        return_json = public_key_schema.dump(new_public_key)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Delete all public keys. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v2.DELETE", log_id)

        try:
            del current_app.data['public_keys']
            current_app.data['public_keys'] = {}
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting recipes. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V2PublicKeyResource(Resource):
    """ Endpoint for the public-keys/{public_key_id} resource. """

    def get(self, public_key_id):
        """ Retrieve a public key. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v2.GET %s", log_id, public_key_id)

        if public_key_id not in current_app.data["public_keys"]:
            current_app.logger.info("%s no IMS image public_key matches public_key_id=%s", log_id, public_key_id)
            return generate_resource_not_found_response()

        return_json = public_key_schema.dump(current_app.data['public_keys'][public_key_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, public_key_id):
        """ Delete a public key. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v2.DELETE %s", log_id, public_key_id)

        try:
            del current_app.data['public_keys'][public_key_id]
        except KeyError:
            current_app.logger.info("%s no IMS image public_key matches public_key_id=%s", log_id, public_key_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204
