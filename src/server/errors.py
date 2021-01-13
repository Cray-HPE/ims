"""
API Error formatting for the Artifact Repository Service which conforms to
RFC 7807. Also, some frequently used errors encapsulated in functions.
Copyright 2018-2020 Hewlett Packard Enterprise Development LP
"""
import http.client

from flask import Response
from httpproblem import problem_http_response


def problemify(*args, **kwargs):
    """
    Wrapper for httpproblem.problem_http_response that returns a Flask
    Response object. Conforms to RFC7807 HTTP Problem Details for HTTP APIs.

    Args:
        Same as httpproblem.problem_http_response. See https://tools.ietf.org/html/rfc7807
        for details on these fields and
        https://github.com/cbornet/python-httpproblem/blob/master/httpproblem/problem.py#L34
        for an explanation.

        problem_http_response kwargs:
            **status
            **title
            **detail
            **type
            **instance
            **kwargs   <-- extension members per RFC 7807

    Returns: flask.Response object of an error in RFC 7807 format
    """
    problem = problem_http_response(*args, **kwargs)
    return Response(problem['body'], status=problem['statusCode'], headers=problem['headers'])


def generate_missing_input_response():
    """
    No input was provided. Reports 400 - Bad Request.

    Returns: results of problemify
    """
    return problemify(status=http.client.BAD_REQUEST,
                      detail='No input provided. Determine the specific information that is missing or invalid and '
                             'then re-run the request with valid information.')


def generate_data_validation_failure(errors):
    """
    Validation errors in input data. Reports 422 - Unprocessable entity

    Args:
        errors: dictionary of errors from Marshmallow schema loads method.

    Returns: results of problemify
    """
    return problemify(status=http.client.UNPROCESSABLE_ENTITY,
                      title='Unprocessable Entity',
                      detail='Input data was understood, but failed validation. Re-run request with valid input values '
                             'for the fields indicated in the response.',
                      errors=errors)


def generate_resource_not_found_response():
    """
    Resource with given id was not found. Reports 404 - Not Found.

    Returns: results of problemify
    """
    return problemify(status=http.client.NOT_FOUND,
                      detail='Requested resource does not exist. Re-run request with valid ID.')


def generate_patch_conflict():
    """
    Resource with given id was found, but cannot be patched due to conflict. Reports 415 - Not Found.

    Returns: results of problemify
    """
    return problemify(status=http.client.CONFLICT,
                      detail='Requested resource exists, but cannot be patched due to a patch conflict. '
                             'Re-run request with valid input values.')
