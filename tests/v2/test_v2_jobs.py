# Copyright 2018-2021 Hewlett Packard Enterprise Development LP
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
Unit tests for resources/jobs.py
"""
import datetime
import io
import json
import unittest
import uuid

import mock
import responses
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber
from kubernetes.client.rest import ApiException
from testtools import TestCase
from testtools.matchers import HasLength

from src.server import app
from src.server.helper import S3Url
from src.server.models.jobs import STATUS_TYPES
from tests.utils import check_error_responses
from tests.v2.ims_fixtures import \
    V2FlaskTestClientFixture, \
    V2JobsDataFixture, \
    V2PublicKeysDataFixture, \
    V2RecipesDataFixture, \
    V2ImagesDataFixture


@mock.patch("src.server.v2.resources.jobs.client")
@mock.patch("src.server.v2.resources.jobs.config")
@mock.patch("src.server.v2.resources.jobs.utils")
class TestV2JobEndpoint(TestCase):
    """
    Test the job/{job_id} endpoint (ims.v2.resources.jobs.JobResource)
    """

    def setUp(self):
        super(TestV2JobEndpoint, self).setUp()
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
        self.test_job_id = str(uuid.uuid4())
        self.data = {
            'job_type': "create",
            'artifact_id': str(uuid.uuid4()),
            'public_key_id': str(uuid.uuid4()),
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
            'kernel_parameters_file_name': self.getUniqueString(),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_job_id,
            'kubernetes_job': 'cray-ims-%s-create' % self.test_job_id,
            'kubernetes_service': 'cray-ims-%s-service' % self.test_job_id,
            'kubernetes_configmap': 'cray-ims-%s-configmap' % self.test_job_id,
        }
        self.useFixture(V2JobsDataFixture(initial_data=self.data))
        self.test_uri = '/jobs/{}'.format(self.data['id'])

    def test_get(self, client_mock, config_mock, utils_mock):
        """ Test the jobs/{job_id} resource retrieval """
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
            elif key in self.data:
                self.assertEqual(response_data[key], self.data[key],
                                 'resource field "{}" returned was not equal'.format(key))

    def test_get_404_bad_id(self, client_mock, config_mock, utils_mock):
        """ Test the artifacts/{artifact_id} resource retrieval with an unknown id """
        response = self.app.get('/jobs/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_delete(self, client_mock, config_mock, utils_mock):
        """ Test the artifacts/{artifact_id} resource removal """
        response = self.app.delete(self.test_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_404_bad_id(self, client_mock, config_mock, utils_mock):
        """ Test the artifacts/{artifact_id} resource removal with an unknown id """
        response = self.app.delete('/jobs/{}'.format(str(uuid.uuid4())))
        check_error_responses(self, response, 404, ['status', 'title', 'detail'])

    def test_delete_k8s_job_not_found_ok(self, utils_mock, config_mock, client_mock):
        exception_text = self.getUniqueString()
        client_mock.BatchV1Api().delete_namespaced_job.side_effect = ApiException(exception_text, reason="Not Found")
        response = self.app.delete(self.test_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

    def test_delete_k8s_api_error(self, utils_mock, config_mock, client_mock):
        exception_text = self.getUniqueString()
        exception_reason = self.getUniqueString()
        client_mock.BatchV1Api().delete_namespaced_job.side_effect = \
            ApiException(exception_text, reason=exception_reason)
        response = self.app.delete(self.test_uri)
        self.assertEqual(response.status_code, 500, 'status code was not 500')
        self.assertEqual(response.json['errors'], ["({0})\nReason: {1}\n".format(exception_text, exception_reason)],
                         'returned exception did not contain expected text')

    def test_delete_general_exception(self, utils_mock, config_mock, client_mock):
        exception_text = self.getUniqueString()
        client_mock.BatchV1Api().delete_namespaced_job.side_effect = Exception(exception_text)
        response = self.app.delete(self.test_uri)
        self.assertEqual(response.status_code, 500, 'status code was not 500')
        self.assertEqual(response.json['errors'], [exception_text], 'returned exception did not contain expected text')

    def test_patch_resultant_image_id(self, client_mock, config_mock, utils_mock):
        input_data = {
            'resultant_image_id': str(uuid.uuid4())
        }

        response = self.app.patch(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        response_data = json.loads(response.data)
        self.assertEqual(set(self.data.keys()).difference(response_data.keys()), set(), 'returned keys not the same')
        self.assertEqual(response_data['resultant_image_id'], input_data['resultant_image_id'],
                         'resource field "resultant_image_id" returned was not equal')

    def test_patch_job_status(self, client_mock, config_mock, utils_mock):

        for status in STATUS_TYPES:
            input_data = {
                'status': status
            }

            response = self.app.patch(self.test_uri, content_type='application/json', data=json.dumps(input_data))
            self.assertEqual(response.status_code, 200, 'status code was not 200')
            response_data = json.loads(response.data)
            self.assertEqual(set(self.data.keys()).difference(response_data.keys()), set(),
                             'returned keys not the same')
            self.assertEqual(response_data['status'], input_data['status'],
                             'resource field "status" returned was not equal')


@mock.patch("src.server.v2.resources.jobs.client")
@mock.patch("src.server.v2.resources.jobs.config")
@mock.patch("src.server.v2.resources.jobs.utils")
class TestV2JobsCollectionEndpoint(TestCase):
    """
    Test the jobs/ collection endpoint (ims.v2.resources.jobs.JobsCollection)
    """

    @classmethod
    def setUpClass(cls):
        cls.stubber = Stubber(app.app.s3)

    def setUp(self):
        super(TestV2JobsCollectionEndpoint, self).setUp()
        self.test_uri = '/jobs'
        self.app = self.useFixture(V2FlaskTestClientFixture()).client
        self.test_recipe_id = str(uuid.uuid4())
        self.test_image_id = str(uuid.uuid4())
        self.test_public_key_id = str(uuid.uuid4())
        self.today = datetime.datetime.now().replace(microsecond=0)
        self.week_ago = self.today - datetime.timedelta(days=7)
        self.recipe_data = {
            'recipe_type': 'kiwi-ng',
            'linux_distribution': 'sles12',
            'name': 'cray_sles12sp3_barebones',
            'link': {
                'path': 's3://ims/{}/recipe.tgz'.format(self.test_recipe_id),
                'etag': self.getUniqueString(self.test_recipe_id),
                'type': 's3'
            },
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_recipe_id,
        }
        self.image_data = {
            'name': 'cray_sles12sp3_barebones',
            'link': {
                'path': 's3://ims/{}/manifest.json'.format(self.test_image_id),
                'etag': self.getUniqueString(),
                'type': 's3'
            },
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_image_id,
        }
        self.job_data = {
            'job_type': "create",
            'status': 'success',
            'artifact_id': str(uuid.uuid4()),
            'public_key_id': self.test_public_key_id,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
            'created': self.week_ago.isoformat(),
            'id': str(uuid.uuid4()),
        }
        self.public_key_data = {
            'name': str(uuid.uuid4()),
            'public_key': str(uuid.uuid4()),
            'created': datetime.datetime.now().replace(microsecond=0).isoformat(),
            'id': self.test_public_key_id,
        }
        self.manifest_rootfs_mime_type = "application/vnd.cray.image.rootfs.squashfs"
        self.manifest_initrd_mime_type = "application/vnd.cray.image.initrd"
        self.manifest_kernel_mime_type = "application/vnd.cray.image.kernel"
        self.s3_manifest_data = {
            "version": "1.0",
            "created": "2020-01-14 03:17:14",
            "artifacts": [
                {
                    "link": {
                        "path": "s3://boot-artifacts/F6C1CC79-9A5B-42B6-AD3F-E7EFCF22CAE8/rootfs",
                        "etag": self.getUniqueString(),
                        "type": "s3"
                    },
                    "type": self.manifest_rootfs_mime_type,
                    "md5": self.getUniqueString()
                },
                {
                    "link": {
                        "path": "s3://boot-artifacts/F6C1CC79-9A5B-42B6-AD3F-E7EFCF22CAE8/initrd",
                        "etag": self.getUniqueString(),
                        "type": "s3"
                    },
                    "type": self.manifest_initrd_mime_type,
                    "md5": self.getUniqueString()
                },
                {
                    "link": {
                        "path": "s3://boot-artifacts/F6C1CC79-9A5B-42B6-AD3F-E7EFCF22CAE8/kernel",
                        "etag": self.getUniqueString(),
                        "type": "s3"
                    },
                    "type": self.manifest_kernel_mime_type,
                    "md5": self.getUniqueString()
                }
            ]
        }
        self.test_jobs = self.useFixture(V2JobsDataFixture(initial_data=self.job_data)).datastore
        self.test_public_keys = self.useFixture(V2PublicKeysDataFixture(initial_data=self.public_key_data)).datastore
        self.recipes = self.useFixture(V2RecipesDataFixture(initial_data=self.recipe_data)).datastore
        self.images = self.useFixture(V2ImagesDataFixture(initial_data=self.image_data)).datastore
        self.test_domain = 'https://api-gw-service-nmn.local'

    def test_delete_jobs_all(self, utils_mock, config_mock, client_mock):
        response = self.app.delete(self.test_uri)
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(0), 'collection was not empty')

    def test_delete_jobs_age_2wks(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?age=2w")
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(1), 'collection should have 1 entry')

    def test_delete_jobs_age_3days(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?age=3d")
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(0), 'collection should be empty')

    def test_delete_jobs_status_error(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?status=error")
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(1), 'collection should have 1 entry')

    def test_delete_jobs_status_success(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?status=success")
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(0), 'collection should be empty')

    def test_delete_jobs_status_invalid(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?status=invalid")
        self.assertEqual(response.status_code, 400, 'status code was not 400')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(1), 'collection should have 1 entry')

    def test_delete_jobs_type_customize(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?job_type=customize")
        response = self.app.delete("/jobs?job_type=customize")
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(1), 'collection should have 1 entry')

    def test_delete_jobs_type_create(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?job_type=create")
        self.assertEqual(response.status_code, 204, 'status code was not 204')
        self.assertEqual(response.data, b'', 'resource returned was not empty')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(0), 'collection should be empty')

    def test_delete_jobs_type_invalid(self, utils_mock, config_mock, client_mock):

        response = self.app.delete("/jobs?job_type=invalid")
        self.assertEqual(response.status_code, 400, 'status code was not 400')

        # verify that all the jobs were deleted
        response = self.app.get(self.test_uri)
        self.assertThat(json.loads(response.data), HasLength(1), 'collection should have 1 entry')

    def test_get(self, utils_mock, config_mock, client_mock):
        """ Test happy path GET """
        response = self.app.get(self.test_uri)
        self.assertEqual(response.status_code, 200, 'status code was not 200')
        self.assertThat(json.loads(response.data), HasLength(1), 'collection did not have an entry')
        response_data = json.loads(response.data)[0]
        for key in self.job_data:
            if key == 'created':
                # microseconds don't always match up
                self.assertAlmostEqual(datetime.datetime.strptime(self.job_data[key],
                                                                  '%Y-%m-%dT%H:%M:%S'),
                                       datetime.datetime.strptime(response_data['created'],
                                                                  '%Y-%m-%dT%H:%M:%S+00:00'),
                                       delta=datetime.timedelta(seconds=5))
            else:
                self.assertEqual(response_data[key], self.job_data[key])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_enable_debug_false(self, s3_mock, mock_open, utils_mock, config_mock, client_mock):
        """ Test happy path POST """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        s3url = S3Url(self.recipe_data['link']['path'])
        expected_params = {'Bucket': s3url.bucket, 'Key': s3url.key}
        self.stubber.add_response('head_object', {"ETag": self.recipe_data['link']["etag"]}, expected_params)

        s3_mock.return_value = "http://localhost/path/to/file_abc.tgz"

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['job_type'], input_job_type, 'job_type was not set properly')
        self.assertEqual(response_data['artifact_id'], input_artifact_id, 'artifact_id was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNone(response_data['ssh_containers'], 'ssh_containers not null')
        self.assertIsNotNone(response_data['created'], 'job creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'job_type', 'artifact_id', 'build_env_size', 'id', 'enable_debug',
                               'public_key_id', 'kubernetes_job', 'kubernetes_service', 'kubernetes_configmap',
                               'ssh_containers', 'status', 'image_root_archive_name', 'initrd_file_name',
                               'kernel_file_name', 'resultant_image_id', 'kubernetes_namespace',
                               'kernel_parameters_file_name'],
                              'returned keys not the same')

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_enable_debug_true(self, s3_mock, mock_open, utils_mock, config_mock, client_mock):

        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id
        debug_ssh_container_name = 'debug'
        debug_ssh_container_jail = False

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': True,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        s3url = S3Url(self.recipe_data['link']['path'])
        expected_params = {'Bucket': s3url.bucket, 'Key': s3url.key}
        self.stubber.add_response('head_object', {"ETag": self.recipe_data['link']["etag"]}, expected_params)

        s3_mock.return_value = "http://localhost/path/to/file_abc.tgz"

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['job_type'], input_job_type, 'job_type was not set properly')
        self.assertEqual(response_data['artifact_id'], input_artifact_id, 'artifact_id was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['ssh_containers'], 'ssh_containers not null')

        external_host_name = "{}.ims.cmn.shasta.local".format(response_data['id'])
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['customer_access']['host'],
                         external_host_name, 'SSH Container host value did not match expected value')
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['customer_access']['port'], 22,
                         'SSH Container host value did not match expected value')

        cluster_local_host_name = \
            "{r[kubernetes_service]}.{r[kubernetes_namespace]}.svc.cluster.local".format(r=response_data)
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['cluster.local']['host'],
                         cluster_local_host_name, 'SSH Container host value did not match expected value')
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['cluster.local']['port'], 22,
                         'SSH Container host value did not match expected value')

        self.assertEqual(response_data['ssh_containers'][0]['name'], debug_ssh_container_name,
                         'SSH Container name value did not match')
        self.assertEqual(response_data['ssh_containers'][0]['jail'], debug_ssh_container_jail,
                         'SSH Container jail value did not match')
        self.assertIsNotNone(response_data['created'], 'job creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'job_type', 'artifact_id', 'build_env_size', 'id', 'enable_debug',
                               'public_key_id', 'kubernetes_job', 'kubernetes_service', 'kubernetes_configmap',
                               'ssh_containers', 'status', 'image_root_archive_name', 'initrd_file_name',
                               'kernel_file_name', 'resultant_image_id', 'kubernetes_namespace',
                               'kernel_parameters_file_name'],
                              'returned keys not the same')

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_ims_job_namespace(self, s3_mock, mock_open, utils_mock, config_mock, client_mock):
        """ Test happy path POST """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id
        job_namespace = self.getUniqueString()

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        s3url = S3Url(self.recipe_data['link']['path'])
        expected_params = {'Bucket': s3url.bucket, 'Key': s3url.key}
        self.stubber.add_response('head_object', {"ETag": self.recipe_data['link']["etag"]}, expected_params)

        s3_mock.return_value = "http://localhost/path/to/file_abc.tgz"

        with mock.patch.dict('os.environ', {'DEFAULT_IMS_JOB_NAMESPACE': job_namespace}):
            self.stubber.activate()
            response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
            self.stubber.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['job_type'], input_job_type, 'job_type was not set properly')
        self.assertEqual(response_data['artifact_id'], input_artifact_id, 'artifact_id was not set properly')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNone(response_data['ssh_containers'], 'ssh_containers not null')
        self.assertIsNotNone(response_data['created'], 'job creation date/time was not set properly')
        self.assertEqual(response_data['kubernetes_namespace'], job_namespace,
                         "kubernetes_namespace was not set properly")
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'job_type', 'artifact_id', 'build_env_size', 'id', 'enable_debug',
                               'public_key_id', 'kubernetes_job', 'kubernetes_service', 'kubernetes_configmap',
                               'ssh_containers', 'status', 'image_root_archive_name', 'initrd_file_name',
                               'kernel_file_name', 'resultant_image_id', 'kubernetes_namespace',
                               'kernel_parameters_file_name'],
                              'returned keys not the same')

    def test_post_create_with_ssh_container(self, utils_mock, config_mock, client_mock):
        """ Test create with ssh_container """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
            'ssh_containers': [
                {'name': 'post-build', 'jail': False}
            ]
        }

        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.assertEqual(response.status_code, 400, 'status code was not 400')

    @responses.activate
    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_customize_with_out_ssh_container(self, s3_mock, mock_open, utils_mock, config_mock, client_mock):
        """ Test happy path POST without a ssh_container """
        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id
        default_ssh_container_name = "customize"
        default_ssh_container_jail = False

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        manifest_s3_info = S3Url(self.image_data["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        self.stubber.add_response(
            'head_object',
            {"ETag": self.image_data["link"]["etag"]},
            manifest_expected_params
        )

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        rootfs_manifest_info = [artifact for artifact in self.s3_manifest_data["artifacts"]
                                if artifact["type"].startswith(self.manifest_rootfs_mime_type)]
        self.assertEqual(len(rootfs_manifest_info), 1)

        rootfs_s3_info = S3Url(rootfs_manifest_info[0]["link"]["path"])
        self.stubber.add_response(
            'head_object',
            {"ETag": rootfs_manifest_info[0]["link"]["etag"]},
            {'Bucket': rootfs_s3_info.bucket, 'Key': rootfs_s3_info.key}
        )

        s3_mock.return_value = "http://localhost/path/to/file_abc.tgz"

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['job_type'], input_job_type, 'job_type was not set properly')
        self.assertEqual(response_data['artifact_id'], input_artifact_id, 'artifact_id was not set properly')
        self.assertIsNotNone(response_data['ssh_containers'], 'ssh_containers not null')
        self.assertEqual(response_data['ssh_containers'][0]['name'], default_ssh_container_name,
                         'SSH Container name value did not match')
        self.assertEqual(response_data['ssh_containers'][0]['jail'], default_ssh_container_jail,
                         'SSH Container jail value did not match')
        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'job creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'job_type', 'artifact_id', 'build_env_size', 'id', 'enable_debug',
                               'public_key_id', 'kubernetes_job', 'kubernetes_service', 'kubernetes_configmap',
                               'ssh_containers', 'status', 'image_root_archive_name', 'initrd_file_name',
                               'kernel_file_name', 'resultant_image_id', 'kubernetes_namespace',
                               'kernel_parameters_file_name'],
                              'returned keys not the same')

    @responses.activate
    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_customize_with_ssh_container(self, s3_mock, mock_open, utils_mock, config_mock, client_mock):
        """ Test happy path POST with one ssh_container """
        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id
        ssh_container_name = "my-ssh-jail"
        ssh_container_jail = True

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
            'ssh_containers': [
                {'name': ssh_container_name, 'jail': ssh_container_jail}
            ]
        }

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        raw_stream = StreamingBody(
            io.BytesIO(s3_manifest_json),
            len(s3_manifest_json)
        )

        manifest_s3_info = S3Url(self.image_data["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        self.stubber.add_response(
            'head_object',
            {"ETag": self.image_data["link"]["etag"]},
            manifest_expected_params
        )

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        rootfs_manifest_info = [artifact for artifact in self.s3_manifest_data["artifacts"]
                                if artifact["type"].startswith(self.manifest_rootfs_mime_type)]
        self.assertEqual(len(rootfs_manifest_info), 1)

        rootfs_s3_info = S3Url(rootfs_manifest_info[0]["link"]["path"])
        self.stubber.add_response(
            'head_object',
            {
                "ETag": rootfs_manifest_info[0]["link"]["etag"],
                "Metadata": {
                    "md5sum": rootfs_manifest_info[0]["md5"]
                }
            },
            {'Bucket': rootfs_s3_info.bucket, 'Key': rootfs_s3_info.key}
        )

        s3_mock.return_value = "http://localhost/path/to/file_abc.tgz"

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 201, 'status code was not 201')
        self.assertEqual(response_data['job_type'], input_job_type, 'job_type was not set properly')
        self.assertEqual(response_data['artifact_id'], input_artifact_id, 'artifact_id was not set properly')
        self.assertEqual(response_data['ssh_containers'][0]['name'], ssh_container_name,
                         'SSH Container name value did not match')
        self.assertEqual(response_data['ssh_containers'][0]['jail'], ssh_container_jail,
                         'SSH Container jail value did not match')

        external_host_name = "{}.ims.cmn.shasta.local".format(response_data['id'])
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['customer_access']['host'],
                         external_host_name, 'SSH Container host value did not match expected value')
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['customer_access']['port'], 22,
                         'SSH Container host value did not match expected value')

        cluster_local_host_name = \
            "{r[kubernetes_service]}.{r[kubernetes_namespace]}.svc.cluster.local".format(r=response_data)
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['cluster.local']['host'],
                         cluster_local_host_name, 'SSH Container host value did not match expected value')
        self.assertEqual(response_data['ssh_containers'][0]['connection_info']['cluster.local']['port'], 22,
                         'SSH Container host value did not match expected value')

        self.assertRegex(response_data['id'],
                         r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
        self.assertIsNotNone(response_data['created'], 'job creation date/time was not set properly')
        self.assertItemsEqual(response_data.keys(),
                              ['created', 'job_type', 'artifact_id', 'build_env_size', 'id', 'enable_debug',
                               'public_key_id', 'kubernetes_job', 'kubernetes_service', 'kubernetes_configmap',
                               'ssh_containers', 'status', 'image_root_archive_name', 'initrd_file_name',
                               'kernel_file_name', 'resultant_image_id', 'kubernetes_namespace',
                               'kernel_parameters_file_name'],
                              'returned keys not the same')

    def test_post_create_with_multiple_ssh_containers(self, utils_mock, config_mock, client_mock):
        """ Post Job Create with multiple ssh_containers requested """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
            'ssh_containers': [
                {'name': 'pre-cfs', 'jail': False},
                {'name': 'cfs', 'jail': True},
                {'name': 'post-cfs', 'jail': False},
            ]
        }

        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        response_data = json.loads(response.data)
        self.assertEqual(response.status_code, 400, 'status code was not 400')

    def test_post_400_no_input(self, utils_mock, config_mock, client_mock):
        """ Test a POST request with no input provided by the client """
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps({}))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    def test_post_422_missing_inputs(self, utils_mock, config_mock, client_mock):
        """ Test a POST request with missing data provided by the client """
        input_data = {'job_type': self.getUniqueString()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'artifact_id': str(uuid.uuid4())}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_improper_type_inputs(self, utils_mock, config_mock, client_mock):
        """ Test a POST request with invalid data provided by the client (bad types) """
        input_data = {'job_type': self.getUniqueInteger(), 'artifact_id': str(uuid.uuid4())}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

        input_data = {'job_type': self.getUniqueString(), 'artifact_id': self.getUniqueInteger()}
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    def test_post_422_unknown_field(self, utils_mock, config_mock, client_mock):
        """ Test a POST request with a field that is not valid for the request """
        input_job_type = self.getUniqueString()
        input_artifact_id = str(uuid.uuid4())
        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'invalid_field': str(uuid.uuid4())  # invalid
        }
        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_422_missing_image_root_archive_name(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where image_root_archive_name is missing """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            # 'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("image_root_archive_name", response.json["errors"],
                      "Expected image_root_archive_name to be listed in error detail")

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_422_image_root_archive_name_is_blank(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where image_root_archive_name is blank """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': "",
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("image_root_archive_name", response.json["errors"],
                      "Expected image_root_archive_name to be listed in error detail")

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_422_kernel_file_name_is_blank(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where kernel_file_name is blank """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': "",
            'initrd_file_name': self.getUniqueString(),
        }

        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("kernel_file_name", response.json["errors"],
                      "Expected kernel_file_name to be listed in error detail")

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_422_initrd_file_name_is_blank(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where initrd_file_name is blank """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': "",
        }

        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("initrd_file_name", response.json["errors"],
                      "Expected initrd_file_name to be listed in error detail")

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_422_invalid_job_type(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where job type is invalid """
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': self.getUniqueString(),
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': "",
        }

        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 422, ['status', 'title', 'detail', 'errors'])
        self.assertIn("job_type", response.json["errors"],
                      "Expected job_type to be listed in error detail")

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_400_invalid_create_artifact_id(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where the artifact_id is invalid for create case """
        input_job_type = "create"
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': str(uuid.uuid4()),
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        response = self.app.post(self.test_uri, content_type='application/json', data=json.dumps(input_data))
        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_422_create_artifact_not_in_s3(self, s3_mock, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where the S3 recipe is not in S3 """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        self.stubber.add_client_error('head_object')

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 422, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_422_customize_manifest_not_in_s3(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where the manifest.json is not in s3  """

        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        self.stubber.add_client_error('head_object')

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 422, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_400_customize_manifest_does_not_have_rootfs(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where the manifest.json does not list a rootfs object  """

        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        manifest_s3_info = S3Url(self.image_data["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        self.stubber.add_response(
            'head_object',
            {"ETag": self.image_data["link"]["etag"]},
            manifest_expected_params
        )

        s3_manifest_data_no_rootfs = {
            "version": "1.0",
            "created": "2020-01-14 03:17:14",
            "artifacts": [
                {
                    "link": {
                        "path": "s3://boot-artifacts/F6C1CC79-9A5B-42B6-AD3F-E7EFCF22CAE8/kernel",
                        "etag": self.getUniqueString(),
                        "type": "s3"
                    },
                    "type": self.manifest_kernel_mime_type,
                    "md5": self.getUniqueString()
                }
            ]
        }

        s3_manifest_json_no_rootfs = json.dumps(s3_manifest_data_no_rootfs).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json_no_rootfs), len(s3_manifest_json_no_rootfs)),
                'ContentLength': len(s3_manifest_json_no_rootfs)
            },
            manifest_expected_params
        )

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_400_customize_manifest_bad_version(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where the manifest.json has an unknown version  """

        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        manifest_s3_info = S3Url(self.image_data["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        self.stubber.add_response(
            'head_object',
            {"ETag": self.image_data["link"]["etag"]},
            manifest_expected_params
        )

        s3_manifest_data_bad_version = {
            "version": "42.0"
        }

        s3_manifest_json_bad_version = json.dumps(s3_manifest_data_bad_version).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json_bad_version), len(s3_manifest_json_bad_version)),
                'ContentLength': len(s3_manifest_json_bad_version)
            },
            manifest_expected_params
        )

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_400_customize_manifest_no_version(self, mock_open, utils_mock, config_mock, client_mock):

        """ Test case where the manifest.json does not have a version  """
        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        manifest_s3_info = S3Url(self.image_data["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        self.stubber.add_response(
            'head_object',
            {"ETag": self.image_data["link"]["etag"]},
            manifest_expected_params
        )

        s3_manifest_data_no_version = {
            "foo": "bar"
        }

        s3_manifest_json_no_version = json.dumps(s3_manifest_data_no_version).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json_no_version), len(s3_manifest_json_no_version)),
                'ContentLength': len(s3_manifest_json_no_version)
            },
            manifest_expected_params
        )

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    def test_post_422_customize_rootfs_not_in_s3(self, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where the rootfs object is not in s3 """

        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        manifest_s3_info = S3Url(self.image_data["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        self.stubber.add_response(
            'head_object',
            {"ETag": self.image_data["link"]["etag"]},
            manifest_expected_params
        )

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        self.stubber.add_client_error('head_object')

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 422, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_400_customize_cannot_create_presigned_url(self, s3_mock, mock_open, utils_mock,
                                                            config_mock, client_mock):
        """ Test case where we cannot generate a presigned url  """
        input_job_type = "customize"
        input_artifact_id = self.test_image_id
        public_key_id = self.test_public_key_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': public_key_id,
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        manifest_s3_info = S3Url(self.image_data["link"]["path"])
        manifest_expected_params = {'Bucket': manifest_s3_info.bucket, 'Key': manifest_s3_info.key}

        self.stubber.add_response(
            'head_object',
            {"ETag": self.image_data["link"]["etag"]},
            manifest_expected_params
        )

        s3_manifest_json = json.dumps(self.s3_manifest_data).encode()
        self.stubber.add_response(
            'get_object',
            {
                'Body': StreamingBody(io.BytesIO(s3_manifest_json), len(s3_manifest_json)),
                'ContentLength': len(s3_manifest_json)
            },
            manifest_expected_params
        )

        rootfs_manifest_info = [artifact for artifact in self.s3_manifest_data["artifacts"]
                                if artifact["type"].startswith(self.manifest_rootfs_mime_type)]
        self.assertEqual(len(rootfs_manifest_info), 1)

        rootfs_s3_info = S3Url(rootfs_manifest_info[0]["link"]["path"])
        self.stubber.add_response(
            'head_object',
            {"ETag": rootfs_manifest_info[0]["link"]["etag"]},
            {'Bucket': rootfs_s3_info.bucket, 'Key': rootfs_s3_info.key}
        )

        parsed_response = {'Error': {'Code': '500', 'Message': 'Error'}}
        s3_mock.side_effect = ClientError(parsed_response, "generate_presigned_url")

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 400, ['status', 'title', 'detail'])

    @mock.patch("src.server.v2.resources.jobs.open", new_callable=mock.mock_open,
                read_data='{"metadata":{"name":"foo"}}')
    @mock.patch("src.server.app.app.s3.generate_presigned_url")
    def test_post_400_public_key_invalid(self, s3_mock, mock_open, utils_mock, config_mock, client_mock):
        """ Test case where the public-key does not exist in IMS """
        input_job_type = "create"
        input_artifact_id = self.test_recipe_id

        input_data = {
            'job_type': input_job_type,
            'artifact_id': input_artifact_id,
            'public_key_id': str(uuid.uuid4()),
            'enable_debug': False,
            'image_root_archive_name': self.getUniqueString(),
            'kernel_file_name': self.getUniqueString(),
            'initrd_file_name': self.getUniqueString(),
        }

        s3url = S3Url(self.recipe_data['link']['path'])
        expected_params = {'Bucket': s3url.bucket, 'Key': s3url.key}
        self.stubber.add_response('head_object', {"ETag": self.recipe_data['link']["etag"]}, expected_params)

        s3_mock.return_value = "http://localhost/path/to/file_abc.tgz"

        self.stubber.activate()
        response = self.app.post('/jobs', content_type='application/json', data=json.dumps(input_data))
        self.stubber.deactivate()

        check_error_responses(self, response, 400, ['status', 'title', 'detail'])


if __name__ == '__main__':
    unittest.main()
