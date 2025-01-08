#
# MIT License
#
# (C) Copyright 2018-2022, 2025 Hewlett Packard Enterprise Development LP
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
Configuration Objects for the Artifact Repository Service
"""
import logging
import os


class Config:
    """
    Parent configuration class. All configurations defined in APP_SETTINGS
    inherit from this class.

    This class configures Flask by setting variables at runtime. A combination
    of Flask-defined and IMS-specific configuration variables can be specified
    here.

    For Flask variables, see http://flask.pocoo.org/docs/1.0/config
    For Flask-Uploads, see http://flask-uploads.readthedocs.io/en/stable/#configuration

    IMS-specific Args:
        LOG_LEVEL: application logging level. Use log levels from the logging
            library.
        HACK_DATASTORE: Location for the temporary data store. Will be removed
            with SHASTACMS-1644

    """
    ENV = 'production'
    DEBUG = False
    TESTING = False
    MAX_CONTENT_LENGTH = None  # Unlimited
    LOG_LEVEL = os.getenv('LOG_LEVEL','INFO')

    # S3 creds for 'IMS' user
    S3_ENDPOINT = os.getenv('S3_ENDPOINT')
    S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
    S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
    S3_SSL_VALIDATE = \
        False if os.getenv('S3_SSL_VALIDATE', 'False').lower() in ('false', 'off', 'no', 'f', '0') \
            else os.getenv('S3_SSL_VALIDATE')
            
    # S3 creds for 'STS' user
    # NOTE: artifacts in boot-images that are uploaded via 'cray artifacts create...' will be
    #  assigned to the STS owner. A multi-part copy must be done as the STS user for this to
    #  succeed. This should not be required and may be a bug in boto3 so this may be able to
    #  be removed at some time in the future.
    S3_STS_ENDPOINT = os.getenv('S3_STS_ENDPOINT')
    S3_STS_ACCESS_KEY = os.getenv('S3_STS_ACCESS_KEY')
    S3_STS_SECRET_KEY = os.getenv('S3_STS_SECRET_KEY')
    S3_STS_SSL_VALIDATE = \
        False if os.getenv('S3_STS_SSL_VALIDATE', 'False').lower() in ('false', 'off', 'no', 'f', '0') \
            else os.getenv('S3_STS_SSL_VALIDATE')

    S3_IMS_BUCKET = os.getenv('S3_IMS_BUCKET', 'ims')
    S3_BOOT_IMAGES_BUCKET = os.getenv('S3_BOOT_IMAGES_BUCKET', 'boot-images')

    S3_URL_EXPIRATION_DEFAULT = 60 * 60 * 24 * 5  # 5 days
    S3_URL_EXPIRATION = int(os.getenv('S3_URL_EXPIRATION', str(S3_URL_EXPIRATION_DEFAULT)))

    S3_CONNECT_TIMEOUT_DEFAULT = 60  # seconds, botocore default
    S3_CONNECT_TIMEOUT = int(os.getenv('S3_CONNECT_TIMEOUT', str(S3_CONNECT_TIMEOUT_DEFAULT)))

    S3_READ_TIMEOUT_DEFAULT = 60  # seconds, botocore default
    S3_READ_TIMEOUT = int(os.getenv('S3_READ_TIMEOUT', str(S3_READ_TIMEOUT_DEFAULT)))

    HACK_DATA_STORE = '/var/ims/data'

    MAX_IMAGE_MANIFEST_SIZE_BYTES_DEFAULT = 1024 * 1024
    MAX_IMAGE_MANIFEST_SIZE_BYTES = int(os.getenv('MAX_IMAGE_MANIFEST_SIZE_BYTES', str(MAX_IMAGE_MANIFEST_SIZE_BYTES_DEFAULT)))


class DevelopmentConfig(Config):
    """
    Configuration for Development. Filesystem paths default to $HOME/ims/...
    """
    DEBUG = True
    ENV = 'development'
    LOG_LEVEL = 'DEBUG'
    HACK_DATA_STORE = os.path.join(os.path.expanduser("~"), 'ims', 'data')


class TestingConfig(Config):
    """Configuration for Testing."""
    TESTING = True
    DEBUG = True
    ENV = 'development'
    LOG_LEVEL = 'DEBUG'


class StagingConfig(Config):
    """Configuration for Staging."""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Configuration for Production."""


APP_SETTINGS = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig
}
