# Kata Containers 

Why Kata?
We are utilizing kata to address security concerns with the overall chroot environment. Utilizing kata will allow 
us to safely utilize the chroot environment by isolating the kernel of the pod from the node host.

Starting with CSM version 1.6, kata containers will be the default runtime for IMS jobs.
This will require that kata be installed onto the non compute nodes in order for deployment to be successful.

You can verify if kata has been installed and configured in containerd by checking /etc/containerd/config.toml file and seeing this within the configuration.

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

If it doesnt exist, this block will need to be included under the [plugins."io.containerd.grpc.v1.cri".containerd]

If you run into issues when trying to run an IMS job using kata. It may not be installed on the ncn in which the IMS job was scheduled.
To install kata follow the steps below.

Log in to an ncn worker and install kata directly on the node using the following commands:

wget -q -c -O /tmp/kata-static.tar.xz https://github.com/kata-containers/kata-containers/releases/download/2.5.1/kata-static-2.5.1-x86_64.tar.xz
tar -xJf /tmp/kata-static.tar.xz -C /
chmod +x /opt/kata/bin/*
ln -sf /opt/kata/bin/containerd-shim-kata-v2 /usr/local/bin/containerd-shim-kata-qemu-v2
sudo chown root.root /
# shellcheck disable=SC2086,SC2046
sudo chown root.root $(tar tJf /tmp/kata-static.tar.xz | sed 's|^|/|g' | xargs echo)
rm /tmp/kata-static.tar.xz

Try running:
kubectl get runtimeclass

If the command doesnt produce any results you will need to install the kata-qemu runtime class onto the kubernetes cluster with the following commands:

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

On the ncn you are working on:
kubectl label node "$(hostname)" --overwrite katacontainers.io/kata-runtime=true
This will allow the runtimeclass to schedule on the node with this label.

Final step would be to drain/cordon node and reboot containerd for the changes to the config.toml file to take effect.