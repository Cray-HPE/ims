#!/bin/sh
#
# MIT License
#
# (C) Copyright 2019-2022 Hewlett Packard Enterprise Development LP
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
set -e
set -o pipefail

mkdir -p /results
python3 -m pip freeze 2>&1 | tee /results/pip_freeze.out

export S3_ENDPOINT=https://rados-gw
export S3_ACCESS_KEY=my_access_key
export S3_SECRET_KEY=my_secret_key
export S3_SSL_VALIDATE=False

pytest -s \
 --cov-report html:/results/coverage_html \
 --cov-report xml:/results/coverage.xml \
 --cov-report term \
 --cov-branch \
 --cov=src \
 --junit-xml=/results/pytest.xml \
 2>&1 | tee /results/pytests.out
