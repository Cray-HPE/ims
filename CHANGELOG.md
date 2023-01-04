# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
