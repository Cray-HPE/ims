# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.9.5] - 2023-06-22
### Changed
- CASMCMS-8362 - Rollback pvc changes, utilize virtiofs k8s annotation to pass in xattr flag

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
