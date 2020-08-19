#!/bin/sh
# Copyright 2019, Cray Inc. All Rights Reserved.

# run pylint and place output in the results
# directory to also be used by SonarQube

mkdir -p /results
pycodestyle -qq --config=/app/.pycodestyle /app/ims || true
pylint ims.app ims | tee /results/pylint.txt 
exit 0
