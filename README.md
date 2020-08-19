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

* [ims-python-helper](https://stash.us.cray.com/projects/SCMS/repos/ims-python-helper)

  Python client library providing higher level and commonly used functions. For instance, 
  The `ims-python-helper` library is used in the `ims-utils` container to set job status 
  and upload and associate new/modified artifacts with a new IMS image record. 
  
* [ims-utils](https://stash.us.cray.com/projects/SCMS/repos/init-ims)

  Utility container used in both the IMS create and customize job work flows as the basis
  for several containers including:
  * The init-containers responsible for downloading the recipe/rootfs archive (`fetch-recipe` 
    and `prepare`)
  * The `buildenv-sidecar` container which is responsible for managing the SSH shell and 
    packaging & uploading of the new/customized artifacts. 
    
* [ims-buildenv-centos7](https://stash.us.cray.com/projects/SCMS/repos/ims-buildenv-centos7)

  Container used in the IMS create and customize workflows to provide a SSH shell environment.
 
* [ims-kiwi-ng-opensuse-x86_64-builder](https://stash.us.cray.com/projects/SCMS/repos/ims-kiwi-ng-opensuse-x86_64-builder/browse)

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
   
   $ docker run -p 9000:9000 -d minio/minio server /data
   941dbec66ecd9fe062a0fc99a2ac1e998e89abc72293d001dc4a484f7a9bc67a
   
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

## Building
```
$ docker build -t ims-service:dev -f Dockerfile.service .
```

## Running Locally

The image can be run with the following command:

```bash
$ docker run --rm --name ims-service \
  -p 5000:80 \
  -e "S3_ACCESS_KEY=minioadmin" \
  -e "S3_SECRET_KEY=minioadmin" \
  -e "S3_ENDPOINT=172.17.0.2:9000" \
  -e "S3_IMS_BUCKET=ims" \
  -e "S3_BOOT_IMAGES_BUCKET=boot-images" \
  -e "FLASK_ENV=staging" \
  -v ~/tmp/datastore:/var/ims/data \
  ims-service:dev
```

This will start the IMS server on `http://localhost:5000`. An S3 instance is
required for the IMS server to do anything meaningful. See the [Configuration Options](#Configuration-Options)
section for more information and further configuration possibilities.

```
$ curl http://127.0.0.1:5000/images
[]
$ curl http://127.0.0.1:5000/recipes
[]
```

**NOTE:** To successfully post jobs to the IMS Jobs endpoint, you must be running under 
kubernetes as the IMS Service tries to launch a new K8S job. This is not expected to 
work when running the IMS Service locally under Docker.

## Testing

### Unit, Code Style & Lint Tests

Run unit tests and codestyle checkers with Docker using the following helper scripts.
```
$ ./runUnitTests.sh
$ ./runCodeStyleCheck.sh
$ ./runLint.sh
```

### CT Tests
CT tests can be found in /ct-tests

On a physical system, CMS tests can be found in /opt/cray/tests/crayctl-stage{NUMBER}/cms
Please see https://connect.us.cray.com/confluence/display/DST/Stage+Tests+Guidelines for more details.

example: run CT test for IMS at crayctl stage 4
```
# /opt/cray/tests/crayctl-stage4/cms/ims_stage4_ct_tests.sh
or
# cmsdev test ims --ct
```

Tests return 0 for success, 1 otherwise

### API and Smoke Tests
Similar to CT tests, API and smoke tests can be ran on a system via the cmsdev tool.
https://stash.us.cray.com/projects/SCMS/repos/cms-tools/browse/cmsdev

example: run IMS smoke tests
```
# cmsdev test ims --smoke --verbose
```
example: run IMS API tests
```
# cmsdev test ims --api
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
| `S3_ENDPOINT` | `None` | The `host[:port]` to connect to the S3 instance. If this is not provided, IMS will fail to start.|
| `S3_PROTOCOL` | `http` | The HTTP schema to use to connect to `S3_ENDPOINT`. Only `http` is supported. |
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

## Versioning

We use [SemVer](semver.org) for versioning. The version should be changed in the
following locations:

1. the repository [`.version`](./.version) file
2. the repository [`.rpm_version`](./.rpm_version) file

For the Helm chart, the version should be updated in `kubernetes/cray-ims/Chart.yaml`
and the appropriate master manifest. This version is not the same version
as the API version.

## Authors

* __Eric Cozzi__ (eric.cozzi@hpe.com)

## License

Copyright 2020, Cray Inc. All Rights Reserved.
