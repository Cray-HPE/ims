# IMS Development Guide

## Overview

The IMS (Image Management Service) Development Guide provides information on how to develop and extend the IMS system. It covers the architecture, components, and best practices for working with IMS.

## Architecture

### Technology Stack
 - Flask - The IMS application is built as a Flask web application.
 - Gunicorn - The application server used to run the Flask application in production.
 - Marshmallow - Used for data serialization and validation.
 - Jinja2 - Templating engine for rendering K8S job definition templates.
 - Boto3 - AWS SDK for Python, used for interacting with S3 artifact repository.
 - Kubernetes Python Client - Used for interacting with the Kubernetes cluster to launch jobs.

### Jobs Launched to do the work

The actual work of building and customizing images is done through Kubernetes jobs launched by the IMS service.
Each job runs in its own pod. There is anti-affinity set up to try and spread the jobs across nodes in the cluster
as they may be resource intensive. Remote build nodes may be set up to offload the work from the cluster nodes both
for better job performance and to relieve resource contention on the cluster nodes.

#### Image Creation Jobs

The image creation jobs start with a recipe artifact and create a container based on the
`ims-kiwi-ng-opensuse-x86_64-builder' image. The workflow consists of several sequential stages.
Each stage is implemented as a separate init container within the job pod. The stages are as follows:

Init Container Stages:
1) fetch-recipe: Downloads and extracts the gzipped recipe archive from S3, verifying the MD5 checksum
1) wait-for-repos: Validates that all HTTP/HTTPS repositories referenced in the Kiwi-NG recipe are accessible
1) build-ca-rpm: Creates an RPM package containing the system's private root CA certificate for secure Nexus repository access
1) build-image: Executes Kiwi-NG to build the image root according to the recipe specifications

Container Stages:
1) sshd: Provides an SSH server for user access to the build environment if debugging is enabled and the build failed
1) buildenv-sidecar: Handles post-build image packaging and upload to S3

Key Features:
* Automatic CA Installation: IMS dynamically installs the NCN Certificate Authority's public certificate to
/etc/cray/ca/certificate_authority.crt within the image root
* Artifact Management: Successful builds automatically uploads artifacts to S3 to be used by BOS during the boot process
* DKMS Support: Recipes can specify DKMS modules to be built and included in the image
* Debug Support: Failed builds can enable an SSH debug shell for troubleshooting when enable_debug=true

#### Image Customization Jobs

The image customization jobs start with an existing image artifact and creates a container where it is
unpacked and an environment is started where a user may SSH into the container and make changes to the
image. When all changes are complete, the environment is torn down and the completed image is packaged
back into an artifact and uploaded to S3. This is the mechanism used by CFS to customize images via
Ansible playbooks.

Init Container Stages:
1) prepare: Downloads and extracts the squashfs image from S3, verifying the MD5 checksum

Container Stages:
1) sshd: Provides an SSH server for user access to the customization environment
1) buildenv-sidecar: Handles post-customization image packaging and upload to S3

Key Features:
* User Access: Users can SSH into the customization environment to make changes directly to the image
* Access Keys: An SSH public key is specified with the job for passwordless access
* Artifact Management: Completed customizations are automatically packaged and uploaded to S3
* DKMS Support: Customizations can include DKMS modules to be built and included in the image

#### Remote Jobs

See the [IMS Remote Build Nodes](README.Remote-Nodes.md) document for more information on remote build nodes.

#### The IMS Namespace and Security

In order to make the required changes to an image being customized, the IMS jobs need to run with elevated
privileges. To limit the security impact of this, the IMS jobs are run in a separate namespace.

The IMS service runs in the 'services' namespace with all other CSM services. The IMS jobs are launched
in the 'ims' namespace. This is done to separate the IMS jobs from the resources in the 'services' namespace.
In K8S the configuration maps, and secrets are namespace specific, so the IMS jobs cannot access the CSM
resources if a user manages to break out of the job pod they are interacting with.

If kernel modifications are required during image creation, the IMS jobs may be run using even higher levels
of privilege. To secure this as much as possible, these jobs are also run inside of a kata VM to isolate
the job pod from the host kernel. See the [IMS Kata Containers](README.Kata.md) document for more information
on kata containers.

### Local Database 'Hack'

When IMS was first developed we implemented a simple local file system to keep track of the data needed for the
service. The intent was to replace this with a proper database as soon as possible. However, due to other priorities
this has not yet happened and the local file system is still in use. The local file system is a set of simple
JSON files that contain all of the records for images, recipes, public keys, and jobs.

These files are stored in the `/var/ims/data` directory within the IMS container. When the IMS service
starts up, it loads all of the records from these files into memory. When a record is created, updated, or deleted,
the corresponding file is updated on the local file system. This directory is mounted into a PVC so that the
data is persisted across restarts of the IMS service. If these files are lost, the IMS service will lose
all of its records.

The main drawback to this is it limits the scalability of the IMS service. Multi-threading or multiple pods running
the IMS service would lead to data corruption as there is no locking mechanism in place for the local file system.
Currently the IMS service is only deployed as a single pod and single-threaded within the pod, so this is not an
issue. However, this does limit the ability to scale the IMS service to handle more load. Moving to a proper
database would resolve this issue.

### Artifacts Stored in S3

The image and recipe files used by IMS are stored as artifacts in S3. This is done to both manage the large
files and to allow the boot process to directly access the image artifacts.

#### Artifact Ownership

If items are uploaded through IMS, the IMS service will use the owner "IMS". If the items are uploaded manually
through the cray cli through `cray artifacts ...` then the owner will be "STS". In most cases this does not make
a difference, but there are few cases where it does. You can find examples in the code where s3 clients are
set up with both owners to handle these cases.

#### IMS S3 Bucket Structure

The primary buckets used by IMS are:
 - ims - contains the recipe artifacts
 - boot-images - contains the boot images used by BOS during the boot process

#### Artifact Soft Delete

When an artifact is deleted through IMS, it is not actually deleted from S3. Instead, it is marked as deleted
by renaming the artifact to have a `deleted` suffix. This allows for recovery of deleted artifacts if needed.
Since artifacts in S3 are immutable, this is actually accomplished by copying the artifact to a new name. For
large image files this may take some time and since the IMS service is currently single-threaded, it may block
other operations until the copy is complete. This would be the primary motivation to use a proper database and
allow multi-threading in the IMS service. All other operations are very fast so would have minimal impact on
other operations being blocked.

## Cray CLI Integration

Changes to the api must be reflected in the cray cli. The cray cli uses an OpenAPI specification
to generate the client code. The OpenAPI spec is located in `ims/api/openapi.yaml`. After making changes
to the api, the OpenAPI spec must be updated to reflect those changes. Once the spec is updated, the
cray cli must be updated as well. See the repo https://github.com/Cray-HPE/craycli for information on
how to update the cray cli with the new spec.

## Local Development

### Create a Development Environment
    The following are required:
    * Python3
    * The Python requirements in requirements.txt
    * Docker (for building the image locally)
    * MinIO or other s3 server for development

    1. Establish a python virtual environment:

    ```
    $ python3 -m venv .env
    $ . .env/bin/activate
    ```

    2. PIP install the requirements file

    ```
    $ pip3 install -r requirements.txt
    ```

    3. Establish a MinIO server

    ```
    $ docker pull minio/minio

    $ docker run -p 9000:9000 -p 9001:9001 -d minio/minio server /data --console-address :9001
    941dbec66ecd9fe062a0fc99a2ac1e998e89abc72293d001dc4a484f7a9bc67a

    NOTE: may need to run 'docker run -p 9000:9000,9001:9001 -d minio/minio server /data --console-address :9001' instead

    $ docker logs 941dbec66ecd9fe062a0fc99a2ac1e998e89abc72293d001dc4a484f7a9bc67a
    Endpoint:  http://172.17.0.2:9000  http://127.0.0.1:9000

    Browser Access:
        http://172.17.0.2:9000  http://127.0.0.1:9000

    Object API (Amazon S3 compatible):
        Go:         https://docs.min.io/docs/golang-client-quickstart-guide
        Java:       https://docs.min.io/docs/java-client-quickstart-guide
        Python:     https://docs.min.io/docs/python-client-quickstart-guide
        JavaScript: https://docs.min.io/docs/javascript-client-quickstart-guide
        .NET:       https://docs.min.io/docs/dotnet-client-quickstart-guide
    Detected default credentials 'minioadmin:minioadmin', please change the credentials immediately using 'MINIO_ACCESS_KEY' and 'MINIO_SECRET_KEY'
    ```

    NOTE: Using podman, the command to start minio would be similar to 
    ```
    $ podman run -p 9000:9000,9001:9001 --net cni-podman1 minio/minio server /data --console-address :9001
    ```

### Building

    If you wish to perform a local build, you will first need to clone or copy the contents of the
    cms-meta-tools repo to `./cms_meta_tools` in the same directory as the `Makefile`. When building
    on github, the cloneCMSMetaTools() function clones the cms-meta-tools repo into that directory.

    For a local build, you will also need to manually write the .version, .docker_version (if this repo
    builds a docker image), and .chart_version (if this repo builds a helm chart) files. When building
    on github, this is done by the setVersionFiles() function.

    ```
    $ docker build -t cray-ims-service:dev -f Dockerfile .
    ```

    NOTE: if base images are in artifactory.algol60.net, be sure to authenticate against the docker repo
    before trying to build:
    ```
    $ docker login artifactory.algol60.net
    ```
    See more information on authentication here:
    https://rndwiki-pro.its.hpecorp.net/display/CSMTemp/Client+Authentication#ClientAuthentication-SecurityConsiderations

### Running Locally

    The image can be run with the following command:

    ```bash
    $ docker run --rm --name cray-ims-service \
    -p 9100:9000 \
    -e "S3_ACCESS_KEY=minioadmin" \
    -e "S3_SECRET_KEY=minioadmin" \
    -e "S3_CONNECT_TIMEOUT=30" \
    -e "S3_READ_TIMEOUT=30" \
    -e "S3_ENDPOINT=http://172.17.0.2:9000" \
    -e "S3_IMS_BUCKET=ims" \
    -e "S3_BOOT_IMAGES_BUCKET=boot-images" \
    -e "FLASK_ENV=staging" \
    -v ~/tmp/datastore:/var/ims/data \
    cray-ims-service:dev
    ```

    This will start the IMS server on `http://localhost:9100`. An S3 instance is
    required for the IMS server to do anything meaningful. See the [Configuration Options](#Configuration-Options)
    section for more information and further configuration possibilities.

    Fetch recipes and images:

    ```
    $ curl http://127.0.0.1:9100/images
    []
    $ curl http://127.0.0.1:9100/recipes
    []
    ```

    Add a public key:

    ```
    $ curl http://127.0.0.1:9100/public-keys -X POST -H "Content-Type: application/json" \
        --data '{"name":"test","public_key":"TEST_KEY_DATA"}'
    ```

    Get a recipe description:

    ```
    $ curl http://127.0.0.1:9100/recipes/RECIPE_ID
    ```

    Patch an image record:

    ```
    curl http://127.0.0.1:9100/images/IMAGE_ID -X PATCH -H "Content-Type: application/json" \
        --data '{"platform":"aarch64"}'
    ```

    Create a job:

    ```
    curl http://127.0.0.1:9100/jobs -X POST -H "Content-Type: application/json" \
        --data '{ "job_type":"create","require_dkms":"False","image_root_archive_name":"Test","artifact_id":"RECIPE_ID", \
        "public_key_id":"PUBLIC_KEY_ID"}'
    ```

    **NOTE:** To successfully post jobs to the IMS Jobs endpoint, you must be running under 
    kubernetes as the IMS Service tries to launch a new K8S job. This is not expected to 
    work when running the IMS Service locally under Docker. However running locally you
    can watch the logs and verify the request posts correctly.

## Testing

### Unit, Code Style & Lint Tests

    Run unit tests and codestyle checkers with Docker using the following helper scripts.
    ```
    $ ./runUnitTests.sh
    $ ./runCodeStyleCheck.sh
    $ ./runLint.sh
    ```

### Setting up PyTest

    PyTest runs the unit tests directly, not inside a container. This means that it needs
    some additional changes to get the correct configuration to run locally.

    The following are required beyond the development system setup:
    * The Python requirements in requirements-test.txt

    1. Activate the virtual environment created for development

        ```
        $ . .env/bin/activate
        ```

    1. Install required python modules

        ```
        $ pip3 install -r requirements-test.txt
        ```

    1. Create pytest.ini file with env vars

        In the parent directory that IMS is cloned into, create the file 'pytest.ini'
        and put the following contents in it:

        ```
        [pytest]
        env =
        FLASK_ENV=development 
        ```

    1. Create a directory for the IMS data files

        This is the directory that the unit tests will use to create the
        data file for IMS object records.

        ```
        cd ~
        mkdir -p ims/data
        ```

