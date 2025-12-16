# Kata Containers 

## Why Kata?

We are utilizing kata to address security concerns with the overall chroot environment. Utilizing kata allows
us to safely utilize the chroot environment by isolating the kernel of the pod from the node host. Enabling
kernel module installation and configuration within the chroot environment required mapping host kernel directories
into the pod which presented security concerns. Kata containers provide a lightweight VM that isolates the pod
kernel from the host kernel while still providing near native performance. Kata is used when 'DKMS' is enabled.

Starting with CSM version 1.6, kata containers are the default runtime for IMS jobs. Kata should be installed
and configured on all non-compute nodes as part of the CSM installation process.

## Hypervisor CPU Configuration

Kata creates a new VM for each pod utilizing the kata runtime. Each container in the pod shares the same VM. The VM
created by kata looks at the cpu limits for each container in the pod and configures the VM cpu count by adding all
the cpu limits together.

If an application running inside a kata container queries the number of available CPUs, it will see the total number of
CPUs assigned to the VM overall, not the number of CPUs assigned to the individual container. This can lead to problems
if the application attempts to use all available CPUs, as it may greatly exceed the CPU limit assigned to the container.

We have observed this behavior with the installation of NVIDIA GPU drivers. As part of the installation process, the
drivers are compiled using all CPUs reported as available. This massively exceeds the CPU limit assigned to the
container and causes the container to be overdriven and respond slowly enough that Kata considers the VM to be
unresponsive and kills it. To avoid this, we have had to reduce the CPU limits for the containers in the pod which
impacts the performance of creating the squashfs image.

When the Kata VM is killed, CFS may not be able to properly detect the failure and report the job as failed. This can
lead to jobs that appear to be stuck in 'running' state indefinitely. If you suspect this has happened, you can check
the logs of the ims-utils container in the pod for messages indicating that the kata VM was killed due to
unresponsiveness.

This should be tracked in future releases of kata to see if there is a way to limit the number of CPUs reported
as available inside the kata VM to match the CPU limit assigned to the container.

## Verifying Kata Installation

Kata should be installed on the master and worker nodes by default. On a worker node, you can check the currently
installed version with:

```bash
/opt/kata/bin/kata-runtime --version
```

If this command fails, kata is not installed on the node. Proceed to the installation instructions below.

## Manually Upgrading/Installing Kata on a Worker Node

These are the places where Kata is installed into the CSM worker node images:
- https://github.com/Cray-HPE/node-images/blob/main/boxes/ncn-node-images/kubernetes/provisioners/common/install.sh#L82
- https://github.com/Cray-HPE/node-images/blob/main/boxes/ncn-node-images/kubernetes/files/resources/common/vars.sh#L56
- https://github.com/Cray-HPE/cray-kubernetes-ansible/blob/main/roles/install_kata/tasks/main.yml#L24

On a worker node, you can check the currently installed version with:

```bash
/opt/kata/bin/kata-runtime --version
```

1. Manually install a new kata
    Condensing the commands in the above source files, here are the steps to manually upgrade or install Kata on a worker node:

    ```bash
    # Newest stable version as of 2025-10-14
    export KATA_VERSION="3.21.0"
    wget -q -c https://github.com/kata-containers/kata-containers/releases/download/${KATA_VERSION}/kata-static-${KATA_VERSION}-amd64.tar.zst
    tar --zstd -xf kata-static-${KATA_VERSION}-amd64.tar.zst -C /
    chmod +x /opt/kata/bin/*
    ln -sf /opt/kata/bin/containerd-shim-kata-v2 /usr/local/bin/containerd-shim-kata-qemu-v2
    mkdir -p /var/lib/kata
    sudo chown root.root /

    #Appends list of annotations that will be utilized for kata in k8s
    sed -i 's/\[\"enable_iommu\"\]/["enable_iommu", "virtio_fs_extra_args", "default_memory", "kernel_params", "cpu_features"]/' /opt/kata/share/defaults/kata-containers/configuration-qemu.toml
    sed -i 's/#file_mem_backend\s=\s\"\"/file_mem_backend = "\/var\/lib\/kata"/' /opt/kata/share/defaults/kata-containers/configuration-qemu.toml

    # Increase the number of vcpus available to the VM
    sed -i '/default_vcpus = 1/c\default_vcpus = 8' /opt/kata/share/defaults/kata-containers/configuration-qemu.toml

    # Ensure proper owner on all installed files
    sudo chown root.root $(tar --zstd -tf kata-static-${KATA_VERSION}-amd64.tar.zst | sed 's|^|/|g' | xargs echo)

    # Remove downloaded archive
    rm kata-static-${KATA_VERSION}-amd64.tar.zst
    ```

1. Update containerd configuration to include kata runtimes
    
    If this is a fresh install of kata, you will need to add the kata runtimes to the containerd config.toml file.
    In the file `/etc/containerd/config.toml` the following section must be included under the 
    `[plugins."io.containerd.grpc.v1.cri".containerd]` section:

    ```text
    [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata]
      runtime_type = "io.containerd.kata.v2"
      privileged_without_host_devices = true
      pod_annotations = ["io.katacontainers.*"]
      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata.options]
        ConfigPath = "/opt/kata/share/defaults/kata-containers/configuration.toml"
    [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-qemu]
      runtime_type = "io.containerd.kata-qemu.v2"
      privileged_without_host_devices = true
      pod_annotations = ["io.katacontainers.*"]
      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.kata-qemu.options]
        ConfigPath = "/opt/kata/share/defaults/kata-containers/configuration-qemu.toml"
    ```

    Final step would be to drain/cordon node and reboot containerd for the changes to the config.toml file to take effect.

1. Verify the kata runtimeclass is installed in kubernetes

    1. On a master node, check for the runtimeclass with:
        ```bash
        kubectl get runtimeclass
        ```
        If this shows a runtimeclass named `kata-qemu`, then the runtimeclass is already installed.
    
    1. In the `kata-qemu` runtimeclass is not defined you will need to create it.

        On a master node, create a file `/tmp/qemu-class.yaml` with the following content:

        ```bash
        cat > /tmp/qemu-class.yaml <<EOF
        ---
        kind: RuntimeClass
        apiVersion: node.k8s.io/v1
        metadata:
            name: kata-qemu
        handler: kata-qemu
        overhead:
            podFixed:
                memory: "160Mi"
                cpu: "250m"
        scheduling:
          nodeSelector:
            katacontainers.io/kata-runtime: "true"
        EOF

        kubectl apply -f /tmp/qemu-class.yaml 
        ```

    1. Label the node for kata scheduling
        
        On the worker node kata was just installed on run the following command to label the node for kata scheduling:

        ```bash
        kubectl label node "$(hostname)" --overwrite katacontainers.io/kata-runtime=true
        ```

        This will allow the runtimeclass to schedule on the node with this label.

## Scheduling Jobs on the Upgraded Node

Sometimes is it useful to schedule an IMS job specifically on the node where you just upgraded or installed kata.
To do this, you will need to manually modify the job templates used by IMS to include a node affinity clause that
specifies the node you want to schedule on. Manually modify the create and customize job templates to change the
pod anti-affinity clause to an affinity clause that will only place the job on the node you are working on.

The affinity clause should look something like this - replacing the node name with the node you are working on:

```yaml
          affinity:
            nodeAffinity:
              requiredDuringSchedulingIgnoredDuringExecution:
                nodeSelectorTerms:
                - matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: In
                    values:
                    - ncn-w005
```

## CASMCMS-8940 - Observed bug with kata / qemu emulation

When using kata containers with qemu emulation, we have observed occasional issues where the
`ldd` command inside the kata container fails with an error similar to:

```text
:/root # ldd /usr/bin/cxi_rh
ldd: exited with unknown exit code (139)
:/root # /lib/ld-linux-aarch64.so.1 --verify /usr/bin/cxi_rh
Segmentation fault (core dumped)
```

The `ldd` command is used to determine the shared library dependencies of a binary. The failure of this
command may result in missing dependent libraries. This appears to be a bug in the qemu emulation used
by kata containers. This can lead to images that fail to boot or run properly due to these missing libraries.

When new versions of kata and qemu-user-static are released, we recommend testing to see if
this bug has been resolved. 

This was last tested and confirmed reproducible in October 2025 with:
- sles15sp6
- kata 3.21.0
- k8s: 1.32.5
- qemu-user-static: 7.2.0-1
