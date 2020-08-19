"""
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""

import http.client
import json

import uuid
from botocore.exceptions import ClientError
from flask import current_app as app
from pprint import pformat

from ims.errors import problemify

try:
    from urllib.parse import urlparse
except ImportError:
    from urllib.parse import urlparse


def get_log_id():
    return str(uuid.uuid4())[:8]


class S3Url(object):
    """
    https://stackoverflow.com/questions/42641315/s3-urls-get-bucket-name-and-path/42641363
    """

    def __init__(self, url):
        self._parsed = urlparse(url, allow_fragments=False)

    @property
    def bucket(self):
        return self._parsed.netloc

    @property
    def key(self):
        if self._parsed.query:
            return self._parsed.path.lstrip('/') + '?' + self._parsed.query
        else:
            return self._parsed.path.lstrip('/')

    @property
    def url(self):
        return self._parsed.geturl()


def read_manifest_json(manifest_json_link):
    """
    Read a manifest.json file from s3. If the object was not found, log it and return an error..
    """

    def _read_s3_manifest_json():
        """
        Read a manifest.json file from s3. If the object was not found, log it and return an error..
        """
        app.logger.info("++ _get_s3_download_url {}.".format(str(manifest_json_link)))

        try:
            s3url = S3Url(manifest_json_link["path"])
            s3_manifest_obj = app.s3.get_object(Bucket=s3url.bucket, Key=s3url.key)
            s3_manifest_data = s3_manifest_obj['Body'].read().decode('utf-8')

        except ClientError as error:
            app.logger.error("Unable to read manifest file {}.".format(str(manifest_json_link)))
            app.logger.debug(error)
            return None, problemify(status=http.client.BAD_REQUEST,
                                    detail='Unable to read manifest file for the s3 artifact {}. Please determine '
                                           'the specific information that is missing or invalid and then '
                                           're-run the request with valid information.'.format(str(manifest_json_link)))

        s3_manifest_json = json.loads(s3_manifest_data)
        return s3_manifest_json, None

    return {
        "s3": _read_s3_manifest_json
    }.get(manifest_json_link["type"].lower())()


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
            s3url = S3Url(artifact_link["path"])
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
        "s3": _get_s3_download_url
    }.get(artifact_link["type"].lower())()


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
            s3url = S3Url(artifact_link["path"])
            s3_obj = app.s3.head_object(
                Bucket=s3url.bucket,
                Key=s3url.key
            )
            if "etag" in artifact_link and artifact_link["etag"] and artifact_link["etag"] != s3_obj["ETag"]:
                app.logger.warning("s3 object {} was found, but has an etag {} that does "
                                   "not match what IMS has.".format(str(artifact_link), s3_obj["ETag"]))
            if "Metadata" in s3_obj and s3_obj["Metadata"] and "md5sum" in s3_obj["Metadata"]:
                md5sum = s3_obj["Metadata"]["md5sum"]

        except ClientError as error:
            app.logger.error("s3 object {} was not found.".format(str(artifact_link)))
            app.logger.debug(error)
            return False, problemify(status=http.client.BAD_REQUEST,
                                     detail='The s3 artifact {} cannot be validated. Please determine the '
                                            'specific information that is missing or invalid and then '
                                            're-run the request with valid information.'.format(str(artifact_link)))
        return md5sum, None

    return {
        "s3": _validate_s3_artifact
    }.get(artifact_link["type"].lower())()


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

            s3url = S3Url(artifact_link["path"])
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
        "s3": _delete_s3_artifact
    }.get(artifact_link["type"].lower())()
