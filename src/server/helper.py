#
# MIT License
#
# (C) Copyright 2018-2022 Hewlett Packard Enterprise Development LP
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
import http.client
import json
import uuid
from io import BytesIO
from pprint import pformat

from botocore.exceptions import ClientError
from flask import current_app as app

from src.server.errors import problemify
from src.server.ims_exceptions import ImsArtifactValidationException, ImsReadManifestJsonException, \
    ImsSoftUndeleteArtifactException

try:
    from urllib.parse import urlparse
except ImportError:
    from urllib.parse import urlparse

IMAGE_MANIFEST_VERSION = 'version'
IMAGE_MANIFEST_ARTIFACTS = 'artifacts'
IMAGE_MANIFEST_ARTIFACT_TYPE = 'type'
IMAGE_MANIFEST_ARTIFACT_TYPE_SQUASHFS = 'application/vnd.cray.image.rootfs.squashfs'

IMAGE_MANIFEST_VERSION_1_0 = '1.0'
IMAGE_MANIFEST_VERSIONS = [
    IMAGE_MANIFEST_VERSION_1_0,
]

ARTIFACT_LINK = 'link'
ARTIFACT_LINK_TYPE = 'type'
ARTIFACT_LINK_PATH = 'path'
ARTIFACT_LINK_ETAG = 'etag'
ARTIFACT_LINK_TYPE_S3 = 's3'
ARTIFACT_LINK_TYPES = [
    ARTIFACT_LINK_TYPE_S3,
]


def get_log_id():
    """ Return a unique string id that can be used to help tie related log entries together. """
    return str(uuid.uuid4())[:8]


class S3Url:
    """
    https://stackoverflow.com/questions/42641315/s3-urls-get-bucket-name-and-path/42641363
    """

    def __init__(self, url):
        self._parsed = urlparse(url, allow_fragments=False)

    @property
    def bucket(self):
        """ return the S3 bucket name """
        return self._parsed.netloc

    @property
    def key(self):
        """ return the S3 key name """
        if self._parsed.query:  # pylint: disable=no-else-return
            return self._parsed.path.lstrip('/') + '?' + self._parsed.query
        else:
            return self._parsed.path.lstrip('/')

    @property
    def url(self):
        """ return the combined S3 url """
        return self._parsed.geturl()

    def __repr__(self):
        return self._parsed.geturl()


def read_manifest_json(manifest_json_link):
    """
    Read a manifest.json file from s3. If the object was not found, log it and return an error..
    """

    def _read_s3_manifest_json():
        """
        Read a manifest.json file from s3. If the object was not found, log it and return an error..
        """
        app.logger.info("++ _read_s3_manifest_json {}.".format(str(manifest_json_link)))

        try:
            s3url = S3Url(manifest_json_link[ARTIFACT_LINK_PATH])
            s3_manifest_obj = app.s3.get_object(Bucket=s3url.bucket, Key=s3url.key)
            if s3_manifest_obj['ContentLength'] >= app.config['MAX_IMAGE_MANIFEST_SIZE_BYTES']:
                return None, problemify(status=http.client.BAD_REQUEST,
                                        detail='Image manifest file is larger than the expected maximum size '
                                               f'for the s3 artifact {str(manifest_json_link)}. Please determine '
                                               'the specific information that is missing or invalid and then '
                                               're-run the request with valid information.')
            s3_manifest_data = s3_manifest_obj['Body'].read().decode('utf-8')

        except (UnicodeDecodeError, ClientError) as error:
            app.logger.error("Unable to read manifest file {}.".format(str(manifest_json_link)))
            app.logger.debug(error)
            raise ImsReadManifestJsonException('Unable to read manifest file for the s3 artifact {}. Please determine '
                                               'the specific information that is missing or invalid and then '
                                               're-run the request with valid '
                                               'information.'.format(str(manifest_json_link)))

        try:
            s3_manifest_json = json.loads(s3_manifest_data)
            return s3_manifest_json, None
        except json.JSONDecodeError:
            raise ImsReadManifestJsonException('Manifest file is not valid Json for the s3 artifact {}. Please '
                                               'determine the specific information that is missing or invalid and then '
                                               're-run the request with valid '
                                               'information.'.format(str(manifest_json_link)))

    return {
        ARTIFACT_LINK_TYPE_S3: _read_s3_manifest_json
    }.get(manifest_json_link[ARTIFACT_LINK_TYPE].lower())()


def get_download_url(artifact_link):
    """
    return a download url for a given artifact_link
    """

    def _get_s3_download_url():
        """
        Given a S3 link, generate a pre-signed url that can be used to access the object.
        """

        app.logger.info("++ _get_s3_download_url {}.".format(str(artifact_link)))

        try:
            s3url = S3Url(artifact_link[ARTIFACT_LINK_PATH])
            url = app.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': s3url.bucket,
                        'Key': s3url.key},
                ExpiresIn=app.config['S3_URL_EXPIRATION'],
            )
        except ClientError as error:
            app.logger.error("Unable to generate a download url for s3 artifact {}.".format(str(artifact_link)))
            app.logger.debug(error)
            return None, problemify(status=http.client.BAD_REQUEST,
                                    detail='Unable to generate a download url for the s3 artifact {}. Please determine '
                                           'the specific information that is missing or invalid and then '
                                           're-run the request with valid information.'.format(str(artifact_link)))
        return url, None

    return {
        ARTIFACT_LINK_TYPE_S3: _get_s3_download_url
    }.get(artifact_link[ARTIFACT_LINK_TYPE].lower())()


def verify_recipe_link_unique(link):
    """
    Do a linear search of known IMS recipes. If the link path value being set matches an existing IMS recipe record,
    raise an UNPROCESSABLE_ENTITY exception.
    """
    if link:
        for recipe_record in app.data['recipes'].values():
            try:
                recipe_link = recipe_record.link
                if recipe_link and link[ARTIFACT_LINK_PATH] == recipe_link[ARTIFACT_LINK_PATH]:
                    app.logger(f'The link path {link[ARTIFACT_LINK_PATH]} matches the link path for the '
                               f'IMS recipe record {recipe_record.id}.')
                    return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                      detail=f'The link path {link[ARTIFACT_LINK_PATH]} matches the link path for the '
                                             f'IMS recipe record {recipe_record.id}. The link value must be unique and '
                                             'cannot be duplicated. Determine the specific information that is missing '
                                             'or invalid and then re-run the request with valid information.')
            except KeyError:
                pass
    return None


def verify_image_link_unique(link):
    """
    Do a linear search of known IMS images. If the link path value being set matches an existing IMS image record,
    raise an UNPROCESSABLE_ENTITY exception.
    """
    if link:
        for image_record in app.data['images'].values():
            try:
                image_link = image_record.link
                if image_link and link[ARTIFACT_LINK_PATH] == image_link[ARTIFACT_LINK_PATH]:
                    app.logger.info(f'The link path {link[ARTIFACT_LINK_PATH]} matches the link path for the '
                                    f'IMS image record {image_record.id}.')
                    return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                      detail=f'The link path {link[ARTIFACT_LINK_PATH]} matches the link path for the '
                                             f'IMS image record {image_record.id}. The link value must be unique and '
                                             'cannot be duplicated. Determine the specific information that is missing '
                                             'or invalid and then re-run the request with valid information.')
            except KeyError:
                pass
    return None


def validate_artifact(artifact_link):
    """
    Verify that a given artifact is available.
    """

    def _validate_s3_artifact():
        """
        Verify that a given artifact is available in S3.
        """

        app.logger.info("++ _validate_s3_artifact {}.".format(str(artifact_link)))

        md5sum = ""
        try:
            s3url = S3Url(artifact_link[ARTIFACT_LINK_PATH])
            s3_obj = app.s3.head_object(
                Bucket=s3url.bucket,
                Key=s3url.key
            )
            if ARTIFACT_LINK_ETAG in artifact_link and artifact_link[ARTIFACT_LINK_ETAG] and \
                    artifact_link[ARTIFACT_LINK_ETAG] != s3_obj["ETag"].strip('\"'):
                app.logger.warning("s3 object {} was found, but has an etag {} that does "
                                   "not match what IMS has.".format(str(artifact_link), s3_obj["ETag"]))
            if "Metadata" in s3_obj and s3_obj["Metadata"] and "md5sum" in s3_obj["Metadata"]:
                md5sum = s3_obj["Metadata"]["md5sum"]

        except ClientError as error:
            app.logger.error(f"Could not validate artifact link or artifact doesn't exist for {str(artifact_link)}.")
            app.logger.debug(error)
            raise ImsArtifactValidationException(f'The s3 artifact {artifact_link} cannot be validated. Please '
                                                 'determine the specific information that is missing or invalid and '
                                                 'then re-run the request with valid information.')
        return md5sum

    try:
        return {
            ARTIFACT_LINK_TYPE_S3: _validate_s3_artifact
        }.get(artifact_link[ARTIFACT_LINK_TYPE].lower())()
    except KeyError:
        app.logger.error(f'The s3 artifact {artifact_link} cannot be validated. The link type is not supported.')
        raise ImsArtifactValidationException(f'The s3 artifact {artifact_link} cannot be validated. The artifact link '
                                             'type is not supported. Please determine the specific information that is '
                                             'missing or invalid and then re-run the request with valid information.')


def validate_image_manifest(link):
    def _validate_1_0_image_artifacts(manifest_json):
        try:
            artifacts = manifest_json[IMAGE_MANIFEST_ARTIFACTS]
        except KeyError:
            return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                              detail="The image's manifest.json is malformed. It does not contain an artifacts map.")

        if not isinstance(artifacts, list):
            return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                              detail="The image's manifest.json is malformed. "
                                     "The artifacts property is not a json list.")

        for artifact in artifacts:

            if not isinstance(artifact, dict):
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. "
                                         "A listed artifact is not a json dictionary.")

            try:
                artifact_link = artifact[ARTIFACT_LINK]
            except KeyError:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. "
                                         "An artifact does not have a link value")

            try:
                link_type = artifact_link[ARTIFACT_LINK_TYPE]
            except KeyError:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. "
                                         "An artifact does not have a link type field")

            if link_type not in ARTIFACT_LINK_TYPES:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. "
                                         f"An artifact link type '{link_type}' not supported")

            try:
                _ = artifact_link[ARTIFACT_LINK_PATH]
            except KeyError:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. "
                                         "An artifact does not have a link path field")

            try:
                validate_artifact(artifact_link)
            except ImsArtifactValidationException as exc:
                app.logger.info("Could not validate artifact link or artifact doesn't exist")
                app.logger.info(str(exc))
                return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

        try:
            root_fs_artifacts = [artifact for artifact in artifacts if
                                 artifact[IMAGE_MANIFEST_ARTIFACT_TYPE].startswith(
                                     IMAGE_MANIFEST_ARTIFACT_TYPE_SQUASHFS)]
        except KeyError:
            return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                              detail="The image's manifest.json is malformed. An artifact does not have a type field")

        if not root_fs_artifacts:
            app.logger.info("No rootfs artifact could be found in the image manifest %s.", link)
            return problemify(status=http.client.BAD_REQUEST,
                              detail=f'Error reading the manifest.json for IMS {link}. The manifest '
                                     'does not include any rootfs artifacts. Determine the specific '
                                     'information that is missing or invalid and then re-run the request '
                                     'with valid information.')

        elif len(root_fs_artifacts) > 1:
            app.logger.info("Multiple rootfs artifacts found in the image manifest %s.", link)
            return problemify(status=http.client.BAD_REQUEST,
                              detail=f'Error reading the manifest.json for {link}. The manifest '
                                     'includes multiple rootfs artifacts. Determine the specific information '
                                     'that is missing or invalid and then re-run the request with valid '
                                     'information.')

    problem = verify_image_link_unique(link)
    if problem:
        app.logger.info("Link value being set is not unique")
        return problem

    try:
        validate_artifact(link)
    except ImsArtifactValidationException as exc:
        app.logger.info("Could not validate artifact link or artifact doesn't exist")
        app.logger.info(str(exc))
        return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

    manifest_json, problem = read_manifest_json(link)
    if problem:
        app.logger.info("Could not read image manifest")
        return problem

    if manifest_json:
        try:
            version = manifest_json[IMAGE_MANIFEST_VERSION]
        except KeyError:
            return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                              detail="The image's manifest.json does not contain a version field.")

        if version not in IMAGE_MANIFEST_VERSIONS:
            return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                              detail="The image's manifest.json has a version that is not supported. "
                                     f"Supported image manifest versions are: {','.join(IMAGE_MANIFEST_VERSIONS)}")

        return {
            IMAGE_MANIFEST_VERSION_1_0: _validate_1_0_image_artifacts
        }[version](manifest_json)


def delete_artifact(artifact_link):
    """
    Delete a given artifact
    """

    def _delete_s3_artifact():
        """
        Delete a given artifact from S3.
        """

        app.logger.info("++ _delete_s3_artifact {}.".format(str(artifact_link)))

        try:
            try:
                validate_artifact(artifact_link)
            except ImsArtifactValidationException as exc:
                app.logger.info("Could not validate artifact link or artifact doesn't exist")
                app.logger.info(str(exc))
                return problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

            s3url = S3Url(artifact_link[ARTIFACT_LINK_PATH])
            response = app.s3.delete_object(
                Bucket=s3url.bucket,
                Key=s3url.key
            )

            app.logger.debug(
                "Deleted artifact {} with response={}".format(artifact_link, pformat(response))  # noqa: E501
            )
        except ClientError as error:
            app.logger.error("Error removing s3 object {}".format(str(artifact_link)))
            app.logger.debug(error)
            return False

        return True

    return {
        ARTIFACT_LINK_TYPE_S3: _delete_s3_artifact
    }.get(artifact_link[ARTIFACT_LINK_TYPE].lower())()


def s3_move_artifact(origin_url, destination_path):
    """ Utility function to orchestrate moving/renaming a S3 artifact to a new key value. """
    new_object = app.s3resource.Object(origin_url.bucket, destination_path)
    new_object.copy_from(CopySource='/'.join([origin_url.bucket, origin_url.key]))
    app.s3resource.Object(origin_url.bucket, origin_url.key).delete()
    return new_object


def soft_delete_artifact(artifact_link):
    """
    Rename a given artifact
    """
    deleted_path = "deleted"

    def _soft_delete_s3_artifact():
        """
        Rename a given artifact from S3.
        """

        app.logger.info("++ _soft_delete_s3_artifact %s.", str(artifact_link))

        try:
            validate_artifact(artifact_link)

            origin_url = S3Url(artifact_link[ARTIFACT_LINK_PATH])
            new_object = s3_move_artifact(origin_url, '/'.join([deleted_path, origin_url.key]))

            return {
                'etag': new_object.e_tag.strip('\"'),
                'path': 's3://' + '/'.join([new_object.bucket_name, new_object.key]),
                'type': ARTIFACT_LINK_TYPE_S3
            }

        except ClientError as error:
            app.logger.error("Error removing s3 object {}".format(str(artifact_link)))
            app.logger.debug(error)
            return False

    return {
        ARTIFACT_LINK_TYPE_S3: _soft_delete_s3_artifact
    }.get(artifact_link[ARTIFACT_LINK_TYPE].lower())()


def soft_undelete_artifact(artifact_link):
    """
    Rename a given artifact
    """
    deleted_path = "deleted"

    def _soft_undelete_s3_artifact():
        """
        Rename a given artifact from S3.
        """

        app.logger.info("++ _soft_undelete_s3_artifact %s.", str(artifact_link))

        try:
            validate_artifact(artifact_link)

            origin_url = S3Url(artifact_link[ARTIFACT_LINK_PATH])
            undeleted_path = origin_url.key
            if not undeleted_path.startswith(deleted_path):
                raise ImsSoftUndeleteArtifactException(f"s3 object key {artifact_link} is not "
                                                       f"in the expected {deleted_path} folder.")
                return False
            undeleted_path = undeleted_path[len(deleted_path):]

            new_object = s3_move_artifact(origin_url, undeleted_path.lstrip('/'))

            return {
                'etag': new_object.e_tag.strip('\"'),
                'path': 's3://' + '/'.join([new_object.bucket_name, new_object.key]),
                'type': ARTIFACT_LINK_TYPE_S3
            }

        except ClientError as error:
            app.logger.error("Error removing s3 object {}".format(str(artifact_link)))
            app.logger.debug(error)
            return False

    return {
        ARTIFACT_LINK_TYPE_S3: _soft_undelete_s3_artifact
    }.get(artifact_link["type"].lower())()


def write_new_image_manifest(manifest_link, manifest_data):
    """ Utility function to write a new image manifest file. """

    def _write_new_s3_image_manifest():
        try:
            s3url = S3Url(manifest_link[ARTIFACT_LINK_PATH])
            bucket = app.s3resource.Bucket(s3url.bucket)
            return bucket.put_object(Key=s3url.key, Body=BytesIO(json.dumps(manifest_data).encode('utf-8')))
        except ClientError as error:
            app.logger.error("Error creating s3 manifest {}".format(str(manifest_link)))
            app.logger.debug(error)
            return False

    return {
        ARTIFACT_LINK_TYPE_S3: _write_new_s3_image_manifest
    }.get(manifest_link[ARTIFACT_LINK_TYPE].lower())()
