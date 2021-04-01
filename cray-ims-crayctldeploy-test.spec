# Copyright 2019-2021 Hewlett Packard Enterprise Development LP

Name: cray-ims-crayctldeploy-test
License: MIT
Summary: Cray post-install tests for Image Management Service (IMS)
Group: System/Management
Version: %(cat .rpm_version_cray-ims-crayctldeploy-test)
Release: %(echo ${BUILD_METADATA})
Source: %{name}-%{version}.tar.bz2
Vendor: Cray Inc.
Requires: python3-requests

# Test defines. These may also make sense to put in a central location
%define tests /opt/cray/tests
%define smslong %{tests}/sms-long
%define testlib %{tests}/lib

# CMS test defines
%define smslongcms %{smslong}/cms
%define cmslib %{testlib}/cms

# IMS test defines
%define smslongims %{smslongcms}/ims
%define imslib %{cmslib}/ims

%description
This is a collection of post-install tests for Image Management Service (IMS)

%prep
%setup -q

%build

%install
install -m 755 -d %{buildroot}%{smslongcms}/
install -m 755 -d %{buildroot}%{imslib}/

# Install long run tests
install ct_tests/ims_api_build_cray_sles15sp1_barebones_test.sh %{buildroot}%{smslongcms}
install ct_tests/ims_cli_build_cray_sles15sp1_barebones_test.sh %{buildroot}%{smslongcms}

# Install test modules
# We do not want the following Python files executable, so they won't get picked up and
# run as a test. Other tests make use of them internally.
install -m 644 ct_tests/lib/ims_build_image.py %{buildroot}%{imslib}
install -m 644 ct_tests/lib/ims_test_api_helpers.py %{buildroot}%{imslib}
install -m 644 ct_tests/lib/ims_test_cli_helpers.py %{buildroot}%{imslib}
install -m 644 ct_tests/lib/ims_test_helpers.py %{buildroot}%{imslib}
install -m 644 ct_tests/lib/ims_build_image_argparse.py %{buildroot}%{imslib}
install -m 644 ct_tests/lib/ims_test_ims_helpers.py %{buildroot}%{imslib}
install -m 644 ct_tests/lib/ims_test_k8s_helpers.py %{buildroot}%{imslib}
install -m 644 ct_tests/lib/ims_test_logger.py %{buildroot}%{imslib}

%clean
rm -f  %{buildroot}%{smslongcms}/ims_api_build_cray_sles15sp1_barebones_test.sh
rm -f  %{buildroot}%{smslongcms}/ims_cli_build_cray_sles15sp1_barebones_test.sh
rm -f  %{buildroot}%{imslib}/ims_build_image.py
rm -f  %{buildroot}%{imslib}/ims_test_api_helpers.py
rm -f  %{buildroot}%{imslib}/ims_test_cli_helpers.py
rm -f  %{buildroot}%{imslib}/ims_test_helpers.py
rm -f  %{buildroot}%{imslib}/ims_build_image_argparse.py
rm -f  %{buildroot}%{imslib}/ims_test_ims_helpers.py
rm -f  %{buildroot}%{imslib}/ims_test_k8s_helpers.py
rm -f  %{buildroot}%{imslib}/ims_test_logger.py
rmdir %{buildroot}%{imslib}

%files
%defattr(755, root, root)
%dir %{imslib}
# We do not want the following files executable (see comment in %install section)
%attr(644, root, root) %{imslib}/ims_build_image.py
%attr(644, root, root) %{imslib}/ims_test_api_helpers.py
%attr(644, root, root) %{imslib}/ims_test_cli_helpers.py
%attr(644, root, root) %{imslib}/ims_test_helpers.py
%attr(644, root, root) %{imslib}/ims_build_image_argparse.py
%attr(644, root, root) %{imslib}/ims_test_ims_helpers.py
%attr(644, root, root) %{imslib}/ims_test_k8s_helpers.py
%attr(644, root, root) %{imslib}/ims_test_logger.py

%{smslongcms}/ims_api_build_cray_sles15sp1_barebones_test.sh
%{smslongcms}/ims_cli_build_cray_sles15sp1_barebones_test.sh

%changelog
