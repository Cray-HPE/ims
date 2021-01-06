#!/bin/bash
# Copyright 2019, Cray Inc. All Rights Reserved.

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
