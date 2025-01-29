#
# MIT License
#
# (C) Copyright 2020-2023, 2025 Hewlett Packard Enterprise Development LP
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
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from testtools import TestCase
from botocore.stub import Stubber
from testtools.matchers import HasLength

from src.server import app
from src.server.helper import S3Url, ARTIFACT_LINK_TYPE_S3
from tests.v3.ims_fixtures import V3FlaskTestClientFixture, V3RecipesDataFixture, V3DeletedRecipesDataFixture
from tests.utils import check_error_responses


class TestV3DeletedRecipeBase(TestCase):
    """ Base class for testing Deleted Recipes """

    def setUp(self):
        super(TestV3DeletedRecipeBase, self).setUp()

        self.s3_stub = Stubber(app.app.s3)
        self.s3resource_stub = Stubber(app.app.s3resource.meta.client)

        self.all_recipes_link = '/v3/recipes'
        self.all_deleted_recipes_link = '/v3/deleted/recipes'

        self.input_recipe_type = 'kiwi-ng'
        self.input_linux_distribution = 'sles12'
        self.input_arch = 'x86_64'
        self.input_require_dkms = False

        self.test_with_link_id = str(uuid4())
        self.test_with_link_uri = f'/v3/deleted/recipes/{self.test_with_link_id}'
        self.test_with_link_record = {
            'name': self.getUniqueString(),
            'link': {
                'path': 'http://ims/deleted/recipes/{}/recipe.tgz'.format(self.test_with_link_id),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            },
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
            'arch': self.input_arch,
            'require_dkms': self.input_require_dkms,
            'template_dictionary': [],
            'created': (datetime.now() - timedelta(days=77)).replace(microsecond=0).isoformat(),
            'deleted': datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_with_link_id,
        }

        self.test_link_none_id = str(uuid4())
        self.test_link_none_uri = f'/v3/deleted/recipes/{self.test_link_none_id}'
        self.test_link_none_record = {
            'name': self.getUniqueString(),
            'link': None,
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
            'template_dictionary': [],
            'created': (datetime.now() - timedelta(days=77)).replace(microsecond=0).isoformat(),
            'deleted': datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_link_none_id,
            'arch': self.input_arch,
            'require_dkms': self.input_require_dkms,
        }

        self.test_no_link_id = str(uuid4())
        self.test_no_link_uri = f'/v3/deleted/recipes/{self.test_no_link_id}'
        self.test_no_link_record = {
            'name': self.getUniqueString(),
            'link': None,
            'recipe_type': self.input_recipe_type,
            'linux_distribution': self.input_linux_distribution,
            'template_dictionary': [],
            'created': (datetime.now() - timedelta(days=77)).replace(microsecond=0).isoformat(),
            'deleted': datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_no_link_id,
            'arch': self.input_arch,
            'require_dkms': self.input_require_dkms,
        }
        self.data = [
            self.test_with_link_record,
            self.test_link_none_record,
            self.test_no_link_record
        ]

        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.useFixture(V3RecipesDataFixture(initial_data={}))
        self.useFixture(V3DeletedRecipesDataFixture(initial_data=self.data))

    def tearDown(self):
        super(TestV3DeletedRecipeBase, self).tearDown()
        self.s3resource_stub.assert_no_pending_responses()
        self.s3_stub.assert_no_pending_responses()

    def stub_soft_undelete(self, bucket, key, etag):
        self.s3_stub.add_response('head_object',
                                  {"ETag": etag},
                                  {'Bucket': bucket, 'Key': key})

        # NOTE: this isn't correct. The 'copy' method looks at the size of the artifact
        #  being copied and either completes it as a single transaction, or breaks it
        #  into multiple transactions. That type of interaction with boto3 does not
        #  stub out correctly and at this time there is no good solution.
        self.s3resource_stub.add_response(method='copy',
                                          service_response={
                                         'ResponseMetadata': {
                                             'HTTPStatusCode': 200,
                                         }
                                     },
                                          expected_params={
                                         'CopySource': {'Bucket':bucket, 'Key':key}
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
                                              'Key': key.replace('deleted/', '')
                                          })


class TestV3DeletedRecipeEndpoint(TestV3DeletedRecipeBase):
    """
    Test the v3/deleted/recipes/{recipe_id} endpoint (ims.v3.resources.recipes.DeletedRecipeResource)
    """

    def test_get(self):
        """ Test the /v3/deleted/recipes/{recipe_id} resource retrieval """

        for test_uri, test_record in [(self.test_with_link_uri, self.test_with_link_record),
                                      (self.test_no_link_uri, self.test_no_link_record)]:
            response = self.app.get(test_uri)
            self.assertEqual(response.status_code, 200, 'status code was not 200')
            response_data = json.loads(response.data)
            self.assertEqual(set(test_record.keys()).difference(response_data.keys()), set(),
                             'returned keys not the same')
            for key in response_data:
                if key in ('created', 'deleted'):
                    # microseconds don't always match up
                    self.assertAlmostEqual(datetime.strptime(test_record[key],
                                                             '%Y-%m-%dT%H:%M:%S'),
                                           datetime.strptime(response_data[key],
                                                             '%Y-%m-%dT%H:%M:%S+00:00'),
                                           delta=timedelta(seconds=1))
                else:
                    self.assertEqual(response_data[key], test_record[key],
                                     'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the /v3/deleted/recipes/{recipe_id} resource retrieval with an unknown id """
        response = self.app.get('/v3/deleted/recipes/{}'.format(str(uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    @pytest.mark.skip(reason="Boto3 Stubber can't handle multi-part copy command")
    def test_soft_undelete(self):
        """ PATCH /v3/deleted/recipes/{recipe_id} """

        artifact_s3_info = S3Url(self.test_with_link_record["link"]["path"])

        # Soft undelete linked recipe
        self.stub_soft_undelete(artifact_s3_info.bucket,
                                artifact_s3_info.key,
                                self.test_with_link_record["link"]["etag"])

        response = self.app.get(self.all_deleted_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 204')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        self.s3_stub.activate()
        self.s3resource_stub.activate()
        response = self.app.patch(self.test_with_link_uri,
                                  content_type='application/json',
                                  data=json.dumps({'operation': 'undelete'}))
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')
        self.s3resource_stub.deactivate()
        self.s3_stub.deactivate()

        response = self.app.get(self.all_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(1), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)-1), 'collection does not match expected result')

    def test_hard_delete(self):
        """ DELETE /v3/deleted/recipes/{recipe_id} """

        artifact_s3_info = S3Url(self.test_with_link_record["link"]["path"])
        artifact_expected_params = {'Bucket': artifact_s3_info.bucket, 'Key': artifact_s3_info.key}
        self.s3_stub.add_response(method='head_object',
                                  service_response={"ETag": self.test_with_link_record["link"]["etag"]},
                                  expected_params=artifact_expected_params)
        self.s3_stub.add_response(method='delete_object',
                                  service_response={},
                                  expected_params=artifact_expected_params)

        self.s3_stub.activate()
        response = self.app.delete(self.test_with_link_uri)
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')


class TestV3RecipesCollectionEndpoint(TestV3DeletedRecipeBase):
    """
    Test the /v3/deleted/recipes/ collection endpoint (ims.v3.resources.recipes.DeletedRecipesCollection)
    """

    def test_get_all(self):
        """ GET /v3/deleted/recipes """

        response = self.app.get(self.all_deleted_recipes_link)
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

    @pytest.mark.skip(reason="Boto3 Stubber can't handle multi-part copy command")
    def test_soft_undelete_all(self):
        """ PATCH /v3/deleted/recipes """

        for record in self.data:
            if 'link' in record and record["link"]:
                artifact_s3_info = S3Url(record["link"]["path"])
                self.stub_soft_undelete(artifact_s3_info.bucket,
                                        artifact_s3_info.key,
                                        record["link"]["etag"])

        response = self.app.get(self.all_deleted_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 204')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        self.s3_stub.activate()
        self.s3resource_stub.activate()
        response = self.app.patch(self.all_deleted_recipes_link,
                                  content_type='application/json',
                                  data=json.dumps({'operation': 'undelete'}))
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')
        self.s3resource_stub.deactivate()
        self.s3_stub.deactivate()

        response = self.app.get(self.all_deleted_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

    def test_hard_delete_all(self):
        """ DELETE /v3/deleted/recipes """

        for record in self.data:
            if 'link' in record and record["link"]:

                artifact_s3_info = S3Url(record["link"]["path"])
                artifact_expected_params = {'Bucket': artifact_s3_info.bucket, 'Key': artifact_s3_info.key}
                self.s3_stub.add_response('head_object', {"ETag": record["link"]["etag"]},
                                          artifact_expected_params)
                self.s3_stub.add_response('delete_object', {}, artifact_expected_params)

        self.s3_stub.activate()
        response = self.app.delete(self.all_deleted_recipes_link)
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_deleted_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_recipes_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')
