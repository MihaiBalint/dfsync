import yaml
from urllib.parse import urlparse


def update_local_kube_config(kube_credentials):
    pass


def read_kube_credentials(kube_host, credentials_file):
    parsed = urlparse(kube_host)
    cluster_name = parsed.hostname.replace("-", "_")
    user_name = f"{cluster_name}_admin"

    try:
        credentials = yaml.safe_load(credentials_file)
        credentials["clusters"][0]["cluster"]["server"] = kube_host
        credentials["clusters"][0]["name"] = cluster_name
        credentials["users"][0]["name"] = user_name
        credentials["contexts"][0]["context"]["cluster"] = cluster_name
        credentials["contexts"][0]["context"]["user"] = user_name
        print(yaml.dump(credentials))

        return credentials
    except yaml.YAMLError as exc:
        print(exc)

    return {}
