# Copyright 2019-2020 Cray Inc.

Name: cray-ims-crayctldeploy
License: Cray Software License Agreement
Summary: Cray deployment ansible roles for Image Management Service (IMS)
Group: System/Management
Version: %(cat .rpm_version_cray-ims-crayctldeploy)
Release: %(echo ${BUILD_METADATA})
Source: %{name}-%{version}.tar.bz2
Vendor: Cray Inc.
Requires: cray-crayctl
Requires: kubernetes-crayctldeploy
Requires: sms-crayctldeploy
Requires: python2-oauthlib
Requires: python3-oauthlib
Requires: python2-boto3
Requires: python3-boto3
Requires: python2-kubernetes
Requires: python3-kubernetes
Requires: cray-cmstools-crayctldeploy
Requires: cme-premium-cf-crayctldeploy
BuildRequires: cme-premium-cf-crayctldeploy-buildmacro

# Project level defines TODO: These should be defined in a central location; DST-892
%define afd /opt/cray/crayctl/ansible_framework
%define roles %{afd}/roles
%define playbooks %{afd}/main
%define modules %{afd}/library

# Test defines. These may also make sense to put in a central location
%define tests /opt/cray/tests
%define stage4 %{tests}/crayctl-stage4

# CMS test defines
%define stage4cms %{stage4}/cms

%description
This is a collection of Ansible runbooks and roles for Image Management Service (IMS)

%prep
%setup -q

%build

%install
install -m 755 -d %{buildroot}%{playbooks}/
install -m 755 -d %{buildroot}%{roles}/
install -m 755 -d %{buildroot}%{modules}/
install -m 755 -d %{buildroot}%{stage4cms}/
install -D -m 644 lib/ims_image_upload.py   %{buildroot}%{modules}/ims_image_upload.py
install -D -m 644 lib/shasta_s3_creds.py    %{buildroot}%{modules}/shasta_s3_creds.py

mkdir -p %{buildroot}%{cme_premium_library_dir}
cp -r lib/shasta_s3_creds.py  %{buildroot}%{cme_premium_library_dir}/shasta_s3_creds.py

# Install smoke tests
install ct_tests/ims_stage4_ct_tests.sh %{buildroot}%{stage4cms}

%clean
rm -rf %{buildroot}%{roles}/*
rm -f  %{buildroot}%{playbooks}/*
rm -f  %{buildroot}%{modules}/*
rm -f  %{buildroot}%{cme_premium_library_dir}/*
rm -f  %{buildroot}%{stage4cms}/ims_stage4_ct_tests.sh

%files
%defattr(755, root, root)
%dir %{playbooks}

%dir %{modules}
%{modules}/ims_image_upload.py
%{modules}/shasta_s3_creds.py

%{stage4cms}/ims_stage4_ct_tests.sh

%{cme_premium_library_dir}/shasta_s3_creds.py

%changelog
