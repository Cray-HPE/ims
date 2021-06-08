# Copyright 2020-2021 Hewlett Packard Enterprise Development LP
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# (MIT License)

import io
import json
from datetime import datetime, timedelta
from uuid import uuid4

from botocore.response import StreamingBody
from botocore.stub import Stubber
from testtools import TestCase
from testtools.matchers import HasLength

from src.server import app
from src.server.helper import S3Url, ARTIFACT_LINK_TYPE_S3
from tests.utils import check_error_responses
from tests.v3.ims_fixtures import V3FlaskTestClientFixture, V3ImagesDataFixture, V3DeletedImagesDataFixture


class TestV3BaseDeletedImage(TestCase):
    """ Base class for testing Deleted Images """

    def setUp(self):
        super(TestV3BaseDeletedImage, self).setUp()

        self.s3_stub = Stubber(app.app.s3)
        self.s3resource_stub = Stubber(app.app.s3resource.meta.client)

        self.all_images_link = '/v3/images'
        self.all_deleted_images_link = '/v3/deleted/images'

        self.test_with_link_id = str(uuid4())
        self.test_with_link_uri = f'/v3/deleted/images/{self.test_with_link_id}'
        self.test_with_link_manifest = {
            "version": "1.0",
            "created": "2020-01-14 03:17:14",
            "artifacts": [
                {
                    "link": {
                        "path": "s3://boot-images/deleted/{}/rootfs".format(self.test_with_link_id),
                        "etag": self.getUniqueString(),
                        "type": ARTIFACT_LINK_TYPE_S3
                    },
                    "type": "application/vnd.cray.image.rootfs.squashfs",
                    "md5": self.getUniqueString()
                },
                {
                    "link": {
                        "path": "s3://boot-images/deleted/{}/deleted_manifest.json".format(self.test_with_link_id),
                        "etag": self.getUniqueString(),
                        "type": ARTIFACT_LINK_TYPE_S3
                    },
                    "type": "application/vnd.cray.image.manifest",
                    "md5": self.getUniqueString()
                }
            ]
        }
        self.test_with_link_record = {
            'id': self.test_with_link_id,
            'name': self.getUniqueString(),
            'link': {
                'path': 's3://boot-images/{}/manifest.json'.format(self.test_with_link_id),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            },
            'created': (datetime.now() - timedelta(days=77)).replace(microsecond=0).isoformat(),
            'deleted': datetime.now().replace(microsecond=0).isoformat(),
        }

        self.test_no_link_id = str(uuid4())
        self.test_no_link_uri = f'/v3/deleted/images/{self.test_no_link_id}'
        self.test_no_link_record = {
            'id': self.test_no_link_id,
            'name': self.getUniqueString(),
            'link': None,
            'created': (datetime.now() - timedelta(days=77)).replace(microsecond=0).isoformat(),
            'deleted': datetime.now().replace(microsecond=0).isoformat(),
        }

        self.data = [
            self.test_with_link_record,
            self.test_no_link_record,
        ]

        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.useFixture(V3ImagesDataFixture(initial_data={}))
        self.useFixture(V3DeletedImagesDataFixture(initial_data=self.data))

    def tearDown(self):
        super(TestV3BaseDeletedImage, self).tearDown()
        self.s3resource_stub.assert_no_pending_responses()
        self.s3_stub.assert_no_pending_responses()

    def stub_soft_undelete(self, bucket, key, etag):
        self.s3_stub.add_response('head_object',
                                  {"ETag": etag},
                                  {'Bucket': bucket, 'Key': key})

        self.s3resource_stub.add_response(method='copy_object',
                                          service_response={
                                              'CopyObjectResult': {
                                                  'ETag': f"\"{etag}\"",
                                              },
                                              'ResponseMetadata': {
                                                  'HTTPStatusCode': 200,
                                              }
                                          },
                                          expected_params={
                                              'Bucket': bucket,
                                              'CopySource': '/'.join([bucket, key]),
                                              'Key': key.replace('deleted/', '')
                                          })

        self.s3resource_stub.add_response(method='delete_object',
                                          service_response={},
                                          expected_params={
                                              'Bucket': bucket,
                                              'Key': key
                                          })

        self.s3resource_stub.add_response(method='head_object',
                                          service_response={
                                              'ETag': f"\"{etag}\"",
                                          },
                                          expected_params={
                                              'Bucket': bucket,
                                              'Key': key.replace('deleted/', '')
                                          })


class TestV3DeletedImageEndpoint(TestV3BaseDeletedImage):
    """
    Test the v3/deleted/images/{image_id} endpoint (ims.v3.resources.images.DeletedImageResource)
    """

    def test_get(self):
        """ Test the /v3/deleted/images/{image_id} resource retrieval """

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
        """ Test the /v3/deleted/images/{image_id} resource retrieval with an unknown id """
        response = self.app.get('/v3/deleted/images/{}'.format(str(uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_soft_undelete(self):
        """ PATCH /v3/deleted/images/{image_id} """

        manifest_s3_info = S3Url(self.test_with_link_record["link"]["path"])

        s3_manifest_json = json.dumps(self.test_with_link_manifest).encode()
        self.s3_stub.add_response(
            method='get_object',
            service_response={
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            expected_params={'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}
        )

        # Soft undelete linked manifest artifacts
        for artifact in self.test_with_link_manifest["artifacts"]:
            artifact_info = S3Url(artifact["link"]["path"])
            self.stub_soft_undelete(artifact_info.bucket,
                                    artifact_info.key,
                                    artifact["link"]["etag"])

        self.s3_stub.add_response(method='head_object',
                                  service_response={'ETag': self.test_with_link_record["link"]["etag"]},
                                  expected_params={'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key})

        # DELETE deleted_manifest.json S3 object
        self.s3_stub.add_response(method='delete_object',
                                  service_response={},
                                  expected_params={
                                      'Bucket': manifest_s3_info.bucket,
                                      'Key': manifest_s3_info.key
                                  })

        response = self.app.get(self.all_deleted_images_link)
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

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(1), 'collection does not match expected result')

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data) - 1), 'collection does not match expected result')

    def test_hard_delete(self):
        """ DELETE /v3/deleted/images/{image_id} """

        manifest_s3_info = S3Url(self.test_with_link_record["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        s3_manifest_json = json.dumps(self.test_with_link_manifest).encode()
        self.s3_stub.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        for artifact in self.test_with_link_manifest["artifacts"]:
            artifact_s3_info = S3Url(artifact["link"]["path"])
            artifact_expected_params = {'Bucket': artifact_s3_info.bucket, 'Key': artifact_s3_info.key}
            self.s3_stub.add_response('head_object', {"ETag": artifact["link"]["etag"]}, artifact_expected_params)
            self.s3_stub.add_response('delete_object', {}, artifact_expected_params)

        self.s3_stub.add_response('head_object',
                                  {"ETag": self.test_with_link_record["link"]["etag"]},
                                  manifest_expected_params)
        self.s3_stub.add_response('delete_object', {}, manifest_expected_params)

        self.s3_stub.activate()
        response = self.app.delete(self.test_with_link_uri)
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')


class TestV3ImagesCollectionEndpoint(TestV3BaseDeletedImage):
    """
    Test the /v3/deleted/images/ collection endpoint (ims.v3.resources.images.DeletedImagesCollection)
    """

    def test_get_all(self):
        """ GET /v3/deleted/images """

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        assert (len(self.data) == len(response_data))
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
        """ PATCH /v3/deleted/images """

        for record in self.data:
            if 'link' in record and record["link"]:
                manifest_s3_info = S3Url(record["link"]["path"])
                manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

                s3_manifest_json = json.dumps(self.test_with_link_manifest).encode()
                self.s3_stub.add_response(
                    method='get_object',
                    service_response={
                        'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                        'ContentLength': len(s3_manifest_json)
                    },
                    expected_params={'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}
                )

                # Soft undelete linked manifest artifacts
                for artifact in self.test_with_link_manifest["artifacts"]:
                    artifact_info = S3Url(artifact["link"]["path"])
                    self.stub_soft_undelete(artifact_info.bucket,
                                            artifact_info.key,
                                            artifact["link"]["etag"])

                self.s3_stub.add_response('head_object',
                                          {"ETag": self.test_with_link_record["link"]["etag"]},
                                          manifest_expected_params)

                # DELETE deleted_manifest.json S3 object
                self.s3_stub.add_response(method='delete_object',
                                          service_response={},
                                          expected_params={
                                              'Bucket': manifest_s3_info.bucket,
                                              'Key': manifest_s3_info.key
                                          })

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 204')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        self.s3_stub.activate()
        self.s3resource_stub.activate()
        response = self.app.patch(self.all_deleted_images_link,
                                  content_type='application/json',
                                  data=json.dumps({'operation': 'undelete'}))
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')
        self.s3resource_stub.deactivate()
        self.s3_stub.deactivate()

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

    def test_hard_delete_all(self):
        """ DELETE /v3/deleted/images """

        for record in self.data:
            if 'link' in record and record["link"]:

                manifest_s3_info = S3Url(self.test_with_link_record["link"]["path"])
                manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

                s3_manifest_json = json.dumps(self.test_with_link_manifest).encode()
                self.s3_stub.add_response(
                    'get_object',
                    {
                        'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                        'ContentLength': len(s3_manifest_json)
                    },
                    manifest_expected_params
                )

                for artifact in self.test_with_link_manifest["artifacts"]:
                    artifact_s3_info = S3Url(artifact["link"]["path"])
                    artifact_expected_params = {'Bucket': artifact_s3_info.bucket, 'Key': artifact_s3_info.key}
                    self.s3_stub.add_response('head_object', {"ETag": artifact["link"]["etag"]},
                                              artifact_expected_params)
                    self.s3_stub.add_response('delete_object', {}, artifact_expected_params)

                self.s3_stub.add_response('head_object',
                                          {"ETag": self.test_with_link_record["link"]["etag"]},
                                          manifest_expected_params)
                self.s3_stub.add_response('delete_object', {}, manifest_expected_params)

        self.s3_stub.activate()
        response = self.app.delete(self.all_deleted_images_link)
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')
