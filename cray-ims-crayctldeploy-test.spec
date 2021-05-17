# Copyright 2019-2021 Hewlett Packard Enterprise Development LP
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

Name: cray-ims-crayctldeploy-test
License: MIT
Summary: Cray post-install tests for Image Management Service (IMS)
Group: System/Management
Version: %(cat .version)
Release: %(echo ${BUILD_METADATA})
Source: %{name}-%{version}.tar.bz2
Vendor: Cray Inc.
Requires: python3-requests

# Test defines. These may also make sense to put in a central location
%define tests /opt/cray/tests
%define testlib %{tests}/lib

# CMS test defines
%define cmslib %{testlib}/cms

# IMS test defines
%define imslib %{cmslib}/ims

%description
This is a collection of post-install tests for Image Management Service (IMS)

%prep
%setup -q

%build

%install
install -m 755 -d %{buildroot}%{imslib}/

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

%changelog
