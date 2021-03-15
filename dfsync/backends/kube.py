import sys
import os
import os.path
import dfsync.backends.kube_exec as kube_exec

from kubernetes import client, config
from kubernetes.stream import stream
from .rsync import rsync_backend


class Alpine:
    @classmethod
    def get_supervise_command(cls):
        return [
            # This command only works in containers based on Alpine linux
            # TODO: detect operating system and run matching supervisor command
            "/bin/sh",
            "-c",
            "echo dfsync && apk --no-cache add supervisor && supervisord -n",
        ]

    @classmethod
    def install_rsync(cls):
        return ["apk", "--no-cache", "add", "rsync"]

    @classmethod
    def check_rsync(cls):
        return ["rsync", "--version"]


class KubeReDeployer:
    def __init__(self):
        # Configs can be set in Configuration class directly or using helper utility
        config.load_kube_config()
        self.api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()
        self._was_status_printed = {}

    def supervisor_install(self, pod, spec, status):
        if status.ready:
            return
        if self._is_supervised(pod, spec, status):
            return

        command = Alpine.get_supervise_command()
        deployments = self._set_deployment_command(pod, spec, status, command)
        print("Supervisor installed on {}".format(" ".join(deployments)))

    def supervisor_uninstall(self, pod, spec, status):
        import ipdb

        ipdb.set_trace()
        if not self._is_supervised(pod, spec, status):
            return

        deployments = self._set_deployment_command(pod, spec, status, command=[])
        print("Supervisor uninstalled from {}".format(" ".join(deployments)))

    def _set_deployment_command(self, pod, spec, status, command):
        namespace = pod.metadata.namespace

        deployments = {}
        for deployment, container_spec in self.list_deployments(namespace, spec.image):
            if spec.name != container_spec.name:
                continue
            container_spec.command = command
            deployments[deployment.metadata.uid] = deployment

        for _, deployment in deployments.items():
            patch = client.V1Deployment(
                api_version="apps/v1",
                kind="Deployment",
                metadata=deployment.metadata,
                spec=deployment.spec,
            )
            self.apps_api.patch_namespaced_deployment(
                name=deployment.metadata.name, namespace=namespace, body=patch
            )
        return [d.metadata.name for _, d in deployments.items()]

    def _is_supervised(self, pod, spec, status):
        if not spec.command:
            return False

        for arg in spec.command:
            if arg.startswith("echo dfsync"):
                return True
        return False

    def status(self, image_base):
        ready_map = {False: "🔴  ", True: "🟢  ", "dev": "🟠  "}
        if self._was_status_printed.get(image_base):
            return

        self._was_status_printed[image_base] = True
        print("Targeting pods using image: {}".format(image_base))
        for pod, spec, status in self.generate_matching_containers(image_base):
            icon = ready_map[status.ready]
            status_msg = status.ready
            if not status.ready and status.state.waiting:
                status_msg = "{} - {}".format(status.ready, status.state.waiting.reason)
            elif not status.ready and status.last_state.waiting:
                status_msg = "{} - {}".format(
                    status.ready, status.last_state.waiting.reason
                )
            elif status.ready and self._is_supervised(pod, spec, status):
                icon = ready_map["dev"]
                status_msg = "supervisor is running"

            self.supervisor_install(pod, spec, status)
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

    def list_deployments(self, namespace, image_base):
        result = self.apps_api.list_namespaced_deployment(namespace)
        for deployment in result.items:
            specs = deployment.spec.template.spec.containers
            for container_spec in specs:
                if not container_spec.image.startswith(image_base):
                    continue
                yield deployment, container_spec

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
                    "{} failed to rsync into {}".format(
                        src_file_path, pod.metadata.name
                    )
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

    def _exec(self, pod, spec, status, command: list):
        return stream(
            self.api.connect_get_namespaced_pod_exec,
            pod.metadata.name,
            pod.metadata.namespace,
            container=status.name,
            command=command,
            stdin=False,
            stdout=True,
            stderr=True,
            tty=False,
        )

    def dry_run_exec(self, pod, spec, status):
        try:
            resp = self._exec(pod, spec, status, Alpine.check_rsync())
            if resp and "runtime exec failed" in resp:
                resp = self._exec(pod, spec, status, Alpine.install_rsync())

            resp = self._exec(pod, spec, status, Alpine.check_rsync())
            if resp and "runtime exec failed" in resp:
                return False

            return len(resp) > 0
        except:
            return False


_instance = KubeReDeployer()
kube_backend = _instance.redeploy
