import click
import json
import subprocess
import sys
import urllib.request
from typing import Optional

from dfsync.lib import ControlledThreadedOperation


def get_package_version(package_name):
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        pass

    try:
        import pkg_resources

        return pkg_resources.get_distribution(package_name).version
    except Exception:
        pass

    return None


def get_installed_version():
    package_name = "dfsync"
    version = get_package_version(package_name)
    return version or "development"


def get_available_versions(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=10"
    with urllib.request.urlopen(url, timeout=5.0) as f:
        data = f.read(20480)
        return [tag["name"] for tag in json.loads(data)]


def get_latest_version():
    try:
        versions = get_available_versions("MihaiBalint", "dfsync")
        if not versions:
            raise ValueError("No version visible on github")

        return versions[0]
    except Exception:
        return get_installed_version()


def parse_version(version_str):
    if not version_str:
        return version_str
    parsed_version = []
    for part in version_str.split("."):
        try:
            parsed_version.append(int(part))
        except Exception:
            parsed_version.append(part)
    return parsed_version


def is_older_version(v1, v2):
    if not v1:
        return True
    elif not v2:
        return False

    p1 = parse_version(v1)
    p2 = parse_version(v2)
    return p1 < p2


class AsyncVersionChecker(ControlledThreadedOperation):
    def __init__(self):
        super().__init__()
        self.latest = None
        self.installed = None
        self.installed_is_older = None
        self._cta_count = None

    def _run_once(self):
        self.installed = get_installed_version()
        self.latest = get_latest_version()
        self.installed_is_older = is_older_version(self.installed, self.latest)
        self._is_install_editable = is_installed_in_editable_mode("dfsync")
        self._cta_count = 0
        self.stop()

    @property
    def should_emit_update_warning(self):
        return self.is_completed and self.installed_is_older and self._cta_count < 1

    def set_emitted_update_warning(self):
        self._cta_count += 1

    def get_update_warning(self):
        if self._is_install_editable:
            return f"dfsync ver. {self.latest} is available, please update! ({self.installed} is installed)"
        else:
            return f"dfsync ver. {self.latest} is available ({self.installed} is installed), please update using `dfsync self-update`"


def _read_editable_location_from_pip_show_output(out: str) -> Optional[str]:
    editable_label = "Editable project location: "
    site_packages_label = "site-packages"
    site_packages_lines = []

    for line in out.split("\n"):
        if line.startswith("Location: "):
            continue
        if line.startswith(editable_label):
            return line[len(editable_label) :].strip()
        if site_packages_label in line:
            site_packages_lines.append(line)

    return "UNKNOWN-EDITABLE-LOCATION" if len(site_packages_lines) > 0 else None


def is_installed_in_editable_mode(package_name: str) -> bool:
    try:
        out = subprocess.check_output([sys.executable, "-m", "pip", "show", "-f", package_name]).decode()
        editable_location = _read_editable_location_from_pip_show_output(out)
        return editable_location is not None
    except Exception:
        return False


def update_package(package_name: str):
    click.echo(f"Running {sys.executable} -m pip install --upgrade {package_name}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", package_name])
    except Exception as e:
        click.echo(f"Failed to update {package_name}: {e}")
