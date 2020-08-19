#!/bin/sh
# Copyright 2020, Cray Inc. All Rights Reserved.

docker rmi -f ims-service-unittests:latest
docker build --target testing -t ims-service-unittests -f Dockerfile.service .
docker run ims-service-unittests:latest
