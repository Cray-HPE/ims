# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Dependencies
- Updated `kubernetes` module to match CSM 1.7 version

## [3.30.0] - 2025-06-25
### Changed
- CASMCMS-9024 - use DST signing keys with kiwi-ng recipe builds.

## [3.29.0] - 2025-06-25
### Updated
- CASMCMS-8022: Updated `ims-utils` version to `2.18` and `kiwi-ng` version to `1.10`

## [3.28.0] - 2025-06-11
### Updated
- CASMCMS-8923 - Updated `cray-ims-kiwi-ng-opensuse-x86_64-builder` version to `1.9`
- CASMCMS-8939 - better port forwarding for remote jobs.

## [3.27.0] - 2025-06-05
### Fixed
- CASMCMS-9452: Cleanup of leftover Cluster/RoleBindings under CMS

## [3.26.0] - 2025-06-04
### Fixed
- CASMCMS-9451 - add pod level security context so PVC's are mounted with the correct owner.

### Dependencies
- Bumped cray-services base chart minimum version to 12.0.0

## [3.25.0] - 2025-05-29
### Dependencies
- CASMCMS-9399 - update gunicorn to v23.0.0 for CVE issue
| Package         | From     | To       |
|-----------------|----------|----------|
| `certifi`       | 2024.2.2 | 2024.7.4 |
| `gunicorn`      | 22.0.0   | 23.0.0   |
| `Jinja2`        | 3.1.4    | 3.1.6    |
| `requests`      | 2.31.0   | 2.32.2   |
| `urllib3`       | 1.26.18  | 1.26.19  |
| `Werkzeug`      | 3.0.3    | 3.0.6    |

## [3.24.3] - 2025-05-14
### Fixed
CASMCMS-9408: Conditionalize podsecuritypolicies references in cray-ims

## [3.24.2] - 2025-04-29
### Fixed
- CASMCMS-9387: API V2: During create image ims stores incorrect metadata for an image
- CASMCMS-9389: IMS image tags removed by soft delete
- CASMCMS-9396: IMS - deleted recipe always gets assigned require_dkms=true

## [3.24.1] - 2025-04-25
### Fixed
- CASMCMS-9386: API spec
  - Correct schemas for `metadata` fields in `ImageRecord` and `DeletedImageRecord`
  - Create new `ImageCreateRecord` schema to reflect that the schema for creating an image is not identical
    to the ones for describing one.
  - Fix incorrectly-named duplicate `operationId`
  - Correct return type of v2 image create endpoint

## [3.24.0] - 2025-04-23
### Fixed
- CASMCMS-9375: During create ims stores incorrect metadata for an image
- CASMCMS-9363: IMS - deleted recipe always gets assigned arch=x86_64

## [3.23.0] - 2025-02-13
### Dependencies
- CASMCMS-9282
  - Bump Alpine version from 3.15 to 3.21, because 3.15 no longer receives security patches
  - Move to `ims-utils` 2.16

## [3.22.0] - 2025-01-29
### Fixed
- CASMCMS-9201 - large artifacts orphaned by delete operation

## [3.21.0] - 2024-12-10
### Fixed
- CASMCMS-9166 - fix image delete/undelete preserving arch setting.

### Dependencies
- Update ims-utils to pick up CASMCMS-9037
- Update ims-sshd to pick up CASMCMS-9226

## [3.20.0] - 2024-10-18
### Changed
- CASMTRIAGE-7401 - anti-affinity in the job pods.

## [3.19.0] - 2024-10-03

### Changed
- CASMTRIAGE-7327 - fix loading default values from ims-config.
- CASMTRIAGE-7274 - fix cpu limits to not overdrive kata vm, add job pod anti-affinity.
- CASMCMS-9147 - stop using alpine:latest image.

## [3.18.0] - 2024-09-24

### Changed
- CASMTRIAGE-7252: Increase DEFAULT_IMS_IMAGE_SIZE from 30 to 60.

### Fixed
- Fixed Dockerfile to stop "from/as" casing warnings at build time

## [3.17.2] - 2024-09-13
### Added
- CASMTRIAGE-6953: Added comment to `src/server/app.py` noting dependency of IMS import tool in `docs-csm`

### Fixed
- Language linting

### Dependencies
- Use `ims-sshd` v1.11 for CSM 1.6

## [3.17.1] - 2024-09-05
### Changed
- Remove Eric Cozzi from chart maintainers. Add David Laine, Julian Smit, and Mitch Harding.

### Dependencies
- CASMCMS-9136: Move `cray-services` base chart minimum version to 11.0.0

## [3.17.0] - 2024-08-29
### Added
- CASMCMS-8979 - add a status endpoint for the remote build nodes.
- CASMCMS-8977 - check that the ssh key is present each time spawning a remote job.
- CASMINST-6602 - enable dkms by default.
- CASMTRIAGE-7169 - job memory size was not getting picked up correctly from the ims configuration settings.
- CASMCMS-9040 - change read/write permissions of recipe config files output in image.

### Dependencies
- CSM 1.6 moved to Kubernetes 1.24, so use client v24.x to ensure compatibility

## [3.16.2] - 2024-07-25
### Dependencies
- Resolved CVE: Require `setuptools` >= 70.0

## [3.16.1] - 2024-06-27
### Fixed
- Corrected openapi spec definition to match CLI

## [3.16.0] - 2024-06-26
### Added
- CASMCMS-8915: IMS API features for tagging built images.
### Dependencies
- CASMCMS-8022 - update python dependencies to most recent versions. 
| Package               | From       | To       |
|-----------------------|------------|----------|
| `aniso8601`           | 3.0.2      | 9.0.1    |
| `boto3`               | 1.12.49    | 1.34.114 |
| `botocore`            | 1.15.49    | 1.34.114 |
| `cachetools`          | 3.0.0      | 5.3.3    |
| `certifi`             | 2019.11.28 | 2024.2.2 |
| `chardet`             | 3.0.4      | 5.2.0    |
| `click`               | 6.7        | 8.1.7    |
| `docutils`            | 0.14       | 0.21.2   |
| `Flask`               | 1.1.4      | 3.0.3    |
| `flask-marshmallow`   | 0.9.0      | 1.2.1    |
| `google-auth`         | 1.6.3      | 2.29.0   |
| `gunicorn`            | 19.10.0    | 22.0.0   |
| `idna`                | 2.8        | 3.7      |
| `itsdangerous`        | 0.24       | 2.2.0    |
| `Jinja2`              | 2.10.3     | 3.1.4    |
| `jmespath`            | 0.9.5      | 1.0.1    |
| `MarkupSafe`          | 1.1.1      | 2.1.5    |
| `marshmallow`         | 3.0.0b16   | 3.21.2   |
| `oauthlib`            | 2.1.0      | 3.2.2    |
| `pyasn1`              | 0.4.8      | 0.6.0    |
| `pyasn1-modules`      | 0.2.8      | 0.4.0    |
| `pytz`                | 2018.4     | 2024.1   |
| `requests`            | 2.23.0     | 2.31.0   |
| `requests-oauthlib`   | 1.0.0      | 1.3.1    |
| `rsa`                 | 4.7.2      | 4.9      |
| `s3transfer`          | 0.3.7      | 0.10.1   |
| `urllib3`             | 1.25.11    | 1.26.18  |
| `websocket-client`    | 0.54.0     | 1.8.0    |
| `Werkzeug`            | 0.15.6     | 3.0.3    |

## [3.15.0] - 2024-05-20
### Dependencies
- CASMCMS-8976 - include updated kiwi-builder version that has new DST signing keys.

## [3.14.2] - 2024-05-16
### Dependencies
- Pin `pytest` to 8.1.1 to prevent unit test failures

## [3.14.1] - 2024-03-21
### Fixed
- CASMCMS-8950: Fixed loading Kubernetes configuration data in the shasta_s3_creds module

## [3.14.0] - 2024-03-01
### Added
- CASMCMS-8795 - add remote-build-nodes API.
- CASMCMS-8925 - ims service in CLBO when vault is not accessible.

## [3.13.0] - 2024-02-22
### Dependencies
- Bumped `kubernetes` from 11.0.0 to 22.6.0 to match CSM 1.6 Kubernetes version
- Bumped `ims-utils` from 2.11 to 2.12 for CSM 1.6

## [3.12.0] - 2023-12-13
### Changed
- CASMTRIAGE-6426 Increased default IMS pvc size

## [3.11.0] - 2023-10-05
### Changed
- CASMTRIAGE-6368 - include ims-sshd fix for sftp access to customize jobs.
- CASMTRIAGE-6292 - increase default mem request/limits yet again.

## [3.10.1] - 2023-10-05
### Changed
- CASMCMS-8828 - increase the default mem requests and limits on jobs.

## [3.10.0] - 2023-09-15
### Changed
- Disabled concurrent Jenkins builds on same branch/commit
- Added build timeout to avoid hung builds
- CASMCMS-8801 - changed the image volume mounts to ude PVCs instead of ephemeral storage.

### Dependencies
Bumped dependency patch versions:
| Package                  | From     | To       |
|--------------------------|----------|----------|
| `aniso8601`              | 3.0.0    | 3.0.2    |
| `boto3`                  | 1.12.9   | 1.12.49  |
| `botocore`               | 1.15.9   | 1.15.49  |
| `Flask`                  | 1.1.1    | 1.1.4    |
| `Flask-RESTful`          | 0.3.6    | 0.3.10   |
| `google-auth`            | 1.6.1    | 1.6.3    |
| `Jinja2`                 | 2.10.1   | 2.10.3   |
| `jmespath`               | 0.9.4    | 0.9.5    |
| `pyasn1-modules`         | 0.2.2    | 0.2.8    |
| `python-dateutil`        | 2.8.1    | 2.8.2    |
| `rsa`                    | 4.7      | 4.7.2    |
| `s3transfer`             | 0.3.0    | 0.3.7    |
| `urllib3`                | 1.25.10  | 1.25.11  |
| `Werkzeug`               | 0.15.5   | 0.15.6   |

## [3.9.8] - 2023-07-18
### Dependencies
- Bump `PyYAML` from 5.4.1 to 6.0.1 to avoid build issue caused by https://github.com/yaml/pyyaml/issues/601

## [3.9.7] - 2023-07-07
### Changed
- CASMCMS-8707 - push arch env vars to all containers in IMS jobs.

## [3.9.6] - 2023-06-27
### Changed
- CASMCMS-8686 - Fix schema update of jobs records.
- CASMCMS-8687 - Fix global require_dkms setting.

## [3.9.5] - 2023-06-22
### Changed
- CASMCMS-8362 - Rollback pvc changes, utilize virtiofs k8s annotation to pass in xattr flag in customize.

## [3.9.4] - 2023-06-20
### Changed
- CASMCMS-8362 - Utilizing PVC for image-vol volume to support unsquashfs

## [3.9.3] - 2023-06-15
### Changed
- CASMCMS-8624 - Adding default `kernel_file_name` based on arch type in the Job schema.

## [3.9.2] - 2023-05-19
### Changed
- CASMCMS-8566 - Set default arm64 runtime to kata

## [3.9.2] - 2023-05-19
### Changed
- CASMCMS-8566 - Set default arm64 runtime to kata

## [3.9.1] - 2023-05-17
### Changed
- CASMCMS-8567 - Support arm64 image customization.

## [3.9.0] - 2023-05-04
### Added
- CASMCMS-8227 - Add platform support to image, recipe, and job objects.
- CASMCMS-8370 - Add argument to recipe patch to allow changing template-parameters values.
- CASMCMS-8459 - Add platform argument through job templates, fixes for arm64 builds.
- CASMCMS-8595 - rename platform to arch, fix kiwi env var.

## [3.8.3] - 2023-01-06
### Changed
- Correct authentication

### Changed
- CASMCMS-8382 - Correct openapi.yaml to match actual API behavior. Linting of language and formatting of same.

## [3.8.3] - 2023-01-06
### Changed
- Correct authentication

## [3.8.2] - 2022-12-22
### Changed
- CASMCMS-8347 - update istio api interface version to 'v1beta1'

## [3.8.1] - 2022-12-20
### Added
- Add Artifactory authentication to Jenkinsfile

## [3.8.0] - 2022-12-16
### Added
- CASM-2374 - Add support for IMS jobs using kata-qemu runtime

## [3.7.2] - 2022-12-16
### Changed
- CASMTRIAGE-4680 - Use authentication credentials to validate to artifactory

## [3.7.1] - 2022-09-30
### Changed
- CASMTRIAGE-4288 - increase readiness/liveness times to allow for operations with larger images.

## [3.7.0] - 2022-09-28
### Changed
- CASMTRIAGE-4268 - pull in new ims-utils that fixes file download performance issue.

## [3.6.1] - 2022-09-09
### Changed
- CASMTRIAGE-4091 - make gunicorn worker timeout configurable to handle larger image sizes

## [3.6.0] - 2022-08-03
### Changed
- Build valid unstable charts
- CASMCMS-7970 - update dev.cray.com addresses.
- CASMCMS-8015 - increase the default ims job size to handle larger images.

### Removed
- Stopped building nonfunctional, outdated test RPM.

## [3.5.0] - 2022-06-30
### Added
- Add support for storing IMS recipes that have template variables
- Add support for passing IMS recipe template values to IMS create jobs

### Changed
- CASMCMS-8041: Spelling corrections

[1.0.0] - (no date)
