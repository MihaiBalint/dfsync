import json
import urllib.request


def get_package_version(package_name):
    try:
        from importlib.metadata import version

        return version(package_name)
    except:
        pass

    try:
        import pkg_resources

        return pkg_resources.get_distribution(package_name).version
    except:
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
    except Exception as e:
        return get_installed_version()


def parse_version(version_str):
    if not version_str:
        return version_str
    parsed_version = []
    for part in version_str.split("."):
        try:
            parsed_version.append(int(part))
        except:
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
