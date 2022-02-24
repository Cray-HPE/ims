# Cray Image Management Service Dockerfile
## Copyright 2018, 2021-2022 Hewlett Packard Enterprise Development LP
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
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# (MIT License)

# Create 'base' image target
FROM artifactory.algol60.net/docker.io/library/alpine:3.13 as base
WORKDIR /app
RUN mkdir -p /var/ims/data /app /results && \
    chown -Rv 65534:65534 /var/ims/data /app /results
VOLUME ["/var/ims/data", "/results"]

RUN apk add --upgrade --no-cache apk-tools && \
    apk update && \
    apk add --no-cache gcc py3-pip python3-dev musl-dev libffi-dev openssl-dev && \
    apk -U upgrade --no-cache

USER 65534:65534

ADD requirements.txt constraints.txt /app/
ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN PIP_INDEX_URL=https://arti.dev.cray.com:443/artifactory/api/pypi/pypi-remote/simple \
    PIP_TRUSTED_HOST=arti.dev.cray.com \
    pip3 install --no-cache-dir -U pip && \
    pip3 install --no-cache-dir -U wheel && \
    pip3 install --no-cache-dir -r requirements.txt

# Install server
COPY src/ /app/src/

# Run unit tests
FROM base as testing

ADD docker_test_entry.sh /app/
ADD requirements-test.txt /app/
RUN pip3 install -r /app/requirements-test.txt

COPY tests /app/tests
ARG FORCE_TESTS=null
CMD [ "./docker_test_entry.sh" ]

# Run openapi validation on openapi.yaml
# NOTE: at this time the openapi-generator-cli base image has CVE vulnerabilities
# that we can't resolve.  Uncomment the below to use for testing and validation.
# FROM arti.dev.cray.com/third-party-docker-stable-local/openapitools/openapi-generator-cli:v5.1.0 as openapi-validator
# RUN mkdir /tmp/api
# COPY api/openapi.yaml /tmp/api/
# ARG FORCE_OPENAPI_VALIDATION_CHECK=null
# RUN docker-entrypoint.sh validate -i /tmp/api/openapi.yaml || true

# Run code style checkers
FROM testing as codestyle
ADD .pylintrc .pycodestyle /app/
ADD runCodeStyleCheck.sh /app/
ARG FORCE_STYLE_CHECKS=null
CMD [ "./runCodeStyleCheck.sh" ]

# Build Application Image
FROM base as application

EXPOSE 9000
# RUN apk add --no-cache py3-gunicorn py3-gevent py3-greenlet
COPY .version /app/
COPY config/gunicorn.py /app/
ENTRYPOINT ["gunicorn", "-c", "/app/gunicorn.py", "src.server.app:app"]
