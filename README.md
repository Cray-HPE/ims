# Image Management Service

## About

The image management service (IMS) is responsible for enabling the creation of 
bootable and non-bootable images, enabling image customization via a SSH-able 
environment, and packaging and association of new/customized image artifacts 
(kernel, rootfs, initrd, etc) with a new IMS image record.

IMS Supports 6 endpoints:
* public-keys

  Manage the public keys which enable ssh access. 
  Public-keys are created and uploaded by the
  administrator to allow access to ssh shells provided
  by IMS during image creation and customization.
      
* recipes

  Manipulate the RecipeRecord metadata about the Kiwi-NG recipes 
  which are stored in the S3 artifact repository as a tgz archive. 
  
  Recipes archives define how an image is to be created including the
  RPMS that will be installed, the RPM repos to use, etc.

* images

  Manipulate the ImageRecord metadata about the IMS Image manifests 
  which are stored in the S3 artifact repository. 
  IMS Image manifests define the individual image artifacts (kernel, initrd, 
  rootfs, etc) that comprise the image. 

* jobs

  Initiate an image creation or customization job.  A create job builds a new
  image from a given recipe using the open source
  [kiwi-ng](https://osinside.github.io/kiwi/index.html) appliance builder tool.
  A customize job creates a SSH-able shell environment exposing the rootfs of
  an existing IMS Image. Administrators can either manually access this SSH
  environment, or use an automated tool (such as CFS) to modify the image root.
  Once customizations of the image root are complete, IMS packages and uploads
  the new/modified artifacts (rootfs, kernel, initrd) to S3 and associates
  the artifacts with a new IMS Image.

* deleted

  Manage soft deletion of IMS Image, Recipe, and Public-Key records. When these
  objects are deleted, the record is marked as deleted, but the artifacts in S3
  are not removed. This allows for recovery of these objects that may have been
  deleted in error.

* remote-build-nodes

  Manage the list of remote build nodes that can be used to offload IMS image
  build and customization jobs to. Remote build nodes can be either x86_64
  or aarch64 architecture, allowing IMS to build images for either platform.

Complete user facing documentation is available on the CSM Documentation site:
[CSM Documentation](https://github.com/Cray-HPE/docs-csm/tree/release/1.7/operations/image_management)

## API Specification

The API specification is located in `api/openapi.yaml`.

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

* [ims-sshd](https://github.com/Cray-HPE/ims-sshd)

  Container used in the IMS customize job work flow to provide an SSH server
  exposing the image rootfs for customization and in the IMS create job work flow
  to provide an SSH server after the recipe build process for debugging purposes.

* [ims-kiwi-ng-opensuse-x86_64-builder](https://github.com/Cray-HPE/ims-kiwi-ng-opensuse-x86_64-builder)

  Container used in the IMS create job work flow to build a new image using the kiwi-ng tool.

## Additional Documentation

* [Developer Documentation](README.Dev.md)
* [Kata Containers Information](README.Kata.md)
* [Remote Build Nodes Information](README.Remote-Nodes.md)

## CT Tests

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

## Build Helpers
This repo uses some build helpers from the 
[cms-meta-tools](https://github.com/Cray-HPE/cms-meta-tools) repo. See that repo for more details.

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
