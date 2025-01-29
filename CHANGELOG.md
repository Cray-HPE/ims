# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.15.1] - 2025-01-29
### Fixed
- CASMCMS-9201 - resolve orphaned S3 artifacts.

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
- CASMCMS-8801 - changed the image volume mounts to ude PVC's instead of ephemeral storage.

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
- CASMCMS-7970 - update dev.cray.com addressess.
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
