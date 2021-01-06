#!/usr/bin/env python3
# Copyright 2020 Cray Inc. All Rights Reserved.

"""
Test helper functions for CLI
"""
 
from ims_test_api_helpers import get_auth_token
from ims_test_helpers import add_resource, error_exit, exception_exit, get_resource, remove_resource, run_cmd_list
from ims_test_logger import info, debug, warn, error
import json
import os
import tempfile

cray_ims_cli_group = {
    "image":        "images",
    "job":          "jobs",
    "public_key":   "public-keys",
    "recipe":       "recipes"
}

def remove_tempfile(second_attempt=False):
    filename = get_resource("auth_tempfile", not_found_okay=second_attempt)
    if filename == None:
        return
    debug("Deleting temporary file created for CLI authentication")
    if second_attempt:
        remove_resource("auth_tempfile")
    if os.path.isfile(filename):
        run_cmd_list(["rm",filename], show_output=False)
    if not second_attempt:
        remove_resource("auth_tempfile")
    debug("Temporary file successfully deleted")

def generate_cli_auth_file():
    # Generate CLI auth token
    info("Generating CLI auth token file")
    auth_token = get_auth_token()
    auth_tempfile = tempfile.mkstemp(prefix="ims-build-test-cli-auth-token-")[1]
    add_resource("auth_tempfile", auth_tempfile, remove_tempfile)
    with open(auth_tempfile, "wt") as f:
        json.dump(auth_token, f)
    info("CLI auth token file successfully created: %s" % auth_tempfile)
    return auth_tempfile

def auth_file():
    auth_tempfile = get_resource("auth_tempfile", not_found_okay=True)
    if auth_tempfile != None:
        return auth_tempfile
    return generate_cli_auth_file()

def cli_argname(argname):
    return "--%s" % argname.replace("_", "-")

def cli_arglist(argmap):
    cli_args = list()
    for argname, argvalue in argmap.items():
        cli_args.extend([cli_argname(argname), str(argvalue)])
    return cli_args

def run_ims_cli_cmd(thing_type, command, *args, parse_json_output=True, return_rc=False):
    auth_tempfile = auth_file()
    cmdlist = [ "cray", "ims", cray_ims_cli_group[thing_type], command, 
        "--format", "json", "--token", auth_tempfile ]
    cmdlist.extend(args)
    cmdresp = run_cmd_list(cmdlist, return_rc=return_rc)
    if parse_json_output:
        try:
            cmdresp["json"] = json.loads(cmdresp["out"])
        except Exception as e:
            exception_exit(e, "to decode a JSON object in the CLI output")
    return cmdresp
