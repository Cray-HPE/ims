"""
Unit tests for resources/recipes.py
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""
import datetime
import json
import responses
import unittest
import uuid
from botocore.stub import Stubber
from testtools import TestCase
from testtools.matchers import HasLength

from ims import app
from ims.helper import S3Url
from tests.utils import check_error_responses
from tests.v2.ims_fixtures import V2FlaskTestClientFixture, V2RecipesDataFixture


class TestV2RecipeEndpoint(TestCase):
    """
    Test the recipe/{recipe_id} endpoint (ims.v2.resources.recipes.RecipeResource)
    """

    @classmethod
    def setUpClass(cls):
        cls.stubber = Stubber(app.app.s3)

    def setUp(self):
        super(TestV2RecipeEndpoint, self).setUp()
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
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
                'type': 's3'
            },
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id,
        }
        self.data_record_link_none = {
            'name': self.getUniqueString(),
            'link': None,
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
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
        self.test_uri_with_link = '/recipes/{}'.format(self.test_id)
        self.test_uri_with_link_cascade_false = '/recipes/{}?cascade=False'.format(self.test_id)
        self.test_uri_link_none = '/recipes/{}'.format(self.test_id_link_none)
        self.test_uri_no_link = '/recipes/{}'.format(self.test_id_no_link)
        self.useFixture(V2RecipesDataFixture(initial_data=self.data))

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
        recipe_expected_params = {'Bucket': recipe_s3_info.bucket, 'Key': recipe_s3_info.key}

        self.stubber.add_response('head_object',
                                  {"ETag": self.data_record_with_link["link"]["etag"]},
                                  recipe_expected_params)
        self.stubber.add_response('delete_object', {}, recipe_expected_params)

        self.stubber.activate()
        response = self.app.delete(self.test_uri_with_link)
        self.stubber.deactivate()

        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_cascade_false(self):
        """ Test the recipes/{recipe_id} resource removal """
        response = self.app.delete(self.test_uri_with_link_cascade_false)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

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
                'type': 's3'
            }
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.stubber.add_response('head_object', {"ETag": link_data["link"]["etag"]}, expected_params)

        self.stubber.activate()
        response = self.app.patch(self.test_uri_link_none, content_type='application/json', data=json.dumps(link_data))
        self.stubber.deactivate()

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
                'type': 's3'
            }
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.stubber.add_response('head_object', {"ETag": link_data["link"]["etag"]}, expected_params)

        self.stubber.activate()
        response = self.app.patch(self.test_uri_with_link, content_type='application/json', data=json.dumps(link_data))
        self.stubber.deactivate()

        self.assertEqual(response.status_code, 409, 'status code was not 409')

    def test_patch_same_link(self):
        """ Test that we're not able to patch a record that already has a link value """

        s3_bucket = "ims"
        s3_key = "{}/recipe.tgz".format(self.data_record_with_link['id'])

        link_data = {
            'link': self.data_record_with_link['link']
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.stubber.add_response('head_object', {"ETag": link_data["link"]["etag"]}, expected_params)

        self.stubber.activate()
        response = self.app.patch(self.test_uri_with_link, content_type='application/json', data=json.dumps(link_data))
        self.stubber.deactivate()

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


class TestV2RecipesCollectionEndpoint(TestCase):
    """
    Test the recipes/ collection endpoint (ims.v2.resources.recipes.RecipesCollection)
    """

    @classmethod
    def setUpClass(cls):
        cls.stubber = Stubber(app.app.s3)

    def setUp(self):
        super(TestV2RecipesCollectionEndpoint, self).setUp()
        self.test_uri = '/recipes'
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
        self.data = {
            'name': self.getUniqueString(),
            'link': {
                'path': self.getUniqueString(),
                'etag': self.getUniqueString(),
                'type': 's3'
            },
            'recipe_type': 'kiwi-ng',
            'linux_distribution': 'sles12',
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': str(uuid.uuid4()),
        }
        self.test_recipes = self.useFixture(V2RecipesDataFixture(initial_data=self.data)).datastore
        self.test_domain = 'https://api-gw-service-nmn.local'

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
            self.stubber.add_response('head_object', {"ETag": link["etag"]}, expected_params)

        self.stubber.activate()
        response = self.app.post('/recipes', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

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
                                  ['created', 'name', 'link', 'recipe_type', 'linux_distribution', 'id'],
                                  'returned keys not the same')
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
            'type': 's3'
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
        self._post(input_linux_distribution='unknowndistro', expected_status_code=422)

    def test_post_400_no_input(self):
        """ Test a POST request with no input provided by the client """
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_missing_inputs(self):
        """ Test a POST request with missing data provided by the client """
        input_data = {'name': self.getUniqueString()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'link': None}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_improper_type_inputs(self):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'name': self.getUniqueInteger(), 'link': None}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'name': self.getUniqueString(), 'link': self.getUniqueInteger()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
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
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
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
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("name", response.json["errors"], "Expected name to be listed in error detail")

    def test_post_400_missing(self):
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
                'type': 's3'
            },
            'recipe_type': input_recipe_type,
            'linux_distribution': input_linux_distribution,
        }

        # This causes the s3 client to return a client error when it receives
        # head_object call
        self.stubber.add_client_error('head_object')

        self.stubber.activate()
        response = self.app.post('/recipes', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

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
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
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
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("linux_distribution", response.json["errors"],
                      "Expected linux_distrobution to be listed in error detail")


if __name__ == '__main__':
    unittest.main()
