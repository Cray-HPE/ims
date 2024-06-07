#
# MIT License
#
# (C) Copyright 2018-2023 Hewlett Packard Enterprise Development LP
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
Images API
"""

import http.client

from flask import jsonify, request, current_app
from flask_restful import Resource
from copy import deepcopy

from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
    generate_resource_not_found_response, generate_patch_conflict
from src.server.helper import delete_artifact, read_manifest_json, get_log_id, \
    validate_image_manifest, IMAGE_MANIFEST_ARTIFACTS
from src.server.models.images import V2ImageRecordInputSchema, V2ImageRecordSchema, V2ImageRecordPatchSchema

image_user_input_schema = V2ImageRecordInputSchema()
image_patch_input_schema = V2ImageRecordPatchSchema()
image_schema = V2ImageRecordSchema()


class V2BaseImageResource(Resource):
    """
    Common base class for V2Images
    """

    def _delete_manifest_and_artifacts(self, log_id, image_id, manifest_link):
        """ Read the manifest.json, delete linked artifacts and then delete the manifest itself. """
        manifest_json, problem = read_manifest_json(manifest_link)
        if problem:
            return False, problem

        try:
            # delete all the artifacts that are listed in the manifest.json
            for artifact in manifest_json[IMAGE_MANIFEST_ARTIFACTS]:
                if "link" in artifact and artifact["link"]:
                    try:
                        delete_artifact(artifact["link"])
                    except Exception as exc:  # pylint: disable=broad-except
                        current_app.logger.warning("%s Could not delete artifact %s listed in the "
                                                   "manifest.json for image_id=%s",
                                                   log_id, artifact, image_id, exc_info=exc)
                else:
                    current_app.logger.warning("%s malformed manifest json for image_id=%s. "
                                               "Artifact does not contain a link value.", log_id, image_id)
        except KeyError:
            current_app.logger.info("%s malformed manifest.json for image_id=%s. No artifacts section.",
                                    log_id, image_id)

        # delete the manifest.json
        delete_artifact(manifest_link)
        return True, None


class V2ImageCollection(V2BaseImageResource):
    """
    Class representing the operations that can be taken on a collection of images
    """

    def get(self):
        """ retrieve a list/collection of images """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v2.GET", log_id)
        current_app.logger.info("%s ++ images.v2.GET RAW:%s" % (log_id, current_app.data["images"].values()))
        return_json = image_schema.dump(iter(current_app.data["images"].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def post(self):
        """ Add a new image to the IMS Service.

        A new image is created from values that passed in via the request body. If the image already
        exists, then a 400 is returned. If the image is created successfully then a 201 is returned.

        """

        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v2.POST", log_id)

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No post data accompanied the POST request.", log_id)
            return generate_missing_input_response()

        current_app.logger.info("%s json_data = %s", log_id, json_data)

        # Validate input
        errors = image_user_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the post data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        new_image = image_schema.load(json_data)

        if new_image.link:
            problem = validate_image_manifest(new_image.link)
            if problem:
                current_app.logger.info("%s Could not validate link artifact or artifact doesn't exist", log_id)
                return problem

        # Save to datastore
        current_app.data['images'][str(new_image.id)] = new_image

        return_json = image_schema.dump(new_image)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Delete all images. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v2.DELETE", log_id)

        try:
            if request.args.get("cascade", 'True').lower() in ['true', 'yes', 't', '1']:
                for image_id, image_record in current_app.data['images'].items():
                    if image_record.link:
                        current_app.logger.info("%s Deleting artifacts for image_id: %s", log_id, image_id)
                        self._delete_manifest_and_artifacts(log_id, image_id, image_record.link)
                    else:
                        current_app.logger.debug("%s No artifacts to delete for image_id: %s", log_id, image_id)
            del current_app.data['images']
            current_app.data['images'] = {}
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting images. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V2ImageResource(V2BaseImageResource):
    """
    Endpoint for the images/{image_id} resource.
    """

    def get(self, image_id):
        """ Retrieve an image. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v2.GET %s", log_id, image_id)

        if image_id not in current_app.data["images"]:
            current_app.logger.info("%s no IMS image record matches image_id=%s", log_id, image_id)
            return generate_resource_not_found_response()

        return_json = image_schema.dump(current_app.data['images'][image_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, image_id):
        """ Delete an image. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v2.DELETE %s", log_id, image_id)

        try:
            if request.args.get("cascade", 'True').lower() in ['true', 'yes', 't', '1']:
                image = current_app.data['images'][image_id]
                if image.link:
                    current_app.logger.info("%s Deleting artifacts", log_id)
                    self._delete_manifest_and_artifacts(log_id, image_id, image.link)
                else:
                    current_app.logger.debug("%s No artifacts to delete", log_id)
            del current_app.data['images'][image_id]
        except KeyError:
            current_app.logger.info("%s no IMS image record matches image_id=%s", log_id, image_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, image_id):
        """ Update an existing image record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v2.PATCH %s", log_id, image_id)

        if image_id not in current_app.data["images"]:
            current_app.logger.info("%s no IMS image record matches image_id=%s", log_id, image_id)
            return generate_resource_not_found_response()

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = image_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        image = current_app.data["images"][image_id]
        for key, value in list(json_data.items()):
            if key == "link":
                if image.link and dict(image.link) == value:
                    # The stored link value matches what is trying to be patched.
                    # In this case, for idempotency reasons, do not return failure.
                    pass
                elif image.link and dict(image.link) != value:
                    current_app.logger.info("%s image record cannot be patched since it already has link info", log_id)
                    return generate_patch_conflict()
                else:
                    problem = validate_image_manifest(value)
                    if problem:
                        current_app.logger.info("%s Could not validate link artifact or artifact doesn't exist", log_id)
                        return problem
            elif key == "arch":
                current_app.logger.info(f"Patching architecture with {value}")
                image.arch = value
            elif key == 'metadata':
                if not value:
                    current_app.logger.info("No metadata values to patch.")
                    continue
                # Even though the API represents Image Metadata Annotations as a list internally, they behave like
                # dictionaries. The ordered nature of the data should not matter, nor are they enforced. As such,
                # converting the list of k:vs to a unified dictionary has performance advantages log(n) when doing
                # multiple insertions or deletions. We will flatten this back out to a list before setting it within
                # the image.
                metadata_dict = deepcopy(image.metadata)
                for changeset in value:
                    operation = changeset.get('operation')
                    if operation not in ['set', 'remove']:
                        current_app.logger.info(f"Unknown requested operation change '{operation}'.")
                        return generate_data_validation_failure(errors=[])
                    annotation_key = changeset.get('key')
                    annotation_value = changeset.get('value', '')

                    if operation == 'set':
                        metadata_dict[annotation_key] = annotation_value
                    elif operation == 'remove':
                        try:
                            del metadata_dict[annotation_key]
                        except KeyError:
                            current_app.logger.info("No-op when removing non-existent metadata from IMS record.")
                            pass
                # With every change made to the image_annotation_dictionary, the last thing that is necessary is
                # to convert the temporary dictionary back into a list of key:value pairs.
                image.metadata = metadata_dict
            else:
                current_app.logger.info(f"{log_id} Not able to patch record field {key} with value {value}")
                return generate_data_validation_failure(errors=[])

            setattr(image, key, value)
        current_app.data['images'][image_id] = image

        return_json = image_schema.dump(current_app.data['images'][image_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)
