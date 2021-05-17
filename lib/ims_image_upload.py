#!/usr/bin/env python
# Copyright 2019-2021 Hewlett Packard Enterprise Development LP
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
The purpose of this ansible module is to assist in the creation (and subsequent
cleanup) of an IMS image from a given rootfs image (which is locally available
to the node executing this plugin).

The module will try its best to resolve fields that are left to the default,
but requires explicit values for reasons of performance and/or security.
"""
import logging
import os
import shutil
import subprocess
import tempfile
import time
from base64 import decodestring
from glob import glob
from logging.handlers import BufferingHandler
from urlparse import urlparse

import requests
from ansible.module_utils.basic import AnsibleModule
from oauthlib.oauth2 import BackendApplicationClient
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from requests_oauthlib import OAuth2Session

from ims_python_helper import ImsHelper

PROTOCOL = 'https'
API_GW_DNSNAME = 'api-gw-service-nmn.local'
TOKEN_URL_DEFAULT = "{}://{}/keycloak/realms/shasta/protocol/openid-connect/token".format(PROTOCOL, API_GW_DNSNAME)  # noqa: E501
IMS_URL_DEFAULT = "{}://{}/apis/ims".format(PROTOCOL, API_GW_DNSNAME)
KERNEL_GLOB_DEFAULT = "boot/vmlinuz-*"
INITRD_GLOB_DEFAULT = "boot/initrd"
PARAMETERS_GLOB_DEFAULT = "boot/parameters-*"
OAUTH_CLIENT_ID_DEFAULT = "admin-client"
CERT_PATH_DEFAULT = "/var/opt/cray/certificate_authority/certificate_authority.crt"  # noqa: E501
LOG_DIR = '/var/log/cray'
LOG_FILE = os.path.join(LOG_DIR, 'ims_image_upload.log')
LOGGER = logging.getLogger()

ANSIBLE_METADATA = {
    'metadata_version': '2.5',
    'status': ['preview', 'stableinterface'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ims_image_upload

short_description: Upload system images and associated artifacts into IMS

version_added: "2.5"

description:
    - Uploads SquashFS system images into S3 and registers them with IMS
    - Registers individual image artifacts resolvable via pattern matching:
        - RootFS
        - Kernel
        - Initrd
        - Parameters Files
    - Upload IMSv2 image manifests

options:
    name:
        required: True
        type: String
    rootfs_path:
        required: True
        type: String
    kernel_glob:
        required: False
        type: String
        default': {KERNEL_GLOB_DEFAULT}
    initrd_glob:
        required: False
        type: String
        default: {INITRD_GLOB_DEFAULT}
    parameters_glob:
        required: False
        type': String,
        default: {PARAMETERS_GLOB_DEFAULT}
    ims-url:
        required: False
        type: String
        default': {IMS_URL_DEFAULT}
    s3-bucket:
        required: False
        type: String
        default: boot-images
    s3-access-key:
        required: True
        type: String
    s3-secret-key:
        required: True
        type: String
    s3-host:
        required: True
        type: String
    token-url:
        required: False
        type: String
        default: {TOKEN_URL_DEFAULT}
    oath-client-id:
        required: False
        type: String
        default: {OAUTH_CLIENT_ID_DEFAULT}
    oath-client-secret
        required: False
        type: String
        default': ''
    certificate
        required: False
        type: String
        default: {CERT_PATH_DEFAULT}

author:
    - jsl
    - rkleinman
'''.format(KERNEL_GLOB_DEFAULT=KERNEL_GLOB_DEFAULT,
           INITRD_GLOB_DEFAULT=INITRD_GLOB_DEFAULT,
           PARAMETERS_GLOB_DEFAULT=PARAMETERS_GLOB_DEFAULT,
           IMS_URL_DEFAULT=IMS_URL_DEFAULT,
           TOKEN_URL_DEFAULT=TOKEN_URL_DEFAULT,
           OAUTH_CLIENT_ID_DEFAULT=OAUTH_CLIENT_ID_DEFAULT,
           CERT_PATH_DEFAULT=CERT_PATH_DEFAULT)

EXAMPLES = '''
# Upload a new system image
- name: Invoke ims_image_upload
  ims_image_upload:
    name: test_image
    rootfs_path: /var/opt/cray/boot_images/SLES15
    s3-bucket: boot-images
    s3-access-key: {{my_s3_access_key}}
    s3-secret-key: {{my_s3_secret_key}}
    s3-host: https://s3.myhost.mydomain.com:12345
  register: result
'''

RETURN = '''
original_message:
    description: The original name param that was passed in
    type: str
    returned: always
message:
    description: The output message that the sample module generates
    type: str
    returned: always
'''


class FlushlessBufferingHandler(BufferingHandler):
    """
    This is a BufferingHandler that never flushes to disk.
    """

    def shouldFlush(self, record):
        return False

    @property
    def as_stream(self):
        """
        Returns the contents of its buffer as if replayed as a stream buffer.
        """
        return '\n'.join([record.getMessage() for record in self.buffer])


class IMSImageUpload(AnsibleModule):

    def __init__(self, fbh, *args, **kwargs):
        super(IMSImageUpload, self).__init__(*args, **kwargs)
        self.temp_mount = None
        self._rootfs_path = None
        self.populate_oath_client_secret()

        # Create an OAuth session and IMS Helper Object
        self.ims_session = IMSOauth2Session(self.params['oath-client-id'],
                                            self.params['oath-client-secret'],
                                            self.params['certificate'],
                                            self.params['token-url'],
                                            2000)

        ims_helper_kwargs = {
            'ims_url': self.params['ims-url'],
            'session': self.ims_session,
            's3_host': self.params['s3-host'],
            's3_secret_key': self.params['s3-secret-key'],
            's3_access_key': self.params['s3-access-key'],
            's3_bucket': self.params['s3-bucket']
        }

        self.ih = ImsHelper(**ims_helper_kwargs)
        self.response = {
            'changed': False, 'failed': True, 'stdout': fbh.as_stream,
            'msg': "Full log of transaction available on target system "
                   "within %r" % (LOG_FILE)
        }

    def populate_oath_client_secret(self):
        """
        Talk with kubernetes and obtain the client secret; this only works if
        the remote execution target allows such interactions; otherwise specify
        the oath-client-secret value in the call to this module.
        """
        if self.params['oath-client-secret']:
            return
        stdout = subprocess.check_output([
            'kubectl', 'get', 'secrets', 'admin-client-auth',
            "-ojsonpath='{.data.client-secret}"
        ])
        self.params['oath-client-secret'] = decodestring(stdout.strip())

    def is_rootfs_path_a_url(self):
        """ Determine if the rootfs_path is a valid http or https URL """
        o = urlparse(self.params['rootfs_path'])
        return {
            'is_url': all([o.scheme, o.netloc, o.path]) and o.scheme.lower() in ['http', 'https'],
            'rootfs_filename': o.path.rsplit('/', 1)[-1] if o.path else "image_root.tgz"
        }

    @property
    def rootfs_path(self):
        """
        Determine if the rootfs_filename path is a valid http:// or https:// url or a filepath. If rootfs_filename
        is a valid url, download the referenced object and return a path to a local file. Otherwise, just return
        the rootfs_filename path since it's already a local file path.
        """
        if not self._rootfs_path:
            url_check = self.is_rootfs_path_a_url()
            if url_check['is_url']:
                session = requests.session()
                session.verify = False

                local_filename = os.path.join(tempfile.mkdtemp(), url_check['rootfs_filename'])
                with session.get(self.params['rootfs_path'], stream=True) as r:
                    r.raise_for_status()
                    with open(local_filename, 'wb') as outf:
                        for chunk in r.iter_content(chunk_size=8192):
                            outf.write(chunk)

                self._rootfs_path = local_filename
            else:
                self._rootfs_path = self.params['rootfs_path']
        return self._rootfs_path

    def mount(self):
        self.temp_mount = tempfile.mkdtemp()
        proc = subprocess.Popen(
            ['mount', self.rootfs_path, self.temp_mount],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        oe = proc.communicate()[0]
        if proc.returncode:
            self.fail_json(msg="Unable mount image: %s" % (oe))

    def umount(self):
        proc = subprocess.Popen(
            ['umount', '--lazy', self.temp_mount],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        oe = proc.communicate()[0]
        if proc.returncode:
            LOGGER.error(oe)
            self.fail_json(msg="Unable to cleanup mounted image: %s" % (oe))
        shutil.rmtree(self.temp_mount, ignore_errors=True)

        # If these differ, this indicates that the path passed in was a URL and
        # we had to download the rootfs. Need to clean up that local file.
        if self.rootfs_path != self.params['rootfs_path']:
            shutil.rmtree(os.path.dirname(os.path.abspath(self.rootfs_path)))

    def mount_glob(self, pattern):
        """
        Returns a globpath relative to the mounted image.
        """
        return os.path.join(self.temp_mount, pattern)

    def image_path(self, pattern):
        """
        Introspects into the image for the path pattern in the image, and then
        checks for ambiguity in the specified pattern. Returns the resulting
        path for this pattern.

        Note: If there are no matches, or there are more than one matches to
        the specified pattern, this exits the module with failure.
        """
        matches = glob(self.mount_glob(pattern))
        lmatches = len(matches)
        if lmatches != 1:
            self.fail_json(
                msg="'%s' needs to resolve to exactly 1 image artifact; "
                    "%s match in the image: %s match the pattern."
                    % (pattern, lmatches, ', '.join(sorted(matches)))
            )
        return matches[0]

    def health_check_ims(self):
        LOGGER.info("Waiting for IMS to be healthy...")
        endpoint = "%s/images" % IMS_URL_DEFAULT
        while True:
            response = self.ims_session.get(endpoint)
            if response.ok:
                LOGGER.info("IMS nominal response on '%s'" % (endpoint))
                return
            else:
                time.sleep(1)

    def __call__(self):
        # Check Health of APIs before proceeding
        self.health_check_ims()

        self.mount()
        LOGGER.info("Registering %s, %s %s and %s".format(
            self.rootfs_path,
            self.image_path(self.params['kernel_glob']),
            self.image_path(self.params['initrd_glob']),
            self.image_path(self.params['parameters_glob']))
        )
        try:
            ih_upload_kwargs = {
                'image_name': self.params['name'],
                'rootfs': [self.rootfs_path],
                'kernel': [self.image_path(self.params['kernel_glob'])],
                'initrd': [self.image_path(self.params['initrd_glob'])],
                'boot_parameters': [self.image_path(self.params['parameters_glob'])]
            }
            response = self.ih.image_upload_artifacts(**ih_upload_kwargs)
        finally:
            self.umount()

        # Propogate forward any results
        self.response['failed'] = False
        self.response['changed'] = True
        for key in ('ims_job_record', 'ims_image_record'):
            if key in response:
                self.response[key] = response[key]

        self.exit_json(**self.response)


class IMSOauth2Session(OAuth2Session):
    def __init__(self, oauth_client_id, oauth_client_secret, ssl_cert, token_url, timeout):  # noqa: E501
        self.client = BackendApplicationClient(client_id=oauth_client_id)
        super(IMSOauth2Session, self).__init__(
            client=self.client, auto_refresh_kwargs={
                'client_id': oauth_client_id,
                'client_secret': oauth_client_secret
            }
        )
        self.verify = ssl_cert
        self.timeout = timeout
        self.hooks['response'].append(IMSOauth2Session.log_request)
        self.hooks['response'].append(IMSOauth2Session.log_response)
        self.fetch_token(token_url=token_url,
                         client_id=oauth_client_id,
                         client_secret=oauth_client_secret,
                         timeout=500)

    @staticmethod
    def log_request(resp, *args, **kwargs):
        """
        This function logs the requests.Response.request request.

        Args:
            resp : The response
        """
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('\n%s\n%s\n%s\n\n%s',
                         '-----------START REQUEST-----------',
                         resp.request.method + ' ' + resp.request.url,
                         '\n'.join('{}: {}'.format(k, v) for k, v in resp.request.headers.items()),
                         resp.request.body)

    @staticmethod
    def log_response(resp, *args, **kwargs):
        """
        This function logs request.Response response.

        Args:
            resp : The response
        """
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('\n%s\n%s\n%s\n\n%s',
                         '-----------START RESPONSE----------',
                         resp.status_code,
                         '\n'.join('{}: {}'.format(k, v) for k, v in resp.headers.items()),
                         resp.content)


def main(fbh):
    # Image/artifacts parameters
    fields = {
        'name': {'required': True, "type": "str"},
        'rootfs_path': {'required': True, "type": "str"},
        'kernel_glob': {'required': False, "type": "str", 'default': KERNEL_GLOB_DEFAULT},
        'initrd_glob': {'required': False, "type": "str", 'default': INITRD_GLOB_DEFAULT},
        'parameters_glob': {'required': False, 'type': 'str', 'default': PARAMETERS_GLOB_DEFAULT}
    }

    # Endpoint Information
    fields.update({
        'ims-url': {'required': False, "type": 'str', 'default': IMS_URL_DEFAULT},
        'token-url': {'required': False, "type": 'str', 'default': TOKEN_URL_DEFAULT},
    })

    # S3 Information
    fields.update({
        's3-bucket': {'required': True, 'type': 'str'},
        's3-access-key': {'required': True, 'type': 'str'},
        's3-secret-key': {'required': True, 'type': 'str'},
        's3-host': {'required': True, 'type': 'str'}
    })

    # Authentication Information
    fields.update({
        'oath-client-id': {'required': False, "type": "str", 'default': OAUTH_CLIENT_ID_DEFAULT},
        'oath-client-secret': {'required': False, "type": 'str', 'default': ''},
        'certificate': {'required': False, "type": "str", "default": CERT_PATH_DEFAULT}
    })

    module = IMSImageUpload(fbh, argument_spec=fields)
    try:
        module()
    except Exception as e:
        module.response['stderr'] = str(e)
        module.fail_json(**module.response)


if __name__ == '__main__':
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    LOGGER.setLevel(logging.DEBUG)
    # Create the logging directory if need be.
    try:
        os.makedirs(LOG_DIR)
    except OSError as ose:
        if ose.errno != 17:
            raise
    _fh = logging.FileHandler(LOG_FILE)
    _fh.setLevel(logging.DEBUG)
    LOGGER.addHandler(_fh)
    fbh = FlushlessBufferingHandler(4096)
    fbh.setLevel(logging.DEBUG)
    LOGGER.addHandler(fbh)
    main(fbh)
