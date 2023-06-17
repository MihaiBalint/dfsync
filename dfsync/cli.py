import sys
from dfsync.monitor import main as sync_main


def dfsync(*args, **kwargs):
    sync_main()


if __name__ == "__main__":
    sync_main()
