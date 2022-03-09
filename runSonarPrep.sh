#!/bin/bash
#
# MIT License
#
# (C) Copyright 2019, 2021-2022 Hewlett Packard Enterprise Development LP
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
# extract coverage.xml to replace container file paths
# with local ones
cd results
tar -ztvf buildResults.tar.gz
tar -xzf buildResults.tar.gz
rm -rf buildResults.tar.gz
cp testing/*.xml .

SOURCE="${WORKSPACE}/"
sed -i "s|/app|$SOURCE|" coverage.xml

# Update the version for Sonarqube dynamically
IMS_VERSION="`cat ${WORKSPACE}/.version`"
echo IMS_VERSION=$IMS_VERSION
sed -i "s|@IMS_VERSION@|$IMS_VERSION|" ${WORKSPACE}/sonar-project.properties

# output coverage for troubleshooting if needed
cat coverage.xml
