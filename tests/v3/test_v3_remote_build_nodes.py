#
# MIT License
#
# (C) Copyright 2023 Hewlett Packard Enterprise Development LP
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
Unit tests for resources/remote_build_nodes.py
"""
import json
import unittest

import datetime
import uuid
from testtools import TestCase
from testtools.matchers import HasLength

from tests.v3.ims_fixtures import V3FlaskTestClientFixture, V3RemoteBuildNodesDataFixture
from tests.utils import check_error_responses


class TestV3RemoteBuildNodesEndpoint(TestCase):
    """
    Test the remote-build-nodes/{remote_build_node_xname} endpoint (ims.v3.resources.remote_build_node.RemoteBuildNodeResource)
    """

    def setUp(self):
        super(TestV3RemoteBuildNodesEndpoint, self).setUp()
        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.data = {
            'xname': self.getUniqueString()
        }
        self.useFixture(V3RemoteBuildNodesDataFixture(initial_data=self.data))
        self.test_uri = '/v3/remote-build-nodes/{}'.format(self.data['xname'])

    def test_get(self):
        """ Test the remote-build-nodes/{remote_build_node_xname} resource retrieval """
        response = self.app.get(self.test_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data.keys()).difference(response_data.keys()), set(), 'returned keys not the same')
        for key in response_data:
            self.assertEqual(response_data[key], self.data[key],
                                'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the artifacts/{artifact_id} resource retrieval with an unknown id """
        response = self.app.get('/v3/remote-build-nodes/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_delete(self):
        """ Test the artifacts/{artifact_id} resource removal """
        response = self.app.delete(self.test_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_404_bad_id(self):
        """ Test the artifacts/{artifact_id} resource removal with an unknown id """
        response = self.app.delete('/v3/remote-build-nodes/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])


class TestV3RemoteBuildNodesCollectionEndpoint(TestCase):
    """
    Test the remote-build-nodes/ collection endpoint (ims.v3.resources.remote_build_nodes.RemoteBuildNodesCollection)
    """

    def setUp(self):
        super(TestV3RemoteBuildNodesCollectionEndpoint, self).setUp()
        self.test_uri = '/v3/remote-build-nodes'
        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.data = {
            'xname': self.getUniqueString()
        }
        self.test_remote_build_nodes = self.useFixture(V3RemoteBuildNodesDataFixture(initial_data=self.data)).datastore

    def test_get(self):
        """ Test happy path GET """
        response = self.app.get(self.test_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(1), 'collection did not have an entry')
        response_data = json.loads(response.data)[0]
        for key in self.data:
            self.assertEqual(response_data[key], self.data[key])

    def test_post(self):
        """ Test happy path POST """
        input_name = self.getUniqueString()
        input_data = {'xname': input_name}

        response = self.app.post('/v3/remote-build-nodes', content_type='application/json', data=json.dumps(input_data))
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['xname'], input_name, 'artifact name was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['xname'],
                              'returned keys not the same')

    def test_post_400_no_input(self):
        """ Test a POST request with no input provided by the client """
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_improper_type_inputs(self):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'xname': self.getUniqueInteger()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_unknown_field(self):
        """ Test a POST request with a field that is not valid for the request """
        input_name = self.getUniqueString()
        input_data = {
            'xname': input_name,
            'invalid_field': str(uuid.uuid4())  # invalid
        }
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_name_is_blank(self):
        """ Test case where the name is blank """
        input_data = {
            'xname': ""
        }
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("xname", response.json["errors"], "Expected xname to be listed in error detail")

if __name__ == '__main__':
    unittest.main()
