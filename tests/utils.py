#
# MIT License
#
# (C) Copyright 2018-2019, 2021-2022 Hewlett Packard Enterprise Development LP
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
"""
Test Utilities
"""

# Format for read/write of test data datetime strings
DATETIME_STRING = '%Y-%m-%dT%H:%M:%S'

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
