"""
Test Fixtures
Copyright 2020 Hewlett Packard Enterprise Development LP
"""

from fixtures import Fixture

from src.server.app import app
from src.server.models.images import V2ImageRecordSchema
from src.server.v3.models.images import V3DeletedImageRecordSchema
from src.server.models.jobs import V2JobRecordSchema
from src.server.models.publickeys import V2PublicKeyRecordSchema
from src.server.v3.models.public_keys import V3DeletedPublicKeyRecordSchema
from src.server.models.recipes import V2RecipeRecordSchema
from src.server.v3.models.recipes import V3DeletedRecipeRecordSchema
from tests.ims_fixtures import _GenericDataFixture


class V3FlaskTestClientFixture(Fixture):
    """ Test Fixture for preparing the Flask test client """

    def _setUp(self):
        app.config['TESTING'] = True
        self.addCleanup(app.config.__setitem__, 'TESTING', False)
        self.client = app.test_client()


class V3PublicKeysDataFixture(_GenericDataFixture):
    schema = V2PublicKeyRecordSchema
    datastore = app.data['public_keys']
    id_field = 'id'


class V3DeletedPublicKeysDataFixture(_GenericDataFixture):
    schema = V3DeletedPublicKeyRecordSchema
    datastore = app.data['deleted_public_keys']
    id_field = 'id'


class V3ImagesDataFixture(_GenericDataFixture):
    schema = V2ImageRecordSchema
    datastore = app.data['images']
    id_field = 'id'


class V3DeletedImagesDataFixture(_GenericDataFixture):
    schema = V3DeletedImageRecordSchema
    datastore = app.data['deleted_images']
    id_field = 'id'


class V3JobsDataFixture(_GenericDataFixture):
    schema = V2JobRecordSchema
    datastore = app.data['jobs']
    id_field = 'id'


class V3RecipesDataFixture(_GenericDataFixture):
    schema = V2RecipeRecordSchema
    datastore = app.data['recipes']
    id_field = 'id'


class V3DeletedRecipesDataFixture(_GenericDataFixture):
    schema = V3DeletedRecipeRecordSchema
    datastore = app.data['deleted_recipes']
    id_field = 'id'
