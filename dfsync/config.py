import os, toml
from collections import namedtuple

Configuration = namedtuple("Configuration", ("additional_sources", "destination", "pod_timeout", "container_command"))
default_config = Configuration(additional_sources=[], destination=None, pod_timeout=30, container_command=None)


def get_absolute_path_relative_to(pyproject_path, relative_path):
    if relative_path == os.path.abspath(relative_path):
        # It's already an absolute path, so don't compute anything
        return relative_path

    parent, _ = os.path.split(os.path.abspath(pyproject_path))
    abs_path = os.path.abspath(os.path.join(parent, relative_path))
    current_dir = os.path.abspath(os.path.curdir) + os.path.sep
    if abs_path.startswith(current_dir):
        return abs_path[len(current_dir) :]
    else:
        return abs_path


def _read_pyproject(pyproject_path):
    config = default_config
    with open(pyproject_path, "r") as f:
        content = toml.loads(f.read())
        dfsync_config = content["tool"].get("dfsync", {}).get("configuration", {})
        adjusted_sources = []
        for src_path in dfsync_config.get("additional_sources", []):
            adjusted_sources.append(get_absolute_path_relative_to(pyproject_path, src_path))
        config = config._replace(**{**dfsync_config, "additional_sources": adjusted_sources})
    return config


def _get_pyproject_path(path):
    pyproject_path = os.path.join(path, "pyproject.toml")
    return pyproject_path if os.path.isfile(pyproject_path) else None


def _merge_config(c1, c2):
    result = c1
    pod_timeout = c2.pod_timeout if c2.pod_timeout != default_config.pod_timeout else c1.pod_timeout

    result = c1._replace(
        **{
            **c2._asdict(),
            "additional_sources": [*c1.additional_sources, *c2.additional_sources],
            "destination": c2.destination or c1.destination,
        }
    )
    return result


def read_config(*pyproject_parent_dirs):
    config = default_config
    for path in pyproject_parent_dirs:
        pyproject_path = _get_pyproject_path(path)
        if pyproject_path is None:
            continue
        try:
            config = _merge_config(config, _read_pyproject(pyproject_path))
        except Exception as e:
            print(f"Skipping {pyproject_path} - {e}")
            continue

    return config
