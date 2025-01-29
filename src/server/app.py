#
# MIT License
#
# (C) Copyright 2018-2025 Hewlett Packard Enterprise Development LP
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
Image Management Service API Main
"""

import os
import http.client
import logging

from flask import Flask
from flask_restful import Api

import boto3
from botocore.config import Config as BotoConfig
from src.server import DataStoreHACK
from src.server.config import APP_SETTINGS
from src.server.errors import problemify
from src.server.resources.healthz import Ready, Live
from src.server.resources.version import Version

from src.server.models.publickeys import V2PublicKeyRecordSchema
from src.server.v3.models.public_keys import V3DeletedPublicKeyRecordSchema
from src.server.models.recipes import V2RecipeRecordSchema
from src.server.v3.models.recipes import V3DeletedRecipeRecordSchema
from src.server.models.images import V2ImageRecordSchema
from src.server.v3.models.images import V3DeletedImageRecordSchema
from src.server.models.jobs import V2JobRecordSchema
from src.server.models.remote_build_nodes import V3RemoteBuildNodeRecordSchema
from src.server.vault import remote_node_key_setup


# CASMTRIAGE-6953: The filename strings in this module ('v2_public_keys.json',
# 'v2.1_images.json', etc) are used by scripts/operations/configuration/update_ims_data_files.py
# in the docs-csm repository to determine the names of the IMS data files inside its
# Kubernetes pod.

def load_datastore(_app):
    """ Utility function to load IMS data files. """

    _app.data['public_keys'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2_public_keys.json'),
        V2PublicKeyRecordSchema(), 'id')
    _app.data['deleted_public_keys'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v3_deleted_public_keys.json'),
        V3DeletedPublicKeyRecordSchema(), 'id')

    _app.data['recipes'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2.2_recipes.json'),
        V2RecipeRecordSchema(), 'id')
    _app.data['deleted_recipes'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v3.2_deleted_recipes.json'),
        V3DeletedRecipeRecordSchema(), 'id')

    _app.data['images'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2.1_images.json'),
        V2ImageRecordSchema(), 'id')
    _app.data['deleted_images'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v3.1_deleted_images.json'),
        V3DeletedImageRecordSchema(), 'id')

    _app.data['jobs'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2.2_jobs.json'),
        V2JobRecordSchema(), 'id')

    _app.data['remote_build_nodes'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2.0_remote_build_nodes.json'),
        V3RemoteBuildNodeRecordSchema(), 'xname')


def load_v2_api(_app):
    """
    Load the v2 IMS API.
    """
    from src.server.v2 import apiv2_blueprint  # pylint: disable=import-outside-toplevel
    _app.register_blueprint(apiv2_blueprint)


def load_v3_api(_app):
    """
    Load the v3 IMS API.
    """
    from src.server.v3 import apiv3_blueprint  # pylint: disable=import-outside-toplevel
    _app.register_blueprint(apiv3_blueprint)


def load_boto3(_app):
    """ Utility function to initialize S3 client objects. """
    boto3.set_stream_logger('boto3.resources', _app.config['LOG_LEVEL'])
    boto3.set_stream_logger("botocore", _app.config['LOG_LEVEL'])
    s3_config = BotoConfig(
            connect_timeout=int(_app.config['S3_CONNECT_TIMEOUT']),
            read_timeout=int(_app.config['S3_READ_TIMEOUT'])
    )
    _app.s3 = boto3.client(
        's3',
        endpoint_url=_app.config['S3_ENDPOINT'],
        aws_access_key_id=_app.config['S3_ACCESS_KEY'],
        aws_secret_access_key=_app.config['S3_SECRET_KEY'],
        verify=_app.config['S3_SSL_VALIDATE'],
        config=s3_config
    )
    _app.s3resource = boto3.resource(
        service_name='s3',
        verify=_app.config['S3_SSL_VALIDATE'],
        endpoint_url=_app.config['S3_ENDPOINT'],
        aws_access_key_id=_app.config['S3_ACCESS_KEY'],
        aws_secret_access_key=_app.config['S3_SECRET_KEY'],
        config=s3_config
    )
    # NOTE: Only present for multi-part file copy of artifacts that are uploaded
    #  through 'cray artifacts create boot-images...' and end up with STS as the
    #  artifact owner.
    _app.s3_sts_resource = boto3.resource(
        service_name='s3',
        verify=_app.config['S3_STS_SSL_VALIDATE'],
        endpoint_url=_app.config['S3_ENDPOINT'],
        aws_access_key_id=_app.config['S3_STS_ACCESS_KEY'],
        aws_secret_access_key=_app.config['S3_STS_SECRET_KEY'],
        config=s3_config
    )

def str_to_log_level(level:str) -> int:
    # NOTE: we only have to do this until we upgrade to Flask:3.2 or later, then the
    # _app.logger.setLevel will take the string version of the logging level
    name_to_level = {
        'CRITICAL': logging.CRITICAL,
        'FATAL': logging.FATAL,
        'ERROR': logging.ERROR,
        'WARN': logging.WARNING,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET,
    }

    # default to INFO if something unexpected is here
    ret_val = name_to_level.get(level)
    if ret_val is None:
        ret_val = logging.INFO
    return ret_val

def create_app():
    """
    Create the Flask application for the Image Management Service. Register
    * Register blueprints
    * Setup datastore
    * Setup logging levels
    * Handle 404 errors app-wide in an RFC 7807-compliant manner

    Returns: Flask application object.
    """
    _app = Flask(__name__)

    # Base app configuration, depends on FLASK_ENV environment variable
    # (which defaults to 'production')
    _app.config.from_object(APP_SETTINGS[os.getenv('FLASK_ENV', 'production')])

    # pylint: disable=E1101
    _app.logger.setLevel(str_to_log_level(_app.config['LOG_LEVEL']))
    _app.logger.info('Image management service configured in {} mode'.format(os.getenv('FLASK_ENV', 'production')))

    # dictionary to all the data store objects
    _app.data = {}

    #dictionary to all the remote build node status objects
    _app.remoteNodes = {}

    # log the gunicorn worker timeout on startup
    _app.logger.info(f"Gunicorn worker timeout: {os.getenv('GUNICORN_WORKER_TIMEOUT', '-1')}")
    _app.logger.info(f"DKMS enabled: {os.getenv('JOB_ENABLE_DKMS', 'Not Set')}")

    # load the saved data files
    load_datastore(_app)
    load_v2_api(_app)
    load_v3_api(_app)
    load_boto3(_app)

    # attempt to generate remote node ssh keys
    remote_node_key_setup(_app)

    try:
        with open("/app/.version") as version_file:
            _app.config["VERSION"] = version_file.read().splitlines()[0]
    except IOError:
        _app.config["VERSION"] = "Unknown"

    api = Api(_app)
    api.add_resource(Version,
                     '/version',
                     endpoint="version")
    api.add_resource(Ready,
                     '/healthz/ready',
                     endpoint="ready")
    api.add_resource(Live,
                     '/healthz/live',
                     endpoint="live")

    # Custom Error Handlers
    @_app.errorhandler(404)
    def _handle_404_error(*args, **kwargs):  # pylint: disable=W0612,W0613
        """
        Handle 404 errors on the app level so they conform to RFC7807.
        Flask-restful's built-in 404 handling does not.
        """
        return problemify(status=http.client.NOT_FOUND,
                          detail='The requested URL was not found on the server. If '
                                 'you entered the URL manually please check your '
                                 'spelling and try again.')

    return _app

app = create_app()

if __name__ == "__main__":
    app.run()
