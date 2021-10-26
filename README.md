### 🔄 dfsync
##### An Intelligent remote directories and files synchronization Tool.

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
    - Build and install at your computer
        - Make Sure **poetry** dependency management and built tool is install in your System.
        - You can find the installation instruction and other information
          about [poetry](https://python-poetry.org/docs/#osx--linux--bashonwindows-install-instructions) by clicking on
          link.
        - After Installation of **poetry** you can verify the version and help page
      ```bash
      $ poety --version
      Poetry version 1.1.11
      $ poety --help
      Poetry version 1.1.11
  
      USAGE
      poetry [-h] [-q] [-v [<...>]] [-V] [--ansi] [--no-ansi] [-n] <command>
           [<arg1>] ... [<argN>]
  
      ARGUMENTS
      <command>              The command to execute
      <arg>                  The arguments of the command
      
      <...line truncated>
      ```
        - Clone the repository using command
          ```bash
            $ git clone https://github.com/MihaiBalint/dfsync.git
            $ cd dfsync
            $ poety install # install project dependencies
            $ poety build   # build and generate arch neutral dfsync-<version>-py3-none-any.whl and an archive tar.gz file.
          ```
        - Now, Install it using _pip_ command.
        - I am considering you have built it and your shell is active in dfsync directory
        - Version might be different check, Verify generated file name before installation.
          ```bash
            $ pip install ./dist/dfsync-0.3.8-py3-none-any.whl
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
```bash
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
