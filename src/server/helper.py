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
import http.client
import json
import uuid
from io import BytesIO
from pprint import pformat

from botocore.exceptions import ClientError
from flask import current_app as app

from src.server.errors import problemify

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
                                               'for the s3 artifact {}. Please determine '
                                               'the specific information that is missing or invalid and then '
                                               're-run the request with valid information.'.format(
                                            str(manifest_json_link)))
            s3_manifest_data = s3_manifest_obj['Body'].read().decode('utf-8')

        except (UnicodeDecodeError, ClientError) as error:
            app.logger.error("Unable to read manifest file {}.".format(str(manifest_json_link)))
            app.logger.debug(error)
            return None, problemify(status=http.client.BAD_REQUEST,
                                    detail='Unable to read manifest file for the s3 artifact {}. Please determine '
                                           'the specific information that is missing or invalid and then '
                                           're-run the request with valid information.'.format(str(manifest_json_link)))

        try:
            s3_manifest_json = json.loads(s3_manifest_data)
            return s3_manifest_json, None
        except json.JSONDecodeError:
            return None, problemify(status=http.client.BAD_REQUEST,
                                    detail='Manifest file is not valid Json for the s3 artifact {}. Please determine '
                                           'the specific information that is missing or invalid and then '
                                           're-run the request with valid information.'.format(str(manifest_json_link)))

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
            app.logger.error("s3 object {} was not found.".format(str(artifact_link)))
            app.logger.debug(error)
            return False, problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                     detail='The s3 artifact {} cannot be validated. Please determine the '
                                            'specific information that is missing or invalid and then '
                                            're-run the request with valid information.'.format(str(artifact_link)))
        return md5sum, None

    try:
        return {
            ARTIFACT_LINK_TYPE_S3: _validate_s3_artifact
        }.get(artifact_link[ARTIFACT_LINK_TYPE].lower())()
    except KeyError:
        return False, problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                 detail='The s3 artifact {} cannot be validated. THe artifact link type is not supported. '
                                        'Please determine the specific information that is missing or invalid and then '
                                        're-run the request with valid information.'.format(str(artifact_link)))


def validate_image_manifest(link):
    def _validate_1_0_image_artifacts(manifest_json):
        try:
            artifacts = manifest_json[IMAGE_MANIFEST_ARTIFACTS]
        except KeyError:
            return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                              detail="The image's manifest.json is malformed. It does not contain an artifacts map.")

        if not isinstance(artifacts, list):
            return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                              detail="The image's manifest.json is malformed. The artifacts property is not a json list.")

        for artifact in artifacts:

            if not isinstance(artifact, dict):
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. A listed artifact is not a json dictionary.")

            try:
                artifact_link = artifact[ARTIFACT_LINK]
            except KeyError:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. An artifact does not have a link value")

            try:
                link_type = artifact_link[ARTIFACT_LINK_TYPE]
            except KeyError:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. An artifact does not have a link type field")

            if link_type not in ARTIFACT_LINK_TYPES:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. An artifact link type '{}' not supported".format(
                                      link_type))

            try:
                link_path = artifact_link[ARTIFACT_LINK_PATH]
            except KeyError:
                return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                                  detail="The image's manifest.json is malformed. An artifact does not have a link path field")

            _, problem = validate_artifact(artifact_link)
            if problem:
                app.logger.info("Could not validate artifact link or artifact doesn't exist")
                return problem

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
                              detail='Error reading the manifest.json for IMS %s. The manifest '
                                     'does not include any rootfs artifacts. Determine the specific '
                                     'information that is missing or invalid and then re-run the request '
                                     'with valid information.'.format(link))

        elif len(root_fs_artifacts) > 1:
            app.logger.info("Multiple rootfs artifacts found in the image manifest %s.", link)
            return problemify(status=http.client.BAD_REQUEST,
                              detail='Error reading the manifest.json for %s. The manifest '
                                     'includes multiple rootfs artifacts. Determine the specific information '
                                     'that is missing or invalid and then re-run the request with valid '
                                     'information.'.format(link))

    _, problem = validate_artifact(link)
    if problem:
        app.logger.info("Could not validate artifact link or artifact doesn't exist")
        return problem

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
            _, problem = validate_artifact(artifact_link)
            if problem:
                app.logger.error("s3 object {} was not found.".format(str(artifact_link)))
                return False

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
            _, problem = validate_artifact(artifact_link)
            if problem:
                app.logger.error("s3 object %s was not found.", str(artifact_link))
                return False

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
            _, problem = validate_artifact(artifact_link)
            if problem:
                app.logger.error("s3 object %s was not found.", str(artifact_link))
                return False

            origin_url = S3Url(artifact_link[ARTIFACT_LINK_PATH])
            undeleted_path = origin_url.key
            if not undeleted_path.startswith(deleted_path):
                app.logger.error("s3 object key %s is not in the expected %s folder.", str(artifact_link), deleted_path)
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
