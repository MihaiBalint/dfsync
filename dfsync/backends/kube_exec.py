#!/usr/bin/env python
import os
import os.path
import subprocess
import sys

from kubernetes import client, config


def get_kubectl_exec_command(namespace, pod_name, container_name, kube_config=None, kube_context=None):
    kubeconfig = [f"--kubeconfig={kube_config}"] if kube_config else []
    context = [f"--context={kube_context}"] if kube_context else []

    ns = ["-n", "{}".format(namespace)] if namespace else []
    pod_name = ["{}".format(pod_name)]
    ctnr = ["-c", "{}".format(container_name)] if container_name else []

    return ["kubectl", *kubeconfig, *context, "exec", *pod_name, "-i", *ns, *ctnr, "--"]


def get_container_command():
    clean_args = []
    for arg in sys.argv[1:]:
        if len(clean_args) == 0 and (not arg or len(arg.strip()) == 0):
            # remove any spaces or empty values from the beginning of sys.argv
            continue
        clean_args.append(arg)
    return clean_args


def main():
    pod_name = os.environ.get("KUBEEXEC_POD")
    if not pod_name:
        raise ValueError("Expecting pod name in 'KUBEEXEC_POD' env. variable")

    kubectl_cmd = get_kubectl_exec_command(
        os.environ.get("KUBEEXEC_NAMESPACE"),
        pod_name,
        os.environ.get("KUBEEXEC_CONTAINER"),
        os.environ.get("KUBEEXEC_KUBECONFIG"),
        os.environ.get("KUBEEXEC_CONTEXT"),
    )

    container_cmd = get_container_command()
    cmd = [*kubectl_cmd, *container_cmd]
    subprocess.check_call(cmd)
    # print("MIHAI\n\n", file=sys.stderr)
    # print(subprocess.check_output(cmd), file=sys.stderr)


if __name__ == "__main__":
    main()
