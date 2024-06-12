#
# MIT License
#
# (C) Copyright 2018-2024 Hewlett Packard Enterprise Development LP
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
