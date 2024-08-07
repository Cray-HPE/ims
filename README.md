# Image Management Service

## About

The image management service (IMS) is responsible for enabling the creation of 
bootable and non-bootable images, enabling image customization via a SSH-able 
environment, and packaging and association of new/customized image artifacts 
(kernel, rootfs, initrd, etc) with a new IMS image record.

IMS Supports 4 endpoints:
* public-keys

  Manage the public keys which enable ssh access. 
  Public-keys are created and uploaded by the
  administrator to allow access to ssh shells provided
  by IMS during image creation and customization.
      
* recipes

  Manipulate the RecipeRecord metadata about the Kiwi-NG recipes 
  which are stored in the S3 artifact repository as a tgz archive. 
  
  Recipes archives define how an image is to be created including the
  RPMS that will be installed, the RPM repos to use, etc. See the
  [Kiwi-ng image description](https://osinside.github.io/kiwi/overview/workflow.html?highlight=image%20description#components-of-an-image-description)
  for specifics.
      
* images

  Manipulate the ImageRecord metadata about the IMS Image manifests 
  which are stored in the S3 artifact repository. 
  IMS Image manifests define the individual image artifacts (kernel, initrd, 
  rootfs, etc) that comprise the image. 
  
  The image manifest json file is defined in [CASMCMS-4368](https://connect.us.cray.com/jira/browse/CASMCMS-4368)
  and an example is shown below:
  
  ```json
  {    
    "created": "2020-02-05 13:24:29.408091",
    "version": "1.0",
    "artifacts": [
      {
        "link": {
            "etag": "f04af5f34635ae7c507322985e60c00c-131",
            "path": "s3://boot-images/1fb58f4e-ad23-489b-89b7-95868fca7ee6/rootfs",
            "type": "s3"
        },
        "md5": "e7d60fdcc8a2617b872a12fcf76f9d53",
        "type": "application/vnd.cray.image.rootfs.squashfs"
      },
      {
        "link": {
            "etag": "2f120baaa065605cee5a8fd9bed731dd",
            "path": "s3://boot-images/1fb58f4e-ad23-489b-89b7-95868fca7ee6/kernel",
            "type": "s3"
        },
        "md5": "2f120baaa065605cee5a8fd9bed731dd",
        "type": "application/vnd.cray.image.kernel"
      },
      {
        "link": {
            "etag": "be2927a765c88558370ee1c5edf1c50c-3",
            "path": "s3://boot-images/1fb58f4e-ad23-489b-89b7-95868fca7ee6/initrd",
            "type": "s3"
        },
        "md5": "aa69151d7fe8dcb66d74cbc05ef3e7cc",
        "type": "application/vnd.cray.image.initrd"
      }
    ]
  }
  ```
  
* jobs

  Initiate an image creation or customization job.  A create job builds a new
  image from a given recipe using the opensource 
  [kiwi-ng](https://osinside.github.io/kiwi/index.html) appliance builder tool. 
  A customize job creates a SSH-able shell environment exposing the rootfs of 
  an existing IMS Image. Administrators can either manually access this SSH
  environment, or use an automated tool (such as CFS) to modify image root. 
  Once customizations of the image root are complete, IMS packages and uploads 
  the new/modified artifacts (rootfs, kernel, initrd) to S3 and associates 
  the artifacts with a new IMS Image.

For instructions on using IMS to build or customize images see https://stash.us.cray.com/projects/SHASTADOCS/repos/shastadocs/browse/source/admin

## Related Software

* [ims-python-helper](https://github.com/Cray-HPE/ims-python-helper)

  Python client library providing higher level and commonly used functions. For instance, 
  The `ims-python-helper` library is used in the `ims-utils` container to set job status 
  and upload and associate new/modified artifacts with a new IMS image record. 
  
* [ims-utils](https://github.com/Cray-HPE/ims-utils)

  Utility container used in both the IMS create and customize job work flows as the basis
  for several containers including:
  * The init-containers responsible for downloading the recipe/rootfs archive (`fetch-recipe` 
    and `prepare`)
  * The `buildenv-sidecar` container which is responsible for managing the SSH shell and 
    packaging & uploading of the new/customized artifacts. 
    
* [ims-buildenv-centos7](https://stash.us.cray.com/projects/SCMS/repos/ims-buildenv-centos7)

  Container used in the IMS create and customize workflows to provide a SSH shell environment.
 
* [ims-kiwi-ng-opensuse-x86_64-builder](https://github.com/Cray-HPE/ims-kiwi-ng-opensuse-x86_64-builder)

  Container used in the IMS create job work flow to build a new image using the kiwi-ng tool. 

* [init-ims](https://stash.us.cray.com/projects/SCMS/repos/init-ims)

  Kubernetes job container used to upload IMS image recipes to IMS/S3 during the Shasta 
  Installation process. 

## API Specification

The API specification is located in `api/openapi.yaml`.

## Development Setup

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

## Building
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

## Running Locally

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

### CT Tests

See cms-tools repo for details on running CT tests for this service.

### Openapi Spec Validation

Validate IMS openapi spec
```
# npx @redocly/openapi-cli lint api/openapi.yaml
No configurations were defined in extends -- using built in recommended configuration by default.

validating api/openapi.yaml...
api/openapi.yaml: validated in 125ms

Woohoo! Your OpenAPI definition is valid. 🎉
```

## Configuration Options

Much of the configuration is viewable from the `ims/config.py`
file. IMS uses a class-based configuration approach where configuration values
are customized by overriding the base configuration, which is also the production
configuration. This results in a clean production configuration environment,
where the needs of testing and development are added on.

### App Settings

| Configuration Value | Default | Description |
| ------------------- | ------- | ----------- |
| `FLASK_ENV` | `'production'` | [Flask Docs](https://flask.palletsprojects.com/en/1.0.x/config/#ENV)|
| `DEBUG` | `False` | [Flask Docs](https://flask.palletsprojects.com/en/1.0.x/config/#DEBUG) |
| `TESTING` | `False` | [Flask Docs](https://flask.palletsprojects.com/en/1.0.x/config/#TESTING) |
| `LOG_LEVEL` | `logging.INFO` | Note, this is the value from the Python `logging` module. |

#### S3 Settings

All of these settings can be modified for different `FLASK_ENV` scenarios. The
defaults below are default for the `production` environment. To override these
variables without modifying `ims/config.py`, simply provide
them as an environment variable when starting the IMS server.

| Configuration Value | Default | Description |
| ------------------- | ------- | ----------- |
| `S3_ACCESS_KEY` | `None` | The access key for the S3 instance. If this is not provided, IMS will fail to start. |
| `S3_SECRET_KEY` | `None` | The secret key for the S3 instance. If this is not provided, IMS will fail to start. |
| `S3_ENDPOINT` | `None` | The `URL` to connect to the S3 instance. If this is not provided, IMS will fail to start.|
| `S3_SSL_VALIDATE` | `False` | Whether or not to verify SSL certificates. |
| `S3_IMS_BUCKET` | `'ims'` | The default S3 bucket where IMS will look for recipe objects.|
| `S3_BOOT_IMAGES_BUCKET` | `'ims'` | The default S3 bucket where IMS will look for image objects.|
| `S3_URL_EXPIRATION` | `60*60*24*5` (5 days) | The length of time (in seconds) that pre-signed download URLs will be valid for. |
| `S3_CONNECT_TIMEOUT` | `60` (seconds) | See [botocore configuration](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html#botocore.config.Config) |
| `S3_READ_TIMEOUT` | `60` (seconds) | See [botocore configuration](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html#botocore.config.Config) |

## Built With

* [Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
* [Flask](https://flask.palletsprojects.com/en/1.1.x/)
* [Python 3](https://docs.python.org/3/)
* [Python Kubernetes Client](https://github.com/kubernetes-client/python)

## Contributing

Requests for Enhancement and Bugs can be filed in the [CASMCMS Jira project](https://connect.us.cray.com/jira/CreateIssue!default.jspa?selectedProjectKey=CASMCMS).

Members of the CASMCMS team should provide a pull request to master. Other
Crayons should fork this repository and provide a pull request to master.

## Build Helpers
This repo uses some build helpers from the 
[cms-meta-tools](https://github.com/Cray-HPE/cms-meta-tools) repo. See that repo for more details.

## Local Builds
If you wish to perform a local build, you will first need to clone or copy the contents of the
cms-meta-tools repo to `./cms_meta_tools` in the same directory as the `Makefile`. When building
on github, the cloneCMSMetaTools() function clones the cms-meta-tools repo into that directory.

For a local build, you will also need to manually write the .version, .docker_version (if this repo
builds a docker image), and .chart_version (if this repo builds a helm chart) files. When building
on github, this is done by the setVersionFiles() function.

## Versioning

In order to make it easier to go from an artifact back to the source code that produced that artifact,
a text file named gitInfo.txt is added to Docker images built from this repo. For Docker images,
it can be found in the / folder. This file contains the branch from which it was built and the most
recent commits to that branch. 

For helm charts, a few annotation metadata fields are appended which contain similar information.

For RPMs, a changelog entry is added with similar information.

## New Release Branches
When making a new release branch:
    * If an `update_external_versions.conf` file exists in this repo, be sure to update that as well, if needed.

## Authors

* __Eric Cozzi__ (eric.cozzi@hpe.com)

## Copyright and License
This project is copyrighted by Hewlett Packard Enterprise Development LP and is under the MIT
license. See the [LICENSE](LICENSE) file for details.

When making any modifications to a file that has a Cray/HPE copyright header, that header
must be updated to include the current year.

When creating any new files in this repo, if they contain source code, they must have
the HPE copyright and license text in their header, unless the file is covered under
someone else's copyright/license (in which case that should be in the header). For this
purpose, source code files include Dockerfiles, Ansible files, RPM spec files, and shell
scripts. It does **not** include Jenkinsfiles, OpenAPI/Swagger specs, or READMEs.

When in doubt, provided the file is not covered under someone else's copyright or license, then
it does not hurt to add ours to the header.
