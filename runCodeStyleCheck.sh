#!/bin/sh
# Copyright 2019-2020 Hewlett Packard Enterprise Development LP

# run pylint and place output in the results
# directory to also be used by SonarQube

mkdir -p /results
pycodestyle --config=/app/.pycodestyle /app/src/server || true
pylint --rcfile=/app/.pylintrc src | tee /results/pylint.txt
exit 0
