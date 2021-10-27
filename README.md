### 🔄 dfsync
##### A tool to intelligently synchronize files and direcotries to remote machines.

dfsync watches local files and folders for changes and copies those changes to a remote machine. This is super useful for software development when you have to edit on one machine but must run the code on a second machine (likely on some specialized hardware).

##### Usage scenarios

Say you have some sensors attached to a Raspberry PI board, dfsync copies the python code you are editing on your developer machine (a laptop) to the Raspberry PI. It monitors your source folder for changes and every time you save a file, it syncs that file to the Raspberry PI, quickly and automatically.

What if you are developing apps targeting deployment in a kubernetes cluster? Every time you change a file, dfsync copies that source code file into the container. Sure you could use use [port-forwarding](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/) or [some of the other development tools](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/) or you could use dfsync a light-weight alternative, no server component, no priviledged DaemonSet required.

So, you are doing AI/ML development and you have a big GPU/TPU server somewhere and you have to edit your code on one machine and run it on the big server, dfsync has you covered, every time you save a file, it automatically syncs that file to the big server. The code is in sync, now it's up to you to run it.

---

### 📦 Installation

- Requirements
    - Python Version
      ```bash
      $ python --version
      Python 3.6  # At least version 3.6 or above.
      ```
    - Install using pip package manager
      ````bash
      $ pip install dfsync
      ````

### 🔨 Development
  
- Build and install dfsync on your computer
    - Make Sure **poetry** dependency management and built tool is install in your System.
    - You can find the installation instruction and other information
      about [poetry](https://python-poetry.org/docs/#osx--linux--bashonwindows-install-instructions) by clicking on
      link.
    - After Installation of **poetry** verify that it's available
      ```bash
      $ poety --version
      Poetry version 1.1.11
      ```
    - Clone the dfsync repository
      ```bash
      $ git clone https://github.com/MihaiBalint/dfsync.git
      $ cd dfsync
      $ poety install # install project dependencies
      $ poetry shell
      (.venv) $ dfsync --help  # Try running dfsync from the development venv that poerty created
      (.venv) $ exit. # exit the dfsync development venv
      $ poety build   # build and generate arch neutral dfsync-<version>-py3-none-any.whl and an archive tar.gz file.
      ```
    - If the build completed without errors and you are in the dfsync source dir, install the build on your system's python using _pip_ command
      ```bash
      $ pip install ./dist/dfsync-0.3.8-py3-none-any.whl   # Version might be different 
      ```
---
        
### 📈 Command-line usages Example
##### Example Usages:
1. Watch src directory and sync changes to a destination on the local file system.
   ```bash
   $ dfsync [src] [destination]
   # OR
   $ dfsync [destination] # Current directory will be treated as [src]
   ```
   ```bash
   $ dfsync src /home/user/absolute/path/to/target/dir # sync src directory to destination.
           Destination, rsync: '/home/user/Desktop/'
           Watching dir(s): 'dist/'; press [Ctrl-C] to exit
   $ dfsync . ../../relative/path/to/target/dir  # Sync current directory (.) into relatively mentioned path.
           Destination, rsync: '../../Desktop/'
           Watching dir(s): '.'; press [Ctrl-C] to exit
   $ dfsync ../../relative/path/to/target/dir # if source directory is omitted, current directory is considered at src directory.
   ```
2. Watch [src] [dir] and sync changes to a remote target using ssh
   ```bash
   $ dfsync src user@target-host:/home/user/absolute/paths/to/remote/host/dir # [src] to [dest] absolute directory.
   # OR
   $ dfsync build user@target-host:~/relative/path/to/user/home # [src=build] to [relative path]
   ```
3. Watch a directory [src] and sync changes to kubernetes pod/containers using the given image name
   ```bash
   $ dfsync src kube://image-name-of-awesome-api:/home/user/awesome-api # 
   # OR
   $ dfsync kube://quay.io/project/name-of-container-image:/home/path/within/container/awesome-api
   ```
---
### 👀 Command-line Reference
```
$ dfsync --help
Usage: dfsync [OPTIONS] [SOURCE]... [DESTINATION]

  Watches a folder for changes and propagates all file changes to a
  destination.

  SOURCE is a path to the folder that dfsync will monitor for changes (or
  current dir if missing)

  DESTINATION is a destination path / psuedo-url

  Example usages:

  1. Watch a dir and sync changes to a target on the local filesystem
     dfsync src /home/user/absolute/paths/to/target/dir
     dfsync . ../../relative/path/to/target/dir
     dfsync ../../relative/path/to/target/dir (if source_dir is omitted, will watch the current dir)

  2. Watch a dir and sync changes to a remote target using ssh
     dfsync src user@target-host:/home/user/absolute/paths/to/remote/host/dir
     dfsync build user@target-host:~/relative/path/to/user/home

  3. Watch a dir and sync changes to kubernetes pod/containers using the given image name
     dfsync src kube://image-name-of-awesome-api:/home/user/awesome-api
     dfsync kube://quay.io/project/name-of-container-image:/home/path/within/container/awesome-api

  dfsync is:
  * git-aware: changes to git internals, files matching .gitignore patterns and untracked files will be ignored
  * editor-aware: changes to temporary files created by source code editors will be ignored
  * transparent: every action is diligently logged in the console

Options:
  --supervisor / --no-supervisor  Try to install supervisor in container
  --kube-host TEXT                Kubernetes api host server address/hostname
  --pod-timeout INTEGER           Pod reconfiguration timeout (default is 30
                                  seconds)

  --help                          Show this message and exit.
```

---
### 📄 Pyproject.toml configuration reference
Instead of passing a large number of arguments from the command line, these can be added to a pyproject.toml file located in the source dir. See example below:

```toml
[tool.dfsync.configuration]
destination = "kube://quay.io/project/app-image-prefix:/home/app-location"
pod_timeout = 30
additional_sources = ["../api-client-lib", "../domain-lib"]
container_command = "./.venv/bin/uvicorn --host 0 --reload myproject:app"
```

