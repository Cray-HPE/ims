#!/bin/sh
# Copyright 2019, Cray Inc. All Rights Reserved.

set -e
set -o pipefail

mkdir -p /results
python3 -m pip freeze 2>&1 | tee /results/pip_freeze.out

export S3_ENDPOINT=rados-gw
export S3_ACCESS_KEY=my_access_key
export S3_SECRET_KEY=my_secret_key

pytest -s \
 --cov-report html:/results/coverage_html \
 --cov-report xml:/results/coverage.xml \
 --cov-report term \
 --cov-branch \
 --cov=ims \
 --junit-xml=/results/pytest.xml \
 2>&1 | tee /results/pytests.out
