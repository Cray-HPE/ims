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
#
# (MIT License)

"""
IMS-related test helper functions
"""
 
from ims_test_api_helpers import ims_url, requests_delete, requests_get, requests_post
from ims_test_cli_helpers import cli_arglist, run_ims_cli_cmd
from ims_test_helpers import add_resource, error_exit, exception_exit, \
                             get_field_from_json, get_ims_id, get_resource, \
                             store_ims_id, unstore_ims_id
from ims_test_logger import info, debug, warn, error
import random

ssh_public_key_file = "/root/.ssh/id_rsa.pub"

def use_api():
    return get_resource("use_api")

def create_ims_thing(thing_type, *cli_args, **request_args):
    """
    Create an IMS thing of the specified type, using the specified request arguments.
    Store the ID of the resulting thing.
    """
    if use_api():
        url = ims_url(thing_type=thing_type)
        debug("Submitting request to %s to create IMS %s" % (url, thing_type))
        json_obj = requests_post(url=url, return_json=True, **request_args)
    else:
        cmdresp = run_ims_cli_cmd(thing_type, "create", *cli_args)
        json_obj = cmdresp["json"]
    id = get_field_from_json(json_obj, "id")
    store_ims_id(thing_type=thing_type, id=id, cleanup=cleanup_function[thing_type])
    info("IMS %s created successfully (id %s)" % (thing_type, id))
    return json_obj

def delete_ims_thing(thing_type, second_attempt=False):
    """
    If called at the end of a normal test run, an IMS thing of this type should
    exist and its ID should be saved.
    If one is not saved, we exit in error. If it is saved, we delete that
    thing. If that delete fails, we exit in error.

    If called during error cleanup, then we delete the thing if an ID is saved.
    """
    id = get_ims_id(thing_type=thing_type, not_found_okay=second_attempt)
    if id == None:
        return
    info("Deleting IMS %s (id %s)" % (thing_type, id))
    if second_attempt:
        unstore_ims_id(thing_type=thing_type)
    if use_api():
        url = ims_url(thing_type=thing_type, id=id)
        requests_delete(url=url)
    else:
        run_ims_cli_cmd(thing_type, "delete", id, parse_json_output=False)
    if not second_attempt:
        unstore_ims_id(thing_type=thing_type)
    info("Delete request reports success")

def delete_ims_image(second_attempt=False):
    delete_ims_thing(thing_type="image", second_attempt=second_attempt)

def delete_ims_job(second_attempt=False):
    delete_ims_thing(thing_type="job", second_attempt=second_attempt)

def delete_ims_public_key(second_attempt=False):
    delete_ims_thing(thing_type="public_key", second_attempt=second_attempt)

cleanup_function = {
    'image': delete_ims_image,
    'job': delete_ims_job,
    'public_key': delete_ims_public_key }

def verify_ims_thing_deleted(thing_type, id):
    """
    Attempt to retrieve an IMS thing which has been previously deleted. We expect this to fail.
    """    
    info("Attempt to retrieve %s to verify it has been deleted (we expect this to fail)" % thing_type)
    if use_api():
        url = ims_url(thing_type=thing_type, id=id)
        requests_get(url=url, return_json=False, expected_sc=404)
    else:
        cmdresp = run_ims_cli_cmd(thing_type, "describe", id, parse_json_output=False, return_rc=True)
        if cmdresp["rc"] == 0:
            error_exit("IMS %s should have been deleted, but it does not appear to be" % thing_type)
    info("IMS %s successfully deleted" % thing_type)

def get_ims_thing(thing_type):
    """
    Describe the IMS thing whose ID we have previously saved.
    """
    id = get_ims_id(thing_type=thing_type)
    info("Describing IMS %s id %s" % (thing_type, id))
    if use_api():
        url = ims_url(thing_type=thing_type, id=id)
        thing = requests_get(url=url, return_json=True)
    else:
        cmdresp = run_ims_cli_cmd(thing_type, "describe", id, parse_json_output=True)
        thing = cmdresp["json"]
    info("Retrieved %s successfully" % thing_type)
    return thing

def describe_ims_image():
    return get_ims_thing("image")

def describe_ims_job():
    return get_ims_thing("job")

def describe_ims_public_key():
    return get_ims_thing("public_key")

def describe_ims_recipe():
    return get_ims_thing("recipe")

def create_ims_job():
    """
    Start the IMS image build job
    """
    info("Starting IMS build job")
    initrd_name = get_resource("initrd_name")
    kernel_name = get_resource("kernel_name")
    create_args = {
        "image_root_archive_name": "test_%s_%d" % (get_resource("recipe_name"), random.randint(1000000,9999999)),
        "enable_debug": False,
        "public_key_id": get_ims_id("public_key"),
        "artifact_id": get_ims_id("recipe"),
        "job_type": "create" }
    if initrd_name:
        create_args["initrd_file_name"] = initrd_name
    if kernel_name:
        create_args["kernel_file_name"] = kernel_name
    if use_api():
        create_ims_thing("job", json=create_args)
    else:
        create_ims_thing("job", *cli_arglist(create_args))

def create_ims_public_key():
    info("Creating IMS public key")
    create_args = { "name" : "%s build test key" % get_resource("recipe_name") }
    if use_api():
        try:
            with open(ssh_public_key_file) as f:
                create_args["public_key"] = f.read().strip()
        except Exception as e:
            exception_error(e, "Reading %s file" % ssh_public_key_file)
        create_ims_thing("public_key", json=create_args)
    else:
        create_args["public-key"] = ssh_public_key_file
        create_ims_thing("public_key", *cli_arglist(create_args))

def get_k8s_build_job(ims_build_job):
    """
    Describe the IMS build job. From that output, find
    and save the kubernetes build job name.
    """
    info("Retrieving kubernetes job name from IMS build job")
    k8s_job_name = get_field_from_json(ims_build_job, "kubernetes_job")
    info("Kubernetes job name retrieved successfully: %s" % k8s_job_name)
    add_resource("k8s_job_name", k8s_job_name)

def get_resultant_image_id(ims_build_job):
    """
    Describe the IMS build job. From that output, verify that the
    status is successful. Then find and save the resultant image id.
    """
    info("Verifying IMS job status from IMS build job")
    ims_job_status = get_field_from_json(ims_build_job, "status")
    if ims_job_status != "success":
        error_exit("IMS job status should be 'success', but it is not: %s" % ims_job_status)
    info("IMS job status reports successful build. Getting resultant image ID")
    resultant_image_id = get_field_from_json(ims_build_job, "resultant_image_id")
    info("Resultant image ID is %s" % resultant_image_id)
    store_ims_id("image", resultant_image_id, cleanup=delete_ims_image)

def list_ims_recipes():
    """
    Return a list of all IMS recipes.
    """
    info("Requesting IMS recipes list")
    if use_api():
        url = ims_url(thing_type="recipe")
        recipes_list = requests_get(url=url, return_json=True)
    else:
        cmdresp = run_ims_cli_cmd("recipe", "list", parse_json_output = True)
        recipes_list = cmdresp["json"]
    try:
        if len(recipes_list) == 0:
            error_exit("No IMS recipes found")
    except TypeError as e:
        error_exit("Request to IMS did not return a list object as expected: %s" % str(e))
    return recipes_list

def get_ims_recipe_id(recipes_list):
    """
    Find the IMS recipe with the name that was passed into the test.
    Save the IMS id of that recipe.
    """
    recipe_name = get_resource("recipe_name")
    for recipe in recipes_list:
        try:
            if recipe["name"] != recipe_name:
                continue
        except KeyError:
            error_exit("IMS recipe does not have name field: %s" % str(recipe))
        info("Found %s recipe: %s" % (recipe_name, str(recipe)))
        try:
            id = recipe["id"]
            info("%s recipe found with id %s" % (recipe_name, id))
            store_ims_id("recipe", id)
            return
        except KeyError:
            error_exit("IMS recipe does not have id field: %s" % str(recipe))
    error_exit("%s not found in IMS recipes list" % recipe_name)