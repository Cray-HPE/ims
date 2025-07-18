#
# MIT License
#
# (C) Copyright 2020-2025 Hewlett Packard Enterprise Development LP
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
Jobs API
"""
import datetime
import http.client
import json
import os
import re
import tempfile
import time
from collections import OrderedDict
from functools import partial
from string import Template

import yaml
from flask import current_app, jsonify, request
from flask_restful import Resource
from kubernetes.client.rest import ApiException

from kubernetes import client, config, utils
from src.server.errors import (generate_data_validation_failure,
                               generate_missing_input_response,
                               generate_resource_not_found_response,
                               problemify)
from src.server.helper import (ARCH_ARM64, ARCH_X86_64, ARTIFACT_LINK,
                               IMAGE_MANIFEST_ARTIFACT_TYPE,
                               IMAGE_MANIFEST_ARTIFACT_TYPE_SQUASHFS,
                               IMAGE_MANIFEST_ARTIFACTS,
                               IMAGE_MANIFEST_VERSION,
                               IMAGE_MANIFEST_VERSION_1_0, get_download_url,
                               get_log_id, read_manifest_json,
                               validate_artifact)
from src.server.ims_exceptions import ImsArtifactValidationException
from src.server.models.jobs import (ARCH_TO_KERNEL_FILE_NAME, JOB_STATUS_ERROR,
                                    JOB_STATUS_SUCCESS, JOB_TYPE_CREATE,
                                    JOB_TYPE_CUSTOMIZE, JOB_TYPES,
                                    KERNEL_FILE_NAME_X86, STATUS_TYPES,
                                    V2JobRecordInputSchema,
                                    V2JobRecordPatchSchema, V2JobRecordSchema)
from src.server.models.remote_build_nodes import V3RemoteBuildNodeRecord
from src.server.models.jobs import V2JobRecordSchema, find_remote_node_for_job
from flask import Flask

job_user_input_schema = V2JobRecordInputSchema()
job_patch_input_schema = V2JobRecordPatchSchema()
job_schema = V2JobRecordSchema()

class V3BaseJobResource(Resource):
    """
    Shared class representing either a collection or a specific job resource.
    """

    def __init__(self):
        # noinspection PyBroadException
        try:
            config.load_incluster_config()
        except Exception:  # pylint: disable=broad-except
            pass

        self.k8scrds = client.CustomObjectsApi(client.ApiClient())

        self.ISTIO_RESOURCE_VERSION = 'v1beta1'
        self.ISTIO_RESOURCE_GROUP = 'networking.istio.io'
        self.ISTIO_RESOURCE_DESTINATION_RULE = 'DestinationRule'
        self.ISTIO_RESOURCE_DESTINATION_RULES = 'destinationrules'

        self.api_gateway_hostname = os.environ.get("API_GATEWAY_HOSTNAME", "api-gw-service-nmn.local")
        self.default_ims_job_namespace = os.environ.get("DEFAULT_IMS_JOB_NAMESPACE", "ims")

        self.job_customer_access_network_access_pool = os.environ.get(
            "JOB_CUSTOMER_ACCESS_NETWORK_ACCESS_POOL", "customer-management")

        # {job.id}.ims.{job_customer_access_subnet_name}.{self.job_customer_access_network_domain}"
        self.job_customer_access_subnet_name = os.environ.get("JOB_CUSTOMER_ACCESS_SUBNET_NAME", "cmn")
        self.job_customer_access_network_domain = os.environ.get("JOB_CUSTOMER_ACCESS_NETWORK_DOMAIN", "shasta.local")
        self.job_enable_dkms = os.getenv("JOB_ENABLE_DKMS", 'True').lower() in ('true', '1', 't')
        
        # NOTE: make sure this isn't a non-zero length string of spaces
        self.job_kata_runtime = os.getenv("JOB_KATA_RUNTIME", "kata-qemu").strip()
        self.job_aarch64_runtime = os.getenv("JOB_AARCH64_RUNTIME", "kata-qemu").strip()

    def _create_namespaced_destination_rule(self, namespace):
        """ Helper routine to create a partial function to create a new ISTIO destination rule. """
        return partial(
            self.k8scrds.create_namespaced_custom_object,
            self.ISTIO_RESOURCE_GROUP, self.ISTIO_RESOURCE_VERSION, namespace, self.ISTIO_RESOURCE_DESTINATION_RULES
        )

    def _delete_namespaced_destination_rule(self, namespace):
        """ Helper routine to create a partial function to delete an ISTIO destination rule. """
        return partial(
            self.k8scrds.delete_namespaced_custom_object,
            self.ISTIO_RESOURCE_GROUP, self.ISTIO_RESOURCE_VERSION, namespace, self.ISTIO_RESOURCE_DESTINATION_RULES
        )

    def _create_istio_destination_rule_for_job(self, log_id, job):
        """ Create a DestinationRule to enable communication with the job pod from inside the kubernetes network """
        current_app.logger.info("%s ++ jobs.v3._create_istio_destination_rule_for_job", log_id)

        name = job.kubernetes_service
        namespace = job.kubernetes_namespace
        body = {
            'apiVersion': '{}/{}'.format(self.ISTIO_RESOURCE_GROUP, self.ISTIO_RESOURCE_VERSION),
            'kind': self.ISTIO_RESOURCE_DESTINATION_RULE,
            'metadata': {
                'name': name,
                'namespace': namespace
            },
            'spec': {
                'host': '{job.kubernetes_service}.{job.kubernetes_namespace}.svc.cluster.local'.format(job=job),
                'trafficPolicy': {
                    'tls': {
                        'mode': "DISABLE",
                    },
                }
            }
        }

        current_app.logger.info("%s body = %s", log_id, str(body))

        try:
            api_response = self._create_namespaced_destination_rule(namespace)(body)
            current_app.logger.debug('%s %s "%s" resource: %s', log_id, self.ISTIO_RESOURCE_DESTINATION_RULE, name,
                                     api_response)
        except ApiException as e:
            current_app.logger.warning(
                '%s Exception when calling CustomObjectsApi->create_namespaced_custom_object', log_id, exc_info=True
            )
            raise e

        return api_response

    def _delete_istio_destination_rule_for_job(self, log_id, job):
        """ Delete a ConfigFrameworkSession """

        current_app.logger.info("%s ++ jobs.v3._delete_istio_destination_rule_for_job", log_id)
        name = job.kubernetes_service
        namespace = job.kubernetes_namespace
        body = client.V1DeleteOptions(propagation_policy='Background')

        api_response = self._delete_namespaced_destination_rule(namespace)(name, body=body)
        current_app.logger.debug('%s %s "%s" resource: %s', log_id, self.ISTIO_RESOURCE_DESTINATION_RULE,
                                 name, api_response)

        return api_response

    def create_kubernetes_resources(self, log_id, new_job, template_params, recipe_type):
        """
        Create kubernetes resources (configmap, service, job, pvc, and destination_rule) for the current job
        """

        # Create the resources defined in template files
        k8s_client = client.ApiClient()
        new_job.kubernetes_namespace = self.default_ims_job_namespace
        job_template_path = os.environ.get("IMS_JOB_TEMPLATE_PATH", "/mnt/ims/v2/job_templates")
        for resource in ("configmap", "service", "job", "pvc"):
            resource_field = "kubernetes_%s" % resource
            fd, output_file_name = tempfile.mkstemp(suffix=".yaml")
            try:
                if new_job.job_type == JOB_TYPE_CREATE:
                    input_file_name = os.path.join(
                        job_template_path, f"create/{recipe_type}/image_{resource}_create.yaml.template"
                    )
                elif new_job.job_type == JOB_TYPE_CUSTOMIZE:
                    input_file_name = os.path.join(
                        job_template_path, f"customize/image_{resource}_customize.yaml.template"
                    )

                with open(input_file_name, 'r') as inf, open(output_file_name, 'w') as outf:
                    template_data = Template(inf.read()).substitute(template_params)
                    setattr(new_job, resource_field, yaml.safe_load(template_data)["metadata"]["name"])
                    outf.write(template_data)

                current_app.logger.debug("%s Creating k8s %s resource %s",
                                         log_id, resource, getattr(new_job, resource_field))

                retry_max = 3
                retry_count = 0
                while True:
                    try:
                        utils.create_from_yaml(k8s_client, output_file_name)
                        break
                    except ApiException as api_exception:
                        if retry_count < retry_max and "timeout" in api_exception.reason.lower():
                            retry_count += 1
                            time.sleep(retry_count)
                            current_app.logger.warning("%s Timeout error creating k8s %s resource %s. Retrying: %s",
                                                       log_id, resource, getattr(new_job, resource_field),
                                                       api_exception)
                        else:
                            current_app.logger.warning("%s Timeout error creating k8s %s resource %s: %s",
                                                       log_id, resource, getattr(new_job, resource_field),
                                                       api_exception)
                            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                                    detail='A timeout was encountered creating the kubernetes %s '
                                                           'resources for your IMS job. Review the errors, take any '
                                                           'corrective action and then re-run the request with valid '
                                                           'information.' % resource)
                    except Exception as exception:  # pylint: disable=broad-except
                        current_app.logger.warning("%s Error encountered creating k8s %s resource %s: %s",
                                                   log_id, resource, getattr(new_job, resource_field), exception)
                        return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                                detail='An error was encountered creating the kubernetes %s resources '
                                                       'for your IMS job. Review the errors, take any corrective '
                                                       'action and then re-run the request with valid '
                                                       'information.' % resource)
            finally:
                os.close(fd)
                os.remove(output_file_name)

        # Create the istio rule for this job
        try:
            self._create_istio_destination_rule_for_job(log_id, new_job)
        except ApiException as api_exception:
            current_app.logger.warning("%s Error encountered creating istio DestinationRule %s",
                                       log_id, new_job.kubernetes_job, exc_info=api_exception)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered creating the kubernetes DestinationRule '
                                           'resources for your IMS job. Review the errors, take any corrective '
                                           'action and then re-run the request with valid information.')

        # Copy the DST signing keys secret from the 'services' namespace for this job
        self._copy_signing_keys_secret(log_id, new_job)
        return new_job, None

    def _copy_signing_keys_secret(self, log_id, job) :
        """Copy the signing keys secret to the job namespace if it exists. """
        k8s_client = client.ApiClient()
        k8s_v1api = client.CoreV1Api(k8s_client)
        secret_name = "hpe-signing-key"
        job_secret_name = "cray-ims-" + str(job.id) + "-signing-keys"

        # Copy the signing keys secret to the job namespace
        try:
            # Read the secret from the services namespace
            secret = k8s_v1api.read_namespaced_secret(secret_name, "services")

            # modify the secret to copy back into the ims namespace
            secret.metadata.namespace = job.kubernetes_namespace
            secret.metadata.name = job_secret_name
            secret.metadata.resource_version = None  # reset the resource version so it can be created
            secret.metadata.uid = None  # reset the uid so it can be created
            secret.metadata.creation_timestamp = None  # reset the creation timestamp so it can be created

            # Create the secret in the job namespace
            k8s_v1api.create_namespaced_secret(namespace=job.kubernetes_namespace, body=secret)
            job.kubernetes_secret = job_secret_name

        except client.ApiException as e:
            current_app.logger.error("%s Error reading signing keys secret %s from namespace services: %s",
                                     log_id, secret_name, e)

    def delete_kubernetes_resources(self, log_id, job, delete_job=True):
        """ Delete the underlying kubernetes resources that are created for the create/customize job workflow """
        errors = []
        retval = True

        k8s_client = client.ApiClient()
        k8s_v1api = client.CoreV1Api(k8s_client)
        k8s_batchv1api = client.BatchV1Api(k8s_client)

        namespace = job.kubernetes_namespace or self.default_ims_job_namespace
        k8s_delete_options = client.V1DeleteOptions()
        k8s_delete_options.propagation_policy = "Background"

        resources = OrderedDict()
        resources['service'] = k8s_v1api.delete_namespaced_service
        if delete_job:
            resources['job'] = k8s_batchv1api.delete_namespaced_job
            resources['configmap'] = k8s_v1api.delete_namespaced_config_map
            resources['pvc'] = k8s_v1api.delete_namespaced_persistent_volume_claim
            resources['secret'] = k8s_v1api.delete_namespaced_secret

        # Delete the underlying kubernetes resources
        for resource, delete_fn in resources.items():
            # PVCs were added to the job in v2.2 of the schema - they may not exist
            # for jobs created before an upgrade.
            name = getattr(job, "kubernetes_%s" % resource)
            if name != None and len(name) > 0:
                current_app.logger.info(f"{log_id} Deleting k8s {resource} {name}.")
            else:
                current_app.logger.info(f"{log_id} k8s resource does not exist for job {resource}.")
                continue

            try:
                delete_fn(body=k8s_delete_options, namespace=namespace, name=name)
            except ApiException as api_exception:
                if api_exception.reason == "Not Found":
                    current_app.logger.info("%s K8s %s %s was not found to delete.",
                                               log_id, resource, name)
                else:
                    current_app.logger.error("%s Received APIException deleting k8s %s %s. %s",
                                             log_id, resource, name, api_exception)
                    errors.append(str(api_exception))
                    retval = False
            except Exception as exception:  # pylint: disable=W0703
                current_app.logger.error("%s Received Exception deleting k8s %s %s. %s",
                                         log_id, resource, name, exception)
                errors.append(str(exception))
                retval = False

        # Delete Istio DestinationRule
        try:
            self._delete_istio_destination_rule_for_job(log_id, job)
        except ApiException as api_exception:
            if api_exception.reason == "Not Found":
                current_app.logger.info("%s K8s DestinationRule %s was not found to delete.",
                                           log_id, job.kubernetes_job)
            else:
                current_app.logger.error("%s Error encountered deleting istio DestinationRule %s",
                                         log_id, job.kubernetes_job, exc_info=True)
                errors.append(str(api_exception))
                retval = False
        except Exception as exception:  # pylint: disable=W0703
            current_app.logger.error("%s Received Exception deleting k8s DestinationRule.",
                                     log_id, exc_info=True)
            errors.append(str(exception))
            retval = False

        return retval, errors

    @staticmethod
    def _age_to_timestamp(age):
        """
        Utility function used to calculate a python datetime object that can be used
        to compare against the created/deleted timestamps of IMS records.
        """

        delta = {}
        for interval in ['weeks', 'days', 'hours', 'minutes']:
            result = re.search(r'(\d+)\w*{}'.format(interval[0]), age, re.IGNORECASE)
            if result:
                delta[interval] = int(result.groups()[0])
        delta = datetime.timedelta(**delta)
        return datetime.datetime.now() - delta


class V3JobCollection(V3BaseJobResource):
    """
    Class representing the operations that can be taken on a collection of jobs
    """

    def get(self):
        """ retrieve a list/collection of jobs """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v3.GET", log_id)
        return_json = job_schema.dump(iter(current_app.data["jobs"].values()), many=True)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    @staticmethod
    def retrieve_artifact_record(job_type, log_id, artifact_id):
        """
        Utility function to get an IMS artifact (recipe or image) record. Depending on the job_type,
        create or customize, the returned artifact record will either be an IMS recipe or an IMS Image.
        """

        def _retrieve_recipe_record():
            current_app.logger.info(f"Retrieving recipe info")
            recipe_record = current_app.data['recipes'].get(str(artifact_id))
            if not recipe_record:
                current_app.logger.info("%s no IMS recipe record matches artifact_id=%s", log_id, artifact_id)
                return None, problemify(status=http.client.BAD_REQUEST,
                                        detail='Invalid artifact_id value in job request. No IMS recipe record '
                                               'found matching id={}. Determine the specific information that '
                                               'is missing or invalid and then re-run the request with valid '
                                               'information.'.format(artifact_id))

            if not recipe_record.link:
                current_app.logger.info("%s The IMS recipe record matching artifact_id=%s does not have a "
                                        "artifact_link.", log_id, artifact_id)
                return None, problemify(http.client.BAD_REQUEST,
                                        detail='The IMS recipe does not have an artifact_link for recipe_id={}. '
                                               'Please determine the specific information that is missing or '
                                               'invalid and then re-run the request with valid information.'.format(
                                                artifact_id))

            return recipe_record, None

        def _retrieve_image_record():
            current_app.logger.info(f"Retrieving image info")
            image_record = current_app.data['images'].get(str(artifact_id))
            if not image_record:
                current_app.logger.info("%s no IMS image record matches artifact_id=%s", log_id, artifact_id)
                return None, problemify(status=http.client.BAD_REQUEST,
                                        detail='Invalid artifact_id value in job request. No IMS image record '
                                               'found matching id={}. Determine the specific information that '
                                               'is missing or invalid and then re-run the request with valid '
                                               'information.'.format(artifact_id))

            if not image_record.link:
                current_app.logger.info("%s The IMS image record matching artifact_id=%s does not have a "
                                        "artifact_link.", log_id, artifact_id)
                return None, problemify(http.client.BAD_REQUEST,
                                        detail='The IMS image does not have an artifact_link for image_id={}. '
                                               'Please determine the specific information that is missing or '
                                               'invalid and then re-run the request with valid information.'.format(
                                                artifact_id))

            return image_record, None

        artifact_record, problem = {
            JOB_TYPE_CREATE: _retrieve_recipe_record,
            JOB_TYPE_CUSTOMIZE: _retrieve_image_record
        }.get(job_type.lower())()

        if problem:
            return None, problem

        try:
            md5sum = validate_artifact(artifact_record.link)
        except ImsArtifactValidationException as exc:
            return None, problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

        return {'artifact': artifact_record, 'md5sum': md5sum}, None

    @staticmethod
    def get_rootfs_artifact_from_manifest(log_id, ims_image_id, manifest_json):
        """
        Utility function used to parse the given manifest_json data structure, and return
        the manifest artifact data for the root-fs artifact.
        """

        def _get_rootfs_artifact_from_v1_manifest():
            try:
                root_fs_artifacts = [artifact for artifact in manifest_json[IMAGE_MANIFEST_ARTIFACTS] if
                                     artifact[IMAGE_MANIFEST_ARTIFACT_TYPE].startswith(IMAGE_MANIFEST_ARTIFACT_TYPE_SQUASHFS)]
            except ValueError as value_error:
                current_app.logger.info("%s Received ValueError while processing manifest file for image_id=%s.",
                                        log_id, ims_image_id, exc_info=value_error)
                return None, problemify(status=http.client.BAD_REQUEST,
                                        detail='The manifest.json file is corrupt or invalid for IMS image_id={}. Could'
                                               'not get a list of artifacts. Determine the specific information that '
                                               'is missing or invalid and then re-run the request with valid '
                                               'information.'.format(ims_image_id))

            if not root_fs_artifacts:
                current_app.logger.info("%s No rootfs artifact could be found in the image manifest for image_id=%s.",
                                        log_id, ims_image_id)
                return None, problemify(status=http.client.BAD_REQUEST,
                                        detail='Error reading the manifest.json for IMS image_id={}. The manifest '
                                               'does not include any rootfs artifacts. Determine the specific '
                                               'information that is missing or invalid and then re-run the request '
                                               'with valid information.'.format(ims_image_id))

            if len(root_fs_artifacts) > 1:
                current_app.logger.info("%s Multiple rootfs artifacts found in the image manifest for image_id=%s.",
                                        log_id, ims_image_id)
                return None, problemify(status=http.client.BAD_REQUEST,
                                        detail='Error reading the manifest.json for IMS image_id={}. The manifest '
                                               'includes multiple rootfs artifacts. Determine the specific information '
                                               'that is missing or invalid and then re-run the request with valid '
                                               'information.'.format(ims_image_id))

            if (ARTIFACT_LINK not in root_fs_artifacts[0]) or (not root_fs_artifacts[0][ARTIFACT_LINK]):
                current_app.logger.info("%s The rootfs referenced in the manifest.json for ims_image_id=%s does not "
                                        "have a artifact_link.", log_id, ims_image_id)
                return None, problemify(http.client.BAD_REQUEST,
                                        detail='The rootfs referenced in the manifest.json for ims_image_id={} does '
                                               'not have a artifact link. Please determine the specific information '
                                               'that is missing or invalid and then re-run the request with valid '
                                               'information.'.format(ims_image_id))

            return root_fs_artifacts[0], None

        try:
            return {
                IMAGE_MANIFEST_VERSION_1_0: _get_rootfs_artifact_from_v1_manifest,
            }.get(manifest_json[IMAGE_MANIFEST_VERSION])()
        except (TypeError, KeyError) as e:
            current_app.logger.info("Unknown manifest version or manifest.json is corrupt or invalid for IMS "
                                    "image_id=%s.", ims_image_id, exc_info=e)
            return None, problemify(status=http.client.BAD_REQUEST,
                                    detail='The manifest.json file is corrupt or invalid for IMS image_id={}. Could '
                                           'not determine the manifest version or manifest version is unsupported. '
                                           'Determine the specific information that is missing or invalid and then '
                                           're-run the request with valid information.'.format(ims_image_id))

    @staticmethod
    def get_artifact_info(job_type, log_id, artifact_id):
        """
        Utility function to return an IMS artifact (recipe or image) record,
        the md5 sum for the artifact, and a download url that can be used to
        download the artifact. Depending on the job_type, create or customize,
        the artifact returned will either be an IMS recipe or an IMS Image.
        """

        def _get_recipe_info(artifact_info):
            """
            Given the artifact_id for a IMS recipe record:
              1. Try to load the IMS recipe record
              2. Verify that the IMS recipe record has a link value
              3. Generate a download URL from the link value
            """
            artifact_record = artifact_info["artifact"]
            md5sum = artifact_info["md5sum"] if artifact_info["artifact"].link else ""
            download_url, problem = get_download_url(artifact_record.link)
            if problem:
                return None, problem

            return {"artifact": artifact_record, "url": download_url, "md5sum": md5sum}, None

        def _get_image_info(artifact_info):
            """
            Given the artifact_id for a IMS image record:
              1. Try to load the IMS image record
              2. Verify that the IMS image record has a link value. The link
                 value points to the image's manifest.json file.
              3. Read and parse the manifest.json file.
              4. Find the artifact in the manifest.json for the rootfs mime type
              5. Generate a download URL for the rootfs artifact
            """
            artifact_record = artifact_info["artifact"]
            manifest_json, problem = read_manifest_json(artifact_record.link)
            if problem:
                return None, problem

            rootfs_artifact, problem = V3JobCollection.get_rootfs_artifact_from_manifest(
                log_id,
                artifact_id,
                manifest_json
            )
            if problem:
                return None, problem

            manifest_rootfs_md5sum = ""
            if "md5" in rootfs_artifact and rootfs_artifact["md5"]:
                manifest_rootfs_md5sum = rootfs_artifact["md5"]

            try:
                s3obj_rootfs_md5sum = validate_artifact(rootfs_artifact[ARTIFACT_LINK])
            except ImsArtifactValidationException as exc:
                return None, problemify(status=http.client.UNPROCESSABLE_ENTITY, detail=str(exc))

            if manifest_rootfs_md5sum and s3obj_rootfs_md5sum and manifest_rootfs_md5sum != s3obj_rootfs_md5sum:
                current_app.logger.info("%s The rootfs md5sum from the manifest.json does not match the md5sum "
                                        "on the rootfs s3 object for ims_image_id=%s. Using the md5sum from the "
                                        "S3 object.", log_id, artifact_id)
            md5sum = s3obj_rootfs_md5sum if s3obj_rootfs_md5sum else manifest_rootfs_md5sum
            md5sum = md5sum if md5sum else ""

            download_url, problem = get_download_url(rootfs_artifact[ARTIFACT_LINK])
            if problem:
                return None, problem

            return {"artifact": artifact_record, "url": download_url, "md5sum": md5sum}, None

        artifact_info, problem = V3JobCollection.retrieve_artifact_record(job_type, log_id, artifact_id)
        if problem:
            current_app.logger.info("%s Could not validate artifact or artifact doesn't exist", log_id)
            return None, problem

        ret_val = {
            JOB_TYPE_CREATE: _get_recipe_info,
            JOB_TYPE_CUSTOMIZE: _get_image_info
        }.get(job_type.lower())(artifact_info)
        return ret_val

    @staticmethod
    def get_public_key_data(log_id, public_key_id):
        """ Retrieve an public key data from an IMS public_key record given a public_key_id. """
        if public_key_id:
            public_key_record = current_app.data['public_keys'].get(str(public_key_id))
            if not public_key_record:
                current_app.logger.info("%s no IMS public_key record matches public_key_id=%s",
                                        log_id, public_key_id)
                return None, problemify(status=http.client.BAD_REQUEST,
                                        detail='Invalid public_key_id value in job request. No IMS public-key '
                                               'record found matching id={}'.format(public_key_id))
            return public_key_record.public_key, None
        return "", None

    def post(self):
        """ Add a new job to the IMS Service.

        A new job is created from values that passed in via the request body. If the job already
        exists, then a 400 is returned. If the job is created successfully then a 201 is returned.

        """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v3.POST", log_id)
        json_data = request.get_json()

        if not json_data:
            current_app.logger.info("%s No post data accompanied the POST request.", log_id)
            return generate_missing_input_response()

        current_app.logger.info("%s json_data = %s", log_id, json_data)

        # keep track of optional user input values
        userSpecifiedDKMS = None
        if 'require_dkms' in json_data:
            userSpecifiedDKMS = json_data['require_dkms']

        # Validate input
        errors = job_user_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the post data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        # Create a job record and populate with user input data
        new_job = job_schema.load(json_data)

        # fill in job information based on job type
        if new_job.job_type == JOB_TYPE_CREATE:
            current_app.logger.debug("%s Processing create request", log_id)

            # TODO CASMCMS-2461 Enable multiple SSH containers during IMS Create/Customize
            # For now, don't allow users to define ssh containers on create
            if new_job.ssh_containers:
                current_app.logger.info("%s User defined ssh containers during image create "
                                        "are not currently supported.", log_id)
                return problemify(status=http.client.BAD_REQUEST,
                                  detail='User defined ssh containers during image create are not currently '
                                         'supported. Determine the specific information that is missing or '
                                         'invalid and then re-run the request with valid information.')

            # If requested to enable debug, add debug ssh shell
            if new_job.enable_debug:
                new_job.ssh_containers = new_job.ssh_containers if new_job.ssh_containers else []
                new_job.ssh_containers.append({'name': "debug", "jail": "False"})

        elif new_job.job_type == JOB_TYPE_CUSTOMIZE:
            current_app.logger.debug("%s Processing customize request", log_id)

            # default to having one ssh container if the user didn't otherwise specify
            if not new_job.ssh_containers:
                new_job.ssh_containers = [{'name': "customize", "jail": "False"}]
        else:
            current_app.logger.info("%s Unsupported job_type %s", log_id, new_job.job_type)
            # Should never get here as there are only two job types, which are validated
            return problemify(http.client.BAD_REQUEST, "Unsupported job_type {} in job_record id={}. Determine "
                                                       "the specific information that is missing or invalid and "
                                                       "then re-run the request with valid "
                                                       "information.".format(new_job.job_type, new_job.id))

        # TODO CASMCMS-2461 Enable multiple SSH containers during IMS Create/Customize
        # For now, only allow one ssh container to be defined
        if new_job.ssh_containers and len(new_job.ssh_containers) > 1:
            current_app.logger.info("%s Only one SSH container is currently supported", log_id)
            return problemify(status=http.client.BAD_REQUEST,
                              detail='Only one SSH container is currently supported. Please remove additional '
                                     'containers, determine the specific information that is missing or '
                                     'invalid and then re-run the request with valid information.')

        # The artifact info consists of the artifact record, a download URL and the md5sum (if available) of the file.
        # Get the information on the artifact being used for the job
        artifact_info, problem = V3JobCollection.get_artifact_info(new_job.job_type, log_id, new_job.artifact_id)
        if problem:
            current_app.logger.info("%s Could not get download url for artifact", log_id)
            return problem
        artifact_record = artifact_info["artifact"]  # pylint: disable=unsubscriptable-object

        current_app.logger.info(f"ARTIFACT_RECORD: {artifact_record}")

        # both images and recipes have an architecture specified - shift into the job
        new_job.arch = artifact_record.arch
        current_app.logger.info(f"architecture: {new_job.arch}")

        # change the file name to match the architecture of the image and recipe, if passed in by user do nothing.
        if new_job.kernel_file_name is None or len(new_job.kernel_file_name) == 0:
            default_file_name = ARCH_TO_KERNEL_FILE_NAME.get(new_job.arch, KERNEL_FILE_NAME_X86) # default to x86 if some failure occurs
            new_job.kernel_file_name = default_file_name

        current_app.logger.info(f"kernel file name: {new_job.kernel_file_name}")

        # Determine cases where the dkms security settings are required without user specifying
        if new_job.arch == ARCH_ARM64:
            # If the architecture is aarch64, then the dkms settings are required
            current_app.logger.info(f" NOTE: aarch64 architecture requires dkms")
            new_job.require_dkms = True
        elif userSpecifiedDKMS==None:
            # if the user didn't specify for the job, look for defaults
            if new_job.job_type == JOB_TYPE_CREATE:
                # Let the setting from the recipe flow through if the user has not specified otherwise
                if artifact_record.require_dkms != self.job_enable_dkms:
                    current_app.logger.info(f"Overriding require_dkms based on recipe setting")
                current_app.logger.info(f"Setting require_dkms based on recipe setting: {artifact_record.require_dkms}")
                new_job.require_dkms = artifact_record.require_dkms
            elif not self.job_enable_dkms:
                # use the default from the ims-config config map
                current_app.logger.info(f"Setting require_dkms based on ims-config setting")
                new_job.require_dkms = False

        # get the public key information
        public_key_data, problem = V3JobCollection.get_public_key_data(log_id, new_job.public_key_id)
        if problem:
            current_app.logger.info("%s Could not get download url for artifact", log_id)
            return problem

        external_dns_hostname = f"{str(new_job.id).lower()}.ims.{self.job_customer_access_subnet_name}.{self.job_customer_access_network_domain}"

        # switch the set of values depending on if the kata-qemu runtime class is used
        job_enable_dkms = "False"
        job_runtime_class = ""
        job_service_account = ""
        job_security_privilege = "false"
        job_security_capabilities = ""
        if new_job.require_dkms:
            job_enable_dkms = "True"
            job_runtime_class = self.job_kata_runtime if "kata" in self.job_kata_runtime else "kata-qemu"
            job_service_account = "ims-service-job-mount"
            job_security_privilege = "true"
            job_security_capabilities = "SYS_ADMIN"

        # aarch64 architecture needs dkms, plus its own runtime class
        if new_job.arch == ARCH_ARM64:
            job_runtime_class = self.job_aarch64_runtime

        # Find if there is a remote node that can run this job 
        remoteNode = find_remote_node_for_job(current_app, new_job)
        if remoteNode != "":
            # set the value of the remote node for the job template
            new_job.remote_build_node = remoteNode

            # Since the job is running on a remote node, do not need to isolate in kata VM
            job_runtime_class = ""

        # set up the template params to feed into the job template
        template_params = {
            "id": str(new_job.id).lower(),
            "size_gb": str(new_job.build_env_size) + "Gi",
            "limit_gb": str(int(new_job.build_env_size) * 3) + "Gi",
            "pvc_gb": str(int(new_job.build_env_size) * 5) + "Gi",
            "job_mem_size": str(new_job.job_mem_size) + "Gi",
            "job_mem_limit": str(int(new_job.job_mem_size) * 5) + "Gi",
            "download_url": artifact_info["url"],  # pylint: disable=unsubscriptable-object
            "download_md5sum": artifact_info["md5sum"],  # pylint: disable=unsubscriptable-object
            "public_key": public_key_data,
            "enable_debug": str(new_job.enable_debug),
            "ssh_jail": str(new_job.ssh_containers[0]["jail"]) if new_job.ssh_containers else "False",
            "image_root_archive_name": new_job.image_root_archive_name,
            "kernel_filename": new_job.kernel_file_name,
            "initrd_filename": new_job.initrd_file_name,
            "kernel_parameters_filename": new_job.kernel_parameters_file_name,
            "address_pool": self.job_customer_access_network_access_pool,
            "hostname": external_dns_hostname,
            "namespace": self.default_ims_job_namespace,
            "s3_bucket": current_app.config["S3_BOOT_IMAGES_BUCKET"],
            "job_enable_dkms": job_enable_dkms,
            "runtime_class": job_runtime_class,
            "service_account": job_service_account,
            "security_privilege": job_security_privilege,
            "security_capabilities": job_security_capabilities,
            "job_arch": new_job.arch,
            "remote_build_node": new_job.remote_build_node
        }

        current_app.logger.info(f"Job template param: {template_params}")
        
        if new_job.job_type == JOB_TYPE_CREATE:
            template_params["template_dictionary"] = \
                json.dumps({r['key']: r['value'] for r in artifact_record.template_dictionary})
            template_params["recipe_type"] = artifact_record.recipe_type

        current_app.logger.info(f"Template arguments: {template_params}")

        new_job, problem = self.create_kubernetes_resources(
            log_id, new_job, template_params,
            artifact_record.recipe_type if new_job.job_type == JOB_TYPE_CREATE else None)
        if problem:
            return problem

        if new_job.ssh_containers:
            # TODO CASMCMS-2461 Enable multiple SSH containers during IMS Create/Customize

            new_job.ssh_containers[0]["status"] = "pending"
            # noinspection PyTypeChecker
            new_job.ssh_containers[0]["connection_info"] = {
                "customer_access": {
                    "host": external_dns_hostname,
                    "port": 22,
                },
                "cluster.local": {
                    "host": "{}.{}.svc.cluster.local".format(new_job.kubernetes_service, new_job.kubernetes_namespace),
                    "port": 22,
                }
            }

        # Save to datastore
        current_app.data['jobs'][str(new_job.id)] = new_job

        return_json = job_schema.dump(new_job)
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return return_json, 201

    def delete(self):
        """ Delete all jobs. """
        errors = []
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v3.DELETE", log_id)

        status_list = [status.lower() for status in request.args.getlist("status")]
        for status in status_list:
            if status not in STATUS_TYPES:
                return problemify(http.client.BAD_REQUEST, "Unsupported status {} in query parameters. Determine "
                                                           "the specific information that is missing or invalid and "
                                                           "then re-run the request with valid "
                                                           "information.".format(status))
        if status_list:
            current_app.logger.info('%s Filter: status=%s', log_id, status_list)

        job_type = request.args.get("job_type", None)
        if job_type and job_type not in JOB_TYPES:
            return problemify(http.client.BAD_REQUEST, "Unsupported job_type {} in query parameters. Determine "
                                                       "the specific information that is missing or invalid and "
                                                       "then re-run the request with valid "
                                                       "information.".format(job_type))
        if job_type:
            current_app.logger.info('%s Filter: job_type=%s', log_id, job_type)

        max_age = None
        age = request.args.get("age", None)
        if age is not None:
            # noinspection PyBroadException
            try:
                max_age = self._age_to_timestamp(age)
            except Exception:  # pylint: disable=broad-except
                current_app.logger.warning('%s Unable to parse age: {}', log_id, age)
                return problemify(http.client.BAD_REQUEST, "Unsupported age {} in query parameters. Determine "
                                                           "the specific information that is missing or invalid and "
                                                           "then re-run the request with valid "
                                                           "information.".format(age))
        if max_age:
            current_app.logger.info('%s Filter: age=%s', log_id, age)

        try:
            jobs_to_delete = []

            for job_id, job in current_app.data['jobs'].items():

                if status_list and job.status not in status_list:
                    continue
                if job_type and job_type != job.job_type:
                    continue
                if max_age and max_age <= job.created.replace(tzinfo=None):
                    continue

                current_app.logger.info("%s Deleting k8s resources for job_id=%s", log_id, job_id)
                retval, delete_errors = self.delete_kubernetes_resources(log_id, job)
                if retval:
                    # We successfully deleted the kubernetes resources for the job
                    # mark that we need to delete the job from our list
                    jobs_to_delete.append(job_id)
                if not retval:
                    errors += delete_errors

            for job_id in jobs_to_delete:
                del current_app.data['jobs'][job_id]
        except KeyError as key_error:
            current_app.logger.info("%s Key not found: %s", log_id, key_error)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered deleting jobs. Review the errors, '
                                           'take any corrective action and then re-run the request with valid '
                                           'information.')

        if errors:
            current_app.logger.info("%s errors encountered during delete: %s", log_id, errors)
            return problemify(status=http.client.INTERNAL_SERVER_ERROR,
                              detail='Errors were encountered deleting the kubernetes resources for '
                                     'one or more IMS jobs. Review the errors, take any corrective '
                                     'action and then re-run the request with valid information.',
                              errors=errors)

        current_app.logger.info("%s return 204", log_id)
        return None, 204


class V3JobResource(V3BaseJobResource):
    """ Endpoint for the jobs/{job_id} resource. """

    def get(self, job_id):
        """ Retrieve a job. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v3.GET %s", log_id, job_id)
        if job_id not in current_app.data["jobs"]:
            current_app.logger.info("%s no IMS job record matches job_id=%s", log_id, job_id)
            return generate_resource_not_found_response()
        return_json = job_schema.dump(current_app.data['jobs'][job_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, job_id):
        """ Delete a job. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v3.DELETE %s", log_id, job_id)

        try:
            job = current_app.data['jobs'][job_id]
            status, errors = self.delete_kubernetes_resources(log_id, job)

            if not status:
                current_app.logger.info("%s errors encountered during delete: %s", log_id, errors)
                return problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                  detail='Errors were encountered deleting the kubernetes resources for '
                                         'IMS job_id=%s. Review the errors, take any corrective '
                                         'action and then re-run the request with valid information.' % job_id,
                                  errors=errors)

            del current_app.data['jobs'][job_id]
        except KeyError:
            current_app.logger.info("%s no IMS job record matches job_id=%s", log_id, job_id)
            return generate_resource_not_found_response()

        current_app.logger.info("%s return 204", log_id)
        return None, 204

    def patch(self, job_id):
        """ Update an existing job record """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v3.PATCH %s", log_id, job_id)

        if job_id not in current_app.data["jobs"]:
            current_app.logger.info("%s no IMS job record matches job_id=%s", log_id, job_id)
            return generate_resource_not_found_response()

        json_data = request.get_json()
        if not json_data:
            current_app.logger.info("%s No patch data accompanied the PATCH request.", log_id)
            return generate_missing_input_response()

        # Validate input
        errors = job_patch_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the PATCH data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        job = current_app.data["jobs"][job_id]
        for key, value in list(json_data.items()):
            if key == "status":
                if value in (JOB_STATUS_ERROR, JOB_STATUS_SUCCESS):
                    # The job pod is either in `error` or `success` state. Either way, processing is complete.
                    # We need to delete the k8s service (to release the CAN IP), but not the IMS job POD.
                    # Leaving the job pod allows users to access the job logs. The job pod will get cleaned up
                    # when the IMS job is deleted.
                    current_app.logger.info("%s Deleting k8s service IP for IMS Job", log_id)
                    status, errors = self.delete_kubernetes_resources(log_id, job, delete_job=False)
                    if not status:
                        current_app.logger.info("%s errors encountered while deleting k8s service IP: %s", log_id, errors)
                        return problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                          detail='Errors were encountered cleaning up kubernetes service IP for '
                                                 'IMS job_id=%s. Review the errors, take any corrective '
                                                 'action and then re-run the request with valid information.' % job_id,
                                          errors=errors)
            setattr(job, key, value)
        current_app.data['jobs'][job_id] = job

        return_json = job_schema.dump(current_app.data['jobs'][job_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)
