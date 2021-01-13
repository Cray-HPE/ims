"""
Unit tests for resources/public_keys.py
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""
import json
import unittest

import datetime
import uuid
from testtools import TestCase
from testtools.matchers import HasLength

from tests.v2.ims_fixtures import V2FlaskTestClientFixture, V2PublicKeysDataFixture
from tests.utils import check_error_responses


class TestV2PublicKeyEndpoint(TestCase):
    """
    Test the public-key/{public_key_id} endpoint (ims.v2.resources.publickeys.PublicKeyResource)
    """

    def setUp(self):
        super(TestV2PublicKeyEndpoint, self).setUp()
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
        self.data = {
            'name': self.getUniqueString(),
            'public_key': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': str(uuid.uuid4()),
        }
        self.useFixture(V2PublicKeysDataFixture(initial_data=self.data))
        self.test_uri = '/public-keys/{}'.format(self.data['id'])

    def test_get(self):
        """ Test the public-keys/{public_key_id} resource retrieval """
        response = self.app.get(self.test_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data.keys()).difference(response_data.keys()), set(), 'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.data[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.data[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the artifacts/{artifact_id} resource retrieval with an unknown id """
        response = self.app.get('/public-keys/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_delete(self):
        """ Test the artifacts/{artifact_id} resource removal """
        response = self.app.delete(self.test_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_404_bad_id(self):
        """ Test the artifacts/{artifact_id} resource removal with an unknown id """
        response = self.app.delete('/public-keys/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])


class TestV2PublicKeysCollectionEndpoint(TestCase):
    """
    Test the public-keys/ collection endpoint (ims.v2.resources.publickeys.PublicKeysCollection)
    """

    def setUp(self):
        super(TestV2PublicKeysCollectionEndpoint, self).setUp()
        self.test_uri = '/public-keys'
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
        self.data = {
            'name': self.getUniqueString(),
            'public_key': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': str(uuid.uuid4()),
        }
        self.test_public_keys = self.useFixture(V2PublicKeysDataFixture(initial_data=self.data)).datastore

    def test_get(self):
        """ Test happy path GET """
        response = self.app.get(self.test_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(1), 'collection did not have an entry')
        response_data = json.loads(response.data)[0]
        for key in self.data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.data[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.data[key])

    def test_post(self):
        """ Test happy path POST """
        input_public_key = self.getUniqueString()
        input_name = self.getUniqueString()
        input_data = {'name': input_name, 'public_key': input_public_key}

        response = self.app.post('/public-keys', content_type='application/json', data=json.dumps(input_data))
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
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_missing_inputs(self):
        """ Test a POST request with missing data provided by the client """
        input_data = {'name': self.getUniqueString()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'public_key': self.getUniqueString()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_improper_type_inputs(self):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'name': self.getUniqueInteger(), 'public_key': self.getUniqueString()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'name': self.getUniqueString(), 'public_key': self.getUniqueInteger()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
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
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_name_is_blank(self):
        """ Test case where the name is blank """
        input_data = {
            'name': "",
            'public_key': self.getUniqueString(),
        }
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("name", response.json["errors"], "Expected name to be listed in error detail")

    def test_post_422_public_key_is_blank(self):
        """ Test case where the public_key is blank """
        input_data = {
            'name': self.getUniqueString(),
            'public_key': "",
        }
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("public_key", response.json["errors"], "Expected public_key to be listed in error detail")


if __name__ == '__main__':
    unittest.main()
