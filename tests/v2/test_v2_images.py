# Copyright 2018-2019, 2021 Hewlett Packard Enterprise Development LP
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

"""
Unit tests for resources/images.py
"""
import datetime
import io
import json
import unittest
import uuid

from botocore.response import StreamingBody
from botocore.stub import Stubber
from testtools import TestCase
from testtools.matchers import HasLength

from src.server import app
from src.server.helper import S3Url
from tests.utils import check_error_responses
from tests.v2.ims_fixtures import V2FlaskTestClientFixture, V2ImagesDataFixture


class TestV2ImageEndpoint(TestCase):
    """
    Test the image/{image_id} endpoint (ims.v2.resources.images.ImageResource)
    """

    @classmethod
    def setUpClass(cls):
        cls.stubber = Stubber(app.app.s3)

    def setUp(self):
        super(TestV2ImageEndpoint, self).setUp()
        self.test_id = str(uuid.uuid4())
        self.test_id_link_none = str(uuid.uuid4())
        self.test_id_no_link = str(uuid.uuid4())
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
        self.data_record_with_link = {
            'name': self.getUniqueString(),
            'link': {
                'path': 's3://boot-images/{}/manifest.json'.format(self.test_id),
                'etag': self.getUniqueString(),
                'type': 's3'
            },
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id,
        }
        self.data_record_link_none = {
            'name': self.getUniqueString(),
            'link': None,
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id_link_none,
        }
        self.data_record_no_link = {
            'name': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id_no_link,
        }
        self.data = [
            self.data_record_with_link,
            self.data_record_link_none,
            self.data_record_no_link
        ]

        self.useFixture(V2ImagesDataFixture(initial_data=self.data))
        self.test_uri_with_link = '/images/{}'.format(self.test_id)
        self.test_uri_with_link_cascade_false = '/images/{}?cascade=False'.format(self.test_id)
        self.test_uri_link_none = '/images/{}'.format(self.test_id_link_none)
        self.test_uri_no_link = '/images/{}'.format(self.test_id_no_link)

        self.s3_manifest_data = {
            "version": "1.0",
            "created": "2020-01-14 03:17:14",
            "artifacts": [
                {
                    "link": {
                        "path": "s3://boot-images/{}/rootfs".format(self.test_id),
                        "etag": self.getUniqueString(),
                        "type": "s3"
                    },
                    "type": "application/vnd.cray.image.rootfs.squashfs",
                    "md5": self.getUniqueString()
                }
            ]
        }

    def test_get(self):
        """ Test the images/{image_id} resource retrieval """
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

    def test_get_link_none(self):
        """ Test the images/{image_id} resource retrieval """
        response = self.app.get(self.test_uri_link_none)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data_record_link_none.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        self.assertEqual(response_data["link"], None)
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.data_record_link_none[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.data_record_link_none[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_no_link(self):
        """ Test the images/{image_id} resource retrieval """
        response = self.app.get(self.test_uri_no_link)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data_record_no_link.keys()).difference(response_data.keys()), set(),
                         'returned keys not the same')
        self.assertEqual(response_data["link"], None)
        for key in response_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.data_record_no_link[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            elif key == 'link':
                self.assertEqual(response_data[key], None,
                                 'resource field "{}" returned was not equal'.format(key))
            else:
                self.assertEqual(response_data[key], self.data_record_no_link[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self):
        """ Test the images/{image_id} resource retrieval with an unknown id """
        response = self.app.get('/images/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_delete(self):
        """ Test the images/{image_id} resource removal """
        manifest_s3_info = S3Url(self.data_record_with_link["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        for artifact in self.s3_manifest_data["artifacts"]:
            artifact_s3_info = S3Url(artifact["link"]["path"])
            artifact_expected_params = {'Bucket': artifact_s3_info.bucket, 'Key': artifact_s3_info.key}
            self.stubber.add_response('head_object', {"ETag": artifact["link"]["etag"]}, artifact_expected_params)
            self.stubber.add_response('delete_object', {}, artifact_expected_params)

        self.stubber.add_response('head_object',
                                  {"ETag": self.data_record_with_link["link"]["etag"]},
                                  manifest_expected_params)
        self.stubber.add_response('delete_object', {}, manifest_expected_params)

        self.stubber.activate()
        response = self.app.delete(self.test_uri_with_link)
        self.stubber.deactivate()

        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_cascade_false(self):
        """ Test the images/{image_id} resource removal """
        response = self.app.delete(self.test_uri_with_link_cascade_false)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_no_link(self):
        """ Test the images/{image_id} resource removal where the image doesn't have a link value"""
        for uri in (self.test_uri_no_link, self.test_uri_link_none):
            response = self.app.delete(uri)
            self.assertEqual(response.status_code, 204, 'status code was not 204')
            self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_404_bad_id(self):
        """ Test the images/{image_id} resource removal with an unknown id """
        response = self.app.delete('/images/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_patch(self):
        """ Test that we're able to patch a record """

        s3_bucket = "boot-images"
        s3_key = "{}/manifest.json".format(self.data_record_link_none['id'])

        link_data = {
            'link': {
                'path': 's3://{}/{}'.format(s3_bucket, s3_key),
                'etag': self.getUniqueString(),
                'type': 's3'
            }
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.stubber.add_response('head_object', {"ETag": link_data["link"]["etag"]}, expected_params)

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        manifest_expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json),
            },
            manifest_expected_params
        )

        expected_params = {'Bucket': s3_bucket, 'Key': "{}/rootfs".format(self.test_id)}
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

        s3_bucket = "boot-images"
        s3_key = "{}/manifest.json".format(self.data_record_with_link['id'])

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

        s3_bucket = "boot-images"
        s3_key = "{}/manifest.json".format(self.data_record_with_link['id'])

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


class TestV2ImagesCollectionEndpoint(TestCase):
    """
    Test the images/ collection endpoint (ims.v2.resources.images.ImagesCollection)
    """

    @classmethod
    def setUpClass(cls):
        cls.stubber = Stubber(app.app.s3)

    def setUp(self):
        super(TestV2ImagesCollectionEndpoint, self).setUp()
        self.test_uri = '/images'
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
        self.test_id = str(uuid.uuid4())
        self.data = {
            'name': self.getUniqueString(),
            'link': {
                'path': 's3://boot-images/{}/manifest.json'.format(self.test_id),
                'etag': self.getUniqueString(),
                'type': 's3'
            },
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_id,
        }
        self.test_images = self.useFixture(V2ImagesDataFixture(initial_data=self.data)).datastore
        self.test_domain = 'https://api-gw-service-nmn.local'

        self.s3_manifest_data = {
            "version": "1.0",
            "created": "2020-01-14 03:17:14",
            "artifacts": [
                {
                    "link": {
                        "path": "s3://boot-images/{}/rootfs".format(self.test_id),
                        "etag": self.getUniqueString(),
                        "type": "s3"
                    },
                    "type": "application/vnd.cray.image.rootfs.squashfs",
                    "md5": self.getUniqueString()
                }
            ]
        }

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
        input_name = self.getUniqueString()
        s3_bucket = 'boot-images'
        s3_key = '{}/manifest.json'.format(uuid.uuid4())
        input_data = {
            'name': input_name,
            'link': {
                'path': 's3://{}/{}'.format(s3_bucket, s3_key),
                'etag': self.getUniqueString(),
                'type': 's3'
            }
        }

        expected_params = {'Bucket': s3_bucket, 'Key': s3_key}
        self.stubber.add_response('head_object', {"ETag": input_data["link"]["etag"]}, expected_params)

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        manifest_expected_params = {'Bucket': s3_bucket, 'Key': s3_key}

        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        expected_params = {'Bucket': s3_bucket, 'Key': "{}/rootfs".format(self.test_id)}
        self.stubber.add_response('head_object', {"ETag": input_data["link"]["etag"]}, expected_params)

        self.stubber.activate()
        response = self.app.post('/images', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'image creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'name', 'link', 'id'],
                              'returned keys not the same')

    def test_post_link_none(self):
        """ Test happy path POST """
        input_name = self.getUniqueString()
        input_data = {
            'name': input_name,
            'link': None
        }

        response = self.app.post('/images', content_type='application/json', data=json.dumps(input_data))
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'image creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'name', 'link', 'id'],
                              'returned keys not the same')

    def test_post_no_link(self):
        """ Test happy path POST """
        input_name = self.getUniqueString()
        input_data = {
            'name': input_name
        }

        response = self.app.post('/images', content_type='application/json', data=json.dumps(input_data))
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['name'], input_name, 'artifact name was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'image creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'name', 'link', 'id'],
                              'returned keys not the same')

    def test_post_400_no_input(self):
        """ Test a POST request with no input provided by the client """
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_improper_type_inputs(self):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'name': self.getUniqueInteger()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_unknown_field(self):
        """ Test a POST request with a field that is not valid for the request """
        input_name = self.getUniqueString()
        input_data = {
            'name': input_name,
            'invalid_field': str(uuid.uuid4())  # invalid
        }
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_name_is_blank(self):
        """ Test case where the name field is empty """
        input_data = {
            'name': "",
        }
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
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
                'type': 's3'
            }
        }

        # This causes the s3 client to return a client error when it receives
        # head_object call
        self.stubber.add_client_error('head_object')

        self.stubber.activate()
        response = self.app.post('/images', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 422, ['status', 'title', 'detail'])


if __name__ == '__main__':
    unittest.main()
