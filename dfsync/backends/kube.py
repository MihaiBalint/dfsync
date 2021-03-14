import sys
import os
import os.path
import dfsync.backends.kube_exec as kube_exec

from kubernetes import client, config
from kubernetes.stream import stream
from .rsync import rsync_backend


class KubeReDeployer:
    def __init__(self):
        # Configs can be set in Configuration class directly or using helper utility
        config.load_kube_config()
        self.api = client.CoreV1Api()
        self._was_status_printed = {}

    def status(self, image_base):
        ready_map = {False: "🔴  ", True: "🟢  "}
        if self._was_status_printed.get(image_base):
            return

        self._was_status_printed[image_base] = True
        print("Targeting pods using image: {}".format(image_base))
        for pod, spec, status in self.generate_matching_containers(image_base):
            status_msg = status.ready
            if not status.ready:
                status_msg = "{} - {}".format(status.ready, status.state.waiting.reason)

            icon = ready_map[status.ready]
            print("{}{} - ready: {}".format(icon, pod.metadata.name, status_msg))
        print("")

    def split_destination(self, destination):
        split_result = destination.split(":")[:2]
        image_base = split_result[0]
        destination_dir = "."
        if len(split_result) > 1:
            destination_dir = split_result[1]

        return image_base, destination_dir

    def get_container_destination_dir(self, pod, status, destination_dir):
        # TODO: maybe change the destination dir by analyzing the container metadata
        return destination_dir

    def get_kubectl_exec_command(self, namespace, pod_name, container_name):
        ns = ["-n", "'{}'".format(namespace)]
        pod_name = ["'{}'".format(pod_name)]
        ctnr = ["-c", "'{}'".format(container_name)]
        cmd = " ".join(["kubectl", "exec", "-i", *ns, *pod_name, *ctnr])
        return cmd, None

    def get_exec_command(self, namespace, pod_name, container_name):
        py_path = os.path.abspath(sys.executable)
        cmd = [py_path, os.path.abspath(kube_exec.__file__)]
        env = {
            **os.environ,
            "KUBEEXEC_POD": pod_name,
            "KUBEEXEC_NAMESPACE": namespace,
            "KUBEEXEC_CONTAINER": container_name,
        }
        return " ".join(cmd), env

    def generate_matching_containers(self, image_base):
        result = self.api.list_pod_for_all_namespaces(watch=False)
        for pod in result.items:
            specs = pod.spec.containers
            statuses = pod.status.container_statuses

            for spec, status in zip(specs, statuses):
                if not status.image.startswith(image_base):
                    continue
                yield pod, spec, status

    def redeploy(self, src_file_path, destination_dir: str = None, **kwargs):
        image_base, destination_dir = self.split_destination(destination_dir)
        self.status(image_base)

        for pod, spec, status in self.generate_matching_containers(image_base):
            if not status.ready:
                print(
                    "{} will not sync in {}, container isn't ready: {}".format(
                        src_file_path, pod.metadata.name, status.state.waiting.reason
                    )
                )
                continue

            if not self.dry_run_exec(pod, spec, status):
                print(
                    "{} failed to sync in {}".format(src_file_path, pod.metadata.name)
                )
                continue

            container_dir = self.get_container_destination_dir(
                pod, status, destination_dir
            )
            rsh_command, rsh_env = self.get_exec_command(
                pod.metadata.namespace, pod.metadata.name, status.name
            )
            self.sync_files(
                rsh_command, src_file_path, container_dir, rsh_env=rsh_env, **kwargs
            )
            # self.redeploy_container(pod, spec, status)

    def sync_files(self, rsh_command, src_file, destination_dir: str = None, **kwargs):
        rsh_destination = ":{}".format(destination_dir)
        rsync_backend(
            src_file,
            destination_dir=rsh_destination,
            rsh=rsh_command,
            blocking_io=True,
            **kwargs
        )

    def dry_run_exec(self, pod, spec, status):
        try:
            resp = stream(
                self.api.connect_get_namespaced_pod_exec,
                pod.metadata.name,
                pod.metadata.namespace,
                container=status.name,
                command="env",
                stdin=False,
                stdout=True,
                stderr=True,
                tty=False,
            )
            return len(resp) > 0
        except:
            return False


_instance = KubeReDeployer()
kube_backend = _instance.redeploy
