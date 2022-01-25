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

"""
Unit tests for resources/recipes.py
"""
import datetime
import json
import responses
import unittest
import uuid
from botocore.stub import Stubber
from testtools import TestCase
from testtools.matchers import HasLength

from src.server import app
from src.server.helper import S3Url, ARTIFACT_LINK_TYPE_S3
from tests.utils import check_error_responses
from tests.v3.ims_fixtures import V3FlaskTestClientFixture, V3RecipesDataFixture, V3DeletedRecipesDataFixture


class TestV3RecipeBase(TestCase):

    def setUp(self):
        super(TestV3RecipeBase, self).setUp()

        self.s3_stub = Stubber(app.app.s3)
        self.s3resource_stub = Stubber(app.app.s3resource.meta.client)

        self.test_id = str(uuid.uuid4())
        self.test_id_link_none = str(uuid.uuid4())
        self.test_id_no_link = str(uuid.uuid4())
        self.input_recipe_type = 'kiwi-ng'
        self.input_linux_distribution = 'sles12'
        self.data_record_with_link = {
            'name': self.getUniqueString(),
            'link': {
                'path': 'http://ims/recipes/{}/recipe.tgz'.format(self.test_id),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            },
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
            'template_dictionary': [],
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id,
        }
        self.data_record_link_none = {
            'name': self.getUniqueString(),
            'link': None,
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
            'template_dictionary': [],
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id_link_none,
        }
        self.data_record_no_link = {
            'name': self.getUniqueString(),
            'link': None,
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id_no_link,
        }
        self.data = [
            self.data_record_with_link,
            self.data_record_link_none,
            self.data_record_no_link
        ]

        self.test_uri_with_link = '/v3/recipes/{}'.format(self.test_id)
        self.test_uri_link_none = '/v3/recipes/{}'.format(self.test_id_link_none)
        self.test_uri_no_link = '/v3/recipes/{}'.format(self.test_id_no_link)
        self.all_recipes_uri = '/v3/recipes'
        self.all_deleted_recipes_uri = '/v3/deleted/recipes'

        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.useFixture(V3RecipesDataFixture(initial_data=self.data))
        self.useFixture(V3DeletedRecipesDataFixture(initial_data={}))

    def tearDown(self):
        super(TestV3RecipeBase, self).tearDown()
        self.s3resource_stub.assert_no_pending_responses()
        self.s3_stub.assert_no_pending_responses()

    def stub_soft_delete(self, bucket, key, etag):
        self.s3_stub.add_response('head_object',
                                  {"ETag": etag},
                                  {'Bucket': bucket, 'Key': key})

        self.s3resource_stub.add_response(method='copy_object',
                                          service_response={
                                              'CopyObjectResult': {
                                                  'ETag': f"\"{ etag }\"",
                                              },
                                              'ResponseMetadata': {
                                                  'HTTPStatusCode': 200,
                                              }
                                          },
                                          expected_params={
                                              'Bucket': bucket,
                                              'CopySource': '/'.join([bucket, key]),
                                              'Key': '/'.join(['deleted', key])
                                          })

        self.s3resource_stub.add_response(method='delete_object',
                                          service_response={},
                                          expected_params={
                                              'Bucket': bucket,
                                              'Key': key
                                          })

        self.s3resource_stub.add_response(method='head_object',
                                          service_response={
                                              'ETag': f"\"{ etag }\"",
                                          },
                                          expected_params={
                                              'Bucket': bucket,
                                              'Key': '/'.join(['deleted', key])
                                          })


class TestV3RecipeEndpoint(TestV3RecipeBase):
    """
    Test the recipe/{recipe_id} endpoint (ims.v3.resources.recipes.RecipeResource)
    """

    def test_get(self):
        """ Test the recipes/{recipe_id} resource retrieval """
        response = self.app.get(self.test_uri_with_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data_record_with_link.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.data_record_with_link[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.data_record_with_link[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the recipes/{recipe_id} resource retrieval with an unknown id """
        response = self.app.get('/recipes/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_delete(self):
        """ Test the recipes/{recipe_id} resource removal """

        recipe_s3_info = S3Url(self.data_record_with_link["link"]["path"])
        self.stub_soft_delete(recipe_s3_info.bucket,
                              recipe_s3_info.key,
                              self.data_record_with_link["link"]["etag"])

        response = self.app.get(self.all_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(0), 'collection does not match expected result')

        self.s3_stub.activate()
        self.s3resource_stub.activate()
        response = self.app.delete(self.test_uri_with_link)
        self.s3resource_stub.deactivate()
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)-1), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(1), 'collection does not match expected result')

    def test_delete_404_bad_id(self):
        """ Test the recipes/{recipe_id} resource removal with an unknown id """
        response = self.app.delete('/recipes/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_patch(self):
        """ Test that we're able to patch a record """

        s3_bucket = "ims"
        s3_key = "{}/recipe.tgz".format(self.data_record_link_none['id'])

        link_data = {
            'link': {
                'path': 's3://{}/{}'.format(s3_bucket, s3_key),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            }
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.s3_stub.add_response('head_object', {"ETag": link_data["link"]["etag"]}, expected_params)

        self.s3_stub.activate()
        response = self.app.patch(self.test_uri_link_none, content_type='application/json', data=json.dumps(link_data))
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data_record_link_none.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.data_record_link_none[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            elif key == 'link':
                self.assertEqual(response_data[key], link_data['link'],
                                 'resource field "{}" returned was not equal'.format(key))
            else:
                self.assertEqual(response_data[key], self.data_record_link_none[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_patch_fail_link_already_exists(self):
        """ Test that we're not able to patch a record that already has a link value """

        s3_bucket = "ims"
        s3_key = "{}/recipe.tgz".format(self.data_record_with_link['id'])

        link_data = {
            'link': {
                'path': 's3://{}/{}'.format(s3_bucket, s3_key),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            }
        }

        self.s3_stub.activate()
        response = self.app.patch(self.test_uri_with_link, content_type='application/json', data=json.dumps(link_data))
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 409, 'status code was not 409')

    def test_patch_same_link(self):
        """ Test that we're not able to patch a record that already has a link value """

        link_data = {
            'link': self.data_record_with_link['link']
        }

        self.s3_stub.activate()
        response = self.app.patch(self.test_uri_with_link, content_type='application/json', data=json.dumps(link_data))
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data_record_link_none.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.data_record_with_link[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.data_record_with_link[key],
                                 'resource field "{}" returned was not equal'.format(key))


class TestV3RecipesCollectionEndpoint(TestV3RecipeBase):
    """
    Test the recipes/ collection endpoint (ims.v3.resources.recipes.RecipesCollection)
    """

    def test_get_all(self):
        """ Test happy path GET """
        response = self.app.get(self.all_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')
        response_data = json.loads(response.data)
        for source_record in self.data:
            found_match = False
            for response_record in response_data:
                if source_record["id"] == response_record["id"]:
                    found_match = True
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

            assert found_match

    def _post(self, input_linux_distribution='sles12', expected_status_code=201, link=None):
        """ Test recipe creation.  Allow variations in linux distribution and expected status
            code to support multiple test cases. """
        input_name = self.getUniqueString()
        input_link = link
        input_recipe_type = 'kiwi-ng'
        input_data = {
            'name': input_name,
            'link': input_link,
            'recipe_type': input_recipe_type,
            'linux_distribution': input_linux_distribution,
        }

        if link:
            s3url = S3Url(link["path"])
            expected_params = {'Bucket': s3url.bucket, 'Key': s3url.key}
            self.s3_stub.add_response('head_object', {"ETag": link["etag"]}, expected_params)

        self.s3_stub.activate()
        response = self.app.post('/recipes', content_type='application/json', data=json.dumps(input_data))
        self.s3_stub.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, expected_status_code, 'status code was not ' + str(expected_status_code))

        if expected_status_code == 201:
            # Only check the response data if the post was successful.
            self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
            self.assertEqual(response_data['recipe_type'], input_recipe_type, 'recipe_type was not set properly')
            self.assertEqual(response_data['linux_distribution'], input_linux_distribution,
                             'linux_distribution was not set properly')
            self.assertRegex(response_data['id'],
                             r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
            self.assertIsNotNone(response_data['created'], 'recipe creation date/time was not set properly')
            self.assertItemsEqual(response_data.keys(),
                                  ['created', 'name', 'link', 'recipe_type', 'linux_distribution',
                                   'template_dictionary', 'id'], 'returned keys not the same')
            if link:
                self.assertEqual(response_data['link'], link, "artifact link values do not match")

    @responses.activate
    def test_post_create_sles12_linux_distro(self):
        """ Test happy path POST intended to create a sles12 distro """
        self._post()

    @responses.activate
    def test_post_create_sles12_linux_distro_with_link(self):
        """ Test happy path POST intended to create a sles12 distro """
        s3_bucket = "ims"
        s3_key = "{}/recipe.tgz".format(str(uuid.uuid4()))
        link = {
            'path': 's3://{}/{}'.format(s3_bucket, s3_key),
            'etag': self.getUniqueString(),
            'type': ARTIFACT_LINK_TYPE_S3
        }
        self._post(link=link)

    @responses.activate
    def test_post_create_centos7_linux_distro(self):
        """ Test happy path POST intended to create a centos7 distro """
        self._post(input_linux_distribution='centos7')

    @responses.activate
    def test_post_create_sles15_linux_distro(self):
        """ Test happy path POST intended to create a sles15 distro """
        self._post(input_linux_distribution='sles15')

    def test_post_422_create_unknown_linux_distro_prevented(self):
        """ Confirm an expected failure with POST intended to create an unknown (to IMS) distro.
            This must result in a 422 status code. """
        self._post(input_linux_distribution='unknown_distro', expected_status_code=422)

    def test_post_400_no_input(self):
        """ Test a POST request with no input provided by the client """
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_missing_inputs(self):
        """ Test a POST request with missing data provided by the client """
        input_data = {'name': self.getUniqueString()}
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'link': None}
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_improper_type_inputs(self):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'name': self.getUniqueInteger(), 'link': None}
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'name': self.getUniqueString(), 'link': self.getUniqueInteger()}
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_unknown_field(self):
        """ Test a POST request with a field that is not valid for the request """
        input_name = self.getUniqueString()
        input_recipe_type = 'kiwi-ng'
        input_linux_distribution = 'sles12'
        input_data = {
            'name': input_name,
            'link': None,
            'recipe_type': input_recipe_type,
            'linux_distribution': input_linux_distribution,
            'invalid_field': str(uuid.uuid4())  # invalid
        }
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_name_is_blank(self):
        """ Test case where name is blank """
        input_name = ""
        input_recipe_type = 'kiwi-ng'
        input_linux_distribution = 'sles12'
        input_data = {
            'name': input_name,
            'link': None,
            'recipe_type': input_recipe_type,
            'linux_distribution': input_linux_distribution,
        }
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("name", response.json["errors"], "Expected name to be listed in error detail")

    def test_post_422_missing(self):
        """ Test case where the S3 artifact is missing from S3 """
        input_name = self.getUniqueString()
        input_recipe_type = 'kiwi-ng'
        input_linux_distribution = 'sles12'
        test_artifact_id = str(uuid.uuid4())
        input_data = {
            'name': input_name,
            'link': {
                'path': 's3://ims/{}/recipe.tgz'.format(test_artifact_id),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            },
            'recipe_type': input_recipe_type,
            'linux_distribution': input_linux_distribution,
        }

        # This causes the s3 client to return a client error when it receives
        # head_object call
        self.s3_stub.add_client_error('head_object')

        self.s3_stub.activate()
        response = self.app.post('/recipes', content_type='application/json', data=json.dumps(input_data))
        self.s3_stub.deactivate()

        check_error_responses(self, response, 422, ['status', 'title', 'detail'])

    def test_post_422_invalid_recipe_type(self):
        """ Test case where recipe_type is invalid """
        input_name = self.getUniqueString()
        input_recipe_type = self.getUniqueString()
        input_linux_distribution = 'sles12'
        input_data = {
            'name': input_name,
            'link': None,
            'recipe_type': input_recipe_type,
            'linux_distribution': input_linux_distribution,
        }
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("recipe_type", response.json["errors"], "Expected recipe_type to be listed in error detail")

    def test_post_422_invalid_linux_distribution(self):
        """ Test case where recipe_type is invalid """
        input_name = self.getUniqueString()
        input_recipe_type = "kiwi-ng"
        input_linux_distribution = self.getUniqueString()
        input_data = {
            'name': input_name,
            'link': None,
            'recipe_type': input_recipe_type,
            'linux_distribution': input_linux_distribution,
        }
        response = self.app.post(self.all_recipes_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("linux_distribution", response.json["errors"],
                      "Expected linux_distribution to be listed in error detail")

    def test_delete_all(self):
        """ DELETE /v3/images """

        for record in self.data:
            if 'link' in record and record["link"]:
                link_info = S3Url(record["link"]["path"])
                # Soft Delete existing manifest.json
                self.stub_soft_delete(link_info.bucket,
                                      link_info.key,
                                      record["link"]["etag"])

        response = self.app.get(self.all_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        self.s3_stub.activate()
        self.s3resource_stub.activate()
        response = self.app.delete(self.all_recipes_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')
        self.s3resource_stub.deactivate()
        self.s3_stub.deactivate()

        response = self.app.get(self.all_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_recipes_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')


if __name__ == '__main__':
    unittest.main()
