#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2020-2022 Hewlett Packard Enterprise Development LP
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
The purpose of this ansible module is to read in a S3 credentials secret from
Kubernetes and respond with the decoded access and secret keys.
"""
import base64
import json

from ansible.module_utils.basic import AnsibleModule
from kubernetes import client, config
from kubernetes.client.api_client import ApiClient
from kubernetes.client.configuration import Configuration
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException


ANSIBLE_METADATA = {
    'metadata_version': '2.5',
    'status': ['preview', 'stableinterface'],
    'supported_by': 'community'
}

DOCUMENTATION = """
---
module: shasta_s3_creds

short_description: Retrieve S3 credentials from Shasta Kubernetes secrets

version_added: "2.8"

description:
    - Retrieve S3 credentials stored in Kubernetes secrets
    - Return the decoded access key and secret key

options:
    k8s_secret:
        required: True
        type: String
    k8s_namespace:
        required: False
        type: String
        default: default

author:
    - rkleinman
"""

EXAMPLES = """
- name: Retrieve credentials from abc-s3-credentials k8s secret
  shasta_s3_creds:
    k8s_secret: abc-s3-credentials
    k8s_namespace: default
  register: creds
  no_log: true

- name: Upload a file to a bucket
  no_log: true
  aws_s3:
    bucket: boot-images
    object: adb41c86-0bdf-4180-bfbf-ab049028274d/manifest.json
    src: /tmp/manifest.json
    mode: put
    encrypt: no
    rgw: true
    s3_url: "http://rgw.local:8080"
    aws_access_key: "{{ creds.access_key }}"
    aws_secret_key: "{{ creds.secret_key }}"
"""

RETURN = """
access_key:
    description: The access key stored in the k8s secret
    type: str
    returned: always
secret_key:
    description: The secret key stored in the k8s secret
    type: str
    returned: always
"""


def run_module():
    module_args = dict(
        k8s_secret=dict(type='str', required=True),
        k8s_namespace=dict(type='str', required=False, default="default")
    )
    result = dict(
        changed=False,
        access_key='',
        secret_key=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if module.check_mode:
        module.exit_json(**result)

    # Load K8S Configuration
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()

    configuration = Configuration()
    k8sclient = ApiClient(configuration=configuration)
    coreapi = client.CoreV1Api(k8sclient)

    # Read the secret
    try:
        secret = coreapi.read_namespaced_secret(
            module.params['k8s_secret'], module.params['k8s_namespace']
        )
    except ApiException as err:
        module.fail_json(msg=json.loads(err.body)['message'], **result)
        pass

    if 'access_key' not in secret.data:
        module.fail_json(
            msg='Secret %r has no access_key' % module.params['k8s_secret'],
            **result
        )
    if 'secret_key' not in secret.data:
        module.fail_json(
            msg='Secret %r has no secret_key' % module.params['k8s_secret'],
            **result
        )

    # Record the result
    result['access_key'] = base64.b64decode(secret.data['access_key'])
    result['secret_key'] = base64.b64decode(secret.data['secret_key'])
    result['changed'] = True
    module.exit_json(**result)


if __name__ == '__main__':
    run_module()
