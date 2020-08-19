"""
Configuration Objects for the Artifact Repository Service
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""
import os

import logging


class Config(object):
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
    LOG_LEVEL = logging.INFO

    S3_PROTOCOL = os.getenv('S3_PROTOCOL', 'http')
    S3_ENDPOINT = os.getenv('S3_ENDPOINT')
    S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
    S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
    S3_IMS_BUCKET = os.getenv('S3_IMS_BUCKET', 'ims')
    S3_BOOT_IMAGES_BUCKET = os.getenv('S3_BOOT_IMAGES_BUCKET', 'boot-images')

    S3_URL_EXPIRATION_DEFAULT = 60 * 60 * 24 * 5  # 5 days
    S3_URL_EXPIRATION = int(os.getenv('S3_URL_EXPIRATION', S3_URL_EXPIRATION_DEFAULT))

    S3_CONNECT_TIMEOUT_DEFAULT = 60  # seconds, botocore default
    S3_CONNECT_TIMEOUT = int(os.getenv('S3_CONNECT_TIMEOUT', S3_CONNECT_TIMEOUT_DEFAULT))

    S3_READ_TIMEOUT_DEFAULT = 60  # seconds, botocore default
    S3_READ_TIMEOUT = int(os.getenv('S3_READ_TIMEOUT', S3_READ_TIMEOUT_DEFAULT))

    HACK_DATA_STORE = '/var/ims/data'

class DevelopmentConfig(Config):
    """
    Configuration for Development. Filesystem paths default to $HOME/ims/...
    """
    DEBUG = True
    ENV = 'development'
    LOG_LEVEL = logging.DEBUG
    HACK_DATA_STORE = os.path.join(os.path.expanduser("~"), 'ims', 'data')


class TestingConfig(Config):
    """Configuration for Testing."""
    TESTING = True
    DEBUG = True
    ENV = 'development'
    LOG_LEVEL = logging.DEBUG


class StagingConfig(Config):
    """Configuration for Staging."""
    DEBUG = True
    LOG_LEVEL = logging.DEBUG


class ProductionConfig(Config):
    """Configuration for Production."""
    pass


APP_SETTINGS = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig
}
