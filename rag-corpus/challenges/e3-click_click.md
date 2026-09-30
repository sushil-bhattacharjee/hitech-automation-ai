# Click Framework Complete Guide

## 📚 Table of Contents
1. [@click.argument vs @click.option](#click-argument-vs-click-option)
2. [Click Option Parameters Explained](#click-option-parameters-explained)
3. [Complete Guide: Click Groups, Commands, and Subcommands](#complete-guide-click-groups-commands-and-subcommands)
4. [Printing Boolean Variables](#printing-boolean-variables-true-or-false-output)

---

## 🆚 @click.argument vs @click.option

| Feature              | `@click.argument`                            | `@click.option`                                |
| -------------------- | -------------------------------------------- | ---------------------------------------------- |
| **Required?**        | Always required (unless `nargs=-1`)          | Optional by default, can be made required      |
| **Order-sensitive?** | Yes – must follow the declared order in CLI  | No – can appear in any order using flags       |
| **Passed by**        | **Position** (e.g., `script.py John`)        | **Option flag** (e.g., `--name John`)          |
| **Good for**         | Essential inputs (like filenames, usernames) | Optional/adjustable behavior (flags, switches) |
| **Default support?** | ❌ No – must be provided                      | ✅ Yes – supports `default=` and `required=`    |
| **Boolean flags?**   | ❌ Not supported                              | ✅ Yes (`is_flag=True`)                         |
| **Repeatable?**      | With `nargs=-1` or `nargs=2`, etc.           | ✅ With `multiple=True`                         |

---

## Click Option Parameters Explained

### Overview

In Click, when defining options with `@click.option()`, there are several parameters that control behavior and display. Here's a complete explanation of each:

---

### 1. `default=True`

Sets the **default value** to `True` when option is not provided.

```python
@click.option("--all/--project", default=True)
def cmd(all):
    print(all)
```

**Usage:**
```bash
$ python cli.py cmd          # all=True (default)
$ python cli.py cmd --all    # all=True
$ python cli.py cmd --project # all=False
```

---

### 2. `is_flag=True`

Makes it a **simple on/off flag** (no value required).

```python
@click.option("--showgid", is_flag=True)
def cmd(showgid):
    print(showgid)
```

**Usage:**
```bash
$ python cli.py cmd           # showgid=False (always False when absent)
$ python cli.py cmd --showgid # showgid=True (turns on when present)
```

---

### 3. `default=None`

Sets the **default value** to `None` when option is not provided.

```python
@click.option("--name", default=None)
def cmd(name):
    print(name)
```

**Usage:**
```bash
$ python cli.py cmd              # name=None
$ python cli.py cmd --name Bob   # name='Bob'
```

---

### 4. `show_default=True`

Shows the **actual default value** in help text.

```python
@click.option("--format", default='json', show_default=True)
def cmd(format):
    print(format)
```

**Help Output:**
```bash
$ python cli.py cmd --help
Options:
  --format TEXT  [default: json]    # <-- Shows actual value
```

---

### 5. `show_default="all: show all projects"`

Shows **custom text** for default instead of actual value.

```python
@click.option("--all/--project", default=True, 
              show_default="all: show all projects")
def cmd(all):
    print(all)
```

**Help Output:**
```bash
$ python cli.py cmd --help
Options:
  --all/--project  [default: all: show all projects]  # <-- Custom text
```

---

### 6. `default='lines'`

Sets the **default value** to the string `'lines'`.

```python
@click.option("--format", default='lines')
def cmd(format):
    print(format)
```

**Usage:**
```bash
$ python cli.py cmd                    # format='lines' (default)
$ python cli.py cmd --format raw       # format='raw'
```

---

### Quick Comparison Table

| Parameter | Purpose | Example Value | When to Use |
|-----------|---------|---------------|-------------|
| `default=True` | Set default to True | Boolean | Boolean options |
| `is_flag=True` | Make it a flag | No value | On/off switches |
| `default=None` | Set default to None | None | Optional values |
| `show_default=True` | Show actual default | Auto | User needs to see default |
| `show_default="..."` | Custom default text | String | Better description needed |
| `default='lines'` | Set default to string | String | String options |

---

### Real Example from Challenge

```python
@click.option('--outformat', '--o', 
              type=click.Choice(['lines', 'raw']), 
              default='lines',      # Default value is 'lines'
              show_default=True)    # Show "default: lines" in help
def listprojects(obj, outformat):
    pass
```

**Help Output:**
```
--outformat, --o [lines|raw]  [default: lines]
```

---

## Complete Guide: Click Groups, Commands, and Subcommands

### 📚 Sections
1. [Creating a Group](#creating-a-group)
2. [Adding Commands Using Decorators](#adding-commands-using-decorators)
3. [Adding Commands Using .add_command()](#adding-commands-using-add_command)
4. [Creating Nested Subcommands](#creating-nested-subcommands)
5. [Challenge Examples Explained](#challenge-examples-explained)

---

### Example: Complete CLI with Context

```python
import click

# 1) CREATE A GROUP WITH CONTEXT
@click.group()
@click.pass_context
def learning(ctx):
    """Learning group"""
    ctx.ensure_object(dict)
    # Initialize dict with three variables
    ctx.obj['api_key'] = 'key-123'
    ctx.obj['username'] = 'admin'
    ctx.obj['debug'] = True


# 2) ADD COMMAND USING DECORATOR WITH CONTEXT
@learning.command()
@click.pass_obj
def testing(obj):
    """Testing command"""
    click.echo(f"Testing with API: {obj['api_key']}")
    click.echo(f"User: {obj['username']}")


# 3) ADD COMMAND USING METHOD
@click.group()
@click.pass_obj
def troubleshooting(obj):
    """Troubleshooting group"""
    click.echo(f"Troubleshooting mode - Debug: {obj['debug']}")

# Add troubleshooting to learning using method
learning.add_command(troubleshooting)


# 4) ADD SUB-COMMAND UNDER TROUBLESHOOTING
@troubleshooting.command()
@click.pass_obj
def debugging(obj):
    """Debugging subcommand"""
    click.echo(f"Debugging as {obj['username']}")
    click.echo(f"API Key: {obj['api_key']}")
    click.echo(f"Debug mode: {obj['debug']}")


# 5) ADD ANOTHER COMMAND USING METHOD
@click.command()
@click.pass_obj
def deploying(obj):
    """Deploying command"""
    click.echo(f"Deploying with user: {obj['username']}")
    click.echo(f"Using API: {obj['api_key']}")

# Add deploying to learning using method
learning.add_command(deploying)


if __name__ == '__main__':
    learning()
```

**Usage:**
```bash
$ python3 add_command.py --help
Usage: add_command.py [OPTIONS] COMMAND [ARGS]...

  Learning group

Options:
  --help  Show this message and exit.

Commands:
  deploying        Deploying command
  testing          Testing command
  troubleshooting  Troubleshooting group

$ python3 add_command.py troubleshooting --help
Usage: add_command.py troubleshooting [OPTIONS] COMMAND [ARGS]...

  Troubleshooting group

Options:
  --help  Show this message and exit.

Commands:
  debugging  Debugging subcommand

$ python3 add_command.py troubleshooting debugging
Troubleshooting mode - Debug: True
Debugging as admin
API Key: key-123
Debug mode: True
```

---

## 1. Creating a Group

A group is a container that can hold multiple commands. It's the main entry point for your CLI application.

### Method 1: Basic Group Creation
```python
import click

@click.group()
def cli():
    """Main CLI application"""
    pass

if __name__ == "__main__":
    cli()
```

**Usage:**
```bash
$ python3 basic_group_creation.py --help
Usage: basic_group_creation.py [OPTIONS] COMMAND [ARGS]...

  Main CLI application

Options:
  --help  Show this message and exit.
```

### Method 2: Group with Context (Challenge-101 Style)
```python
import click

@click.group()
@click.pass_context
def challenge101(ctx):
    """Main group with shared context"""
    ctx.ensure_object(dict)
    # Initialize shared resources here
    config = json.load(open("config.json"))
    ctx.obj["asana"] = AsanaRestApi(config["PAT"])

if __name__ == "__main__":
    challenge101()
```

### Example 2: API Client Group with Context
```python
import click
import requests

@click.group()
@click.pass_context
def api_client(ctx):
    """API client with shared session"""
    ctx.ensure_object(dict)
    # Create a shared session for all commands
    ctx.obj['session'] = requests.Session()
    ctx.obj['base_url'] = 'https://api.example.com'
    print("API Client initialized")

if __name__ == "__main__":
    api_client()
```

---

## 2. Add Commands Using Decorators

This is the most common way to add commands to a group - using the `@groupname.command()` decorator.

### Basic Pattern:
```python
@group_name.command()
def command_name():
    pass
```

### Challenge-101 Example: [@group_name.command()]
```python
import click

# Creating GROUP challenge101
@click.group()
@click.pass_context
def challenge101(ctx):
    ctx.ensure_object(dict)
    config = json.load(open("config.json"))
    ctx.obj["asana"] = AsanaRestApi(config["PAT"])

# Adding command "listprojects" using @groupname.command() decorator
@challenge101.command()  # <-- This adds 'listprojects' to 'challenge101' group
@click.option('--outputformat', type=click.Choice(['lines', 'raw']))
@click.pass_obj
def listprojects(obj, outputformat):
    projects = obj["asana"].get("/projects")
    print("Projects:")
    # ... rest of code

if __name__ == '__main__':
    challenge101()
```

**Usage:**
```bash
$ python3 add_command.py --help
Usage: add_command.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  listprojects
```

---

## 3. Adding Commands Using .add_command()

This method adds commands programmatically at the end of the file or anywhere in the code.

### Basic Pattern:
```python
@click.command()  # Note: using @click.command(), NOT @group.command()
def my_command():
    pass

# Later in the code
group_name.add_command(my_command)
```

### Challenge-101 Example (Using add_command):
```python
# Adding command using groupname.add_command() method with @click.command decorator
@click.command()  # <-- Note: @click.command, NOT @challenge101.command()
@click.option('--project', type=int, required=True)
@click.pass_obj
def listtasks(obj, project):
    pass

challenge101.add_command(listtasks)  # <-- This adds 'listtasks' to 'challenge101'
```

**Usage:**
```bash
$ python3 add_command.py --help
Usage: add_command.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  listprojects
  listtasks
```

### Example 1: Dynamically Adding Commands
```python
import click

@click.group()
def cli():
    """Main CLI"""
    pass

# Define commands separately
@click.command()
@click.option('--verbose', is_flag=True)
def status(verbose):
    """Check system status"""
    print("System is running")
    if verbose:
        print("CPU: 45%, Memory: 60%")

@click.command()
@click.argument('service')
def restart(service):
    """Restart a service"""
    print(f"Restarting {service}...")

# Add commands to group programmatically
cli.add_command(status)
cli.add_command(restart)

# You can even conditionally add commands
import os
if os.getenv('ENABLE_DEBUG'):
    @click.command()
    def debug():
        """Debug mode"""
        print("Debug information...")
    
    cli.add_command(debug)
```

### Example 2: Building Commands from Configuration
```python
import click

@click.group()
def tools():
    """Tool collection"""
    pass

# Create commands from a list
tool_list = ['hammer', 'screwdriver', 'wrench']

for tool_name in tool_list:
    # Create a command dynamically
    @click.command(name=tool_name)
    @click.pass_context
    def tool_cmd(ctx, tool=tool_name):  # Capture tool_name in default arg
        """Use a tool"""
        print(f"Using {tool}")
    
    # Add to group
    tools.add_command(tool_cmd)

# Manual command addition
@click.command()
@click.option('--all', is_flag=True)
def inventory(all):
    """Show tool inventory"""
    print("Tool inventory:")
    if all:
        print("- hammer\n- screwdriver\n- wrench")

tools.add_command(inventory)
```

---

## 4. Creating Nested Subcommands

Subcommands are commands within commands, creating a hierarchy like `git remote add`.

### Challenge-308 Example Explained:
```python
# Main group
@click.group()
def expertconf():
    pass

# Create a subgroup
@expertconf.group()  # <-- This creates 'add' as a subgroup of 'expertconf'
def add():
    pass

# Add command to the subgroup
@click.command()
@click.argument('router_address')
def ospf(router_address):
    """Configure OSPF"""
    print(f"Configuring OSPF on {router_address}")

# Add ospf to the 'add' subgroup
add.add_command(ospf)

# Usage: python script.py add ospf 192.168.1.1
```

### Example 1: Git-like Structure
```python
import click

# Main group
@click.group()
def git():
    """Git-like CLI"""
    pass

# Subgroup: remote
@git.group()
def remote():
    """Manage remotes"""
    pass

# Commands under 'remote' subgroup
@remote.command()
@click.argument('name')
@click.argument('url')
def add(name, url):
    """Add a remote"""
    print(f"Adding remote '{name}' with URL: {url}")

@remote.command()
@click.argument('name')
def remove(name):
    """Remove a remote"""
    print(f"Removing remote '{name}'")

@remote.command()
def list():
    """List all remotes"""
    print("origin  https://github.com/user/repo.git")

# Usage:
# python git.py remote add origin https://github.com/user/repo.git
# python git.py remote remove origin
# python git.py remote list
```

### Example 2: Database Admin Tool
```python
import click

# Main group
@click.group()
@click.pass_context
def admin(ctx):
    """Database admin tool"""
    ctx.ensure_object(dict)
    ctx.obj['connection'] = 'localhost:5432'

# Subgroup: user management
@admin.group()
@click.pass_context
def user(ctx):
    """User management"""
    print(f"Connected to: {ctx.obj['connection']}")

# Commands under 'user' subgroup
@user.command()
@click.option('--name', required=True)
@click.option('--email', required=True)
@click.pass_obj
def create(obj, name, email):
    """Create a user"""
    print(f"Creating user: {name} ({email})")
    print(f"On server: {obj['connection']}")

@user.command()
@click.option('--id', type=int, required=True)
def delete(id):
    """Delete a user"""
    print(f"Deleting user with ID: {id}")

# Subgroup: database management
@admin.group()
def database():
    """Database management"""
    pass

@database.command()
@click.argument('name')
def backup(name):
    """Backup a database"""
    print(f"Backing up database: {name}")

# Alternative way to add a command
@click.command()
@click.option('--format', type=click.Choice(['json', 'csv']))
def export(format):
    """Export database"""
    print(f"Exporting in {format} format")

database.add_command(export)

# Usage:
# python admin.py user create --name John --email john@example.com
# python admin.py user delete --id 123
# python admin.py database backup mydb
# python admin.py database export --format json
```

---

## 5. Challenge Examples Explained

### Challenge-101 Structure:
```python
# 1. CREATE GROUP with context
@click.group()
@click.pass_context
def challenge101(ctx):
    # Initialize shared resources
    ctx.ensure_object(dict)
    config = json.load(open("config.json"))
    ctx.obj["asana"] = AsanaRestApi(config["PAT"])

# 2. ADD COMMANDS using decorator method
@challenge101.command()  # <-- Decorator method
@click.pass_obj
def listprojects(obj, outputformat):
    # Command code

@challenge101.command()  # <-- Decorator method
@click.pass_obj
def listtasks(obj, project, showgid):
    # Command code

# 3. ADD COMMAND using add_command method
@click.command()  # <-- Note: @click.command, not @challenge101.command
@click.pass_obj
def setstatus(obj, task, completed):
    # Command code

challenge101.add_command(setstatus)  # <-- Manual addition
```

**Why use `.add_command()` for setstatus?**
- The challenge required you to add it at a specific location
- It demonstrates an alternative way to add commands
- Useful when you want to conditionally add commands

### Challenge-308 Structure (Nested):
```python
# 1. CREATE MAIN GROUP
@click.group()
def expertconf():
    pass

# 2. CREATE SUBGROUP under main group
@expertconf.group()  # <-- Creates 'add' as subgroup of 'expertconf'
def add():
    pass

# 3. CREATE COMMAND
@click.command()
def ospf(router_address, username, ethsubintf):
    # Command code

# 4. ADD COMMAND TO SUBGROUP
add.add_command(ospf)  # <-- Adds 'ospf' to 'add' subgroup

# Result: expertconf -> add -> ospf
# Usage: python script.py add ospf <arguments>
```

---

## 🎯 Quick Reference

### Decision Tree:
1. **Need a main CLI entry?** → Create a group with `@click.group()`
2. **Need shared data between commands?** → Add `@click.pass_context` to group
3. **Adding a simple command?** → Use `@group.command()` decorator
4. **Need to add command conditionally/dynamically?** → Use `.add_command()`
5. **Need command hierarchies (like git)?** → Create subgroups with `@group.group()`

### Common Patterns:
```python
# Pattern 1: Simple group with commands
@click.group()
def cli():
    pass

@cli.command()
def cmd1():
    pass

# Pattern 2: Group with context
@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = {'shared': 'data'}

@cli.command()
@click.pass_obj
def cmd1(obj):
    print(obj['shared'])

# Pattern 3: Nested groups
@click.group()
def main():
    pass

@main.group()
def sub():
    pass

@sub.command()
def cmd():
    pass

# Pattern 4: Dynamic command addition
@click.command()
def dynamic_cmd():
    pass

main.add_command(dynamic_cmd)
```

---

## Printing Boolean Variables: True or False Output

### ✅ Yes, You're Correct!

When you print boolean variables directly, Python displays them as `True` or `False` (capitalized).

---

### 📊 Examples from Your Code

#### Example 1: Printing `showgid`
```python
@click.option('--showgid', '-g', is_flag=True, help="Show GID of tasks")
def listtasks(obj, project, showgid):
    print(f"showgid = {showgid}")
    print(f"Type: {type(showgid)}")
```

**Output Examples:**
```bash
# Without the flag
$ python3 asana.py listtasks --project 123
showgid = False
Type: <class 'bool'>

# With the flag
$ python3 asana.py listtasks --project 123 --showgid
showgid = True
Type: <class 'bool'>
```

#### Example 2: Printing `completed`
```python
@click.option('--completed/--not-completed', default=False)
def setstatus(obj, task, completed):
    print(f"completed = {completed}")
    print(f"Type: {type(completed)}")
```

**Output Examples:**
```bash
# With --completed flag
$ python3 asana.py setstatus --task 123 --completed
completed = True
Type: <class 'bool'>

# With --not-completed flag
$ python3 asana.py setstatus --task 123 --not-completed
completed = False
Type: <class 'bool'>

# With no flag (using default)
$ python3 asana.py setstatus --task 123
completed = False
Type: <class 'bool'>
```

---

#### Example 3: Printing `[default: lines] | show_default=True`
```python
## Requirement C
@challenge101.command()
@click.option('--outputformat', type=click.Choice(['lines', 'raw']), default='lines', show_default=True)
@click.pass_obj
##
def listprojects(obj, outputformat):
    projects = obj["asana"].get("/projects")
    print("Projects:")
    ## Requirement D
    data = projects["data"]
    if outputformat == "lines":
        for entry in data:
            print(entry["name"] + " GID=" + entry["gid"])
    if outputformat == "raw":
        for entry in data:
            print(entry)
    ##
```

**Output Examples:**
```bash
$ python3 asana.py listprojects --help
Usage: asana.py listprojects [OPTIONS]
Options:
  --outputformat [lines|raw]  [default: lines]
  --help                      Show this message and exit.
```

---

### 🎨 Different Ways to Print Booleans

#### 1. Direct Printing (Shows `True` or `False`)
```python
showgid = True
completed = False

print(showgid)           # Output: True
print(completed)         # Output: False
print(f"{showgid}")      # Output: True
print(f"{completed}")    # Output: False
```

#### 2. In String Concatenation (Converts to 'True' or 'False')
```python
showgid = True
completed = False

print("showgid: " + str(showgid))       # Output: showgid: True
print("completed: " + str(completed))   # Output: completed: False
```

#### 3. Using Conditional Display (Custom Messages)
```python
showgid = True
completed = False

# Custom messages based on boolean value
print("Show GID: Yes" if showgid else "Show GID: No")
# Output: Show GID: Yes

print("Task is completed" if completed else "Task is not completed")
# Output: Task is not completed
```

#### 4. Converting to Other Representations
```python
showgid = True
completed = False

# Convert to lowercase string
print(str(showgid).lower())       # Output: true
print(str(completed).lower())     # Output: false

# Convert to integer (True=1, False=0)
print(int(showgid))               # Output: 1
print(int(completed))             # Output: 0

# Convert to custom symbols
print("✓" if showgid else "✗")    # Output: ✓
print("✓" if completed else "✗")  # Output: ✗
```

---

### 📝 In Your Actual Code Context

#### When You Debug Your Code:
```python
@click.option('--showgid', '-g', is_flag=True, help="Show GID of tasks")
def listtasks(obj, project, showgid):
    # Debug prints
    print(f"Debug: showgid = {showgid}")  # Will print: Debug: showgid = True/False
    
    tasks = obj["asana"].get(f"/projects/{project}/tasks")
    
    for task in tasks["data"]:
        task_details = obj["asana"].get(f"/tasks/{task['gid']}")
        
        # Using the boolean in logic
        if showgid:  # This checks if showgid is True
            print(f"{task_details['data']['name']}, GID={task['gid']}, Completed={task_details['data']['completed']}")
        else:
            print(f"{task_details['data']['name']}, Completed={task_details['data']['completed']}")
```

#### What About `task_details['data']['completed']`?
```python
# This is ALSO a boolean from the API
task_details = obj["asana"].get(f"/tasks/{task['gid']}")
print(task_details['data']['completed'])  # Output: True or False

# When you convert to string:
print("Completed=" + str(task_details['data']['completed']))
# Output: Completed=True or Completed=False
```

---

### 🔍 Important Notes

#### 1. Case Sensitivity
```python
# Python booleans are capitalized
print(True)   # Output: True (capital T)
print(False)  # Output: False (capital F)

# Not 'true' or 'false' (lowercase)
```

#### 2. String Conversion
```python
showgid = True

# These all produce the string "True"
print(f"{showgid}")           # True
print(str(showgid))           # True
print("Value: " + str(showgid))  # Value: True
```

#### 3. JSON vs Python
```python
import json

showgid = True

# Python representation
print(showgid)                    # Output: True

# JSON representation (lowercase)
print(json.dumps(showgid))        # Output: true
print(json.dumps({"showgid": showgid}))  # Output: {"showgid": true}
```

---

### 💡 Practical Debugging Example

```python
@challenge101.command()
@click.option('--project', type=int, required=True)
@click.option('--showgid', '-g', is_flag=True)
@click.pass_obj
def listtasks(obj, project, showgid):
    # Debug section
    print("\n=== DEBUG INFO ===")
    print(f"project = {project}")       # Output: project = 1211312397849557
    print(f"showgid = {showgid}")       # Output: showgid = True or False
    print(f"type(project) = {type(project)}")  # Output: type(project) = <class 'int'>
    print(f"type(showgid) = {type(showgid)}")  # Output: type(showgid) = <class 'bool'>
    print("==================\n")
    
    # Rest of your code...
```

**Sample Output:**
```
=== DEBUG INFO ===
project = 1211312397849557
showgid = True
type(project) = <class 'int'>
type(showgid) = <class 'bool'>
==================
```

---

### 🎓 Summary

**Yes, you're absolutely correct!** When you print boolean variables:
- They display as `True` or `False` (capitalized)
- `showgid` will print as either `True` or `False`
- `completed` will print as either `True` or `False`
- `task_details['data']['completed']` will also print as `True` or `False`

This is Python's standard representation of boolean values!

---

## @click.option() - Complete Parameter Reference

### What is @click.option()?

It's a **decorator** - specifically a **Click decorator** that adds command-line options to a function.

### Terminology:

| Term | What it means |
|------|---------------|
| **Decorator** | Python feature using `@` symbol |
| **Click decorator** | Decorator from the Click library |
| **Option decorator** | Adds a command-line option/flag |

### Examples:

```python
@click.option('--name')        # This is a decorator
def cmd(name):                 # It decorates this function
    pass

@click.command()               # Also a decorator
@click.option('--verbose')     # Also a decorator
@click.pass_obj                # Also a decorator
def mycommand(obj, verbose):
    pass
```

---

## Core Parameters

```python
@click.option(
    # BASIC
    '--name', '-n',              # Option names (long and short form)
    
    # TYPE & VALIDATION
    type=int,                    # Type: int, str, float, click.Choice(), click.Path(), etc.
    required=True,               # Make option mandatory
    multiple=True,               # Allow multiple values
    
    # DEFAULT VALUES
    default='value',             # Default value
    default=None,                # No default
    show_default=True,           # Show default in help (True shows actual value)
    show_default="custom text",  # Custom default text in help
    
    # FLAGS
    is_flag=True,                # Make it a boolean flag (--verbose)
    flag_value='value',          # Value when flag is used
    
    # BOOLEAN FLAGS
    '--enable/--disable',        # Boolean flag pair
    
    # HELP & DISPLAY
    help="Description text",     # Help text shown in --help
    
    # PROMPTING
    prompt=True,                 # Prompt user if not provided
    prompt="Enter name",         # Custom prompt text
    hide_input=True,             # Hide input (for passwords)
    confirmation_prompt=True,    # Ask twice (for passwords)
    
    # ENVIRONMENT VARIABLES
    envvar='MY_VAR',             # Read from environment variable
    
    # CALLBACKS
    callback=my_function,        # Validation/transformation function
    
    # COUNTING
    count=True,                  # Count occurrences (-vvv = 3)
    
    # OTHER
    metavar='<name>',            # Display name in help
    expose_value=True,           # Pass to function (default True)
    is_eager=False,              # Process before other options
)
```

---

## Common Examples

### 1. Simple String Option
```python
@click.option('--name', type=str, help="Your name")
def cmd(name):
    pass
```

### 2. Required Integer
```python
@click.option('--port', type=int, required=True, help="Port number")
def cmd(port):
    pass
```

### 3. Choice Selection
```python
@click.option('--format', type=click.Choice(['json', 'xml', 'csv']), default='json')
def cmd(format):
    pass
```

### 4. Boolean Flag
```python
@click.option('--verbose', '-v', is_flag=True, help="Enable verbose mode")
def cmd(verbose):
    pass
```

### 5. Boolean Flag Pair
```python
@click.option('--enable/--disable', default=True)
def cmd(enable):
    pass
```

### 6. Multiple Values
```python
@click.option('--tag', multiple=True, help="Add tags (can be used multiple times)")
def cmd(tag):
    # tag will be a tuple: ('tag1', 'tag2', 'tag3')
    pass
```

### 7. Password Prompt
```python
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
def cmd(password):
    pass
```

### 8. With Default and Show
```python
@click.option('--timeout', type=int, default=30, show_default=True, help="Timeout in seconds")
def cmd(timeout):
    pass
# Help shows: --timeout INTEGER  Timeout in seconds  [default: 30]
```

### 9. Count Flag
```python
@click.option('-v', '--verbose', count=True, help="Verbosity level")
def cmd(verbose):
    # -v = 1, -vv = 2, -vvv = 3
    pass
```

### 10. Environment Variable
```python
@click.option('--api-key', envvar='API_KEY', help="API key (or set API_KEY env var)")
def cmd(api_key):
    pass
```

---

## Examples from Your Challenge

```python
# Simple choice with default
@click.option('--outformat', '--o', 
              type=click.Choice(['lines', 'raw']), 
              default='lines', 
              show_default=True)

# Required integer
@click.option("--project", type=int, help="Project path", required=True)

# Simple flag
@click.option("--showgid", "--g", is_flag=True, help="Show GID of tasks")

# Boolean pair with custom default text
@click.option('--all/--project', 
              default=True, 
              help="Show all projects or specific project", 
              show_default="all: show all projects")

# Boolean pair with default
@click.option("--show/--not-show", default=False)
```

---

## Special Types

```python
# File path
@click.option('--input', type=click.Path(exists=True), help="Input file")

# Directory path
@click.option('--output', type=click.Path(file_okay=False, dir_okay=True))

# Choice
@click.option('--format', type=click.Choice(['json', 'xml'], case_sensitive=False))

# Float range
@click.option('--percentage', type=click.FloatRange(0, 100))

# Integer range
@click.option('--port', type=click.IntRange(1, 65535))

# UUID
@click.option('--id', type=click.UUID)

# DateTime
@click.option('--date', type=click.DateTime(formats=['%Y-%m-%d']))
```

---

## Full Function Signature (simplified)

```python
def option(
    *param_decls,           # '--name', '-n'
    type=None,              # Data type
    required=False,         # Is required?
    default=None,           # Default value
    callback=None,          # Validation function
    multiple=False,         # Multiple values?
    count=False,            # Count flag?
    is_flag=None,           # Boolean flag?
    flag_value=None,        # Flag value
    help=None,              # Help text
    hidden=False,           # Hide from help?
    show_default=None,      # Show default in help?
    prompt=False,           # Prompt user?
    confirmation_prompt=False,  # Double prompt?
    hide_input=False,       # Hide input?
    envvar=None,            # Environment variable
    show_envvar=False,      # Show env var in help?
    metavar=None,           # Display name
    expose_value=True,      # Pass to function?
    is_eager=False,         # Process early?
    **attrs
)
```

**Most commonly used:** `type`, `required`, `default`, `help`, `is_flag`, and `show_default`.

---

## click.Choice() - Detailed Explanation

### It's a Class, Not a Function

`click.Choice()` is a **class** (not a function) that creates a choice type validator for Click options and arguments.

---

### Signature

```python
click.Choice(
    choices,              # List/tuple of valid choices (required)
    case_sensitive=True   # Whether to enforce case sensitivity (default: True)
)
```

---

### Parameters

#### 1. `choices` (required)
**Type:** list or tuple  
**Description:** The valid values that the user can choose from

#### 2. `case_sensitive` (optional)
**Type:** bool  
**Default:** `True`  
**Description:** Whether the choice matching is case-sensitive

---

### Basic Examples

#### Simple Choice
```python
@click.option('--format', type=click.Choice(['json', 'xml', 'csv']))
def cmd(format):
    print(f"Format: {format}")
```

**Usage:**
```bash
$ python cli.py --format json     # ✅ Valid
$ python cli.py --format xml      # ✅ Valid
$ python cli.py --format yaml     # ❌ Error: Invalid choice: yaml
```

#### Case-Insensitive
```python
@click.option('--format', type=click.Choice(['JSON', 'XML', 'CSV'], case_sensitive=False))
def cmd(format):
    print(f"Format: {format}")
```

**Usage:**
```bash
$ python cli.py --format json     # ✅ Valid (converts to JSON)
$ python cli.py --format Json     # ✅ Valid (converts to JSON)
$ python cli.py --format JSON     # ✅ Valid
$ python cli.py --format jSoN     # ✅ Valid (converts to JSON)
```

#### With Default Value
```python
@click.option('--format', 
              type=click.Choice(['json', 'xml', 'csv']), 
              default='json',
              show_default=True)
def cmd(format):
    print(f"Format: {format}")
```

**Help Output:**
```
--format [json|xml|csv]  [default: json]
```

#### With Arguments (not just options)
```python
@click.command()
@click.argument('format', type=click.Choice(['json', 'xml', 'csv']))
def convert(format):
    print(f"Converting to {format}")
```

**Usage:**
```bash
$ python cli.py convert json      # ✅ Valid
$ python cli.py convert txt       # ❌ Error
```

---

### Why This Syntax? `click.Choice(['json', 'xml', 'csv'])`

#### Why NOT `click.Choice('json', 'xml', 'csv')`?

This would pass **3 separate arguments** to the class:

```python
click.Choice('json', 'xml', 'csv')
#            ^^^^^^  ^^^^^  ^^^^^
#            arg1    arg2   arg3
```

But `Choice()` only accepts **2 parameters**:
1. `choices` (list/tuple)
2. `case_sensitive` (bool)

**Result:** `TypeError: __init__() takes from 2 to 3 positional arguments but 4 were given`

#### Why NOT `click.Choice['json', 'xml', 'csv']`?

Square brackets `[]` are **NOT** for calling classes/functions!

**Square brackets are for:**
```python
# 1. Indexing
my_list[0]

# 2. List literals
choices = ['json', 'xml', 'csv']

# 3. Dictionary literals
data = {'key': 'value'}

# 4. Type hints (Python 3.9+)
def func(items: list[str]):
    pass
```

**Parentheses `()` are for calling:**
```python
# Calling functions
print("hello")

# Calling classes (creating instances)
click.Choice(['json', 'xml'])
```

**Result:** `TypeError: 'type' object is not subscriptable`

---

### Visual Comparison

```python
# ✅ CORRECT - Pass a list
type=click.Choice(['json', 'xml', 'csv'])
#                 └─────────────────────┘
#                    ONE parameter (a list)

# ❌ WRONG - Multiple arguments
type=click.Choice('json', 'xml', 'csv')
#                 ^^^^^^  ^^^^^  ^^^^^
#                 3 arguments (expects 1-2)

# ❌ WRONG - Wrong syntax
type=click.Choice['json', 'xml', 'csv']
#                └──────────────────────┘
#                Square brackets = not a function call
```

---

### Why Design It This Way?

#### 1. Flexibility
You can pass the choices from a variable:

```python
# Define choices elsewhere
FORMATS = ['json', 'xml', 'csv']

# Use them
@click.option('--format', type=click.Choice(FORMATS))
def cmd(format):
    pass
```

#### 2. Type Safety
The parameter is explicitly a collection (list/tuple):

```python
# Works with list
click.Choice(['json', 'xml'])

# Works with tuple
click.Choice(('json', 'xml'))

# Works with any iterable
choices = ['json', 'xml']
click.Choice(choices)
```

#### 3. Consistent with Python Patterns
Many Python functions take a single iterable:

```python
max([1, 2, 3])        # Not max(1, 2, 3) for lists
sorted(['b', 'a'])    # Takes one iterable
set(['a', 'b'])       # Takes one iterable
```

---

### Alternative Syntax

#### Using a Tuple (also valid)
```python
@click.option('--format', type=click.Choice(('json', 'xml', 'csv')))
#                                           └───────────────────────┘
#                                           Tuple instead of list
```

#### Pre-defined Choices
```python
VALID_FORMATS = ['json', 'xml', 'csv', 'yaml']

@click.option('--format', type=click.Choice(VALID_FORMATS))
def cmd(format):
    pass
```

---

### Case Sensitivity Comparison

#### Case Sensitive (default)
```python
@click.option('--level', type=click.Choice(['DEBUG', 'INFO', 'ERROR']))
def cmd(level):
    pass
```

```bash
$ python cli.py --level DEBUG     # ✅ Valid
$ python cli.py --level debug     # ❌ Error: Invalid choice: debug
$ python cli.py --level info      # ❌ Error: Invalid choice: info
```

#### Case Insensitive
```python
@click.option('--level', type=click.Choice(['DEBUG', 'INFO', 'ERROR'], case_sensitive=False))
def cmd(level):
    pass
```

```bash
$ python cli.py --level DEBUG     # ✅ Valid → 'DEBUG'
$ python cli.py --level debug     # ✅ Valid → 'DEBUG'
$ python cli.py --level DeBuG     # ✅ Valid → 'DEBUG'
```

---

### Error Messages

When user provides invalid choice:

```python
@click.option('--format', type=click.Choice(['json', 'xml']))
```

**Error:**
```bash
$ python cli.py --format yaml
Error: Invalid value for '--format': invalid choice: yaml. (choose from json, xml)
```

---

### Complete Example

```python
import click

@click.command()
@click.option('--output-format', 
              type=click.Choice(['json', 'xml', 'csv', 'yaml'], case_sensitive=False),
              default='json',
              show_default=True,
              help='Output format for the data')
@click.option('--log-level',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              default='INFO',
              help='Logging level')
def export(output_format, log_level):
    """Export data in various formats"""
    click.echo(f"Exporting in {output_format.upper()} format")
    click.echo(f"Log level: {log_level}")

if __name__ == '__main__':
    export()
```

**Usage:**
```bash
$ python export.py --help
Usage: export.py [OPTIONS]

  Export data in various formats

Options:
  --output-format [json|xml|csv|yaml]
                                  Output format for the data  [default: json]
  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  Logging level
  --help                          Show this message and exit.

$ python export.py --output-format XML --log-level DEBUG
Exporting in XML format
Log level: DEBUG

$ python export.py --output-format json
Exporting in JSON format
Log level: INFO
```

---

### Summary Table

| Syntax | Valid? | Why? |
|--------|--------|------|
| `click.Choice(['json', 'xml'])` | ✅ Yes | Correct - passes a list |
| `click.Choice(('json', 'xml'))` | ✅ Yes | Correct - passes a tuple |
| `click.Choice('json', 'xml')` | ❌ No | Wrong - passes 2 separate args |
| `click.Choice['json', 'xml']` | ❌ No | Wrong - `[]` not for function calls |

| Aspect | Details |
|--------|---------|
| **Type** | Class |
| **Purpose** | Restrict input to specific choices |
| **Required Parameter** | `choices` (list/tuple) |
| **Optional Parameter** | `case_sensitive` (bool) |
| **Returns** | The selected choice (as string) |
| **Error** | Raises error if invalid choice provided |
| **Use with** | `@click.option()` or `@click.argument()` |

**Key Point:** The class needs ONE iterable parameter, not multiple individual arguments!

