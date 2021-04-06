# Copyright 2020-2021 Hewlett Packard Enterprise Development LP
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

"""
Kubernetes-related test helper functions
"""

import base64
from ims_test_helpers import add_resource, error_exit, exception_exit, get_resource, run_cmd
from ims_test_logger import info, debug, warn, error
import kubernetes
import re
import time
import warnings
import yaml

k8s_pod_created_pattern = "^Created pod:\s\s*(\S\S*)$"
k8s_pod_created_prog = re.compile(k8s_pod_created_pattern)

def k8s_client():
    """
    Initializes the kubernetes client instance (if needed) and
    returns it.
    """
    kc = get_resource("k8s_client", not_found_okay=True)
    if kc != None:
        return kc
    debug("Initializing kubernetes client")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=yaml.YAMLLoadWarning)
        kubernetes.config.load_kube_config()
    kc = kubernetes.client.CoreV1Api()
    add_resource("k8s_client", kc)
    return kc

def get_k8s_secret():
    """
    Returns the kubernetes admin-client-auth secret string
    """
    debug("Getting client secret from kubernetes")
    k8s_secret = k8s_client().read_namespaced_secret(name="admin-client-auth", namespace="default")
    k8sec = k8s_secret.data["client-secret"]
    debug("Client secret is %s" % k8sec)
    debug('Decoding client secret from base64')
    secret = base64.b64decode(k8sec)
    debug("Decoded secret is %s" % secret)
    return secret

def get_k8s_pod_name_from_k8s_event(e):
    """
    Determine if this kubernetes event records the creation of the image
    build pod. If so, return the name of that pod.
    """
    if e.involved_object.kind != "Job":
        return None
    elif e.involved_object.name != get_resource("k8s_job_name"):
        return None
    elif e.involved_object.namespace != "ims":
        return None
    elif e.reason != "SuccessfulCreate":
        return None
    result = k8s_pod_created_prog.match(e.message.strip())
    if result:
        return result.group(1)
    return None

def run_k8s_describe_cmd(resource_type, resource_name):
    """
    Run the kubectl command to describe the specified kubernetes object.
    """
    k8s_describe_command = "kubectl -n ims describe %s %s" % (resource_type, resource_name)
    run_cmd(k8s_describe_command)

def get_k8s_build_pod_name():
    """
    Review the kubernetes events to find the one reporting the creation of the
    image build pod. Save the name of the pod if found.
    """
    info("Getting kubernetes build pod name")
    for i in [ 1, 2 ]:
        if i == 2:
            info("Unable to get kubernetes pod name. Will retry after 5 seconds.")
            time.sleep(5)
        k8s_eventlist = k8s_client().list_namespaced_event(namespace="ims").items
        for event in k8s_eventlist:
            pod_name = get_k8s_pod_name_from_k8s_event(event)
            if pod_name != None:
                info("Successfully determined build pod name: %s" % pod_name)
                add_resource("k8s_pod_name", pod_name)
                return
    error("Kubernetes pod name not found in kubernetes event data")
    print("Full kubernetes event list for ims:")
    print(k8s_eventlist)
    k8s_job_name = get_resource("k8s_job_name")
    run_k8s_describe_cmd("job", k8s_job_name)
    error_exit("Unable to get kubernetes pod name")

ims_build_init_containers = { "fetch-recipe", "wait-for-repos", "build-ca-rpm", "build-image" }

def wait_until_container_start(container_name):
    """
    Wait until kubernetes reports that the requested container has started (that is,
    either running or terminated)
    """
    pod_name = get_resource("k8s_pod_name")
    max_wait_seconds=60
    for i in range(max_wait_seconds):
        if i > 0:
            time.sleep(1)
        pod = k8s_client().read_namespaced_pod(name=pod_name, namespace="ims")
        if container_name in ims_build_init_containers:
            statuses = pod.status.init_container_statuses
        else:
            statuses = pod.status.container_statuses
        if statuses:
            try:
                statuslist = [ s for s in statuses ]
            except TypeError:
                continue
        else:
            continue
        for cs in statuses:
            if cs.name == container_name:
                if cs.state.running != None:
                    info("Container is running")
                    return
                elif cs.state.terminated != None:
                    info("Container terminated")
                    return
    label = "Kubernetes container %s in pod %s" % (container_name, pod_name)
    error("%s not started even after retrying for %d seconds" % (label, max_wait_seconds))
    run_k8s_describe_cmd("pod", pod_name)
    error_exit("%s not started even after retrying for %d seconds" % (label, max_wait_seconds))

def show_k8s_container_log(container_name):
    """
    Display and log the kubernetes container log.
    """
    pod_name = get_resource("k8s_pod_name")
    label = "container %s in pod %s" % (container_name, pod_name)
    info("Waiting for kubernetes %s" % label)
    wait_until_container_start(container_name)
    info("Getting kubernetes log for %s" % label)
    run_cmd("kubectl -n ims logs -f %s -c %s" % (pod_name, container_name))
    info("Successfully got log for %s" % label)
