"""
Test Fixtures
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
"""

from fixtures import Fixture

from src.server.app import app
from src.server.models.images import V2ImageRecordSchema
from src.server.models.jobs import V2JobRecordSchema
from src.server.models.publickeys import V2PublicKeyRecordSchema
from src.server.models.recipes import V2RecipeRecordSchema
from tests.ims_fixtures import _GenericDataFixture


class V2FlaskTestClientFixture(Fixture):
    """ Test Fixture for preparing the Flask test client """

    def _setUp(self):
        app.config['TESTING'] = True
        self.addCleanup(app.config.__setitem__, 'TESTING', False)
        self.client = app.test_client()


class V2PublicKeysDataFixture(_GenericDataFixture):
    schema = V2PublicKeyRecordSchema
    datastore = app.data['public_keys']
    id_field = 'id'


class V2ImagesDataFixture(_GenericDataFixture):
    schema = V2ImageRecordSchema
    datastore = app.data['images']
    id_field = 'id'


class V2JobsDataFixture(_GenericDataFixture):
    schema = V2JobRecordSchema
    datastore = app.data['jobs']
    id_field = 'id'


class V2RecipesDataFixture(_GenericDataFixture):
    schema = V2RecipeRecordSchema
    datastore = app.data['recipes']
    id_field = 'id'
