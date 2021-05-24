import sys
import os
import os.path

from kubernetes import client, config, watch
from kubernetes.stream import stream

from dfsync.filters import GIT_FILTER
from .rsync import rsync_backend


class Alpine:
    @classmethod
    def name(cls):
        return "Alpine linux (or apk-based Alpine clone)"

    @classmethod
    def get_supervise_command(cls):
        return [
            "/bin/sh",
            "-c",
            "echo dfsync && apk --no-cache add supervisor rsync; supervisord -n",
        ]

    @classmethod
    def install_rsync(cls):
        return ["apk", "--no-cache", "add", "rsync"]

    @classmethod
    def check_rsync(cls):
        return ["rsync", "--version"]

    @classmethod
    def check_package_manager(cls):
        return ["apk", "--version"]

    @classmethod
    def check_can_exec(cls):
        return ["true"]


class CentOS:
    @classmethod
    def name(cls):
        return "CentOS linux (or dnf-based CentOS clone)"

    @classmethod
    def get_supervise_command(cls):
        return [
            "/bin/bash",
            "-c",
            "echo dfsync && dnf install -y supervisor rsync; supervisord -n",
        ]

    @classmethod
    def install_rsync(cls):
        return ["dnf", "install", "-y", "rsync"]

    @classmethod
    def check_rsync(cls):
        return ["rsync", "--version"]

    @classmethod
    def check_package_manager(cls):
        return ["dnf", "--version"]

    @classmethod
    def check_can_exec(cls):
        return ["true"]


class Ubuntu:
    @classmethod
    def name(cls):
        return "Ubuntu/Debian linux (or apt-based Debian clone)"

    @classmethod
    def get_supervise_command(cls):
        return [
            "/bin/bash",
            "-c",
            "echo dfsync && apt install -y supervisor rsync; supervisord -n",
        ]

    @classmethod
    def install_rsync(cls):
        return ["apt", "install", "-y", "rsync"]

    @classmethod
    def check_rsync(cls):
        return ["rsync", "--version"]

    @classmethod
    def check_package_manager(cls):
        return ["apt", "--version"]

    @classmethod
    def check_can_exec(cls):
        return ["true"]


class Generic:
    @classmethod
    def name(cls):
        return "Generic linux (with bash, rsync and supervisor installed)"

    @classmethod
    def get_supervise_command(cls):
        return [
            "/bin/bash",
            "-c",
            "echo dfsync && supervisord -n",
        ]

    @classmethod
    def install_rsync(cls):
        return ["true"]

    @classmethod
    def check_rsync(cls):
        return ["rsync", "--version"]

    @classmethod
    def check_package_manager(cls):
        return ["true"]

    @classmethod
    def get_uncrash_command(cls):
        return ["/bin/sh", "-c", "echo uncrash && sleep 10m"]

    @classmethod
    def check_can_exec(cls):
        return ["true"]


def please_wait(msg="Please wait"):
    print("⌛  {}...".format(msg))


class KubeReDeployer:
    def __init__(self):
        # Configs can be set in Configuration class directly or using helper utility
        config.load_kube_config()
        self.api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()
        self._image_distro = None

    def supervisor_install(self, pod, spec, status):
        if self._is_supervised(pod, spec, status):
            return

        command = self._image_distro.get_supervise_command()
        deployments = self._set_deployment_command(pod, spec, status, command)
        print("Supervisor installing on {}".format(" ".join(deployments)))

    def supervisor_uninstall(self, pod, spec, status):
        if not self._is_supervised(pod, spec, status):
            return

        deployments = self._set_deployment_command(pod, spec, status, command=[])
        print("Supervisor uninstalling from {}".format(" ".join(deployments)))

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
                api_version="apps/v1", kind="Deployment", metadata=deployment.metadata, spec=deployment.spec,
            )
            self.apps_api.patch_namespaced_deployment(
                name=deployment.metadata.name, namespace=namespace, body=patch, async_req=False, _request_timeout=30,
            )
        return [d.metadata.name for _, d in deployments.items()]

    def _is_supervised(self, pod, spec, status, command_marker="echo dfsync"):
        if not spec.command:
            return False

        for arg in spec.command:
            if arg.startswith(command_marker):
                return True
        return False

    def _is_uncrashed(self, pod, spec, status):
        return self._is_supervised(pod, spec, status, command_marker="echo uncrash")

    def status(self, image_base):
        ready_map = {False: "🔴  ", True: "🟢  ", "dev": "🟠  "}
        # print("Pods using image: {}".format(image_base))
        for pod, spec, status in self.generate_matching_containers(image_base):
            icon = ready_map[status.ready]
            status_msg = status.ready
            if not status.ready and status.state.waiting:
                status_msg = "{} - {}".format(status.ready, status.state.waiting.reason)
            elif not status.ready and status.last_state.waiting:
                status_msg = "{} - {}".format(status.ready, status.last_state.waiting.reason)
            elif status.ready and self._is_supervised(pod, spec, status):
                icon = ready_map["dev"]
                status_msg = "supervisor is running"
            elif status.ready and self._is_uncrashed(pod, spec, status):
                icon = ready_map["dev"]
                status_msg = "still sleeping, having recovered from crashed state"

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
        backends_dir, _ = os.path.split(os.path.abspath(__file__))
        cmd = [py_path, os.path.join(backends_dir, "kube_exec.py")]
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
            for spec, status in self.list_containers(pod):
                if not status:
                    continue
                if not status.image.startswith(image_base):
                    continue
                yield pod, spec, status

    def list_containers(self, pod):
        containers = {}
        for spec in pod.spec.containers:
            record = containers.get(spec.name) or [None, None]
            record[0] = spec
            containers[spec.name] = record

        for status in pod.status.container_statuses or []:
            record = containers.get(status.name) or [None, None]
            record[1] = status
            containers[status.name] = record
        return containers.values()

    def sync(self, src_file_path, destination_dir: str = None, **kwargs):
        image_base, destination_dir = self.split_destination(destination_dir)

        for pod, spec, status in self.generate_matching_containers(image_base):
            if not status.ready:
                reason = "Unknown"
                if status.state.waiting:
                    reason = "Waiting - ".format(status.state.waiting.reason)
                elif status.state.terminated:
                    reason = "Terminated - ".format(status.state.terminated.reason)

                print(
                    "{} will not sync in {}, container isn't ready: {}".format(src_file_path, pod.metadata.name, reason)
                )
                continue

            if not self.dry_run_exec(pod, spec, status):
                print("{} failed to rsync into {}".format(src_file_path, pod.metadata.name))
                continue

            container_dir = self.get_container_destination_dir(pod, status, destination_dir)
            rsh_command, rsh_env = self.get_exec_command(pod.metadata.namespace, pod.metadata.name, status.name)
            self.sync_files(rsh_command, src_file_path, container_dir, rsh_env=rsh_env, **kwargs)

    def sync_files(self, rsh_command, src_file, destination_dir: str = None, **kwargs):
        rsh_destination = ":{}".format(destination_dir)
        rsync_args = {
            **kwargs,
            "destination_dir": rsh_destination,
            "rsh": rsh_command,
            "blocking_io": True,
        }
        if isinstance(src_file, (tuple, list)):
            rsync_backend.sync_project(src_file, **rsync_args)
        elif src_file == "./":
            rsync_backend.sync_project([src_file], **rsync_args)
        else:
            rsync_backend.sync(src_file, **rsync_args)

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

    def _uncrash(self, pod, spec, status):
        if status.ready:
            return
        if not status.state.waiting and not status.state.terminated:
            return

        print("Pod {}, is crashing, attempting deployment recovery".format(pod.metadata.name))
        crashing_command = spec.command
        deployments = self._set_deployment_command(pod, spec, status, Generic.get_uncrash_command())

        please_wait()
        w = watch.Watch()
        for event in w.stream(self.api.list_pod_for_all_namespaces, timeout_seconds=30):
            event_pod = event["object"]
            if pod.metadata.name != event_pod.metadata.name:
                continue
            for event_status in event_pod.status.container_statuses or []:
                if event_status.container_id == status.container_id:
                    if event["type"] == "DELETED":
                        print("Deployment recovered".format(pod.metadata.name))
                        w.stop()
                        return True

        print("Pod {} recovery failed".format(pod.metadata.name))
        deployments = self._set_deployment_command(pod, spec, status, crashing_command)
        return False

    def _stabilize(self, pod, spec, status):
        try:
            resp = self._exec(pod, spec, status, Generic.check_can_exec())
            return
        except:
            self._uncrash(pod, spec, status)

    def _sniff_image_distro(self, pod, spec, status):
        for distro in [Alpine, CentOS, Ubuntu]:
            try:
                resp = self._exec(pod, spec, status, distro.check_package_manager())
                if resp and "runtime exec failed" in resp:
                    continue

                return distro
            except:
                pass

        print("Failed to detect container image OS variant. Assuming bash, rsync and supervisor are already installed")
        return Generic

    def dry_run_exec(self, pod, spec, status):
        try:
            resp = self._exec(pod, spec, status, self._image_distro.check_rsync())
            if resp and "runtime exec failed" in resp:
                resp = self._exec(pod, spec, status, self._image_distro.install_rsync())

            resp = self._exec(pod, spec, status, self._image_distro.check_rsync())
            if resp and "runtime exec failed" in resp:
                return False

            return len(resp) > 0
        except:
            return False

    def stabilize_deployments(self, image_base):
        # Uncrash crashed deployments
        for pod, spec, status in self.generate_matching_containers(image_base):
            self._stabilize(pod, spec, status)

    def inspect_deployment_images(self, image_base):
        distros = set()
        for pod, spec, status in self.generate_matching_containers(image_base):
            distro = self._sniff_image_distro(pod, spec, status)
            distros.add(distro)
        self._image_distro = list(distros)[0]
        print(f"Assuming OS in container image: {self._image_distro.name()}")

    def toggle_supervisor(self, image_base, action="install"):
        pods = {}

        for pod, spec, status in self.generate_matching_containers(image_base):
            if action == "install":
                self.supervisor_install(pod, spec, status)
            else:
                self.supervisor_uninstall(pod, spec, status)
            pods[pod.metadata.name] = pod

        if not len(pods):
            print("None of the deployment containers match the given image")
            return

        please_wait()
        w = watch.Watch()
        cleanup_started = False
        for event in w.stream(self.api.list_pod_for_all_namespaces, timeout_seconds=30):
            pod = event["object"]
            if pod.metadata.name not in pods:
                continue

            if event["type"] == "DELETED":
                del pods[pod.metadata.name]
            elif event["type"] != "ADDED" and not cleanup_started:
                please_wait("Cleaning up")
                cleanup_started = True

            if len(pods) == 0:
                w.stop()
        if len(pods) > 0:
            print("Time-out waiting for pods: {}".format(", ".join(pods.keys())))

    def on_monitor_start(
        self, src_file_paths: list = None, destination_dir: str = None, supervisor: bool = True, **kwargs
    ):
        image_base, _ = self.split_destination(destination_dir)
        if supervisor:
            self.stabilize_deployments(image_base)
        self.inspect_deployment_images(image_base)
        if supervisor:
            self.toggle_supervisor(image_base, "install")
        self.status(image_base)
        for p in src_file_paths:
            GIT_FILTER.load_ignored_files(p)
        self.sync(src_file_paths, destination_dir, **kwargs)

    def on_monitor_exit(self, destination_dir: str = None, supervisor: bool = True, **kwargs):
        image_base, _ = self.split_destination(destination_dir)
        if supervisor:
            self.toggle_supervisor(image_base, "uninstall")
        self.status(image_base)


kube_backend = KubeReDeployer()
