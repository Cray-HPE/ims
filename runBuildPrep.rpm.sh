#!/bin/sh
# Copyright 2020, Cray Inc. All Rights Reserved.

# Add the repository that contains the CME premium build macro RPM
zypper ar --no-gpgcheck --refresh http://car.dev.cray.com/artifactory/shasta-premium/SHASTA-OS/sle15_sp1_ncn/x86_64/dev/master/ shasta-os-build-resource

