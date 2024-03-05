#
# MIT License
#
# (C) Copyright 2020-2022 Hewlett Packard Enterprise Development LP
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
Test Fixtures
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
from src.server.models.remote_build_nodes import V3RemoteBuildNodeRecordSchema

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


class V3RemoteBuildNodesDataFixture(_GenericDataFixture):
    schema = V3RemoteBuildNodeRecordSchema
    datastore = app.data['remote_build_nodes']
    id_field = 'xname'


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
