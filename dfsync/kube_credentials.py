import os
import os.path
import yaml
from urllib.parse import urlparse

LOCAL_CREDENTIALS_FILE = os.path.expanduser("~/.kube/config")
EMPTY_CREDENTIALS = """apiVersion: v1
kind: Config
clusters: []
contexts: []
preferences: {}
users: []
current-context: ''
"""


def update_local_kube_config(new_kube_credentials):
    try:
        with open(LOCAL_CREDENTIALS_FILE, "r") as f:
            credentials = yaml.safe_load(f)
    except FileNotFoundError as e:
        credentials = yaml.safe_load(EMPTY_CREDENTIALS)
        kube_dir, _ = os.path.split(LOCAL_CREDENTIALS_FILE)
        os.makedirs(kube_dir, exist_ok=True)

    clusters_entry = new_kube_credentials["clusters"][0]
    contexts_entry = new_kube_credentials["contexts"][0]
    users_entry = new_kube_credentials["users"][0]

    server = clusters_entry["cluster"]["server"]
    cluster_name = None

    for entry in credentials["clusters"]:
        if entry["cluster"]["server"] == server and cluster_name is None:
            cluster_name = entry["name"]
            entry["name"] = clusters_entry["name"]
            entry["cluster"] = clusters_entry["cluster"]
            print(f"Updating entry in clusters section for {server}")
        elif entry["cluster"]["server"] == server and cluster_name is not None:
            print(f'Warning, found duplicate to server {entry["cluster"]["server"]}')
        else:
            print(f'Found reference to server {entry["cluster"]["server"]}')
    if cluster_name is None:
        credentials["clusters"].append(clusters_entry)
        cluster_name = clusters_entry["name"]
        print(f"Adding entry to clusters section for {server}")

    user_name = None
    for entry in credentials["contexts"]:
        if entry["context"]["cluster"] == cluster_name:
            user_name = entry["context"]["user"]
            entry["name"] = contexts_entry["name"]
            entry["context"] = contexts_entry["context"]
            print(f"Updating entry in contexts section for cluster '{cluster_name}'")
            break
    if user_name is None:
        credentials["contexts"].append(contexts_entry)
        user_name = contexts_entry["context"]["user"]
        print(f"Adding entry to contexts section for cluster '{cluster_name}'")

    found_user = None
    for entry in credentials["users"]:
        if entry["name"] == user_name:
            entry["user"] = users_entry["user"]
            found_user = True
            print(f"Updating entry in users section '{user_name}'")
            break

    if not found_user:
        credentials["users"].append(users_entry)
        print(f"Adding entry to users section '{user_name}'")

    if not credentials["current-context"]:
        credentials["current-context"] = contexts_entry["name"]

    credentials_yaml = yaml.dump(credentials)
    with open(f"{LOCAL_CREDENTIALS_FILE}.new", "w") as f:
        f.write(credentials_yaml)

    if os.path.isfile(LOCAL_CREDENTIALS_FILE):
        if os.path.isfile(f"{LOCAL_CREDENTIALS_FILE}.old"):
            os.remove(f"{LOCAL_CREDENTIALS_FILE}.old")
        os.rename(f"{LOCAL_CREDENTIALS_FILE}", f"{LOCAL_CREDENTIALS_FILE}.old")

    os.rename(f"{LOCAL_CREDENTIALS_FILE}.new", f"{LOCAL_CREDENTIALS_FILE}")

    return credentials_yaml


def contextualize_kube_credentials(kube_host, credentials_file):
    parsed = urlparse(kube_host)
    cluster_name = parsed.hostname.replace("-", "_")
    user_name = f"{cluster_name}_admin"

    try:
        credentials = yaml.safe_load(credentials_file)
        if len(credentials.get("clusters", [])) == 0:
            raise ValueError("kube config has an empty or missing 'clusters' section")
        elif len(credentials["clusters"]) > 1:
            print("Warning, kube config has multiple 'clusters', will only use the first one")

        if len(credentials.get("users", [])) == 0:
            raise ValueError("kube config has an empty or missing 'users' section")
        elif len(credentials["users"]) > 1:
            print("Warning, kube config has multiple 'users', will only use the first one")

        if len(credentials.get("contexts", [])) == 0:
            raise ValueError("kube config has an empty or missing 'contexts' section")
        elif len(credentials["contexts"]) > 1:
            print("Warning, kube config has multiple 'contexts', will only use the first one")

        clusters_entry = credentials["clusters"][0]
        clusters_entry["cluster"]["server"] = kube_host
        clusters_entry["name"] = cluster_name

        users_entry = credentials["users"][0]
        users_entry["name"] = user_name

        contexts_entry = credentials["contexts"][0]
        contexts_entry["context"]["cluster"] = cluster_name
        contexts_entry["context"]["user"] = user_name
        contexts_entry["name"] = f"kubernetes-admin@{cluster_name}"

        result = {
            "clusters": [clusters_entry],
            "users": [users_entry],
            "contexts": [contexts_entry],
        }

        return result
    except yaml.YAMLError as exc:
        print(exc)

    return {}
