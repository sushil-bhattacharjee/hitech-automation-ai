# Challenge E5-TYPER: GitLab API with Typer Framework

## Challenge Overview

Design a CLI application to interact with a private GitLab instance (`https://gitlab.hitech.com`) using the Typer framework and OAuth2.0 Bearer token authentication. The CLI must support Typer apps, sub-apps (subgroups), commands with various option types (Enum-based Choice, boolean flag pairs, boolean flags, required integer via `typer.Option()`, positional arguments via `typer.Argument()`), and module-level state sharing via a dictionary.

---

## TODO List

### TODO-1: Configure OAuth2.0 Bearer token authentication
Update `self.headers` with the proper Authorization header using the `token` parameter passed to the `GitlabAPI` constructor.

### TODO-2: Create Typer apps and wire up the CLI structure
Create the main `app` and sub-app `individual_app`, register the sub-app, and add `@app.command()` decorators to register `listprojects`, `project`, `projectpath`, and `branches`.

```
$ python3 e5_typer.py --help

 Usage: e5_typer.py [OPTIONS] COMMAND [ARGS]...

╭─ Commands ────────────────────────────────────╮
│ branches                                      │
│ listprojects                                  │
│ project                                       │
│ projectpath                                   │
│ individual                                    │
╰───────────────────────────────────────────────╯
```

### TODO-3: Add the '--outformat' option to the 'listprojects' command
Define the `outformat` function parameter using Typer's type-annotation approach with `typer.Option()`. Use the `OutFormat` Enum (already provided) to restrict values to `lines` and `raw`, defaulting to `lines`.

```
$ python3 e5_typer.py listprojects --help

 Usage: e5_typer.py listprojects [OPTIONS]

╭─ Options ─────────────────────────────────────╮
│ --outformat,--o  [lines|raw]  [default: lines]│
│ --help                        Show this ...   │
╰───────────────────────────────────────────────╯
```

### TODO-4: Create 'project' command with '--all/--project' boolean flag pair
Define the `all` function parameter using `typer.Option()` with a boolean flag pair. The `--all/--project` pair defaults to `True` with custom `show_default` text.

```
$ python3 e5_typer.py project --help

 Usage: e5_typer.py project [OPTIONS]

╭─ Options ─────────────────────────────────────╮
│ --all  --project  Show all projects or        │
│                   specific project             │
│                   [default: (all: show all     │
│                   projects)]                   │
│ --help            Show this message and exit.  │
╰───────────────────────────────────────────────╯
```

### TODO-5: Create 'projectpath' with required integer option and boolean flag
Define the function parameters for `projectpath` using `typer.Option()`:
- `--project` (type: int, required) — Help text: "Project path"
- `--showgid` (short form: `--g`) — boolean flag. Help text: "Show GID of tasks"

```
$ python3 e5_typer.py projectpath --help

 Usage: e5_typer.py projectpath [OPTIONS]

╭─ Options ─────────────────────────────────────╮
│ *  --project      INTEGER  Project path       │
│                            [required]          │
│    --showgid,--g           Show GID of tasks   │
│    --help                  Show this ...       │
╰───────────────────────────────────────────────╯
```

### TODO-6: Create 'branches' command with a positional argument and a details flag
Register `branches` under the main app. It accepts `project_id` as a positional ARGUMENT (integer) using `typer.Argument()`, and `--details` / `-d` as a boolean flag using `typer.Option()`.

```
$ python3 e5_typer.py branches --help

 Usage: e5_typer.py branches [OPTIONS] PROJECT_ID

  List branches for a specific project

╭─ Arguments ───────────────────────────────────╮
│ *  PROJECT_ID  INTEGER  [required]             │
╰───────────────────────────────────────────────╯
╭─ Options ─────────────────────────────────────╮
│ -d, --details           Show detailed branch  │
│                         info                   │
│ --help                  Show this message ...  │
╰───────────────────────────────────────────────╯

$ python3 e5_typer.py branches 16
Branches for project 16:

  • bugfix
  • feature
  • main

$ python3 e5_typer.py branches 16 -d
Branches for project 16:

  • bugfix
    Commit: b36e9379
    Message: Initial commit
    Protected: False

  • feature
    Commit: fa1b3006
    Message: Adding First Solution
    Protected: False

  • main
    Commit: fbbb6ed2
    Message: Adding First File
    Protected: True
```

### TODO-7: Create 'namespace' command with '--show/--not-show' boolean flag pair
Define the `show` function parameter using `typer.Option()` with `--show/--not-show` flag pair, defaulting to `False`.

```
$ python3 e5_typer.py individual path --help

 Usage: e5_typer.py individual path [OPTIONS]

╭─ Options ─────────────────────────────────────╮
│ --show  --not-show  [default: not-show]        │
│ --help              Show this message ...      │
╰───────────────────────────────────────────────╯
```

### TODO-8: Register 'namespace' and 'commitmessage' under the individual sub-app
Register both commands to `individual_app` using `@individual_app.command()` with the `name` parameter to alias them as `path` and `message`.

```
$ python3 e5_typer.py individual --help

 Usage: e5_typer.py individual [OPTIONS] COMMAND [ARGS]...

╭─ Commands ────────────────────────────────────╮
│ path                                          │
│ message                                       │
╰───────────────────────────────────────────────╯
```

---

## Initial Files

### pat.json
```json
{ "PAT": "glpat-yourPAT" }
```

### e5_typer.py
```python
import requests
import typer
import json
import urllib3
from enum import Enum

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GitlabAPI():
    headers = {}
    def __init__(self, token):
        self.headers['Accept'] = 'application/json'
        self.headers['Content-Type'] = 'application/json'

        #! TODO-1: Configure OAuth2.0 Bearer token authentication
        # The GitLab API requires an OAuth2.0 Bearer token for authentication.
        # Using the 'token' parameter, update self.headers with the appropriate
        # Authorization header so that all subsequent API requests are authenticated.
        # Ref: The token value is read from pat.json and passed to this constructor.

        # TODO-1 <---- Add proper header for OAuth2.0 authentication ---->


    def get(self, api_endpoint_path):
        response = requests.get("https://gitlab.hitech.com/api/v4/" + api_endpoint_path, headers=self.headers, verify=False)
        return response.json()


# Module-level state replaces Click's ctx.obj
state = {"gitlab": None}


#! TODO-2: Create Typer apps and wire up the CLI structure
#
# In Typer, the equivalent of Click's @click.group() is creating a typer.Typer() instance.
# Requirements:
#   - Create the main Typer app instance.
#   - Create a separate Typer instance for the 'individual' sub-app.
#   - Register the individual sub-app under the main app with name "individual".
#   - The @app.callback() (already provided below) replaces Click's group function
#     for initialization logic.
#   - Register listprojects, project, projectpath, and branches as commands under
#     the main app using the @app.command() decorator (see TODO-3 through TODO-6).
#
# Expected help output:
"""
$ python3 e5_typer.py --help

 Usage: e5_typer.py [OPTIONS] COMMAND [ARGS]...

╭─ Commands ────────────────────────────────────╮
│ branches                                      │
│ listprojects                                  │
│ project                                       │
│ projectpath                                   │
│ individual                                    │
╰───────────────────────────────────────────────╯
"""

# TODO-2 <---- Create the main Typer app ---->
# TODO-2 <---- Create the individual sub-app ---->
# TODO-2 <---- Register the individual sub-app under main app ---->

# @app.callback() replaces @click.group() + @click.pass_context
@app.callback()
def main():
    config = json.load(open("pat.json"))
    state["gitlab"] = GitlabAPI(config["PAT"])


# Typer uses Enum instead of click.Choice
class OutFormat(str, Enum):
    lines = "lines"
    raw = "raw"


#! TODO-3: Register 'listprojects' and add the '--outformat' option
#
# Register 'listprojects' as a command under the main app.
# The function parameter must use Typer's type-annotation pattern:
#   - Parameter name: outformat
#   - Type annotation: OutFormat (the Enum defined above)
#   - Default via typer.Option() with:
#       a) Default value: OutFormat.lines
#       b) Long form: "--outformat"
#       c) Short form: "--o"
#       d) show_default enabled
#
# Expected help output:
"""
$ python3 e5_typer.py listprojects --help

╭─ Options ─────────────────────────────────────╮
│ --outformat,--o  [lines|raw]  [default: lines]│
│ --help                        Show this ...   │
╰───────────────────────────────────────────────╯
"""

# TODO-3 <---- Add proper decorator ---->
def listprojects(# TODO-3 <---- Define the outformat parameter with typer.Option() ---->
):
    projects = state["gitlab"].get("projects")
    print("Projects: ")
    for project in projects:
        if outformat == OutFormat.lines:
            print(f"id: {project['id']} name: {project['name']}")
        elif outformat == OutFormat.raw:
            print(f"id: {project['id']}")


#! TODO-4: Create 'project' command with '--all/--project' boolean flag pair
#
# Register 'project' as a command under the main app.
# The function parameter must use Typer's type-annotation pattern:
#   - Parameter name: all
#   - Type annotation: bool
#   - Default via typer.Option() with:
#       a) Default value: True
#       b) Flag pair: "--all/--project"
#       c) show_default text: "all: show all projects"
#       d) help text: "Show all projects or specific project"
#   - When --all: list all projects as "<id> - <n>"
#   - When --project: fetch and display project ID 21's main branch web_url
#
# Expected help output:
"""
$ python3 e5_typer.py project --help

╭─ Options ─────────────────────────────────────╮
│ --all  --project  Show all projects or        │
│                   specific project             │
│                   [default: (all: show all     │
│                   projects)]                   │
│ --help            Show this message and exit.  │
╰───────────────────────────────────────────────╯
"""

# TODO-4 <---- Add proper decorator ---->
def project(# TODO-4 <---- Define the 'all' parameter with typer.Option() ---->
):
    if all:
        path = state["gitlab"].get("projects")
        for p in path:
            print(f"{p['id']} - {p['name']}")
    else:
        path = state["gitlab"].get("projects/21/repository/branches/main")
        print("\n PRINTING THE PROJECT ID 21 e4_gitlab")
        print(path["web_url"])


#! TODO-5: Create 'projectpath' with required integer option and boolean flag
#
# Register 'projectpath' as a command under the main app.
# Define two function parameters using Typer's type-annotation pattern:
#   - 'project': type int, required (no default value), help: "Project path"
#     Hint: In Typer, use ... (Ellipsis) as the default to make an option required.
#   - 'showgid': type bool, flag (default False), long: "--showgid", short: "--g",
#     help: "Show GID of tasks"
#   - When --showgid is passed: print "id: <id> path: <path>"
#   - When --showgid is omitted: print only the path
#
# Expected help output:
"""
$ python3 e5_typer.py projectpath --help

╭─ Options ─────────────────────────────────────╮
│ *  --project      INTEGER  Project path       │
│                            [required]          │
│    --showgid,--g           Show GID of tasks   │
│    --help                  Show this ...       │
╰───────────────────────────────────────────────╯
"""

# TODO-5 <---- Add proper decorator ---->
def projectpath(
    # TODO-5 <---- Define the 'project' parameter with typer.Option() ---->,
    # TODO-5 <---- Define the 'showgid' parameter with typer.Option() ---->
):
    path = state["gitlab"].get(f"projects/{project}")
    print("Project path: ")
    if showgid:
        print(f"id: {path['id']} path: {path['path']}")
    else:
        print(path['path'])


#! TODO-6: Create 'branches' command with a positional argument and a details flag
#
# Register 'branches' as a command under the main app.
# Define two function parameters:
#   - 'project_id': type int, positional ARGUMENT (use typer.Argument()).
#   - 'details': type bool, option flag with long form '--details' and short form '-d'.
#     Help text: "Show detailed branch info"
#   - The function docstring must be: "List branches for a specific project"
#   - Without -d: print each branch name as "  • <n>"
#   - With -d: print branch name, first 8 chars of commit ID, commit message
#     (stripped), and protected status.
#
# Expected output:
"""
$ python3 e5_typer.py branches --help

 Usage: e5_typer.py branches [OPTIONS] PROJECT_ID

  List branches for a specific project

╭─ Arguments ───────────────────────────────────╮
│ *  PROJECT_ID  INTEGER  [required]             │
╰───────────────────────────────────────────────╯
╭─ Options ─────────────────────────────────────╮
│ -d, --details           Show detailed branch  │
│                         info                   │
│ --help                  Show this message ...  │
╰───────────────────────────────────────────────╯

$ python3 e5_typer.py branches 16
Branches for project 16:

  • bugfix
  • feature
  • main

$ python3 e5_typer.py branches 16 -d
Branches for project 16:

  • bugfix
    Commit: b36e9379
    Message: Initial commit
    Protected: False

  • feature
    Commit: fa1b3006
    Message: Adding First Solution
    Protected: False

  • main
    Commit: fbbb6ed2
    Message: Adding First File
    Protected: True
"""

# TODO-6 <---- Add proper decorator ---->
def branches(
    # TODO-6 <---- Define the 'project_id' parameter with typer.Argument() ---->,
    # TODO-6 <---- Define the 'details' parameter with typer.Option() ---->
):
    """List branches for a specific project"""
    branches_data = state["gitlab"].get(f"projects/{project_id}/repository/branches")
    print(f"Branches for project {project_id}:\n")
    for branch in branches_data:
        if details:
            print(f"  • {branch['name']}")
            print(f"    Commit: {branch['commit']['id'][:8]}")
            print(f"    Message: {branch['commit']['message'].strip()}")
            print(f"    Protected: {branch['protected']}\n")
        else:
            print(f"  • {branch['name']}")


#! TODO-7: Create 'namespace' command with '--show/--not-show' boolean flag pair
#
# Define the 'show' function parameter using Typer's type-annotation pattern:
#   - Parameter name: show
#   - Type annotation: bool
#   - Default via typer.Option() with:
#       a) Default value: False
#       b) Flag pair: "--show/--not-show"
#       c) show_default enabled
#   - When --show: print "id: <id> <namespace_name>" for each project
#   - When --not-show: print "id: <id> <path_with_namespace>" for each project
#   - This command will be registered under individual_app in TODO-8.
#
# Expected help output (accessed as 'individual path'):
"""
$ python3 e5_typer.py individual path --help

╭─ Options ─────────────────────────────────────╮
│ --show  --not-show  [default: not-show]        │
│ --help              Show this message ...      │
╰───────────────────────────────────────────────╯
"""

# TODO-8 <---- Add proper decorator to register as 'path' under individual_app ---->
def namespace(# TODO-7 <---- Define the 'show' parameter with typer.Option() ---->
):
    path = state["gitlab"].get("projects")
    if show:
        for entry in path:
            print(f"id: {entry['id']} {entry['namespace']['name']}")
    else:
        for entry in path:
            print(f"id: {entry['id']} {entry['path_with_namespace']}")


#! TODO-8: Register 'commitmessage' under the individual sub-app
#
# Register 'commitmessage' under individual_app with the name "message".
# The final CLI tree must be:
#
#   app (Typer)
#   ├── listprojects      ← @app.command()
#   ├── project           ← @app.command()
#   ├── projectpath       ← @app.command()
#   ├── branches          ← @app.command()
#   └── individual (sub-app)
#       ├── path          ← 'namespace', registered with name="path"
#       └── message       ← 'commitmessage', registered with name="message"
#
# Expected help output:
"""
$ python3 e5_typer.py individual --help

╭─ Commands ────────────────────────────────────╮
│ path                                          │
│ message                                       │
╰───────────────────────────────────────────────╯
"""

# TODO-8 <---- Add proper decorator to register as 'message' under individual_app ---->
def commitmessage():
    projects = state["gitlab"].get("projects")
    for entry in projects:
        commit = state["gitlab"].get(f"projects/{entry['id']}/repository/branches/main")
        print(f"{entry['name']} | commit_id: {commit['commit']['id']} | {commit['commit']['message']}")


if __name__ == "__main__":
    app()
```

---

## Solution as Last Resort

<details>
<summary>⚠️ Click to reveal solution — try solving it yourself first!</summary>

```python
import requests
import typer
import json
import urllib3
from enum import Enum

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GitlabAPI():
    headers = {}
    def __init__(self, token):
        self.headers['Accept'] = 'application/json'
        self.headers['Content-Type'] = 'application/json'
        self.headers['Authorization'] = f"Bearer {token}"                                               #! TODO-1

    def get(self, api_endpoint_path):
        response = requests.get("https://gitlab.hitech.com/api/v4/" + api_endpoint_path, headers=self.headers, verify=False)
        return response.json()


# Module-level state replaces Click's ctx.obj
state = {"gitlab": None}

app = typer.Typer()                                                                                     #! TODO-2
individual_app = typer.Typer()                                                                          #! TODO-2
app.add_typer(individual_app, name="individual")                                                        #! TODO-2

# @app.callback() replaces @click.group() + @click.pass_context
@app.callback()
def main():
    config = json.load(open("pat.json"))
    state["gitlab"] = GitlabAPI(config["PAT"])


# Typer uses Enum instead of click.Choice
class OutFormat(str, Enum):
    lines = "lines"
    raw = "raw"


@app.command()                                                                                          #! TODO-3
def listprojects(outformat: OutFormat = typer.Option(OutFormat.lines, "--outformat", "--o",
                                                      show_default=True)):                              #! TODO-3
    projects = state["gitlab"].get("projects")
    print("Projects: ")
    for project in projects:
        if outformat == OutFormat.lines:
            print(f"id: {project['id']} name: {project['name']}")
        elif outformat == OutFormat.raw:
            print(f"id: {project['id']}")


@app.command()                                                                                          #! TODO-4
def project(all: bool = typer.Option(True, "--all/--project",
                                      show_default="all: show all projects",
                                      help="Show all projects or specific project")):                   #! TODO-4
    if all:
        path = state["gitlab"].get("projects")
        for p in path:
            print(f"{p['id']} - {p['name']}")
    else:
        path = state["gitlab"].get("projects/21/repository/branches/main")
        print("\n PRINTING THE PROJECT ID 21 e4_gitlab")
        print(path["web_url"])


@app.command()                                                                                          #! TODO-5
def projectpath(
    project: int = typer.Option(..., "--project", help="Project path"),                                 #! TODO-5
    showgid: bool = typer.Option(False, "--showgid", "--g", help="Show GID of tasks")                   #! TODO-5
):
    path = state["gitlab"].get(f"projects/{project}")
    print("Project path: ")
    if showgid:
        print(f"id: {path['id']} path: {path['path']}")
    else:
        print(path['path'])


@app.command()                                                                                          #! TODO-6
def branches(
    project_id: int = typer.Argument(..., help="Project ID"),                                           #! TODO-6
    details: bool = typer.Option(False, "--details", "-d", help="Show detailed branch info")            #! TODO-6
):
    """List branches for a specific project"""
    branches_data = state["gitlab"].get(f"projects/{project_id}/repository/branches")
    print(f"Branches for project {project_id}:\n")
    for branch in branches_data:
        if details:
            print(f"  • {branch['name']}")
            print(f"    Commit: {branch['commit']['id'][:8]}")
            print(f"    Message: {branch['commit']['message'].strip()}")
            print(f"    Protected: {branch['protected']}\n")
        else:
            print(f"  • {branch['name']}")


@individual_app.command(name="path")                                                                    #! TODO-8
def namespace(show: bool = typer.Option(False, "--show/--not-show", show_default=True)):                #! TODO-7
    path = state["gitlab"].get("projects")
    if show:
        for entry in path:
            print(f"id: {entry['id']} {entry['namespace']['name']}")
    else:
        for entry in path:
            print(f"id: {entry['id']} {entry['path_with_namespace']}")


@individual_app.command(name="message")                                                                 #! TODO-8
def commitmessage():
    projects = state["gitlab"].get("projects")
    for entry in projects:
        commit = state["gitlab"].get(f"projects/{entry['id']}/repository/branches/main")
        print(f"{entry['name']} | commit_id: {commit['commit']['id']} | {commit['commit']['message']}")


if __name__ == "__main__":
    app()
```

</details>

---

## Detailed Test Result

<details>
<summary>Click to display</summary>

```
$ python3 e5_typer.py --help

 Usage: e5_typer.py [OPTIONS] COMMAND [ARGS]...

╭─ Options ──────────────────────────────────────────╮
│ --install-completion    Install completion          │
│ --show-completion       Show completion             │
│ --help                  Show this message and exit. │
╰────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────╮
│ branches                                           │
│ listprojects                                       │
│ project                                            │
│ projectpath                                        │
│ individual                                         │
╰────────────────────────────────────────────────────╯
```

```
$ python3 e5_typer.py listprojects --help

 Usage: e5_typer.py listprojects [OPTIONS]

╭─ Options ──────────────────────────────────────────╮
│ --outformat,--o  [lines|raw]  [default: lines]     │
│ --help                        Show this message    │
│                               and exit.            │
╰────────────────────────────────────────────────────╯
```

```
$ python3 e5_typer.py listprojects --o lines
Projects: 
id: 21 name: e4_gitlab
id: 20 name: C102-Flask-RestX
id: 19 name: C101-Python-Click
id: 18 name: YANG
id: 17 name: Flask_RESTX
id: 16 name: CLICK_GRAPHQL
id: 15 name: TestA_Workbook
id: 14 name: Test_Moc1
id: 11 name: C305-Gitlab-CICD
id: 10 name: C305-Gitlab_CICD
id: 7 name: app2lb2
id: 6 name: OSPFCICDthruGithub
id: 5 name: OSPFCICD
id: 4 name: Terraform2
id: 3 name: CICD
id: 2 name: application
id: 1 name: terraform
```

```
$ python3 e5_typer.py listprojects
Projects: 
id: 21 name: e4_gitlab
id: 20 name: C102-Flask-RestX
id: 19 name: C101-Python-Click
id: 18 name: YANG
id: 17 name: Flask_RESTX
id: 16 name: CLICK_GRAPHQL
id: 15 name: TestA_Workbook
id: 14 name: Test_Moc1
id: 11 name: C305-Gitlab-CICD
id: 10 name: C305-Gitlab_CICD
id: 7 name: app2lb2
id: 6 name: OSPFCICDthruGithub
id: 5 name: OSPFCICD
id: 4 name: Terraform2
id: 3 name: CICD
id: 2 name: application
id: 1 name: terraform
```

```
$ python3 e5_typer.py listprojects --o raw
Projects: 
id: 21
id: 20
id: 19
id: 18
id: 17
id: 16
id: 15
id: 14
id: 11
id: 10
id: 7
id: 6
id: 5
id: 4
id: 3
id: 2
id: 1
```

```
$ python3 e5_typer.py project --help

 Usage: e5_typer.py project [OPTIONS]

╭─ Options ──────────────────────────────────────────╮
│ --all  --project  Show all projects or specific    │
│                   project                          │
│                   [default: (all: show all         │
│                   projects)]                       │
│ --help            Show this message and exit.      │
╰────────────────────────────────────────────────────╯
```

```
$ python3 e5_typer.py project
21 - e4_gitlab
20 - C102-Flask-RestX
19 - C101-Python-Click
18 - YANG
17 - Flask_RESTX
16 - CLICK_GRAPHQL
15 - TestA_Workbook
14 - Test_Moc1
11 - C305-Gitlab-CICD
10 - C305-Gitlab_CICD
7 - app2lb2
6 - OSPFCICDthruGithub
5 - OSPFCICD
4 - Terraform2
3 - CICD
2 - application
1 - terraform
```

```
$ python3 e5_typer.py project --project

 PRINTING THE PROJECT ID 21 e4_gitlab
https://gitlab.hitech.com/mock3/e4_gitlab/-/tree/main
```

```
$ python3 e5_typer.py projectpath --help

 Usage: e5_typer.py projectpath [OPTIONS]

╭─ Options ──────────────────────────────────────────╮
│ *  --project      INTEGER  Project path [required] │
│    --showgid,--g           Show GID of tasks       │
│    --help                  Show this message and   │
│                            exit.                   │
╰────────────────────────────────────────────────────╯
```

```
$ python3 e5_typer.py projectpath --project 16
Project path: 
click_graphql
```

```
$ python3 e5_typer.py projectpath --project 16 --g
Project path: 
id: 16 path: click_graphql
```

```
$ python3 e5_typer.py branches --help

 Usage: e5_typer.py branches [OPTIONS] PROJECT_ID

  List branches for a specific project

╭─ Arguments ────────────────────────────────────────╮
│ *  PROJECT_ID  INTEGER  [required]                  │
╰────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────╮
│ -d, --details           Show detailed branch info  │
│ --help                  Show this message and exit. │
╰────────────────────────────────────────────────────╯
```

```
$ python3 e5_typer.py branches 16
Branches for project 16:

  • bugfix
  • feature
  • main
```

```
$ python3 e5_typer.py branches 16 -d
Branches for project 16:

  • bugfix
    Commit: b36e9379
    Message: Initial commit
    Protected: False

  • feature
    Commit: fa1b3006
    Message: Adding First Solution
    Protected: False

  • main
    Commit: fbbb6ed2
    Message: Adding First File
    Protected: True
```

```
$ python3 e5_typer.py branches 16 --details
Branches for project 16:

  • bugfix
    Commit: b36e9379
    Message: Initial commit
    Protected: False

  • feature
    Commit: fa1b3006
    Message: Adding First Solution
    Protected: False

  • main
    Commit: fbbb6ed2
    Message: Adding First File
    Protected: True
```

```
$ python3 e5_typer.py individual --help

 Usage: e5_typer.py individual [OPTIONS] COMMAND [ARGS]...

╭─ Options ──────────────────────────────────────────╮
│ --help          Show this message and exit.         │
╰────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────╮
│ path                                               │
│ message                                            │
╰────────────────────────────────────────────────────╯
```

```
$ python3 e5_typer.py individual path --help

 Usage: e5_typer.py individual path [OPTIONS]

╭─ Options ──────────────────────────────────────────╮
│ --show  --not-show  [default: not-show]             │
│ --help              Show this message and exit.     │
╰────────────────────────────────────────────────────╯
```

```
$ python3 e5_typer.py individual path
id: 21 mock3/e4_gitlab
id: 20 mock/c102-flask-restx
id: 19 mock/c101-python-click
id: 18 workbook/yang
id: 17 workbook/flask_restx
id: 16 workbook/click_graphql
id: 15 root/testa_workbook
id: 14 root/test_moc1
id: 11 root/c305-gitlab-cicd
id: 10 root/c305-gitlab_cicd
id: 7 root/app2lb2
id: 6 root/ospfcicdthrugithub
id: 5 root/ospfcicd
id: 4 root/Terraform2
id: 3 root/cicd
id: 2 root/application
id: 1 root/terraform
```

```
$ python3 e5_typer.py individual path --show
id: 21 mock3
id: 20 Mock
id: 19 Mock
id: 18 workbook
id: 17 workbook
id: 16 workbook
id: 15 Administrator
id: 14 Administrator
id: 11 Administrator
id: 10 Administrator
id: 7 Administrator
id: 6 Administrator
id: 5 Administrator
id: 4 Administrator
id: 3 Administrator
id: 2 Administrator
id: 1 Administrator
```

```
$ python3 e5_typer.py individual message
e4_gitlab | commit_id: 544a2a5a2c5b6ebe4548216bc93e3b2770b20a5e | adding removing ssh keys instruction in .gitlba

C102-Flask-RestX | commit_id: 14155bf64adef172d40399115c8bf6d828276a5b | Initial commit
C101-Python-Click | commit_id: 294689eec6079fee69a1ba47225c08bcfa470e11 | adding test file
YANG | commit_id: 23bfed92b4278457e9b15369ea549983251163d9 | Initial commit
Flask_RESTX | commit_id: b157d0020eec0e555cbad4bf9b2a5c4546cd05d2 | Initial commit
CLICK_GRAPHQL | commit_id: fbbb6ed2f460e192c175b9567f2a50eccff795ae | Adding First File
TestA_Workbook | commit_id: 81d94c5eef2a6e07b8a5a3e9265a63f15d409e73 | Initial commit
Test_Moc1 | commit_id: 59a57060ad9bdbece2e5445849b0e6be7d602f05 | Initial commit
C305-Gitlab-CICD | commit_id: 6140cfef61356fe33807d7d552b74c9d12726327 | just add it

C305-Gitlab_CICD | commit_id: 8fda10359f0e2ac524d50647740562ccd569e35f | Initial commit
app2lb2 | commit_id: 7a21b7d75a2fb8f0b15e3bc8ea946387aca8ffa5 | Error correction under test_lb

OSPFCICDthruGithub | commit_id: 2cceb6c7d2b0cea85b9d7f88c94a07aa5fcea4dc | Initial commit
OSPFCICD | commit_id: d9ae42483d232dc173e2cccc0e6b5fc625c6f624 | removing requirements.txt duplicating

Terraform2 | commit_id: 9b1bbd4219e69caaf1990ea7efed1acce6aa04cd | Adding route in UbuntuPC/Roadrunner for fina test in the CI

CICD | commit_id: 2009965b202a99f5bc5aacf53cbd859dfd02aa94 | Systemtest-3 wSystembuild-1

application | commit_id: 4a0ad591e9ec06fb7850c1bc7a2786075c17160b | Upload New File
terraform | commit_id: 4e2b1b0b6478f1fe6e8c848f09e0608a11ed16bb | LB dep test3
```

</details>

---

## TYPER_EXPLANATION

<details>
<summary>⚠️ Click to reveal — use as a reference only after attempting the challenge</summary>

### 1. Click vs Typer — Key Differences

| Concept | Click | Typer |
|---|---|---|
| **App creation** | `@click.group()` on a function | `app = typer.Typer()` |
| **Initialization** | `@click.pass_context` + `ctx.obj` | `@app.callback()` + module-level `state` dict |
| **Register command** | `@group.command()` or `group.add_command()` | `@app.command()` |
| **Sub-groups** | `@click.group()` + `add_command()` | `sub = typer.Typer()` + `app.add_typer(sub, name=...)` |
| **Choice restriction** | `type=click.Choice(['a','b'])` | `class MyEnum(str, Enum)` + type annotation |
| **Options** | `@click.option('--name', ...)` decorator | `name: type = typer.Option(default, ...)` parameter |
| **Arguments** | `@click.argument('name', type=int)` decorator | `name: int = typer.Argument(...)` parameter |
| **Object passing** | `@click.pass_obj` | Module-level `state` dict (no decorator needed) |
| **Required option** | `required=True` | `typer.Option(...)` (Ellipsis = required) |

---

### 2. Creating the App and Sub-Apps

```python
# Main app (replaces @click.group())
app = typer.Typer()

# Sub-app (replaces nested @click.group())
individual_app = typer.Typer()

# Wire sub-app into main (replaces group.add_command(subgroup))
app.add_typer(individual_app, name="individual")
```

---

### 3. Initialization with @app.callback()

Replaces Click's `@click.group()` + `@click.pass_context` pattern:

```python
state = {"gitlab": None}   # module-level, replaces ctx.obj

@app.callback()
def main():
    config = json.load(open("pat.json"))
    state["gitlab"] = GitlabAPI(config["PAT"])
```

Commands access shared state directly via `state["gitlab"]` — no `@click.pass_obj` needed.

---

### 4. typer.Option() — The Core Pattern

In Typer, options are defined as **function parameters with type annotations**:

```python
param_name: type = typer.Option(default, "--long-form", "--short", help="...", show_default=True)
```

**Required option** — use `...` (Ellipsis) as default:
```python
project: int = typer.Option(..., "--project", help="Project path")
# Help shows: *  --project  INTEGER  Project path [required]
```

**Boolean flag (is_flag equivalent):**
```python
showgid: bool = typer.Option(False, "--showgid", "--g", help="Show GID of tasks")
# --showgid → True,  omitted → False
```

**Boolean flag pair:**
```python
all: bool = typer.Option(True, "--all/--project",
                          show_default="all: show all projects",
                          help="Show all projects or specific project")
# --all → True,  --project → False,  omitted → True (default)
```

**Enum-based Choice:**
```python
class OutFormat(str, Enum):
    lines = "lines"
    raw = "raw"

outformat: OutFormat = typer.Option(OutFormat.lines, "--outformat", "--o", show_default=True)
# Help shows: --outformat,--o  [lines|raw]  [default: lines]
```

---

### 5. typer.Argument() — Positional Arguments

In Typer, positional arguments use `typer.Argument()` instead of Click's `@click.argument()`:

```python
project_id: int = typer.Argument(..., help="Project ID")
```

- `...` (Ellipsis) means required (positional args are always required)
- The type annotation (`int`) controls validation
- Appears in help under a separate `Arguments` section, not `Options`

**Click vs Typer comparison:**
```python
# Click:
@click.argument('project_id', type=int)
def branches(project_id): ...

# Typer:
def branches(project_id: int = typer.Argument(...)): ...
```

---

### 6. Registering Commands

**Under main app:**
```python
@app.command()
def listprojects(...):
    pass
```

**Under sub-app with aliased name:**
```python
@individual_app.command(name="path")
def namespace(...):
    pass

@individual_app.command(name="message")
def commitmessage():
    pass
```

The `name` parameter in `@sub_app.command(name="alias")` works like Click's `add_command(func, name="alias")`.

---

### 7. Decision Tree

1. **Need a CLI app?** → `app = typer.Typer()`
2. **Need initialization logic?** → `@app.callback()` + module-level `state` dict
3. **Need a sub-group (e.g. `cli sub cmd`)?** → `sub = typer.Typer()` + `app.add_typer(sub, name="...")`
4. **Adding a command?** → `@app.command()` or `@sub.command(name="alias")`
5. **Need restricted choices?** → Define `class MyEnum(str, Enum)` + use as type annotation
6. **Need a required option?** → `typer.Option(...)` with Ellipsis
7. **Need a positional argument?** → `param: type = typer.Argument(...)`
8. **Need a boolean flag?** → `typer.Option(False, "--flag", "--f")` or `"--show/--not-show"` for pairs

</details>
