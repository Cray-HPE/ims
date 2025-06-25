#
# MIT License
#
# (C) Copyright 2018-2025 Hewlett Packard Enterprise Development LP
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
Jobs Models
"""

import datetime
import os
import uuid
from typing import Literal

from marshmallow import RAISE, Schema, fields, post_load
from marshmallow.validate import Length, OneOf, Range

from src.server.helper import ARCH_ARM64, ARCH_X86_64
from src.server.vault import test_private_key_file
from src.server.models.remote_build_nodes import RemoteNodeStatus

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

KERNEL_FILE_NAME_ARM = 'Image'
KERNEL_FILE_NAME_X86 = 'vmlinuz'
KERNEL_TYPES = (KERNEL_FILE_NAME_ARM, KERNEL_FILE_NAME_X86)
ARCH_TO_KERNEL_FILE_NAME = dict({
    ARCH_ARM64: KERNEL_FILE_NAME_ARM,
    ARCH_X86_64: KERNEL_FILE_NAME_X86
})

DEFAULT_INITRD_FILE_NAME = 'initrd'
DEFAULT_IMAGE_SIZE = os.environ.get("DEFAULT_IMS_IMAGE_SIZE", "60")
DEFAULT_JOB_MEM_SIZE = os.environ.get("DEFAULT_IMS_JOB_MEM_SIZE", "8")
DEFAULT_KERNEL_PARAMETERS_FILE_NAME = 'kernel-parameters'

# pylint: disable=R0902
class V2JobRecord:
    """ The JobRecord object """

    # pylint: disable=W0622,R0913
    def __init__(self, job_type, artifact_id, id=None, created=None, status=None,
                 public_key_id=None, kubernetes_job=None, kubernetes_service=None,
                 kubernetes_configmap=None, enable_debug=False,
                 build_env_size=None, image_root_archive_name=None, kernel_file_name=None,
                 initrd_file_name=None, resultant_image_id=None, ssh_containers=None,
                 kubernetes_namespace=None, kernel_parameters_file_name=None, require_dkms=True,
                 arch=None, job_mem_size=None, kubernetes_pvc=None, remote_build_node="",
                 kubernetes_secret=None):
        # Supplied
        # v2.0
        self.job_type = job_type
        self.artifact_id = artifact_id
        self.public_key_id = public_key_id
        self.enable_debug = enable_debug
        self.image_root_archive_name = image_root_archive_name
        self.kernel_file_name = kernel_file_name
        self.initrd_file_name = initrd_file_name or DEFAULT_INITRD_FILE_NAME
        self.kernel_parameters_file_name = kernel_parameters_file_name or DEFAULT_KERNEL_PARAMETERS_FILE_NAME
        self.resultant_image_id = resultant_image_id
        self.ssh_containers = ssh_containers
        
        # v2.1
        self.require_dkms = require_dkms

        # derived
        # v2.0
        self.id = id or uuid.uuid4()
        self.created = created or datetime.datetime.now()
        self.status = status or JOB_STATUS_CREATING
        self.build_env_size = build_env_size or DEFAULT_IMAGE_SIZE
        self.kubernetes_job = kubernetes_job
        self.kubernetes_service = kubernetes_service
        self.kubernetes_configmap = kubernetes_configmap
        self.kubernetes_namespace = kubernetes_namespace

        # v2.1
        self.arch = arch

        # v2.2
        self.kubernetes_pvc = kubernetes_pvc
        self.job_mem_size = job_mem_size or DEFAULT_JOB_MEM_SIZE

        # v2.3
        self.remote_build_node = remote_build_node or ""

        # v2.4
        self.kubernetes_secret = kubernetes_secret

    def __repr__(self):
        return '<v2JobRecord(id={self.id!r})>'.format(self=self)


class SshContainerInputSchema(Schema):
    """ A schema specifically for defining and validating user input of SSH Containers """
    name = fields.String(metadata={"metadata": {"description": "SSH Container name"}})
    jail = fields.Boolean(metadata={"metadata": {"description": "Whether to use an SSH jail to restrict access to the image root. Default = False"}}, 
                          load_default=False, dump_default=False)


class V2JobRecordInputSchema(Schema):
    """ A schema specifically for defining and validating user input of Job requests """
    artifact_id = fields.UUID(required=True,
                              metadata={"metadata": {"description": "IMS record id (either recipe or image depending on job_type) for the source artifact"}},)
    public_key_id = fields.UUID(required=True,metadata={"metadata": {"description": "IMS record id for the public_key record to use."}})
    job_type = fields.Str(required=True,metadata={"metadata": {"description": "The type of job, either 'create' or 'customize'"}},
                          validate=OneOf(JOB_TYPES, error="Job type must be one of: {choices}."))
    image_root_archive_name = fields.Str(required=True, metadata={"metadata": {"description": "Name to be given to the image root artifact"}},
                                         validate=Length(min=1, error="image_root_archive_name field must not be blank"))
    enable_debug = fields.Boolean(load_default=False,dump_default=False,
                                  metadata={"metadata": {"description": "Whether to enable debugging of the job"}})
    build_env_size = fields.Integer(dump_default=DEFAULT_IMAGE_SIZE,
                                    metadata={"metadata": {"description": "Approximate disk size in GiB to reserve for the image build environment (usually 2x final image size)"}},
                                    validate=Range(min=1, error="build_env_size must be greater than or equal to 1"))
    kernel_file_name = fields.Str(metadata={"metadata": {"description": "Name of the kernel file to extract and upload"}})

    initrd_file_name = fields.Str(load_default="initrd", dump_default="initrd",
                                  metadata={"metadata": {"description": "Name of the initrd file to extract and upload"}},
                                  validate=Length(min=1, error="initrd_file_name field must not be blank"))

    kernel_parameters_file_name = \
        fields.Str(load_default="kernel-parameters", dump_default="kernel-parameters",
                   metadata={"metadata": {"description": "Name of the kernel parameters file to extract and upload"}},
                   validate=Length(min=1, error="kernel_parameters_file_name field must not be blank"))

    ssh_containers = fields.List(fields.Nested(SshContainerInputSchema()), allow_none=True)

    # v2.1
    require_dkms = fields.Boolean(required=False, load_default=True, dump_default=True,
                                  metadata={"metadata": {"description": "Job requires the use of dkms"}})

    # v2.2
    job_mem_size = fields.Integer(dump_default=DEFAULT_JOB_MEM_SIZE, required=False,
                                  validate=Range(min=1, error="build_env_size must be greater than or equal to 1"),
                                  metadata={"metadata": {"description": "Approximate working memory in GiB to reserve for the build job "
                                    "environment (loosely proportional to the final image size)"}})

    @post_load
    def make_job(self, data, many, partial):
        """ Marshall an object out of the individual data components """
        return V2JobRecord(**data)

    class Meta:  # pylint: disable=missing-docstring
        model = V2JobRecord
        unknown = RAISE  # do not allow unknown fields in the schema


class SshConnectionInfo(Schema):
    """ A schema specifically for validating SSH Container Connection Info """
    host = fields.String(metadata={"metadata": {"description": "Host ip or name to use to connect to the SSH container"}})
    port = fields.Integer(metadata={"metadata": {"description": "Port number to use to connect to the SSH container"}})


class SshContainerSchema(SshContainerInputSchema):
    """ A schema specifically for validating SSH Containers """
    status = fields.String(metadata={"metadata": {"description": "SSH Container Status"}})
    host = fields.String(metadata={"metadata": {"description": "Host ip or name to use to connect to the SSH container"}})
    port = fields.Integer(metadata={"metadata": {"description": "Port number to use to connect to the SSH container"}})
    connection_info = fields.Dict(keys=fields.Str(), values=fields.Nested(SshConnectionInfo))

    class Meta:  # pylint: disable=missing-docstring
        # host and port have been deprecated and are no longer used.
        load_only = ("host", "port",)


class V2JobRecordSchema(V2JobRecordInputSchema):
    """
    Schema for a fully-formed JobRecord object such as an object being
    read in from a database. Builds upon the basic input fields in
    JobRecordInputSchema.
    """
    id = fields.UUID(metadata={"metadata": {"description": "Unique id of the job"}})
    created = fields.DateTime(metadata={"metadata": {"description": "Time the job record was created"}})
    kubernetes_job = fields.Str(allow_none=True,
                                metadata={"metadata": {"description": "Job name for the underlying Kubernetes job"}})
    kubernetes_service = fields.Str(allow_none=True,
                                    metadata={"metadata": {"description": "Service name for the underlying Kubernetes service"}})
    kubernetes_configmap = fields.Str(allow_none=True,
                                      metadata={"metadata": {"description": "ConfigMap name for the underlying Kubernetes configmap"}})
    kubernetes_namespace = fields.Str(allow_none=True, load_default="default", dump_default="default",
                                      metadata={"metadata": {"description": "Kubernetes namespace where the IMS job resources were created"}})
    status = fields.Str(allow_none=False,metadata={"metadata": {"description": "State of the job request"}},
                        validate=OneOf(STATUS_TYPES, error="Job state must be one of: {choices}."))
    resultant_image_id = fields.UUID(allow_none=True,
                                     metadata={"metadata": {"description": "Unique id of the resultant image record"}})
    ssh_containers = fields.List(fields.Nested(SshContainerSchema()), allow_none=True)
    
    # v2.1
    arch = fields.Str(metadata={"metadata": {"description": "Architecture of the job"}},
                          validate=OneOf([ARCH_ARM64,ARCH_X86_64]),
                          load_default=ARCH_X86_64, dump_default=ARCH_X86_64)

    # v2.2
    kubernetes_pvc = fields.Str(allow_none=True,
                                metadata={"metadata": {"description": "PVC name for the underlying Kubernetes image pvc"}})

    # v2.3
    remote_build_node = fields.Str(allow_none=False, load_default="", dump_default="",
                                   metadata={"metadata": {"description": "XName of remote job if running on a remote node"}})

    # v2.4
    kubernetes_secret = fields.Str(allow_none=True,
                                metadata={"metadata": {"description": "Secret name for the job"}})

    # after reading in the data, make sure there is an arch defined - default to x86
    @post_load(pass_original=False)
    def fill_arch(self, data, many, partial, **kwargs):
        if not "arch" in data or data["arch"] is None:
            data["arch"] = ARCH_X86_64
        return data

class V2JobRecordPatchSchema(Schema):
    """
    Schema for a updating a JobRecord object.
    """
    status = fields.Str(required=False,metadata={"metadata": {"description": "State of the job request"}},
                        validate=OneOf(STATUS_TYPES, error="Job state must be one of: {choices}."))
    resultant_image_id = fields.UUID(required=False,
                                     metadata={"metadata": {"description": "Unique id of the resultant image record"}})

#NOTE: this can't live in helper.py due to a circular dependency
def find_remote_node_for_job(app, job: V2JobRecordSchema) -> str:
    """Find a remote node that can run this job.
    Args:
        job (V2JobRecordSchema): job that is going to be run
    Returns:
        str: xname of remote node or ""
    """
    app.logger.info(f"Checking for remote build node for job")
    best_node = ""
    best_node_job_count = 10000 # seed with a really big number of jobs

    # make sure the ssh key was set up correctly
    if not test_private_key_file(app):
        app.logger.error("Problem with ssh key - unable to create remote jobs")
        return best_node

    # Since the ssh key is good - look for a valid node
    for xname, remote_node in app.data['remote_build_nodes'].items():
        nodeStatus = remote_node.getStatus()
        if nodeStatus.ableToRunJobs and nodeStatus.nodeArch == job.arch:
            app.logger.info(f"Matching remote node: {xname}, current jobs on node: {nodeStatus.numCurrentJobs}")
            
            # -1 means no job information, make sure we don't prefer those nodes
            numNodeJobs = nodeStatus.numCurrentJobs
            if numNodeJobs == -1:
                numNodeJobs = 10000
                
            # matching arch - can use the node, now pick the node with the least jobs running
            if best_node == "" or numNodeJobs < best_node_job_count:
                best_node = remote_node.xname
                best_node_job_count = numNodeJobs
    return best_node
