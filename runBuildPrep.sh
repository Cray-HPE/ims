#!/bin/bash
# Copyright 2020, Cray Inc. All Rights Reserved.
set -x -o pipefail

get_container_versions_on_branch() {
  local BRANCH=$1
  if wget "http://car.dev.cray.com/artifactory/shasta-premium/SCMS/noos/noarch/${BRANCH}/cms-team/manifest.txt"; then
    echo "Contents of manifest.txt"
    echo "===="
    cat manifest.txt
    echo "===="

    IMS_UTILS_VERSION=$(grep cray-ims-utils manifest.txt | sed s/.*://g | tr -d '[:space:]')
    IMS_KIWI_NG_VERSION=$(grep cray-ims-kiwi-ng-opensuse-x86_64-builder manifest.txt | sed s/.*://g | tr -d '[:space:]')
    IMS_SSHD_VERSION=$(grep cray-ims-sshd manifest.txt | sed s/.*://g | tr -d '[:space:]')
    rm manifest.txt

    if [[ -n $IMS_UTILS_VERSION && -n $IMS_SSHD_VERSION && -n $IMS_KIWI_NG_VERSION ]]; then
      return 0
    fi

    echo "ERROR: Missing one or more expected versions in the manifest file"
    echo "IMS_UTILS_VERSION=\"$IMS_UTILS_VERSION\""
    echo "IMS_KIWI_NG_VERSION=\"$IMS_KIWI_NG_VERSION\""
    echo "IMS_SSHD_VERSION=\"$IMS_SSHD_VERSION\""
  else
    echo "ERROR: Could not wget manifest file."
  fi
  return 1
}

get_container_versions() {
  if [[ $GIT_BRANCH =~ release\/.* ]]; then
    echo "Release Breanch"
    get_container_versions_on_branch "$GIT_BRANCH"
  else
    echo "non-Release Branch"
    get_container_versions_on_branch "dev/master"
  fi
}

pin_dependent_containers() {
  if get_container_versions; then
    if ! sed -i "s/cray_ims_utils_image_version:.*/cray_ims_utils_image_version: \"${IMS_UTILS_VERSION}\"/g" kubernetes/cray-ims/values.yaml; then
      echo "ERROR: sed returned failure trying to pin cray_ims_utils_image_version"
      return 1
    fi
    if ! sed -i "s/cray_ims_kiwi_ng_opensuse_x86_64_builder_image_version:.*/cray_ims_kiwi_ng_opensuse_x86_64_builder_image_version: \"${IMS_KIWI_NG_VERSION}\"/g" kubernetes/cray-ims/values.yaml; then
      echo "ERROR: sed returned failure trying to pin cray_ims_kiwi_ng_opensuse_x86_64_builder_image_version"
      return 1
    fi
    if ! sed -i "s/cray_ims_sshd_image_version:.*/cray_ims_sshd_image_version: \"${IMS_SSHD_VERSION}\"/g" kubernetes/cray-ims/values.yaml; then
      echo "ERROR: sed returned failure trying to pin cray_ims_sshd_image_version"
      return 1
    fi

    echo "Contents of values.yaml"
    echo "===="
    cat kubernetes/cray-ims/values.yaml
    echo "===="

    return 0
  fi
}

if ! pin_dependent_containers; then
  echo "ERROR: Failed to pin dependent container versions."
  exit 1
fi
exit 0
