# IMS Remote Build Nodes

There are no aarch64 K8S management nodes in the cluster, so any aarch64 image jobs run in pods on the cluster
are done using emulation. Empirical results show this is close to 13X slower than running the equivalent x86 job.
Remote build nodes were originally set up so that an aarch64 compute node could be used to natively run
the aarch64 image jobs. There is nothing architecture specific about the remote build nodes, so they may be used
for x86 jobs as well to offload work from the cluster nodes. Since these jobs are also running outside of the K8S
cluster, they can sidestep the need to run in a separate VM for security reasons. The remote jobs may also use the
entire resources of the remote node. This allows for increased performance on x86 jobs, so many users are now taking
advantage of remote build nodes for both architectures.

As far as users are concerned there is no difference in monitoring or interacting with remote jobs versus jobs
run directly in the K8S cluster. The IMS service handles all of the details of managing remote jobs.

## Basic Mechanisms

The basic mechanism for remote jobs is to use podman containers to run the job on the remote node. There is a
docker image created within the K8S pod that is copied to the remote node and run there. The image and
container on the remote node have the ims job id embedded in the name so it is easy to track which
container on the remote node corresponds to which job in the K8S cluster.

### Load Balancing

There is a rudimentary load balancer built into the IMS service that will look at the number of active jobs on
each active remote build node and select the node with the least number of active jobs to run the next job. There
is a current issue in that `sat bootprep` will spawn the jobs so quickly that the jobs have not been registered
on the remote node before the next job selection is made. This can lead to an uneven distribution of jobs on the
remote nodes.

### Remote Recipe Builds

Image creation jobs build a new docker image with the recipe files embedded in the image, run the kiwi-ng
application on the remote node, then copy the results back to the K8S pod for uploading to S3. In most cases the
compute nodes are not allowed direct access to S3 for security reasons requiring this additional step.

### Remote Image Customizations

For the image customization jobs, a container running an ssh server is started on the remote node and the
connection is forwarded from the K8S pod to the remote container. The sshd service is started in the pod
running on the remote build node and the users credentials are set up there. The pod running in the K8S cluster
set up an iptables rule to forward the ssh connection directly to the remote pod.

The image being customized may be large, so unlike the recipe builds, the image is copied to a temporary
directory on the remote node which is then mounted into the remote container. This avoids the need to copy the
image into and out of the container.

### Debugging Remote Jobs

At times it may be necessary to debug a remote job. The easiest way to do this is to ssh directly to the
remote build node, then use podman to exec into the running container or examine the container logs.
