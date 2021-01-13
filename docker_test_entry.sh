#!/bin/sh
# Copyright 2019-2020 Hewlett Packard Enterprise Development LP

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
