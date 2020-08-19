"""
Test Fixtures
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""

from fixtures import Fixture

from ims.app import app
from ims.v2.models.images import V2ImageRecordSchema
from ims.v2.models.jobs import V2JobRecordSchema
from ims.v2.models.publickeys import V2PublicKeyRecordSchema
from ims.v2.models.recipes import V2RecipeRecordSchema
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
