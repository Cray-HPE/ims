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
General IMS test helper functions.
"""

from ims_test_logger import info, section, subtest, debug, warn, error, verbose_output
import subprocess
import sys
import traceback

resources_created = 0
resources = dict()

#
# Test fatal exit functions
#

def error_exit(msg="Error encountered. Exiting."):
    error(msg)
    info("FAILED")
    resource_cleanup()
    section("Test failed")
    sys.exit(1)

def exception_exit(err, attempting=None):
    if attempting != None:
        error("%s attempting %s: %s" % (str(type(err)), attempting, str(err)))
    else:
        error("Unexpected error encountered: %s: %s" % (str(type(err)), str(err)))
    for line in traceback.format_exception(type(err), err, err.__traceback__):
        info(line.rstrip())
    error_exit()

#
# Utility functions
#

def resource_cleanup():
    """
    Clean up all resources created by test
    """
    section("Doing cleanup (if needed)")
    resources_to_clean = sorted(
        [r for r in resources.values() if r["cleanup"] != None], 
        key=lambda r: r["count"], 
        reverse=True)
    for r in resources_to_clean:
        clean_func = r["cleanup"]
        cleanup_attempted = r["cleanup_attempted"]
        r["cleanup_attempted"] = True
        clean_func(second_attempt=cleanup_attempted)

def get_resource(resource_name, not_found_okay=False):
    try:
        return resources[resource_name]["value"]
    except KeyError:
        if not_found_okay:
            return None
        error_exit("Programming logic error. resources['%s'] should be set, but it is not. resources = %s" % (resource_name, str(resources)))

def ims_thing_id_resource_name(thing_type):
    return "ims_%s_id" % thing_type

def get_ims_id(thing_type, not_found_okay=False):
    resource_name=ims_thing_id_resource_name(thing_type)
    return get_resource(resource_name=resource_name, not_found_okay=not_found_okay)

def add_resource(resource_name, value, cleanup=None):
    global resources_created
    resources[resource_name] = {
        'value': value, 
        'cleanup': cleanup,
        'cleanup_attempted': False,
        'count': resources_created }
    resources_created += 1

def remove_resource(resource_name):
    del resources[resource_name]

def store_ims_id(thing_type, id, cleanup=None):
    resource_name = ims_thing_id_resource_name(thing_type)
    add_resource(resource_name=resource_name, value=id, cleanup=cleanup)

def unstore_ims_id(thing_type):
    resource_name = ims_thing_id_resource_name(thing_type)
    remove_resource(resource_name)

def do_run_cmd(cmd_list, cmd_string, show_output=None, return_rc=False, env_var=None):
    """ 
    Runs the specified command, then displays, logs, and returns the output
    """
    if show_output == None:
        show_output = verbose_output
    info("Running command: %s" % cmd_string)
    run_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "check": not return_rc }
    if env_var != None:
        run_kwargs['env'] = env_var
    if show_output:
        output = info
    else:
        output = debug
    try:
        cmddone = subprocess.run(cmd_list, **run_kwargs)
        cmdout = cmddone.stdout.decode()
        cmderr = cmddone.stderr.decode()
        cmdrc = cmddone.returncode
        output("Command stdout:\n%s" % cmdout)
        output("Command stderr:\n%s" % cmderr)
        output("Command return code: %d" % cmdrc)
        if return_rc:
            return { "rc": cmdrc, "out": cmdout, "err": cmderr }
        return { "out": cmdout }
    except subprocess.CalledProcessError as e:
        error("%s command failed with return code %d" % (
            cmd_string, e.returncode))
        info("Command stdout:\n%s" % e.stdout.decode())
        info("Command stderr:\n%s" % e.stderr.decode())
        error_exit()

def run_cmd_list(cmd_list, **kwargs):
    cmd_string = " ".join(cmd_list)
    return do_run_cmd(cmd_list=cmd_list, cmd_string=cmd_string, **kwargs)

def run_cmd(cmd_string, **kwargs):
    cmd_list = cmd_string.split()
    return do_run_cmd(cmd_list=cmd_list, cmd_string=cmd_string, **kwargs)

def get_field_from_json(json_obj, field):
    """
    Returns the requested field from the specified JSON object, raising a fatal error
    if it is not found.
    """
    try:
        return json_obj[field]
    except KeyError:
        error_exit("No %s field found in JSON object" % field)
