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
import json
from datetime import datetime, timedelta
from uuid import uuid4

from testtools import TestCase
from testtools.matchers import HasLength

from src.server import app
from src.server.helper import S3Url
from tests.v3.ims_fixtures import V3FlaskTestClientFixture, V3PublicKeysDataFixture, V3DeletedPublicKeysDataFixture
from tests.utils import check_error_responses


class TestV3DeletedPublicKeysBase(TestCase):
    """ Base class for testing Deleted PublicKeys """

    def setUp(self):
        super(TestV3DeletedPublicKeysBase, self).setUp()

        self.all_public_keys_link = '/v3/public-keys'
        self.all_deleted_public_keys_link = '/v3/deleted/public-keys'

        self.test_public_key_id = str(uuid4())
        self.test_public_key_uri = '/v3/deleted/public-keys/{}'.format(self.test_public_key_id)
        self.test_public_key_record = {
            'name': self.getUniqueString(),
            'public_key': self.getUniqueString(),
            'created': (datetime.now() - timedelta(days=77)).replace(microsecond=0).isoformat(),
            'deleted': datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_public_key_id,
        }

        self.data = [
            self.test_public_key_record,
        ]

        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.useFixture(V3PublicKeysDataFixture(initial_data=[]))
        self.useFixture(V3DeletedPublicKeysDataFixture(initial_data=self.data))


class TestV3DeletedPublicKeysEndpoint(TestV3DeletedPublicKeysBase):
    """
    Test the v3/deleted/public_keys/{public_key_id} endpoint (ims.v3.resources.public_keys.DeletedPublicKeysResource)
    """

    def test_get(self):
        """ Test the /v3/deleted/public_keys/{public_key_id} resource retrieval """

        response = self.app.get(self.test_public_key_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.test_public_key_record.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key in ('created', 'deleted'):
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.strptime(self.test_public_key_record[key],
                                                         '%Y-%m-%dT%H:%M:%S'),
                                       datetime.strptime(response_data[key],
                                                         '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=timedelta(seconds=1))
            else:
                self.assertEqual(response_data[key], self.test_public_key_record[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the /v3/deleted/public_keys/{public_keys_id} resource retrieval with an unknown id """
        response = self.app.get('/'.join([self.all_deleted_public_keys_link, str(uuid4())]))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_soft_undelete(self):
        """ PATCH /v3/deleted/public_keys/{public_key_id} """

        response = self.app.get(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 204')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        response = self.app.patch(self.test_public_key_uri,
                                  content_type='application/json',
                                  data=json.dumps({'operation': 'undelete'}))
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(1), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)-1), 'collection does not match expected result')

    def test_hard_delete(self):
        """ DELETE /v3/deleted/public_keys/{public_keys_id} """

        response = self.app.delete(self.test_public_key_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)-1), 'collection does not match expected result')


class TestV3PublicKeysCollectionEndpoint(TestV3DeletedPublicKeysBase):
    """
    Test the /v3/deleted/public-keys/ collection endpoint (ims.v3.resources.public_keys.DeletedPublicKeysCollection)
    """

    def test_get_all(self):
        """ GET /v3/deleted/public-keys """

        response = self.app.get(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        assert(len(self.data) == len(response_data))
        for source_record in self.data:
            match_found = False
            for response_record in response_data:
                if source_record['id'] == response_record['id']:
                    match_found = True

                    self.assertEqual(set(source_record.keys()).difference(response_record.keys()), set(),
                                     'returned keys not the same')

                    for key in response_record:
                        if key in ('created', 'deleted'):
                            # microseconds don't always match up
                            self.assertAlmostEqual(datetime.strptime(source_record[key],
                                                                     '%Y-%m-%dT%H:%M:%S'),
                                                   datetime.strptime(response_record[key],
                                                                     '%Y-%m-%dT%H:%M:%S+00:00'),
                                                   delta=timedelta(seconds=1))
                        else:
                            self.assertEqual(source_record[key], response_record[key],
                                             'resource field "{}" returned was not equal'.format(key))
            assert match_found

    def test_soft_undelete_all(self):
        """ PATCH /v3/deleted/public_keys """

        response = self.app.get(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 204')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        response = self.app.patch(self.all_deleted_public_keys_link,
                                  content_type='application/json',
                                  data=json.dumps({'operation': 'undelete'}))
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

    def test_hard_delete_all(self):
        """ DELETE /v3/deleted/public-keys """

        response = self.app.delete(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_deleted_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_public_keys_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')
