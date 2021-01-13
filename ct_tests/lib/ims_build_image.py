#!/usr/bin/env python3
# Copyright 2020 Cray Inc. All Rights Reserved.

"""
Usage: <ims_build_image.py> [-i <initrd_name>] [-k <kernel name>] [-v] {api|cli} <recipe_name>

Uses the IMS API or CLI to test building an image using the 
specified recipe. 

Some output is sent to stdout/stderr. More extensive
output is logged in:
/opt/cray/tests/ims-build-<recipe_name>.log

Exits with 0 return code if successful, 1 otherwise.
"""

from ims_build_image_argparse import parse_args 
from ims_test_api_helpers import \
    ims_url, requests_delete, requests_get, requests_post
from ims_test_cli_helpers import cli_arglist, run_ims_cli_cmd
from ims_test_helpers import \
    add_resource, error_exit, exception_exit, get_ims_id, get_resource, \
    resource_cleanup, run_cmd_list
from ims_test_ims_helpers import \
    create_ims_job, create_ims_public_key, delete_ims_thing, \
    describe_ims_image, describe_ims_job, describe_ims_public_key, \
    describe_ims_recipe, get_ims_recipe_id, get_k8s_build_job, \
    get_resultant_image_id, list_ims_recipes, verify_ims_thing_deleted
from ims_test_k8s_helpers import get_k8s_build_pod_name, show_k8s_container_log
from ims_test_logger import info, init_logger, section, subtest, debug, warn, error
import json
import os
import random
import sys
import tempfile
import time

def do_test():
    subtest("List IMS recipes")
    recipes_list = list_ims_recipes()
    
    recipe_name = get_resource("recipe_name")
    subtest("Get IMS recipe ID of %s" % recipe_name)
    get_ims_recipe_id(recipes_list)
    
    subtest("Describe IMS recipe")
    describe_ims_recipe()

    subtest("Create IMS public key")
    create_ims_public_key()
    
    subtest("Describe IMS public key")
    describe_ims_public_key()

    subtest("Start IMS build job")
    create_ims_job()

    subtest("Describe IMS build job")
    ims_build_job = describe_ims_job()

    subtest("Get name of kubernetes job")
    get_k8s_build_job(ims_build_job)

    subtest("Get name of kubernetes pod")
    get_k8s_build_pod_name()

    for cname in [ "fetch-recipe", "wait-for-repos", "build-ca-rpm", "build-image", "buildenv-sidecar" ]:
        subtest("Show kubernetes log for %s container" % cname)
        show_k8s_container_log(cname)

    subtest("Describe IMS build job")
    ims_build_job = describe_ims_job()

    subtest("Get resultant image ID")
    get_resultant_image_id(ims_build_job)

    subtest("Examine resultant IMS image")
    describe_ims_image()

    for thing_type in [ "job", "image", "public_key" ]:
        subtest("Deleting IMS %s" % thing_type)
        # Have to remember the ID since we will remove it from our resource store in the delete function
        id = get_ims_id(thing_type=thing_type)
        delete_ims_thing(thing_type=thing_type)

        subtest("Attempt to retrieve deleted IMS %s" % thing_type)
        verify_ims_thing_deleted(thing_type=thing_type, id=id)

    subtest("Doing final test cleanup")
    resource_cleanup()

    section("Test passed")

if __name__ == '__main__':
    test_parameters = parse_args()
    clean_recipe_name = ''.join([c for c in test_parameters["recipe_name"] if c.isalnum() or c in { '-', '_' }])
    init_logger(logfile_suffix=clean_recipe_name, verbose=test_parameters["verbose"])
    info("Starting test")
    debug("Arguments: %s" % sys.argv[1:])
    info("Recipe name: %s" % test_parameters["recipe_name"])
    if test_parameters["initrd_name"] != None:
        info("Initrd name: %s" % test_parameters["initrd_name"])
    if test_parameters["kernel_name"] != None:
        info("Kernel name: %s" % test_parameters["kernel_name"])
    if test_parameters["use_api"]:
        info("Using IMS API")
    else:
        info("Using IMS CLI")
    for k in [ "recipe_name", "initrd_name", "kernel_name", "use_api" ]:
        add_resource(k, test_parameters[k])
    try:
        do_test()
    except Exception as e:
        # Adding this here to do cleanup when unexpected errors are hit (and to log those errors)
        exception_exit(e)
    sys.exit(0)