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
Unit tests for resources/public_keys.py
"""
import json
import unittest

import datetime
import uuid
from testtools import TestCase
from testtools.matchers import HasLength

from tests.v3.ims_fixtures import V3FlaskTestClientFixture, V3PublicKeysDataFixture, V3DeletedPublicKeysDataFixture
from tests.utils import check_error_responses


class TestV3PublicKeyBase(TestCase):

    def setUp(self):
        super(TestV3PublicKeyBase, self).setUp()

        self.test_public_key_id = str(uuid.uuid4())
        self.test_public_key_uri = '/v3/public-keys/{}'.format(self.test_public_key_id)
        self.test_public_key_record = {
            'name': self.getUniqueString(),
            'public_key': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_public_key_id,
        }

        self.data = [
            self.test_public_key_record,
        ]

        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.useFixture(V3PublicKeysDataFixture(initial_data=self.data))
        self.useFixture(V3DeletedPublicKeysDataFixture(initial_data=[]))

        self.all_public_keys_uri = '/v3/public-keys'
        self.all_deleted_public_keys_uri = '/v3/deleted/public-keys'


class TestV3PublicKeyEndpoint(TestV3PublicKeyBase):
    """
    Test the public-key/{public_key_id} endpoint (ims.v3.resources.publickeys.PublicKeyResource)
    """

    def test_get(self):
        """ Test the public-keys/{public_key_id} resource retrieval """
        response = self.app.get(self.test_public_key_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.test_public_key_record.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.test_public_key_record[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data[key],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=1))
            else:
                self.assertEqual(response_data[key], self.test_public_key_record[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the artifacts/{artifact_id} resource retrieval with an unknown id """
        response = self.app.get('/'.join([self.all_public_keys_uri, str(uuid.uuid4())]))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_delete(self):
        """ Test the artifacts/{artifact_id} resource removal """
        response = self.app.get(self.all_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(0), 'collection does not match expected result')

        response = self.app.delete(self.test_public_key_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)-1), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(1), 'collection does not match expected result')

    def test_delete_404_bad_id(self):
        """ Test the artifacts/{artifact_id} resource removal with an unknown id """
        response = self.app.delete('/v3/public-keys/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])


class TestV3PublicKeysCollectionEndpoint(TestV3PublicKeyBase):
    """
    Test the public-keys/ collection endpoint (ims.v3.resources.publickeys.PublicKeysCollection)
    """

    def test_get_all(self):
        """ Test happy path GET """
        response = self.app.get(self.all_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')
        response_data = json.loads(response.data)
        for source_record in self.data:
            match_found = False
            for response_record in response_data:
                if source_record['id'] == response_record['id']:
                    match_found = True
                    for key in source_record:
                        if key == 'created':
                            # microseconds don't always match up
                            self.assertAlmostEqual(datetime.datetime.strptime(source_record[key],
                                                                              '%Y-%m-%dT%H:%M:%S'),
                                                   datetime.datetime.strptime(response_record[key],
                                                                              '%Y-%m-%dT%H:%M:%S+00:00'),
                                                   delta=datetime.timedelta(seconds=1))
                        else:
                            self.assertEqual(source_record[key], response_record[key])

            assert match_found

    def test_post(self):
        """ Test happy path POST """
        input_public_key = self.getUniqueString()
        input_name = self.getUniqueString()
        input_data = {'name': input_name, 'public_key': input_public_key}

        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
        self.assertEqual(response_data['public_key'], input_public_key, 'public_key was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'public_key creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'name', 'public_key', 'id'],
                              'returned keys not the same')

    def test_post_400_no_input(self):
        """ Test a POST request with no input provided by the client """
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_missing_inputs(self):
        """ Test a POST request with missing data provided by the client """
        input_data = {'name': self.getUniqueString()}
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'public_key': self.getUniqueString()}
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_improper_type_inputs(self):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'name': self.getUniqueInteger(), 'public_key': self.getUniqueString()}
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'name': self.getUniqueString(), 'public_key': self.getUniqueInteger()}
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_unknown_field(self):
        """ Test a POST request with a field that is not valid for the request """
        input_name = self.getUniqueString()
        input_public_key = self.getUniqueString()
        input_data = {
            'name': input_name,
            'public_key': input_public_key,
            'invalid_field': str(uuid.uuid4())  # invalid
        }
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_name_is_blank(self):
        """ Test case where the name is blank """
        input_data = {
            'name': "",
            'public_key': self.getUniqueString(),
        }
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("name", response.json["errors"], "Expected name to be listed in error detail")

    def test_post_422_public_key_is_blank(self):
        """ Test case where the public_key is blank """
        input_data = {
            'name': self.getUniqueString(),
            'public_key': "",
        }
        response = self.app.post(self.all_public_keys_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("public_key", response.json["errors"], "Expected public_key to be listed in error detail")

    def test_delete_all(self):
        """ DELETE /v3/public-keys """

        response = self.app.get(self.all_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.delete(self.all_public_keys_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_public_keys_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

if __name__ == '__main__':
    unittest.main()
