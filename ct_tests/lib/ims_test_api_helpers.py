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
Test helper functions for API calls
"""

from ims_test_helpers import add_resource, error_exit, exception_exit, get_field_from_json, get_resource
from ims_test_k8s_helpers import get_k8s_secret
from ims_test_logger import info, section, subtest, debug, warn, error
import requests
import warnings

url_base = "https://api-gw-service-nmn.local"
ims_url_base = "%s/apis/ims" % url_base

token_url="%s/keycloak/realms/shasta/protocol/openid-connect/token" % url_base
ims_images_url_base="%s/images" % ims_url_base
ims_jobs_url_base="%s/jobs" % ims_url_base
ims_public_keys_url_base="%s/public-keys" % ims_url_base
ims_recipes_url_base="%s/recipes" % ims_url_base

#
# IMS endpoint construction functions
#

def ims_url(thing_type, id=None):
    url_base = "{ims_url_base}/{ims_thing_type}s".format(
        ims_url_base=ims_url_base,
        ims_thing_type=thing_type.replace("_","-"))
    if id:
        return "%s/%s" % (url_base, id)
    return url_base

#
# API utility functions
#

def show_response(resp):
    """
    Displays and logs the contents of an API response
    """
    debug("Status code of API response: %d" % resp.status_code)
    for field in ['reason','text','headers']:
        val = getattr(resp, field)
        if val:
            debug("API response %s: %s" % (field, str(val)))

def do_request(method, url, **kwargs):
    """
    Wrapper for call to requests functions. Displays, logs, and makes the request,
    then displays, logs, and returns the response.
    """
    req_args = { "verify": False, "timeout": 30 }
    req_args.update(kwargs)
    debug("Sending %s request to %s with following arguments" % (method.__name__, url))
    for k in req_args:
        debug("%s = %s" % (k, str(req_args[k])))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", 
            category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
        try:
            resp = method(url=url, **req_args)
            show_response(resp)
            return resp
        except Exception as e:
            exception_exit(e, "API request")

def check_response(resp, expected_sc=200, return_json=False):
    """
    Checks to make sure the response has the expected status code. If requested,
    returns the JSON object from thje response.
    """
    if resp.status_code != expected_sc:
        error_exit("Request status code expected to be %d, but was not" % expected_sc)
    if return_json:
        try:
            return resp.json()
        except Exception as e:
            exception_exit(e, "to decode JSON object in response body")

#
# Auth functions
#

def validate_auth_token_response(token_resp):
    auth_token = check_response(resp=token_resp, return_json=True)
    for k in [ "access_token", "refresh_token" ]:
        try:
            if k not in auth_token:
                error_exit("%s field not found in JSON object of response" % k)
        except Exception as e:
            exception_exit(e, "checking %s field from JSON object in response" % k)
    add_resource("auth_token", auth_token)
    return auth_token

def get_auth_token():
    """
    Requests and stores a new auth token
    """
    auth_token = get_resource("auth_token", not_found_okay=True)
    if auth_token != None:
        return auth_token
    info("Getting auth token")
    secret = get_k8s_secret()
    request_data = { 
        "grant_type": "client_credentials",
        "client_id": "admin-client",
        "client_secret": secret }
    token_resp = do_request(method=requests.post, url=token_url, data=request_data)
    auth_token = validate_auth_token_response(token_resp)
    info("Auth token successfully obtained")
    return auth_token

def refresh_auth_token(auth_token):
    """
    Refreshes a previously-obtained auth token
    """
    info("Refreshing auth token")
    secret = get_k8_secret()
    request_data = { 
        "grant_type": "refresh_token",
        "refresh_token": auth_token["refresh_token"],
        "client_id": "admin-client",
        "client_secret": secret }
    token_resp = do_request(method=requests.post, url=token_url, data=request_data)
    auth_token = validate_auth_token_response(token_resp)
    info("Auth token successfully refreshed")
    return auth_token

def do_request_with_auth_retry(method, expected_sc, return_json=False, **kwargs):
    """
    Wrapper to our earlier requests wrapper. This wrapper calls the previous wrapper,
    but if the response indicates an expired token error, then the token is refreshed
    and the request is re-tried with the refreshed token. A maximum of one retry will
    be attempted.
    """
    auth_token = get_auth_token()
    try:
        kwargs["headers"]["Authorization"] = "Bearer %s" % auth_token["access_token"]
    except KeyError:
        kwargs["headers"] = { "Authorization": "Bearer %s" % auth_token["access_token"] }
    resp = do_request(method=method, **kwargs)
    if resp.status_code != 401 or expected_sc == 401:
        if return_json:
            return check_response(resp=resp, expected_sc=expected_sc, return_json=True)
        check_response(resp=resp, expected_sc=expected_sc)
        return resp
    else:
        json_obj = check_response(resp=resp, expected_sc=401, return_json=True)
    try:
        if json_obj["exp"] != "token expired":
            error_exit("Expected response with status code %d" % expected_sc)
    except KeyError:
        error_exit("Expected response with status code %d" % expected_sc)
    debug("Received token expired response (status code 401). Will attempt to refresh auth token and retry request")
    auth_token = refresh_auth_token()
    kwargs["headers"]["Authorization"] = "Bearer %s" % auth_token["access_token"]
    debug("Retrying request")
    resp = do_request(method, *args, **kwargs)
    if return_json:
        return check_response(resp=resp, expected_sc=expected_sc, return_json=True)
    check_response(resp=resp, expected_sc=expected_sc)
    return resp

#
# Requests functions
#

def requests_get(expected_sc=200, **kwargs):
    """
    Calls our above requests wrapper for a GET request, and sets the default expected status code to 200
    """
    return do_request_with_auth_retry(method=requests.get, expected_sc=expected_sc, **kwargs)

def requests_post(expected_sc=201, **kwargs):
    """
    Calls our above requests wrapper for a POST request, and sets the default expected status code to 201.
    If a JSON object is being included in the request, the appropriate content-type field is set in the
    header, if not already set.
    """
    if "json" in kwargs:
        try:
            if "Content-Type" not in kwargs["headers"]:
                kwargs["headers"]["Content-Type"] = "application/json"
        except KeyError:
            kwargs["headers"] = { "Content-Type": "application/json" }
    return do_request_with_auth_retry(method=requests.post, expected_sc=expected_sc, **kwargs)

def requests_delete(expected_sc=204, **kwargs):
    """
    Calls our above requests wrapper for a DELETE request, and sets the default expected status code to 204
    """
    return do_request_with_auth_retry(method=requests.delete, expected_sc=expected_sc, **kwargs)
