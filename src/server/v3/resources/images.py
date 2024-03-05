#
# MIT License
#
# (C) Copyright 2020-2023 Hewlett Packard Enterprise Development LP
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

from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
    generate_resource_not_found_response, generate_patch_conflict
from src.server.helper import delete_artifact, soft_delete_artifact, soft_undelete_artifact, \
    read_manifest_json, get_log_id, write_new_image_manifest, IMAGE_MANIFEST_VERSION_1_0, ARTIFACT_LINK_TYPE, \
    ARTIFACT_LINK, IMAGE_MANIFEST_ARTIFACTS, validate_image_manifest
from src.server.ims_exceptions import ImsReadManifestJsonException, ImsArtifactValidationException, \
    ImsSoftUndeleteArtifactException
from src.server.models.images import V2ImageRecordInputSchema, V2ImageRecordSchema, V2ImageRecordPatchSchema, \
    V2ImageRecord
from src.server.v3.models import PATCH_OPERATION_UNDELETE
from src.server.v3.models.images import V3DeletedImageRecordPatchSchema, V3DeletedImageRecord, \
    V3DeletedImageRecordSchema

image_user_input_schema = V2ImageRecordInputSchema()
image_patch_input_schema = V2ImageRecordPatchSchema()
deleted_image_patch_input_schema = V3DeletedImageRecordPatchSchema()
image_schema = V2ImageRecordSchema()
deleted_image_schema = V3DeletedImageRecordSchema()


class V3BaseImageResource(Resource):
    """
    Common base class for V3Images
    """

    images_table = 'images'
    deleted_images_table = 'deleted_images'

    def _create_deleted_manifest(self, deleted_image, artifacts):
        """
        Utility function to create a deleted_manifest.json from an image and set of artifacts.
        """

        manifest_data = {
            'version': IMAGE_MANIFEST_VERSION_1_0,
            'created': deleted_image.deleted.strftime("%Y-%m-%d %H:%M:%S"),
            'artifacts': artifacts
        }
        manifest_link = {
            'path': f's3://{current_app.config["S3_BOOT_IMAGES_BUCKET"]}/deleted/'
                    f'{deleted_image.id}/deleted_manifest.json',
            'type': deleted_image.link[ARTIFACT_LINK_TYPE]
        }
        write_new_image_manifest(manifest_link, manifest_data)
        return manifest_link

    def _soft_delete_manifest_and_artifacts(self, log_id, image_id, manifest_link):
        """ Read the manifest.json, delete linked artifacts and then delete the manifest itself. """
        manifest_json, problem = read_manifest_json(manifest_link)
        if problem:
            return None, problem

        soft_deleted_artifacts = []
        try:
            # delete all the artifacts that are listed in the manifest.json
            for artifact in manifest_json[IMAGE_MANIFEST_ARTIFACTS]:
                if ARTIFACT_LINK in artifact and artifact[ARTIFACT_LINK]:
                    try:
                        link = soft_delete_artifact(artifact[ARTIFACT_LINK])
                        if link:
                            soft_deleted_artifacts.append(
                                {
                                    'type': artifact[ARTIFACT_LINK_TYPE],
                                    'md5': artifact['md5'],
                                    'link': link
                                }
                            )

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

        # rename the manifest.json
        link = soft_delete_artifact(manifest_link)
        if link:
            soft_deleted_artifacts.append(
                {
                    'type': 'application/vnd.cray.image.manifest',
                    # 'md5': artifact['md5'],
                    'link': link
                }
            )

        return soft_deleted_artifacts, None

    def _soft_undelete_manifest_and_artifacts(self, log_id, image_id, manifest_link):
        """ Read the manifest.json, delete linked artifacts and then delete the manifest itself. """
        manifest_json, problem = read_manifest_json(manifest_link)
        if problem:
            return None, problem

        original_manifest_link = manifest_link
        try:
            # undelete all the artifacts that are listed in the deleted_manifest.json
            for artifact in manifest_json[IMAGE_MANIFEST_ARTIFACTS]:
                if ARTIFACT_LINK in artifact and artifact[ARTIFACT_LINK]:
                    try:
                        link = soft_undelete_artifact(artifact[ARTIFACT_LINK])
                        if artifact['type'] == 'application/vnd.cray.image.manifest':
                            original_manifest_link = link

                    except ImsSoftUndeleteArtifactException:
                        current_app.logger.warning("%s Could not undelete artifact %s listed in the "
                                                   "manifest.json for image_id=%s",
                                                   log_id, artifact, image_id)
                    except Exception as exc:  # pylint: disable=broad-except
                        current_app.logger.warning("%s Could not undelete artifact %s listed in the "
                                                   "manifest.json for image_id=%s",
                                                   log_id, artifact, image_id, exc_info=exc)
                else:
                    current_app.logger.warning("%s malformed manifest json for image_id=%s. "
                                               "Artifact does not contain a link value.", log_id, image_id)
        except KeyError:
            current_app.logger.info("%s malformed manifest.json for image_id=%s. No artifacts section.",
                                    log_id, image_id)
            return False, problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                     detail="The image's manifest.json is malformed. "
                                            "The manifest does not contain an artifacts section.")

        if original_manifest_link != manifest_link:
            # delete the deleted_manifest.json
            delete_artifact(manifest_link)

        # return link to the original manifest
        return original_manifest_link, None

    def _delete_manifest_and_artifacts(self, log_id, image_id, manifest_link):
        """ Read the manifest.json, delete linked artifacts and then delete the manifest itself. """
        manifest_json, problem = read_manifest_json(manifest_link)
        if problem:
            return False, problem

        try:
            # delete all the artifacts that are listed in the manifest.json
            for artifact in manifest_json[IMAGE_MANIFEST_ARTIFACTS]:
                if ARTIFACT_LINK in artifact and artifact[ARTIFACT_LINK]:
                    try:
                        delete_artifact(artifact[ARTIFACT_LINK])
                    except Exception as exc:  # pylint: disable=broad-except
                        current_app.logger.warning("%s Could not delete artifact %s listed in the "
                                                   "manifest.json for image_id=%s",
                                                   log_id, artifact, image_id, exc_info=exc)
                else:
                    current_app.logger.warning("%s malformed manifest json for image_id=%s. "
                                               "Artifact does not contain a link value.", log_id, image_id)
        except (KeyError, TypeError):
            current_app.logger.info("%s malformed manifest.json for image_id=%s. No artifacts section.",
                                    log_id, image_id)
            return False, problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                     detail="The image's manifest.json is malformed. "
                                            "The manifest does not contain a manifest section.")

        # delete the manifest.json
        delete_artifact(manifest_link)
        return True, None


class V3ImageCollection(V3BaseImageResource):
    """
    Class representing the operations that can be taken on a collection of images
    """

    def get(self):
        """ retrieve a list/collection of images """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v3.GET", log_id)
        return_json = image_schema.dump(iter(current_app.data[self.images_table].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def post(self):
        """ Add a new image to the IMS Service.

        A new image is created from values that passed in via the request body. If the image already
        exists, then a 400 is returned. If the image is created successfully then a 201 is returned.

        """

        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v3.POST", log_id)

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
                return problem

        # Save to datastore
        current_app.data[self.images_table][str(new_image.id)] = new_image

        return_json = image_schema.dump(new_image)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Delete all images. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v3.DELETE", log_id)

        try:
            images_to_delete = []
            for image_id, image in current_app.data[self.images_table].items():

                # TODO ADD IMAGE FILTER OPTIONS

                deleted_image = V3DeletedImageRecord(name=image.name, link=image.link,
                                                     id=image.id, created=image.created)
                if deleted_image.link:
                    try:
                        artifacts, _ = self._soft_delete_manifest_and_artifacts(log_id, image_id, image.link)
                        deleted_image.link = self._create_deleted_manifest(deleted_image, artifacts)
                    except ImsReadManifestJsonException as exc:
                        current_app.logger.info(f"Unable to read IMS image manifest. Ignoring. ")
                        current_app.logger.info(str(exc))
                    except ImsArtifactValidationException as exc:
                        current_app.logger.info(f"The artifact {image.link} is not in S3 and "
                                                f"was not soft-deleted. Ignoring")
                        current_app.logger.info(str(exc))

                current_app.data[self.deleted_images_table][image_id] = deleted_image
                images_to_delete.append(image_id)

            for image_id in images_to_delete:
                del current_app.data[self.images_table][image_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting images. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V3ImageResource(V3BaseImageResource):
    """
    Endpoint for the images/{image_id} resource.
    """

    def get(self, image_id):
        """ Retrieve an image. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v3.GET %s", log_id, image_id)

        if image_id not in current_app.data[self.images_table]:
            current_app.logger.info("%s no IMS image record matches image_id=%s", log_id, image_id)
            return generate_resource_not_found_response()

        return_json = image_schema.dump(current_app.data[self.images_table][image_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, image_id):
        """ Delete an image. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v3.DELETE %s", log_id, image_id)

        try:
            image = current_app.data[self.images_table][image_id]
            deleted_image = V3DeletedImageRecord(name=image.name, link=image.link, id=image.id, created=image.created)
            if deleted_image.link:
                try:
                    artifacts, _ = self._soft_delete_manifest_and_artifacts(log_id, image_id, image.link)
                    deleted_image.link = self._create_deleted_manifest(deleted_image, artifacts)
                except ImsReadManifestJsonException as exc:
                    current_app.logger.info(f"Unable to read IMS image manifest. Ignoring. ")
                    current_app.logger.info(str(exc))
                except ImsArtifactValidationException as exc:
                    current_app.logger.info(f"The artifact {image.link} is not in S3 and "
                                            f"was not soft-deleted. Ignoring")
                    current_app.logger.info(str(exc))
            current_app.data[self.deleted_images_table][image_id] = deleted_image
            del current_app.data[self.images_table][image_id]
        except KeyError:
            current_app.logger.info("%s no IMS image record matches image_id=%s", log_id, image_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, image_id):
        """ Update an existing image record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ images.v3.PATCH %s", log_id, image_id)

        if image_id not in current_app.data[self.images_table]:
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

        image = current_app.data[self.images_table][image_id]
        for key, value in list(json_data.items()):
            if key == ARTIFACT_LINK:
                if image.link and dict(image.link) == value:
                    # The stored link value matches what is trying to be patched.
                    # In this case, for idempotency reasons, do not return failure.
                    pass
                elif image.link and dict(image.link) != value:
                    current_app.logger.info("%s image record cannot be patched since it already has link info", log_id)
                    return generate_patch_conflict()
                else:
                    try:
                        problem = validate_image_manifest(value)
                        if problem:
                            return problem
                    except ImsReadManifestJsonException as exc:
                        current_app.logger.info(f"Unable to read IMS image manifest. Ignoring. ")
                        current_app.logger.info(str(exc))
                    except ImsArtifactValidationException as exc:
                        current_app.logger.info(f"The artifact {value} is not in S3 and "
                                                f"was not soft-deleted. Ignoring")
                        current_app.logger.info(str(exc))
            elif key == "arch":
                current_app.logger.info(f"Patching architecture with {value}")
                image.arch = value
            elif key == 'metadata':
                current_app.logger.info("Patching metadata annotations.")
                if 'annotations' not in value:
                    continue
                else:
                    # Even though the API represents Image Metadata Annotations as a list internally, they behave like
                    # dictionaries. The ordered nature of the data should not matter, nor are they enforced. As such,
                    # converting the list of k:vs to a unified dictionary has performance advantages log(n) when doing
                    # multiple insertions or deletions. We will flatten this back out to a list before setting it within
                    # the image.
                    image_annotation_dict = {}
                    for image_key, image_value in image.metadata.annotations:
                        image_annotation_dict[image_key] = image_value
                        
                    for changeset in value['annotations']:
                        operation = changeset.get('operation')
                        if operation not in ['set', 'remove']:
                            current_app.logger.info(f"Unknown requested operation change '{operation}'")
                            return generate_data_validation_failure(errors=[])
                        annotation_key = changeset.get('key')
                        annotation_value = changeset.get('value', '')

                        if operation == 'set':
                            # It should not be possible to do so with the API, but there should be at most one
                        elif operation == 'remove':
                            pass

            else:
                current_app.logger.info(f"{log_id} Not able to patch record field {key} with value {value}")
                return generate_data_validation_failure(errors=[])

            setattr(image, key, value)
        current_app.data[self.images_table][image_id] = image

        return_json = image_schema.dump(current_app.data[self.images_table][image_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)


class V3DeletedImageCollection(V3BaseImageResource):
    """
    Class representing the operations that can be taken on a collection of deleted images
    """

    def get(self):
        """ retrieve a list/collection of images """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_images.v3.GET", log_id)
        return_json = deleted_image_schema.dump(iter(current_app.data[self.deleted_images_table].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self):
        """ Permanently delete all images. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_images.v3.DELETE", log_id)

        try:
            images_to_delete = []
            for deleted_image_id, deleted_image in current_app.data[self.deleted_images_table].items():

                # TODO ADD IMAGE FILTER OPTIONS

                if deleted_image.link:
                    try:
                        current_app.logger.info("%s Deleting artifacts for deleted_image_id: %s", log_id,
                                                deleted_image_id)
                        _, errors = self._delete_manifest_and_artifacts(log_id, deleted_image_id, deleted_image.link)
                        if errors:
                            return errors
                    except ImsReadManifestJsonException as exc:
                        current_app.logger.info(f"Unable to read IMS image manifest. Ignoring. ")
                        current_app.logger.info(str(exc))
                    except ImsArtifactValidationException as exc:
                        current_app.logger.info(f"The artifact {deleted_image.link} is not in S3 and "
                                                f"was not soft-deleted. Ignoring")
                        current_app.logger.info(str(exc))
                else:
                    current_app.logger.debug("%s No artifacts to delete for deleted_image_id: %s",
                                             log_id, deleted_image_id)
                images_to_delete.append(deleted_image_id)

            for deleted_image_id in images_to_delete:
                del current_app.data[self.deleted_images_table][deleted_image_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting images. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self):
        """ Undelete all images. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_images.v3.PATCH", log_id)

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = deleted_image_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        try:  # pylint: disable=too-many-nested-blocks
            images_to_undelete = []
            for deleted_image_id, deleted_image in current_app.data[self.deleted_images_table].items():

                # TODO ADD IMAGE FILTER OPTIONS

                image = V2ImageRecord(name=deleted_image.name, link=deleted_image.link,
                                      id=deleted_image.id, created=deleted_image.created)
                for key, value in list(json_data.items()):
                    if key == "operation":
                        if value == PATCH_OPERATION_UNDELETE:
                            if image.link:
                                try:
                                    original_manifest_link, errors = self._soft_undelete_manifest_and_artifacts(
                                        log_id, deleted_image_id, image.link)
                                    if errors:
                                        return errors
                                    image.link = original_manifest_link
                                except ImsReadManifestJsonException as exc:
                                    current_app.logger.info(f"Unable to read IMS image manifest. ")
                                    current_app.logger.info(str(exc))
                                    return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))
                                except ImsArtifactValidationException as exc:
                                    current_app.logger.info(f"The artifact {image.link} is not in S3 and "
                                                            f"was not soft-deleted.")
                                    current_app.logger.info(str(exc))
                                    return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))
                            current_app.data[self.images_table][deleted_image_id] = image
                            images_to_undelete.append(deleted_image_id)
                        else:
                            current_app.logger.info("%s Unsupported patch operation value %s.", log_id, value)
                            return generate_data_validation_failure(errors=[])
                    else:
                        current_app.logger.info('%s Unsupported patch request key="%s" value="%s"', log_id, key, value)
                        return generate_data_validation_failure(errors=[])

            for deleted_image_id in images_to_undelete:
                del current_app.data[self.deleted_images_table][deleted_image_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered undeleting images. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        return None, 204


class V3DeletedImageResource(V3BaseImageResource):
    """
    Endpoint for the deleted/images/{deleted_image_id} resource.
    """

    def get(self, deleted_image_id):
        """ Retrieve an image. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_images.v3.GET %s", log_id, deleted_image_id)

        if deleted_image_id not in current_app.data[self.deleted_images_table]:
            current_app.logger.info("%s no IMS image record matches deleted_image_id=%s", log_id, deleted_image_id)
            return generate_resource_not_found_response()

        return_json = deleted_image_schema.dump(current_app.data[self.deleted_images_table][deleted_image_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, deleted_image_id):
        """ Permanently delete an image. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_images.v3.DELETE %s", log_id, deleted_image_id)

        try:
            image = current_app.data[self.deleted_images_table][deleted_image_id]
            if image.link:
                try:
                    current_app.logger.info("%s Deleting artifacts", log_id)
                    _, errors = self._delete_manifest_and_artifacts(log_id, deleted_image_id, image.link)
                    if errors:
                        return errors
                except ImsReadManifestJsonException as exc:
                    current_app.logger.info(f"Unable to read IMS image manifest. Ignoring. ")
                    current_app.logger.info(str(exc))
                except ImsArtifactValidationException as exc:
                    current_app.logger.info(f"The artifact {image.link} is not in S3 and "
                                            f"was not soft-deleted. Ignoring")
                    current_app.logger.info(str(exc))
            else:
                current_app.logger.debug("%s No artifacts to delete", log_id)
            del current_app.data[self.deleted_images_table][deleted_image_id]
        except KeyError:
            current_app.logger.info("%s no IMS image record matches deleted_image_id=%s", log_id, deleted_image_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, deleted_image_id):
        """ Undelete an existing image record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ deleted_images.v3.PATCH %s", log_id, deleted_image_id)

        if deleted_image_id not in current_app.data[self.deleted_images_table]:
            current_app.logger.info("%s no IMS image record matches deleted_image_id=%s", log_id, deleted_image_id)
            return generate_resource_not_found_response()

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = deleted_image_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        deleted_image = current_app.data[self.deleted_images_table][deleted_image_id]
        image = V2ImageRecord(name=deleted_image.name, link=deleted_image.link,
                              id=deleted_image.id, created=deleted_image.created)
        for key, value in list(json_data.items()):
            if key == "operation":
                if value == PATCH_OPERATION_UNDELETE:
                    if image.link:
                        try:
                            original_manifest_link, errors = self._soft_undelete_manifest_and_artifacts(
                                log_id, deleted_image_id, image.link)
                            if errors:
                                return errors
                            image.link = original_manifest_link
                        except ImsReadManifestJsonException as exc:
                            current_app.logger.info(f"Unable to read IMS image manifest. ")
                            current_app.logger.info(str(exc))
                            return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))
                        except ImsArtifactValidationException as exc:
                            current_app.logger.info(f"The artifact {image.link} is not in S3 and "
                                                    f"was not soft-deleted.")
                            current_app.logger.info(str(exc))
                            return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

                    current_app.data[self.images_table][deleted_image_id] = image
                    del current_app.data[self.deleted_images_table][deleted_image_id]
                else:
                    current_app.logger.info("%s Unsupported patch operation value %s.", log_id, value)
                    return generate_data_validation_failure(errors=[])
            else:
                current_app.logger.info('%s Unsupported patch request key="%s" value="%s"', log_id, key, value)
                return generate_data_validation_failure(errors=[])

        return None, 204
