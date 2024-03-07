import pytest, yaml, tempfile

import dfsync.kube_credentials
from dfsync.kube_credentials import update_local_kube_config


@pytest.fixture
def mock_kube_credentials(mocker):
    with tempfile.NamedTemporaryFile(delete=True) as temp:
        mocker.patch("dfsync.kube_credentials.LOCAL_CREDENTIALS_FILE", temp.name)
        return temp.name


def test_update_missing_kube_config(mock_kube_credentials):
    new_kube_credentials = {
        "clusters": [{"cluster": {"server": "test_server"}, "name": "test_cluster"}],
        "contexts": [{"context": {"cluster": "test_cluster", "user": "test_user"}, "name": "test_context"}],
        "users": [{"user": {"username": "test_user"}, "name": "test_user"}],
    }
    result = update_local_kube_config(new_kube_credentials)
    assert "test_cluster" in result
    assert "test_context" in result
    assert "test_user" in result


def test_update_empty_kube_config(mock_kube_credentials):
    with open(mock_kube_credentials, "wb") as f:
        empty_config = {
            "clusters": [],
            "contexts": [],
            "users": [],
        }
        f.write(yaml.dump(empty_config).encode())

    new_kube_credentials = {
        "clusters": [{"name": "test_cluster", "cluster": {"server": "test_server"}}],
        "contexts": [{"name": "test_context", "context": {"cluster": "test_cluster", "user": "test_user"}}],
        "users": [{"name": "test_user", "user": {"username": "test_username", "password": "test_password"}}],
    }
    update_local_kube_config(new_kube_credentials)

    # Verify the results
    with open(mock_kube_credentials, "r") as f:
        credentials = yaml.safe_load(f)

        assert credentials["clusters"][0]["name"] == "test_cluster"
        assert credentials["clusters"][0]["cluster"]["server"] == "test_server"
        assert credentials["contexts"][0]["name"] == "test_context"
        assert credentials["contexts"][0]["context"]["cluster"] == "test_cluster"
        assert credentials["contexts"][0]["context"]["user"] == "test_user"
        assert credentials["users"][0]["name"] == "test_user"
        assert credentials["users"][0]["user"]["username"] == "test_username"
        assert credentials["users"][0]["user"]["password"] == "test_password"


def test_update_existing_kube_config(mock_kube_credentials):
    with open(mock_kube_credentials, "wb") as f:
        existing_config = {
            "clusters": [
                {"name": "existing_cluster", "cluster": {"server": "existing_server"}},
            ],
            "contexts": [
                {"name": "existing_context", "context": {"cluster": "existing_cluster", "user": "existing_user"}}
            ],
            "users": [
                {"name": "existing_user", "user": {"username": "existing_username", "password": "existing_password"}}
            ],
        }
        f.write(yaml.dump(existing_config).encode())

    new_kube_credentials = {
        "clusters": [{"name": "new_cluster", "cluster": {"server": "new_server"}}],
        "contexts": [{"name": "new_context", "context": {"cluster": "new_cluster", "user": "new_user"}}],
        "users": [{"name": "new_user", "user": {"username": "new_username", "password": "new_password"}}],
    }
    update_local_kube_config(new_kube_credentials)

    # Verify the results
    with open(mock_kube_credentials, "r") as f:
        credentials = yaml.safe_load(f)

        assert len(credentials["clusters"]) == 2
        assert len(credentials["contexts"]) == 2
        assert len(credentials["users"]) == 2

        assert credentials["clusters"][1]["name"] == "new_cluster"
        assert credentials["clusters"][1]["cluster"]["server"] == "new_server"
        assert credentials["contexts"][1]["name"] == "new_context"
        assert credentials["contexts"][1]["context"]["cluster"] == "new_cluster"
        assert credentials["contexts"][1]["context"]["user"] == "new_user"
        assert credentials["users"][1]["name"] == "new_user"
        assert credentials["users"][1]["user"]["username"] == "new_username"
        assert credentials["users"][1]["user"]["password"] == "new_password"
