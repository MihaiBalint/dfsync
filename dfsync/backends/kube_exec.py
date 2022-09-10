#!/usr/bin/env python
import os, os.path, subprocess, sys, time

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

    kube_container = os.environ.get("KUBEEXEC_CONTAINER")
    kubectl_cmd = get_kubectl_exec_command(
        os.environ.get("KUBEEXEC_NAMESPACE"),
        pod_name,
        kube_container,
        os.environ.get("KUBEEXEC_KUBECONFIG"),
        os.environ.get("KUBEEXEC_CONTEXT"),
    )

    with open(f"dfsync-{kube_container}.log", "a") as f:
        container_cmd = get_container_command()
        cmd = [*kubectl_cmd, *container_cmd]
        cmd_str = " ".join(cmd)
        print(f"[{pod_name}] Running: {cmd_str}", file=f, flush=True)
        try:
            subprocess.check_call(cmd)

        except Exception as e:
            err = str(e) or type(e)
            print(f"[{pod_name}] Error: {err}", file=f, flush=True)

        finally:
            print(f"[{pod_name}] Exiting", file=f, flush=True)


if __name__ == "__main__":
    main()
