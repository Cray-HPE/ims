#
# MIT License
#
# (C) Copyright 2023-2024 Hewlett Packard Enterprise Development LP
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

import subprocess
import requests
import os
import json
from requests.exceptions import HTTPError, ConnectionError
from kubernetes import client, config

VAULT_SERVICE_ENDPOINT_CLUSTER = 'http://cray-vault.vault:8200'
VAULT_SERVICE_ENDPOINT_EXTERNAL = 'https://api-gw-service-nmn.local/apis/vault'
VAULT_VERSION = 'v1'
TRANSIT_KEY = 'ecdsa-p384-compute-imsssh-key'
ROLE = 'ssh_user_certs_compute'

def get_kube_token():
    try:
        proc = subprocess.Popen(
            ['cat', '/var/run/secrets/kubernetes.io/serviceaccount/token'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        oe = proc.communicate()[0]
    except Exception as e:
        print("Failed reading in service account token")
        return None
    return oe.decode('utf-8')

def generate_public_key(app):
    try:
        proc = subprocess.Popen(
            ['ssh-keygen', '-y', '-f', '/app/id_ecdsa'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
        oe, _ = proc.communicate()
        oe = oe.decode('utf-8')
        export_public_key(app, oe)
        return oe
    except Exception as e:
        print(f"Failed generating ssh keys. Error: {e}")
    return None

def generate_auth_endpoint():
    endpoint = '%s/%s/auth/kubernetes/login' %(VAULT_SERVICE_ENDPOINT_CLUSTER, VAULT_VERSION)
    return endpoint

def generate_transit_endpoint():
    endpoint = '%s/%s/transit/keys/%s' %(VAULT_SERVICE_ENDPOINT_CLUSTER, VAULT_VERSION, TRANSIT_KEY)
    return endpoint

def generate_certificate_signing_endpoint():
    endpoint = '%s/%s/%s/sign/compute' %(VAULT_SERVICE_ENDPOINT_CLUSTER, VAULT_VERSION, ROLE)
    return endpoint

def generate_signing_key_endpoint():
     endpoint = '%s/%s/transit/export/signing-key/%s' %(VAULT_SERVICE_ENDPOINT_CLUSTER, VAULT_VERSION, TRANSIT_KEY)
     return endpoint

def vault_authentication(app, kube_token):
    token_payload = {'jwt': kube_token, 'role': 'ssh-user-certs-compute'}
    try:
        response = requests.post(generate_auth_endpoint(), token_payload )
        response.raise_for_status()
        json_obj = json.loads(response.text)
        token = json_obj['auth']['client_token']
        return {'X-Vault-Token': token}
    except HTTPError as err:
        app.logger.error("Failed to authenticate with vault: %s", err)
        raise

def create_exportable_key(app):
    payload = {"type": "ecdsa-p384", "exportable": "true"}
    try:
        response = requests.post(generate_transit_endpoint(), headers=vault_authentication(app, get_kube_token()), json=payload)
        response.raise_for_status()
    except HTTPError as err:
        app.logger.error(("Failed to create exportable key in vault: %s", err))
        raise

def get_exportable_key(app):
    try:
        response = requests.get(generate_signing_key_endpoint(), headers=vault_authentication(app, get_kube_token()))
        response.raise_for_status()
        values = json.loads(response.text)
        key = values['data']['keys']['1']
        return key
    except HTTPError as err:
        app.logger.error("Failed to get exportable key from vault: %s", err)
    return None

def export_private_key(app, private_key):
    # This will throw an error on attempting to write a null
    if private_key == None:
        app.logger.error("Attempting to write an empty private key")
        return
    
    with open('id_ecdsa', 'w') as local_private_key:
        local_private_key.write(private_key)
    os.chmod('id_ecdsa', 0o600)

def export_public_key(app, public_key):
    # This will throw an error on attempting to write a null
    if public_key == None:
        app.logger.error("Attempting to write an empty public key")
        return

    with open('id_ecdsa.pub', 'w') as local_public_key:
        local_public_key.write(public_key)
    os.chmod('id_ecdsa.pub', 0o600)

def read_file(path):
    with open(path, mode='r') as f:
        file = f.read()
    return file

def sign_public_key(app, public_key):
    payload = {"public_key": public_key, "ttl": "87600h", "valid_principals": "root", "key_id": "ims compute node root"}
    try:
        response = requests.post(generate_certificate_signing_endpoint(), headers=vault_authentication(app, get_kube_token()), json=payload)
        response.raise_for_status()
        values = json.loads(response.text)
        certificate = values['data']['signed_key']
        return certificate
    except HTTPError as err:
        app.logger.info("Failed to sign public key: %s", err)
    return None

def export_certificate(certificate):
    with open('id_ecdsa.pub.cert', 'w') as local_certificate:
        local_certificate.write(certificate)
    os.chmod('id_ecdsa.pub.cert', 0o640)

def create_configmap_object(key_path, cert_path, pub_path, namespace):
    metadata = client.V1ObjectMeta(name="cray-ims-remote-keys", namespace=namespace)
    configmap = client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        data=dict(private_key=read_file(key_path), certificate=read_file(cert_path), public_key=read_file(pub_path)),
        metadata=metadata
    )
    return configmap

def post_config_map(app, config_map, namespace):
    config.load_incluster_config()
    client_api = client.CoreV1Api()
    try:
        api = client_api.create_namespaced_config_map(namespace=namespace, body=config_map)
    except Exception as exception:
        app.logger.info("Failed to create k8s key config map: %s", exception)

def get_config_map(app):
    config.load_incluster_config()
    client_api = client.CoreV1Api()
    try:
        cm = client_api.read_namespaced_config_map(name="cray-ims-remote-keys", namespace="services")
        return cm
    except Exception as exception:
        app.logger.info("Remote keys configmap not found")
    return None

def generate_ca(app):
    create_exportable_key(app)
    export_private_key(app, get_exportable_key(app))
    export_certificate(sign_public_key(app, generate_public_key(app)))

def remote_node_key_setup(app):
    # do not fail - this key is not essential to the running of IMS
    # NOTE: after this the private key needs to exist at /app/ssh/id_rsa
    #       for the remote build options to work
    try:
        # if key already exists, do nothing
        keys = get_exportable_key(app)
        cm = get_config_map(app)
        if keys != None and cm != None:
            # Copy the keys into files
            export_private_key(app, keys)
            app.logger.info("Remote build node ssh keys already exist")
            return 

        # need to generate the key
        app.logger.info(f"Attempting to generate remote build node ssh keys in {os. getcwd()}")
        generate_ca(app)
        post_config_map(app, create_configmap_object('id_ecdsa', 'id_ecdsa.pub.cert', 'id_ecdsa.pub', "services"), "services")
        post_config_map(app, create_configmap_object('id_ecdsa', 'id_ecdsa.pub.cert', 'id_ecdsa.pub', "ims"), "ims")
    except Exception as err:
        # remote builds are not required, don't let this crash the entire system
        app.logger.info(f"Unable to generate remote build node ssh keys - remote builds not enabled. Error: {err}")
