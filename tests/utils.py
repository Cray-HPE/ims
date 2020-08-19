"""
Test Utilities
Copyright 2018, 2019, Cray Inc. All Rights Reserved.
"""


def check_error_responses(testcase, response, status_code, fields):
    """
    Helper function for checking error responses. Checks the following:

    * Status code is as expected
    * Content-Type header is application/problem+json
    * Fields in the error response match `fields` provided
    * Status code of response matches status code reported in error data

    Args:
        testcase: the TestCase instance (self)
        response: the response object from the Flask test client
        status_code: expected status code in the response
        fields: fields to check for in error response

    Returns: Nothing. Asserts are made on the testcase.
    """
    testcase.assertEqual(response.status_code, status_code, 'status code was not as expected')
    testcase.assertEqual(response.headers['Content-Type'], 'application/problem+json',
                         'problem content type was not correct')
    testcase.assertItemsEqual(response.json.keys(), fields, 'error fields were not as expected')
    testcase.assertEqual(response.status_code, response.json['status'],
                         'response status code and error status code were not equal')
