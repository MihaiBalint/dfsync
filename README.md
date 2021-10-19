### dfsync
##### An Intelligent remote directories and files synchronization Tool.

### Installation

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
            pip install ./dist/dfsync-0.3.8-py3-none-any.whl
          ```

### Commandline usages Example

### Commandline Reference

### Tool Configuration
