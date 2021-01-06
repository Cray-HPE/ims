"""
Jobs API
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
"""
import datetime
import http.client
import os
import re
import tempfile
from collections import OrderedDict
from functools import partial
from string import Template

import time
import yaml
from flask import jsonify, request, current_app
from flask_restful import Resource
from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException

from src.server.errors import problemify, generate_missing_input_response, generate_data_validation_failure, \
    generate_resource_not_found_response
from src.server.helper import validate_artifact, get_log_id, get_download_url, read_manifest_json
from src.server.models.jobs import V2JobRecordInputSchema, V2JobRecordSchema, V2JobRecordPatchSchema, \
    JOB_TYPE_CREATE, JOB_TYPE_CUSTOMIZE, JOB_TYPES, STATUS_TYPES

job_user_input_schema = V2JobRecordInputSchema()
job_patch_input_schema = V2JobRecordPatchSchema()
job_schema = V2JobRecordSchema()


class V2BaseJobResource(Resource):
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

        self.ISTIO_RESOURCE_VERSION = 'v1alpha3'
        self.ISTIO_RESOURCE_GROUP = 'networking.istio.io'
        self.ISTIO_RESOURCE_DESTINATION_RULE = 'DestinationRule'
        self.ISTIO_RESOURCE_DESTINATION_RULES = 'destinationrules'

        self.api_gateway_hostname = os.environ.get("API_GATEWAY_HOSTNAME", "api-gw-service-nmn.local")
        self.default_ims_job_namespace = os.environ.get("DEFAULT_IMS_JOB_NAMESPACE", "ims")

        self.shasta_domain = os.environ.get("SHASTA_DOMAIN", "shasta.local")
        self.customer_access_pool = os.environ.get("CUSTOMER_ACCESS_POOL", "customer-access")

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
        current_app.logger.info("%s ++ jobs.v2._create_istio_destination_rule_for_job", log_id)

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

        current_app.logger.info("%s ++ jobs.v2._delete_istio_destination_rule_for_job", log_id)
        name = job.kubernetes_service
        namespace = job.kubernetes_namespace
        body = client.V1DeleteOptions(propagation_policy='Background')
        try:
            api_response = self._delete_namespaced_destination_rule(namespace)(name, body=body)
            current_app.logger.debug('%s %s "%s" resource: %s', log_id, self.ISTIO_RESOURCE_DESTINATION_RULE,
                                     name, api_response)
        except ApiException as e:
            current_app.logger.warning(
                '%s Exception when calling delete_namespaced_custom_object', log_id, exc_info=True
            )
            raise e

        return api_response

    def create_kubernetes_resources(self, log_id, new_job, template_params, recipe_type):
        """
        Create kubernetes resources (configmap, service, job and destination_rule) for the current job
        """

        k8s_client = client.ApiClient()
        new_job.kubernetes_namespace = self.default_ims_job_namespace
        for resource in ("configmap", "service", "job"):
            resource_field = "kubernetes_%s" % resource
            fd, output_file_name = tempfile.mkstemp(suffix=".yaml")
            try:
                if new_job.job_type == JOB_TYPE_CREATE:
                    input_file_name = "/mnt/ims/v2/job_templates/create/{0}/image_{1}_create.yaml.template".format(
                        recipe_type,
                        resource
                    )
                elif new_job.job_type == JOB_TYPE_CUSTOMIZE:
                    input_file_name = "/mnt/ims/v2/job_templates/customize/image_{0}_customize.yaml.template".format(
                        resource
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

        try:
            self._create_istio_destination_rule_for_job(log_id, new_job)
        except ApiException as api_exception:
            current_app.logger.warning("%s Error encountered creating istio DestinationRule %s",
                                       log_id, new_job.kubernetes_job, exc_info=api_exception)
            return None, problemify(status=http.client.INTERNAL_SERVER_ERROR,
                                    detail='An error was encountered creating the kubernetes DestinationRule '
                                           'resources for your IMS job. Review the errors, take any corrective '
                                           'action and then re-run the request with valid information.')

        return new_job, None

    def delete_kubernetes_resources(self, log_id, job):
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
        resources['job'] = k8s_batchv1api.delete_namespaced_job
        resources['configmap'] = k8s_v1api.delete_namespaced_config_map

        # Delete the underlying kubernetes service, job and configmap resources
        for resource, delete_fn in resources.items():
            name = getattr(job, "kubernetes_%s" % resource)
            current_app.logger.info("%s Deleting k8s %s %s.", log_id, resource, name)

            try:
                delete_fn(body=k8s_delete_options, namespace=namespace, name=name)
            except ApiException as api_exception:
                if api_exception.reason == "Not Found":
                    current_app.logger.warning("%s K8s %s %s was not found to delete.",
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
                current_app.logger.warning("%s K8s DestinationRule %s was not found to delete.",
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


class V2JobCollection(V2BaseJobResource):
    """
    Class representing the operations that can be taken on a collection of jobs
    """

    def get(self):
        """ retrieve a list/collection of jobs """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v2.GET", log_id)
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

        md5sum, problem = validate_artifact(artifact_record.link)
        if problem:
            return None, problem

        return {'artifact': artifact_record, 'md5sum': md5sum}, None

    @staticmethod
    def get_rootfs_artifact_from_manifest(log_id, ims_image_id, manifest_json):
        """
        Utility function used to parse the given manifest_json data structure, and return
        the manifest artifact data for the root-fs artifact.
        """

        def _get_rootfs_artifact_from_v1_manifest():
            try:
                root_fs_artifacts = [artifact for artifact in manifest_json['artifacts'] if
                                     artifact['type'].startswith('application/vnd.cray.image.rootfs.squashfs')]
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

            if ("link" not in root_fs_artifacts[0]) or (not root_fs_artifacts[0]["link"]):
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
                "1.0": _get_rootfs_artifact_from_v1_manifest,
            }.get(manifest_json['version'])()
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

            rootfs_artifact, problem = V2JobCollection.get_rootfs_artifact_from_manifest(
                log_id,
                artifact_id,
                manifest_json
            )
            if problem:
                return None, problem

            manifest_rootfs_md5sum = ""
            if "md5" in rootfs_artifact and rootfs_artifact["md5"]:
                manifest_rootfs_md5sum = rootfs_artifact["md5"]

            s3obj_rootfs_md5sum, problem = validate_artifact(rootfs_artifact["link"])
            if problem:
                return None, problem

            if manifest_rootfs_md5sum and s3obj_rootfs_md5sum and manifest_rootfs_md5sum != s3obj_rootfs_md5sum:
                current_app.logger.info("%s The rootfs md5sum from the manifest.json does not match the md5sum "
                                        "on the rootfs s3 object for ims_image_id=%s. Using the md5sum from the "
                                        "S3 object.", log_id, artifact_id)
            md5sum = s3obj_rootfs_md5sum if s3obj_rootfs_md5sum else manifest_rootfs_md5sum
            md5sum = md5sum if md5sum else ""

            download_url, problem = get_download_url(rootfs_artifact["link"])
            if problem:
                return None, problem

            return {"artifact": artifact_record, "url": download_url, "md5sum": md5sum}, None

        artifact_info, problem = V2JobCollection.retrieve_artifact_record(job_type, log_id, artifact_id)
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
        current_app.logger.info("%s ++ jobs.v2.POST", log_id)
        json_data = request.get_json()

        if not json_data:
            current_app.logger.info("%s No post data accompanied the POST request.", log_id)
            return generate_missing_input_response()

        current_app.logger.info("%s json_data = %s", log_id, json_data)

        # Validate input
        errors = job_user_input_schema.validate(json_data)
        if errors:
            current_app.logger.info("%s There was a problem validating the post data: %s", log_id, errors)
            return generate_data_validation_failure(errors)

        # Create a job record if the user input data was valid
        new_job = job_schema.load(json_data)

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
        artifact_info, problem = V2JobCollection.get_artifact_info(new_job.job_type, log_id, new_job.artifact_id)
        if problem:
            current_app.logger.info("%s Could not get download url for artifact", log_id)
            return problem

        artifact_record = artifact_info["artifact"]  # pylint: disable=unsubscriptable-object

        public_key_data, problem = V2JobCollection.get_public_key_data(log_id, new_job.public_key_id)
        if problem:
            current_app.logger.info("%s Could not get download url for artifact", log_id)
            return problem

        external_dns_hostname = "{}.ims.{}".format(str(new_job.id).lower(), self.shasta_domain)

        template_params = {
            "id": str(new_job.id).lower(),
            "size_gb": str(new_job.build_env_size) + "Gi",
            "limit_gb": str(int(new_job.build_env_size) * 3) + "Gi",
            "download_url": artifact_info["url"],  # pylint: disable=unsubscriptable-object
            "download_md5sum": artifact_info["md5sum"],  # pylint: disable=unsubscriptable-object
            "public_key": public_key_data,
            "enable_debug": str(new_job.enable_debug),
            "ssh_jail": str(new_job.ssh_containers[0]["jail"]) if new_job.ssh_containers else "False",
            "image_root_archive_name": new_job.image_root_archive_name,
            "kernel_filename": new_job.kernel_file_name,
            "initrd_filename": new_job.initrd_file_name,
            "address_pool": self.customer_access_pool,
            "hostname": external_dns_hostname,
            "namespace": self.default_ims_job_namespace,
            "s3_bucket": current_app.config["S3_BOOT_IMAGES_BUCKET"]
        }

        if new_job.job_type == JOB_TYPE_CREATE:
            template_params["recipe_type"] = artifact_record.recipe_type

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
        current_app.logger.info("%s ++ jobs.v2.DELETE", log_id)

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

            for job_id, job in list(current_app.data['jobs'].items()):

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


class V2JobResource(V2BaseJobResource):
    """ Endpoint for the jobs/{job_id} resource. """

    def get(self, job_id):
        """ Retrieve a job. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v2.GET %s", log_id, job_id)
        if job_id not in current_app.data["jobs"]:
            current_app.logger.info("%s no IMS job record matches job_id=%s", log_id, job_id)
            return generate_resource_not_found_response()
        return_json = job_schema.dump(current_app.data['jobs'][job_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)

    def delete(self, job_id):
        """ Delete a job. """
        log_id = get_log_id()
        current_app.logger.info("%s ++ jobs.v2.DELETE %s", log_id, job_id)

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
        current_app.logger.info("%s ++ jobs.v2.PATCH %s", log_id, job_id)

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
            setattr(job, key, value)
        current_app.data['jobs'][job_id] = job

        return_json = job_schema.dump(current_app.data['jobs'][job_id])
        current_app.logger.info("%s Returning json response: %s", log_id, return_json)
        return jsonify(return_json)
