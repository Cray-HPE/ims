#
# MIT License
#
# (C) Copyright 2020-2023 Hewlett Packard Enterprise Development LP
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
Unit tests for resources/images.py
"""
import datetime
import io
import json
import unittest
import uuid
from botocore.response import StreamingBody
from botocore.stub import Stubber, ANY
from testtools import TestCase
from testtools.matchers import HasLength

from src.server import app
from src.server.helper import S3Url, ARTIFACT_LINK_TYPE_S3
from tests.utils import check_error_responses, DATETIME_STRING
from tests.v3.ims_fixtures import V3FlaskTestClientFixture, V3ImagesDataFixture, V3DeletedImagesDataFixture


class TestV3ImageBase(TestCase):

    def setUp(self):
        super(TestV3ImageBase, self).setUp()

        self.s3_stub = Stubber(app.app.s3)
        self.s3resource_stub = Stubber(app.app.s3resource.meta.client)

        self.test_with_link_id = str(uuid.uuid4())
        self.test_arch = "x86_64"
        self.test_with_link_uri = '/v3/images/{}'.format(self.test_with_link_id)
        self.test_with_link_record = {
            'name': self.getUniqueString(),
            'link': {
                'path': 's3://boot-images/{}/manifest.json'.format(self.test_with_link_id),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            },
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_with_link_id,
            'arch': self.test_arch,
            'metadata': {}
        }

        self.test_link_none_id = str(uuid.uuid4())
        self.test_link_none_uri = '/v3/images/{}'.format(self.test_link_none_id)
        self.test_link_none_record = {
            'name': self.getUniqueString(),
            'link': None,
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_link_none_id,
            'arch': self.test_arch,
            'metadata': {}
        }

        self.test_no_link_id = str(uuid.uuid4())
        self.test_no_link_uri = '/v3/images/{}'.format(self.test_no_link_id)
        self.test_no_link_record = {
            'name': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_no_link_id,
            'arch': self.test_arch,
            'metadata': {}
        }
        self.test_data_record_with_metadata_id = str(uuid.uuid4())
        self.test_data_record_with_metadata_uri = '/v3/images/{}'.format(self.test_data_record_with_metadata_id)
        self.test_data_record_with_metadata_record = {
            'name': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_data_record_with_metadata_id,
            'arch': self.test_arch,
            'metadata': {'foo': 'bar'}
        }

        self.data_record_with_no_metadata_id = str(uuid.uuid4())
        self.data_record_with_no_metadata_uri = '/v3/images/{}'.format(self.data_record_with_no_metadata_id)
        self.data_record_with_no_metadata_record = {
            'name': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.data_record_with_no_metadata_id,
            'arch': self.test_arch
        }
        self.data = [
            self.data_record_with_link,
            self.data_record_link_none,
            self.data_record_no_link,
            self.data_record_with_metadata,
            self.data_record_with_no_metadata
        ]

        self.app = self.useFixture(V3FlaskTestClientFixture()).client
        self.useFixture(V3ImagesDataFixture(initial_data=self.data))
        self.useFixture(V3DeletedImagesDataFixture(initial_data={}))

        self.all_images_link = '/v3/images'
        self.all_deleted_images_link = '/v3/deleted/images'

        self.s3_manifest_data = {
            "version": "1.0",
            "created": "2020-01-14 03:17:14",
            "artifacts": [
                {
                    "link": {
                        "path": "s3://boot-images/{}/rootfs".format(self.test_with_link_id),
                        "etag": self.getUniqueString(),
                        "type": ARTIFACT_LINK_TYPE_S3
                    },
                    "type": "application/vnd.cray.image.rootfs.squashfs",
                    "md5": self.getUniqueString()
                }
            ]
        }

    def tearDown(self):
        super(TestV3ImageBase, self).tearDown()
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


class TestV3ImageEndpoint(TestV3ImageBase):
    """
    Test the v3/images/{image_id} endpoint (ims.v3.resources.images.ImageResource)
    """

    def test_get(self):
        """ Test the /v3/images/{image_id} resource retrieval """
        response = self.app.get(self.test_with_link_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.test_with_link_record.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.test_with_link_record[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  DATETIME_STRING),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.test_with_link_record[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_link_none(self):
        """ Test the /v3/images/{image_id} resource retrieval """
        response = self.app.get(self.test_link_none_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.test_link_none_record.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        self.assertEqual(response_data["link"], None)
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.test_link_none_record[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  DATETIME_STRING),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.test_link_none_record[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_no_link(self):
        """ Test the /v3/images/{image_id} resource retrieval """
        response = self.app.get(self.test_no_link_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.test_no_link_record.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        self.assertEqual(response_data["link"], None)
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.test_no_link_record[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  DATETIME_STRING),
                                       delta=datetime.timedelta(seconds=5))
            elif key == 'link':
                self.assertEqual(response_data[key], None,
                                 'resource field "{}" returned was not equal'.format(key))
            else:
                self.assertEqual(response_data[key], self.test_no_link_record[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the /v3/images/{image_id} resource retrieval with an unknown id """
        response = self.app.get('/v3/images/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_soft_delete(self):
        """ Test the /v3/images/{image_id} resource soft-delete """

        manifest_s3_info = S3Url(self.test_with_link_record["link"]["path"])
        # manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        self.s3_stub.add_response(
            method='get_object',
            service_response={
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            expected_params={'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}
        )

        # Soft delete linked manifest artifacts
        for artifact in self.s3_manifest_data["artifacts"]:
            artifact_info = S3Url(artifact["link"]["path"])
            self.stub_soft_delete(artifact_info.bucket,
                                  artifact_info.key,
                                  artifact["link"]["etag"])

        # Soft Delete existing manifest.json
        self.stub_soft_delete(manifest_s3_info.bucket,
                              manifest_s3_info.key,
                              self.test_with_link_record["link"]["etag"])

        # PUT deleted_manifest.json S3 object
        self.s3resource_stub.add_response(method='put_object',
                                          service_response={},
                                          expected_params={
                                         'Body': ANY,
                                         'Bucket': manifest_s3_info.bucket,
                                         'Key': '/'.join(
                                             ['deleted',
                                              self.test_with_link_record['id'],
                                              f'deleted_{ manifest_s3_info.key.split("/")[-1] }']
                                         )
                                     })

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        self.s3_stub.activate()
        self.s3resource_stub.activate()
        response = self.app.delete(self.test_with_link_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')
        self.s3resource_stub.deactivate()
        self.s3_stub.deactivate()

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)-1), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(1), 'collection does not match expected result')

    def test_soft_delete_no_link(self):
        """ Test the /v3/images/{image_id} resource removal where the image doesn't have a link value"""

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        for uri in (self.test_no_link_uri, self.test_link_none_uri):
            response = self.app.delete(uri)
            self.assertEqual(response.status_code, 204, 'status code was not 204')
            self.assertEqual(response.data, b'', 'resource returned was not empty')

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)-2), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(2), 'collection does not match expected result')

    def test_soft_delete_404_bad_id(self):
        """ Test the /v3/images/{image_id} resource removal with an unknown id """

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        response = self.app.delete('/v3/images/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

    def test_patch_change_architecture(self):
        """ Test that we're able to patch a record with a new architecture"""
        
        archs = ['x86_64','aarch64','x86_64']
        for arch in archs:
            patch_data = {'arch': arch}
            response = self.app.patch(self.test_link_none_uri, content_type='application/json', data=json.dumps(patch_data))

            self.assertEqual(response.status_code, 200, 'status code was not 200')
            response_data = json.loads(response.data)
            self.assertEqual(set(self.test_link_none_record.keys()).difference(response_data.keys()), set(),
                            'returned keys not the same')
            for key in response_data:
                if key == 'created':
                    # microseconds don't always match up
                    self.assertAlmostEqual(datetime.datetime.strptime(self.test_link_none_record[key],
                                                                    '%Y-%m-%dT%H:%M:%S'),
                                        datetime.datetime.strptime(response_data['created'],
                                                                    DATETIME_STRING),
                                        delta=datetime.timedelta(seconds=5))
                elif key == 'arch':
                    self.assertEqual(response_data[key], patch_data['arch'],
                                    'resource field "{}" returned was not equal'.format(key))
                else:
                    self.assertEqual(response_data[key], self.test_link_none_record[key],
                                    'resource field "{}" returned was not equal'.format(key))

    def test_patch(self):
        """ Test that we're able to patch a record """

        s3_bucket = "boot-images"
        s3_key = "{}/manifest.json".format(self.test_link_none_record['id'])

        link_data = {
            'link': {
                'path': 's3://{}/{}'.format(s3_bucket, s3_key),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            }
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.s3_stub.add_response('head_object', {"ETag": link_data["link"]["etag"]}, expected_params)

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        manifest_expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.s3_stub.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json),
            },
            manifest_expected_params
        )

        expected_params = {'Bucket': s3_bucket, 'Key': "{}/rootfs".format(self.test_with_link_id)}
        self.s3_stub.add_response('head_object', {"ETag": link_data["link"]["etag"]}, expected_params)

        self.s3_stub.activate()
        response = self.app.patch(self.test_link_none_uri, content_type='application/json', data=json.dumps(link_data))
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.test_link_none_record.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.test_link_none_record[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  DATETIME_STRING),
                                       delta=datetime.timedelta(seconds=5))
            elif key == 'link':
                self.assertEqual(response_data[key], link_data['link'],
                                 'resource field "{}" returned was not equal'.format(key))
            else:
                self.assertEqual(response_data[key], self.test_link_none_record[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_patch_fail_link_already_exists(self):
        """ Test that we're not able to patch a record that already has a link value """

        s3_bucket = "boot-images"
        s3_key = "{}/manifest.json".format(self.test_with_link_record['id'])

        link_data = {
            'link': {
                'path': 's3://{}/{}'.format(s3_bucket, s3_key),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            }
        }

        self.s3_stub.activate()
        response = self.app.patch(self.test_with_link_uri, content_type='application/json', data=json.dumps(link_data))
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 409, 'status code was not 409')

    def test_patch_same_link(self):
        """ Test that we're not able to patch a record that already has a link value """

        link_data = {
            'link': self.test_with_link_record['link']
        }

        self.s3_stub.activate()
        response = self.app.patch(self.test_with_link_uri, content_type='application/json', data=json.dumps(link_data))
        self.s3_stub.deactivate()

        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.test_link_none_record.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.test_with_link_record[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  DATETIME_STRING),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.test_with_link_record[key],
                                 'resource field "{}" returned was not equal'.format(key))

class TestV3ImagesCollectionEndpoint(TestV3ImageBase):
    """
    Test the /v3/images/ collection endpoint (ims.v3.resources.images.ImagesCollection)
    """

    def test_get_all(self):
        """ Test happy path GET """
        response = self.app.get(self.all_images_link)
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(response_data,
                        HasLength(len(self.data)), 'collection does not match expected result')
        for source_record in self.data:
            match_found = False
            for response_record in response_data:
                if source_record['id'] == response_record['id']:
                    match_found = True

                    self.assertEqual(set(source_record.keys()).difference(response_record.keys()), set(),
                                     'returned keys not the same')

                    for key in source_record:
                        if key == 'created':
                            # microseconds don't always match up
                            self.assertAlmostEqual(datetime.datetime.strptime(source_record[key],
                                                                              '%Y-%m-%dT%H:%M:%S'),
                                                   datetime.datetime.strptime(response_record[key],
                                                                              DATETIME_STRING),
                                                   delta=datetime.timedelta(seconds=1))
                        else:
                            self.assertEqual(source_record[key], response_record[key])

            assert match_found

    def test_post(self):
        """ Test happy path POST """
        input_name = self.getUniqueString()
        s3_bucket = 'boot-images'
        s3_key = '{}/manifest.json'.format(uuid.uuid4())
        input_data = {
            'name': input_name,
            'link': {
                'path': 's3://{}/{}'.format(s3_bucket, s3_key),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            }
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.s3_stub.add_response('head_object', {"ETag": input_data["link"]["etag"]}, expected_params)

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        manifest_expected_params = {'Bucket': s3_bucket, 'Key': s3_key}

        self.s3_stub.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        expected_params = {'Bucket': s3_bucket, 'Key': "{}/rootfs".format(self.test_with_link_id)}
        self.s3_stub.add_response('head_object', {"ETag": input_data["link"]["etag"]}, expected_params)

        self.s3_stub.activate()
        response = self.app.post('/v3/images', content_type='application/json', data=json.dumps(input_data))
        self.s3_stub.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'image creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'name', 'link', 'id', 'arch'],
                              'returned keys not the same')

    def test_post_link_none(self):
        """ Test happy path POST """
        input_name = self.getUniqueString()
        input_data = {
            'name': input_name,
            'link': None
        }

        response = self.app.post('/v3/images', content_type='application/json', data=json.dumps(input_data))
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'image creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'name', 'link', 'id', 'arch', 'metadata',],
                              'returned keys not the same')

    def test_post_no_link(self):
        """ Test happy path POST """
        input_name = self.getUniqueString()
        input_data = {
            'name': input_name
        }

        response = self.app.post('/v3/images', content_type='application/json', data=json.dumps(input_data))
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'image creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'name', 'link', 'id', 'arch', 'metadata'],
                              'returned keys not the same')

    def test_post_400_no_input(self):
        """ Test a POST request with no input provided by the client """
        response = self.app.post(self.all_images_link, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_improper_type_inputs(self):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'name': self.getUniqueInteger()}
        response = self.app.post(self.all_images_link, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_unknown_field(self):
        """ Test a POST request with a field that is not valid for the request """
        input_name = self.getUniqueString()
        input_data = {
            'name': input_name,
            'invalid_field': str(uuid.uuid4())  # invalid
        }
        response = self.app.post(self.all_images_link, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_name_is_blank(self):
        """ Test case where the name field is empty """
        input_data = {
            'name': "",
        }
        response = self.app.post(self.all_images_link, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("name", response.json["errors"], "Expected name to be listed in error detail")

    def test_post_422_missing(self):
        """ Test case where the S3  artifact is missing from S3 """
        input_name = self.getUniqueString()
        test_artifact_id = str(uuid.uuid4())
        input_data = {
            'name': input_name,
            'link': {
                'path': 's3://boot-images/{}/manifest.json'.format(test_artifact_id),
                'etag': self.getUniqueString(),
                'type': ARTIFACT_LINK_TYPE_S3
            }
        }

        # This causes the s3 client to return a client error when it receives
        # head_object call
        self.s3_stub.add_client_error('head_object')

        self.s3_stub.activate()
        response = self.app.post('/v3/images', content_type='application/json', data=json.dumps(input_data))
        self.s3_stub.deactivate()

        check_error_responses(self, response, 422, ['status', 'title', 'detail'])

    def test_soft_delete_all(self):
        """ DELETE /v3/images """

        for record in self.data:
            if 'link' in record and record["link"]:
                manifest_s3_info = S3Url(self.test_with_link_record["link"]["path"])
                s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
                self.s3_stub.add_response(
                    method='get_object',
                    service_response={
                        'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                        'ContentLength': len(s3_manifest_json)
                    },
                    expected_params={'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}
                )

                # Soft delete linked manifest artifacts
                for artifact in self.s3_manifest_data["artifacts"]:
                    artifact_info = S3Url(artifact["link"]["path"])
                    self.stub_soft_delete(artifact_info.bucket,
                                          artifact_info.key,
                                          artifact["link"]["etag"])

                # Soft Delete existing manifest.json
                self.stub_soft_delete(manifest_s3_info.bucket,
                                      manifest_s3_info.key,
                                      record["link"]["etag"])

                # PUT deleted_manifest.json S3 object
                self.s3resource_stub.add_response(method='put_object',
                                                  service_response={},
                                                  expected_params={
                                                 'Body': ANY,
                                                 'Bucket': manifest_s3_info.bucket,
                                                 'Key': '/'.join(
                                                     ['deleted',
                                                      record['id'],
                                                      f'deleted_{manifest_s3_info.key.split("/")[-1]}']
                                                 )
                                             })

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')

        self.s3_stub.activate()
        self.s3resource_stub.activate()
        response = self.app.delete(self.all_images_link)
        self.assertEqual(response.status_code, 204, 'status code was not 200')
        self.assertEqual(response.data, b'', 'resource returned was not empty')
        self.s3resource_stub.deactivate()
        self.s3_stub.deactivate()

        response = self.app.get(self.all_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(0), 'collection does not match expected result')

        response = self.app.get(self.all_deleted_images_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data),
                        HasLength(len(self.data)), 'collection does not match expected result')


if __name__ == '__main__':
    unittest.main()
