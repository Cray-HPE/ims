"""
Public Keys API
Copyright 2020 Hewlett Packard Enterprise Development LP
"""

import http.client
from flask import jsonify, request, current_app
from flask_restful import Resource

from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
    generate_resource_not_found_response
from src.server.helper import get_log_id
from src.server.models.publickeys import V2PublicKeyRecordInputSchema, V2PublicKeyRecordSchema, V2PublicKeyRecord
from src.server.v3.models.public_keys import V3DeletedPublicKeyRecordPatchSchema, V3DeletedPublicKeyRecordSchema, \
    V3DeletedPublicKeyRecord
from src.server.v3.models import PATCH_OPERATION_UNDELETE

public_key_user_input_schema = V2PublicKeyRecordInputSchema()
deleted_public_key_patch_input_schema = V3DeletedPublicKeyRecordPatchSchema()
public_key_schema = V2PublicKeyRecordSchema()
deleted_public_key_schema = V3DeletedPublicKeyRecordSchema()


class V3BasePublicKeyResource(Resource):
    """
    Common base class for V3PublicKeys
    """

    public_keys_table = 'public_keys'
    deleted_public_keys_table = 'deleted_public_keys'


class V3PublicKeyCollection(V3BasePublicKeyResource):
    """
    Class representing the operations that can be taken on a collection of public keys
    """

    def get(self):
        """ retrieve a list/collection of public keys """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v3.GET", log_id)
        return_json = public_key_schema.dump(iter(current_app.data[self.public_keys_table].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def post(self):
        """ Add a new public key to the IMS Service.

        A new public key is created from values that passed in via the request body. If the public key already
        exists, then a 400 is returned. If the public key is created successfully then a 201 is returned.

        """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v3.POST", log_id)

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
        current_app.data[self.public_keys_table][str(new_public_key.id)] = new_public_key

        return_json = public_key_schema.dump(new_public_key)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Soft-delete all public_keys. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v3.DELETE", log_id)

        try:
            public_keys_to_delete = []
            for public_key_id, public_key in current_app.data[self.public_keys_table].items():

                # TODO ADD PUBLIC_KEY FILTER OPTIONS

                deleted_public_key = V3DeletedPublicKeyRecord(name=public_key.name, id=public_key.id,
                                                              created=public_key.created,
                                                              public_key=public_key.public_key)
                current_app.data[self.deleted_public_keys_table][public_key_id] = deleted_public_key
                public_keys_to_delete.append(public_key_id)

            for public_key_id in public_keys_to_delete:
                del current_app.data[self.public_keys_table][public_key_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting public_keys. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V3PublicKeyResource(V3BasePublicKeyResource):
    """ Endpoint for the public-keys/{public_key_id} resource. """

    def get(self, public_key_id):
        """ Retrieve a public key. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v3.GET %s", log_id, public_key_id)

        if public_key_id not in current_app.data[self.public_keys_table]:
            current_app.logger.info("%s no IMS image public_key matches public_key_id=%s", log_id, public_key_id)
            return generate_resource_not_found_response()

        return_json = public_key_schema.dump(current_app.data[self.public_keys_table][public_key_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, public_key_id):
        """ Delete a public_key. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ public_keys.v3.DELETE %s", log_id, public_key_id)

        try:
            public_key = current_app.data[self.public_keys_table][public_key_id]
            deleted_public_key = V3DeletedPublicKeyRecord(name=public_key.name, id=public_key.id,
                                                          created=public_key.created,
                                                          public_key=public_key.public_key)
            current_app.data[self.deleted_public_keys_table][public_key_id] = deleted_public_key
            del current_app.data[self.public_keys_table][public_key_id]
        except KeyError:
            current_app.logger.info("%s no IMS public_key record matches public_key_id=%s", log_id, public_key_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V3DeletedPublicKeyCollection(V3BasePublicKeyResource):
    """
    Class representing the operations that can be taken on a collection of public keys
    """

    def get(self):
        """ retrieve a list/collection of public keys """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_public_keys.v3.GET", log_id)
        return_json = deleted_public_key_schema.dump(
            iter(current_app.data[self.deleted_public_keys_table].values()), many=True
        )
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self):
        """ Permanently delete all public_keys. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_public_keys.v3.DELETE", log_id)

        try:
            public_keys_to_delete = []
            for deleted_public_key_id, _ in current_app.data[self.deleted_public_keys_table].items():

                # TODO ADD PUBLIC_KEY FILTER OPTIONS

                public_keys_to_delete.append(deleted_public_key_id)

            for deleted_public_key_id in public_keys_to_delete:
                del current_app.data[self.deleted_public_keys_table][deleted_public_key_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting public_keys. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self):
        """ Undelete all public_keys. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_public_keys.v3.PATCH", log_id)

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = deleted_public_key_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        try:
            public_keys_to_undelete = []
            for deleted_public_key_id, deleted_public_key in current_app.data[self.deleted_public_keys_table].items():

                # TODO ADD PUBLIC_KEY FILTER OPTIONS

                public_key = V2PublicKeyRecord(name=deleted_public_key.name, id=deleted_public_key.id,
                                               created=deleted_public_key.created,
                                               public_key=deleted_public_key.public_key)
                for key, value in list(json_data.items()):
                    if key == "operation":
                        if value == PATCH_OPERATION_UNDELETE:
                            current_app.data[self.public_keys_table][deleted_public_key_id] = public_key
                            public_keys_to_undelete.append(deleted_public_key_id)
                        else:
                            current_app.logger.info("%s Unsupported patch operation value %s.", log_id, value)
                            return generate_data_validation_failure(errors=[])
                    else:
                        current_app.logger.info('%s Unsupported patch request key="%s" value="%s"', log_id, key, value)
                        return generate_data_validation_failure(errors=[])

            for deleted_public_key_id in public_keys_to_undelete:
                del current_app.data[self.deleted_public_keys_table][deleted_public_key_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered undeleting public keys. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        return None, 204


class V3DeletedPublicKeyResource(V3BasePublicKeyResource):
    """ Endpoint for the deleted/public-keys/{deleted_public_key_id} resource. """

    def get(self, deleted_public_key_id):
        """ Retrieve a deleted public key. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_public_keys.v3.GET %s", log_id, deleted_public_key_id)

        if deleted_public_key_id not in current_app.data[self.deleted_public_keys_table]:
            current_app.logger.info("%s no IMS image public_key matches deleted_public_key_id=%s",
                                    log_id, deleted_public_key_id)
            return generate_resource_not_found_response()

        return_json = deleted_public_key_schema.dump(
            current_app.data[self.deleted_public_keys_table][deleted_public_key_id]
        )
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, deleted_public_key_id):
        """ Delete a public key. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_public_keys.v3.DELETE %s", log_id, deleted_public_key_id)

        try:
            del current_app.data[self.deleted_public_keys_table][deleted_public_key_id]
        except KeyError:
            current_app.logger.info("%s no IMS image public_key matches deleted_public_key_id=%s",
                                    log_id, deleted_public_key_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, deleted_public_key_id):
        """ Undelete an existing public_key record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_public_keys.v3.PATCH %s", log_id, deleted_public_key_id)

        if deleted_public_key_id not in current_app.data[self.deleted_public_keys_table]:
            current_app.logger.info("%s no IMS public_key record matches deleted_public_key_id=%s",
                                    log_id, deleted_public_key_id)
            return generate_resource_not_found_response()

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = deleted_public_key_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        deleted_public_key = current_app.data[self.deleted_public_keys_table][deleted_public_key_id]
        public_key = V2PublicKeyRecord(name=deleted_public_key.name, id=deleted_public_key.id,
                                       created=deleted_public_key.created, public_key=deleted_public_key.public_key)
        for key, value in list(json_data.items()):
            if key == "operation":
                if value == PATCH_OPERATION_UNDELETE:
                    current_app.data[self.public_keys_table][deleted_public_key_id] = public_key
                    del current_app.data[self.deleted_public_keys_table][deleted_public_key_id]
                else:
                    current_app.logger.info("%s Unsupported patch operation value %s.", log_id, value)
                    return generate_data_validation_failure(errors=[])
            else:
                current_app.logger.info('%s Unsupported patch request key="%s" value="%s"', log_id, key, value)
                return generate_data_validation_failure(errors=[])

        return None, 204
