"""
Jobs Models
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
"""

import os

import datetime
import uuid
from marshmallow import Schema, fields, post_load, RAISE
from marshmallow.validate import OneOf, Length, Range

JOB_TYPE_CREATE = 'create'
JOB_TYPE_CUSTOMIZE = 'customize'

JOB_STATUS_CREATING = 'creating'
JOB_STATUS_FETCHING_IMAGE = 'fetching_image'
JOB_STATUS_FETCHING_RECIPE = 'fetching_recipe'
JOB_STATUS_WAITING_FOR_REPOS = 'waiting_for_repos'
JOB_STATUS_BUILDING_IMAGE = 'building_image'
JOB_STATUS_PACKAGING_ARTIFACTS = 'packaging_artifacts'
JOB_STATUS_WAITING_ON_USER = 'waiting_on_user'
JOB_STATUS_ERROR = 'error'
JOB_STATUS_SUCCESS = 'success'

JOB_TYPES = (JOB_TYPE_CREATE, JOB_TYPE_CUSTOMIZE)
STATUS_TYPES = (JOB_STATUS_CREATING,
                JOB_STATUS_FETCHING_IMAGE,
                JOB_STATUS_FETCHING_RECIPE,
                JOB_STATUS_WAITING_FOR_REPOS,
                JOB_STATUS_BUILDING_IMAGE,
                JOB_STATUS_PACKAGING_ARTIFACTS,
                JOB_STATUS_WAITING_ON_USER,
                JOB_STATUS_ERROR,
                JOB_STATUS_SUCCESS)

DEFAULT_INITRD_FILE_NAME = 'initrd'
DEFAULT_KERNEL_FILE_NAME = 'vmlinuz'
DEFAULT_IMAGE_SIZE = os.environ.get("DEFAULT_IMS_IMAGE_SIZE", 10)


# pylint: disable=R0902
class V2JobRecord:
    """ The JobRecord object """

    # pylint: disable=W0622,R0913
    def __init__(self, job_type, artifact_id, id=None, created=None, status=None,
                 public_key_id=None, kubernetes_job=None, kubernetes_service=None,
                 kubernetes_configmap=None, enable_debug=False,
                 build_env_size=None, image_root_archive_name=None, kernel_file_name=None,
                 initrd_file_name=None, resultant_image_id=None, ssh_containers=None,
                 kubernetes_namespace=None):
        # Supplied
        self.job_type = job_type
        self.artifact_id = artifact_id
        self.public_key_id = public_key_id
        self.enable_debug = enable_debug
        self.image_root_archive_name = image_root_archive_name
        self.kernel_file_name = kernel_file_name or DEFAULT_KERNEL_FILE_NAME
        self.initrd_file_name = initrd_file_name or DEFAULT_INITRD_FILE_NAME
        self.resultant_image_id = resultant_image_id
        self.ssh_containers = ssh_containers

        # derived
        self.id = id or uuid.uuid4()
        self.created = created or datetime.datetime.now()
        self.status = status or JOB_STATUS_CREATING
        self.build_env_size = build_env_size or DEFAULT_IMAGE_SIZE
        self.kubernetes_job = kubernetes_job
        self.kubernetes_service = kubernetes_service
        self.kubernetes_configmap = kubernetes_configmap
        self.kubernetes_namespace = kubernetes_namespace

    def __repr__(self):
        return '<v2JobRecord(id={self.id!r})>'.format(self=self)


class SshContainerInputSchema(Schema):
    """ A schema specifically for defining and validating user input of SSH Containers """
    name = fields.String(description="SSH Container name")
    jail = fields.Boolean(description="Whether to use an SSH jail to restrict access to the image root. "
                                      "Default = False", default=False)


class V2JobRecordInputSchema(Schema):
    """ A schema specifically for defining and validating user input of Job requests """
    artifact_id = fields.UUID(required=True,
                              description="IMS record id (either recipe or image depending on job_type)"
                                          "for the source artifact")
    public_key_id = fields.UUID(required=True,
                                description="IMS record id for the public_key record to use.")
    job_type = fields.Str(required=True,
                          description="The type of job, either 'create' or 'customize'",
                          validate=OneOf(JOB_TYPES, error="Job type must be one of: {choices}."))
    image_root_archive_name = fields.Str(required=True,
                                         description="Name to be given to the imageroot artifact",
                                         validate=Length(min=1,
                                                         error="image_root_archive_name field must not be blank"))
    enable_debug = fields.Boolean(default=False,
                                  Description="Whether to enable debugging of the job")
    build_env_size = fields.Integer(Default=10,
                                    Description="approximate disk size in GiB to reserve for the image build"
                                                "environment (usually 2x final image size)",
                                    validate=Range(min=1, error="build_env_size must be greater than or equal to 1"))
    kernel_file_name = fields.Str(default="vmlinuz",
                                  description="Name of the kernel file to extract and upload",
                                  validate=Length(min=1, error="kernel_file_name field must not be blank"))
    initrd_file_name = fields.Str(default="initrd",
                                  description="Name of the initrd file to extract and upload",
                                  validate=Length(min=1, error="initrd_file_name field must not be blank"))

    ssh_containers = fields.List(fields.Nested(SshContainerInputSchema()), allow_none=True)

    @post_load
    def make_job(self, data):
        """ Marshall an object out of the individual data components """
        return V2JobRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V2JobRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class SshConnectionInfo(Schema):
    """ A schema specifically for validating SSH Container Connection Info """
    host = fields.String(description="Host ip or name to use to connect to the SSH container")
    port = fields.Integer(description="Port number to use to connect to the SSH container")


class SshContainerSchema(SshContainerInputSchema):
    """ A schema specifically for validating SSH Containers """
    status = fields.String(description="SSH Container Status")
    host = fields.String(description="Host ip or name to use to connect to the SSH container")
    port = fields.Integer(description="Port number to use to connect to the SSH container")
    connection_info = fields.Dict(key=fields.Str(), values=fields.Nested(SshConnectionInfo))

    class Meta:  # pylint: disable=missing-docstring
        # host and port have been deprecated and are no longer used.
        load_only = ("host", "port",)


class V2JobRecordSchema(V2JobRecordInputSchema):
    """
    Schema for a fully-formed JobRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    JobRecordInputSchema.
    """
    id = fields.UUID(description="the unique id of the job")
    created = fields.DateTime(description="the time the job record was created")
    kubernetes_job = fields.Str(allow_none=True,
                                description="Job name for the underlying Kubernetes job")
    kubernetes_service = fields.Str(allow_none=True,
                                    description="Service name for the underlying Kubernetes service")
    kubernetes_configmap = fields.Str(allow_none=True,
                                      description="ConfigMap name for the underlying Kubernetes configmap")
    kubernetes_namespace = fields.Str(allow_none=True, default="default",
                                      description="Kubernetes namespace where the IMS job resources were created")
    status = fields.Str(allow_none=False,
                        description="state of the job request",
                        validate=OneOf(STATUS_TYPES, error="Job state must be one of: {choices}."))
    resultant_image_id = fields.UUID(allow_none=True,
                                     description="the unique id of the resultant image record")
    ssh_containers = fields.List(fields.Nested(SshContainerSchema()), allow_none=True)


class V2JobRecordPatchSchema(Schema):
    """
    Schema for a updating a JobRecord object.
    """
    status = fields.Str(required=False,
                        description="state of the job request",
                        validate=OneOf(STATUS_TYPES, error="Job state must be one of: {choices}."))
    resultant_image_id = fields.UUID(required=False,
                                     description="the unique id of the resultant image record")
