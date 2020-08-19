"""
Image Management Service API Main
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""

import http.client
import os

from flask import Flask
from flask_restful import Api

from ims import DataStoreHACK
from ims.config import APP_SETTINGS
from ims.errors import problemify
from ims.resources.version import Version
from ims.resources.healthz import Ready, Live


def load_v2_api(_app):
    """
    Load the v2 IMS API.
    """
    import boto3
    from botocore.config import Config as BotoConfig
    from ims.v2 import apiv2_blueprint
    from ims.v2.models.publickeys import V2PublicKeyRecordSchema
    from ims.v2.models.recipes import V2RecipeRecordSchema
    from ims.v2.models.images import V2ImageRecordSchema
    from ims.v2.models.jobs import V2JobRecordSchema

    _app.data['public_keys'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2_public_keys.json'),
        V2PublicKeyRecordSchema(), 'id')
    _app.data['recipes'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2_recipes.json'),
        V2RecipeRecordSchema(), 'id')
    _app.data['images'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2_images.json'),
        V2ImageRecordSchema(), 'id')
    _app.data['jobs'] = DataStoreHACK(
        os.path.join(_app.config['HACK_DATA_STORE'], 'v2_jobs.json'),
        V2JobRecordSchema(), 'id')

    # Register blueprints/versions of API here
    _app.register_blueprint(apiv2_blueprint)

    boto3.set_stream_logger('boto3.resources', _app.config['LOG_LEVEL'])
    _app.s3 = boto3.client(
        's3',
        endpoint_url=_app.config['S3_PROTOCOL'] + "://" + _app.config['S3_ENDPOINT'],
        aws_access_key_id=_app.config['S3_ACCESS_KEY'],
        aws_secret_access_key=_app.config['S3_SECRET_KEY'],
        use_ssl=False,
        verify=False,
        config=BotoConfig(
            connect_timeout=int(_app.config['S3_CONNECT_TIMEOUT']),
            read_timeout=int(_app.config['S3_READ_TIMEOUT']),
        ),
    )
    _app.s3session = boto3.Session(
        aws_access_key_id=_app.config['S3_ACCESS_KEY'],
        aws_secret_access_key=_app.config['S3_SECRET_KEY'],
    )


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
    _app.logger.setLevel(_app.config['LOG_LEVEL'])
    _app.logger.info('Image management service configured in {} mode'.format(os.getenv('FLASK_ENV', 'production')))

    _app.data = {}

    load_v2_api(_app)

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
