#!/usr/bin/env python3
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
Test helper functions for CLI
"""
 
from ims_test_api_helpers import get_auth_token
from ims_test_helpers import add_resource, error_exit, exception_exit, get_resource, remove_resource, run_cmd_list
from ims_test_logger import info, debug, warn, error
import json
import os
import tempfile

config_tempfile = None

cray_cli = "/usr/bin/cray"

config_error_strings = [
    "Unable to connect to cray",
    "verify your cray hostname",
    "core.hostname",
    "No configuration exists",
    "cray init" ]

cli_config_file_text = """\
[core]
hostname = "https://api-gw-service-nmn.local"
"""

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

def generate_cli_config_file(prefix=None):
    """
    Write CLI config file text to a file and return the filename
    """
    global config_tempfile
    if prefix == None:
        prefix = "cms-test-cli-config-file-"
    else:
        prefix = "%s-cli-config-file-" % prefix
    with tempfile.NamedTemporaryFile(mode="wt", prefix=prefix, delete=False) as f:
        config_tempfile = f.name
        f.write(cli_config_file_text)
    info("CLI config file successfully created: %s" % config_tempfile)
    return config_tempfile

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

def config_env():
    env_var = os.environ.copy()
    if config_tempfile:
        env_var["CRAY_CONFIG"] = config_tempfile
    else:
        env_var["CRAY_CONFIG"] = generate_cli_config_file()
    info("Environment variable CRAY_CONFIG set to '%s' for CLI command execution" % env_var["CRAY_CONFIG"])
    return env_var

def cli_argname(argname):
    return "--%s" % argname.replace("_", "-")

def cli_arglist(argmap):
    cli_args = list()
    for argname, argvalue in argmap.items():
        cli_args.extend([cli_argname(argname), str(argvalue)])
    return cli_args

def run_ims_cli_cmd(thing_type, command, *args, parse_json_output=True, return_rc=False):
    auth_tempfile = auth_file()
    cmdlist = [ cray_cli, "ims", cray_ims_cli_group[thing_type], command, 
        "--format", "json", "--token", auth_tempfile ]
    cmdlist.extend(args)
    if config_tempfile:
        # Specify our own config file via environment variable
        cmdresp = run_cmd_list(cmdlist, return_rc=return_rc, env_var=config_env())
    else:
        # Let's try CLI command without our own config file first.
        cmdresp = run_cmd_list(cmdlist, return_rc=True)
        if cmdresp["rc"] != 0:
            if any(estring in cmdresp["err"] for estring in config_error_strings):
                info("CLI command failure may be due to configuration error. Will generate our own config file and retry")
                cmdresp = run_cmd_list(cmdlist, return_rc=True, env_var=config_env())
                if cmdresp["rc"] != 0:
                    info("CLI command failed even using our CLI config file.")
                    error("%s command failed with return code %d" % (
                        " ".join(cmdlist), cmdresp["rc"]))
                    info("Command stdout:\n%s" % cmdresp["out"])
                    info("Command stderr:\n%s" % cmdresp["err"])
                    error_exit()
                elif not return_rc:
                    # Command passed but user did not request return code in the response, so let's remove it
                    del cmdresp["rc"]
            else:
                info("CLI command failed and does not appear to be obviously related to the CLI config")
                error("%s command failed with return code %d" % (
                    " ".join(cmdlist), cmdresp["rc"]))
                info("Command stdout:\n%s" % cmdresp["out"])
                info("Command stderr:\n%s" % cmdresp["err"])
                error_exit()
        elif not return_rc:
            # Command passed but user did not request return code in the response, so let's remove it
            del cmdresp["rc"]
    if parse_json_output:
        try:
            cmdresp["json"] = json.loads(cmdresp["out"])
        except Exception as e:
            exception_exit(e, "to decode a JSON object in the CLI output")
    return cmdresp
