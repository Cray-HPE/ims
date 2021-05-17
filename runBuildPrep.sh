#!/bin/bash
# Copyright 2020-2021 Hewlett Packard Enterprise Development LP
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

set -x -o pipefail

get_container_versions_on_branch() {
  local BRANCH=$1
  if wget "https://arti.dev.cray.com/artifactory/csm-misc-${BRANCH}-local/manifest/manifest.txt"; then
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
    echo "Release Branch"
    if ! get_container_versions_on_branch "stable"; then
      return 1
    fi
  else
    echo "non-Release Branch"
    if ! get_container_versions_on_branch "master"; then
      return 1
    fi
  fi
  return 0
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
  return 1
}

update_versions() {
    ./install_cms_meta_tools.sh || exit 1
    RC=0
    ./cms_meta_tools/update_versions/update_versions.sh || RC=1
    rm -rf ./cms_meta_tools
    return $RC
}

# Update the version strings from the placeholder value
if ! update_versions ; then
  echo "ERROR: Failed updating version placeholder strings"
  exit 1
fi

if ! pin_dependent_containers; then
  echo "ERROR: Failed to pin dependent container versions."
  exit 1
fi
exit 0
