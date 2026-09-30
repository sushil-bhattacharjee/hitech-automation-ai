# pyATS Runtime & Job File Guide

## Table of Contents
- [What is a Job File?](#what-is-a-job-file)
- [What is Runtime?](#what-is-runtime)
- [Basic Job File Structure](#basic-job-file-structure)
- [Simple Examples](#simple-examples)
- [Understanding taskid](#understanding-taskid)
- [CLI Commands](#cli-commands)
- [Best Practices](#best-practices)

---

## What is a Job File?

A **job file** is the orchestrator or controller of your test automation:

- **Testscript** = the actual tests (what to test)
- **Job file** = the controller (which tests to run, when, and how)

### Analogy
- **Testscript** → Worker doing specific tasks
- **Job file** → Manager deciding which workers to deploy and in what order

---

## What is Runtime?

**Runtime** is an object automatically created by pyATS when you run a job. It contains:

- **Directory information** (where logs/results are stored)
- **Job execution details** (start time, parameters, etc.)
- **Configuration data**
- **Testbed information** (if passed via CLI)

Think of runtime as the **execution context** - all the information about *this specific run*.

---

## Basic Job File Structure

Every job file must have a `main()` function:

```python
from pyats.easypy import run

def main(runtime):
    """
    Entry point for the job file
    runtime is automatically provided by pyATS
    """
    run('my_testscript.py')
```

---

## Simple Examples

### Example 1: Minimal Job File

```python
# simple_job.py

from pyats.easypy import run

def main(runtime):
    """
    Simplest job file - runs one testscript
    """
    run('my_testscript.py')
```

**Run it:**
```bash
pyats run job simple_job.py --testbed-file testbed.yaml
```

---

### Example 2: Job File with Runtime

```python
# job_with_runtime.py

from pyats.easypy import run

def main(runtime):
    """
    Job file that uses runtime information
    """
    
    # Access runtime directory
    print(f"Results will be saved in: {runtime.directory}")
    
    # Pass runtime to testscript
    run('my_testscript.py', runtime=runtime)
```

**Run it:**
```bash
pyats run job job_with_runtime.py --testbed-file testbed.yaml
```

---

### Example 3: Manually Loading Testbed

```python
# job_manual_testbed.py

from pyats.easypy import run
from genie.testbed import load

def main(runtime):
    """
    Job file that loads testbed manually
    """
    
    # Load testbed from file
    testbed = load('testbed.yaml')
    
    # Run testscript with all parameters
    run(
        testscript='my_testscript.py',
        runtime=runtime,
        testbed=testbed
    )
```

**Run it:**
```bash
# No --testbed-file needed since we load it manually
pyats run job job_manual_testbed.py
```

---

### Example 4: Multiple Testscripts in Sequence

```python
# sequential_tests_job.py

from pyats.easypy import run

def main(runtime):
    """
    Job file running multiple testscripts one after another
    """
    
    print("Starting test suite...")
    
    # Run tests in sequence
    run('test_connectivity.py', runtime=runtime)
    run('test_interfaces.py', runtime=runtime)
    run('test_routing.py', runtime=runtime)
    
    print("Test suite completed!")
```

**Run it:**
```bash
pyats run job sequential_tests_job.py --testbed-file testbed.yaml
```

---

### Example 5: Conditional Execution

```python
# conditional_job.py

from pyats.easypy import run

def main(runtime):
    """
    Job file with conditional logic
    """
    
    # Run basic tests first
    result = run('basic_tests.py', runtime=runtime)
    
    # Only run advanced tests if basic tests passed
    if result.result == 'Passed':
        print("Basic tests passed, running advanced tests...")
        run('advanced_tests.py', runtime=runtime)
    else:
        print("Basic tests failed, skipping advanced tests")
```

**Run it:**
```bash
pyats run job conditional_job.py --testbed-file testbed.yaml
```

---

### Example 6: With Custom Parameters

```python
# job_with_params.py

from pyats.easypy import run
from genie.testbed import load

def main(runtime):
    """
    Job file passing custom parameters to testscript
    """
    
    testbed = load('testbed.yaml')
    
    # Pass custom parameters to testscript
    run(
        testscript='validate_vlans.py',
        runtime=runtime,
        testbed=testbed,
        vlan_file='vlans.yaml',      # Custom parameter
        check_mode=True,              # Custom parameter
        timeout=300                   # Custom parameter
    )
```

**Run it:**
```bash
pyats run job job_with_params.py
```

---

## Understanding taskid

### What is taskid?

`taskid` is a **unique identifier** for each task that helps:

1. **Distinguish between different test runs** in logs and reports
2. **Track specific tasks** when running multiple testscripts
3. **Filter tasks** using CLI arguments
4. **Organize results** in the final report

### Example: Multiple Testscripts with taskids

```python
# network_validation_job.py

from pyats.easypy import run
from genie.testbed import load

def main(runtime):
    """
    Complete network validation with unique taskids
    """
    
    testbed = load('testbed.yaml')
    
    # Task 1: Connectivity check
    run(
        testscript='check_connectivity.py',
        taskid='Connectivity-Check',        # Unique ID
        runtime=runtime,
        testbed=testbed
    )
    
    # Task 2: VLAN validation
    run(
        testscript='validate_vlans.py',
        taskid='VLAN-Validation',           # Different ID
        runtime=runtime,
        testbed=testbed
    )
    
    # Task 3: Interface health
    run(
        testscript='check_interfaces.py',
        taskid='Interface-Health',          # Another unique ID
        runtime=runtime,
        testbed=testbed
    )
```

**Run it:**
```bash
# Run all tasks
pyats run job network_validation_job.py

# Run only specific task
pyats run job network_validation_job.py --task-uids "VLAN-Validation"

# Run multiple specific tasks
pyats run job network_validation_job.py --task-uids "Connectivity-Check,VLAN-Validation"
```

### Report Output with taskids

```
+------------------------------------------------------------------------------+
| Task Result Summary                                                           |
+------------------------------------------------------------------------------+
Connectivity-Check                                                        PASSED
VLAN-Validation                                                           PASSED
Interface-Health                                                          PASSED
+------------------------------------------------------------------------------+
```

---

## CLI Commands

### Basic Execution

```bash
# With testbed file from CLI
pyats run job my_job.py --testbed-file testbed.yaml

# Without testbed file (loaded manually in job)
pyats run job my_job.py
```

### With Additional Options

```bash
# Specify output directory
pyats run job my_job.py --testbed-file testbed.yaml --runinfo-dir /path/to/results

# Run specific tasks only
pyats run job my_job.py --task-uids "Task-1,Task-2"

# Disable email notifications
pyats run job my_job.py --testbed-file testbed.yaml --no-mail

# Set log level
pyats run job my_job.py --testbed-file testbed.yaml --loglevel DEBUG
```

### Getting Help

```bash
# View all available options
pyats run job --help
```

---

## Best Practices

### 1. Use Descriptive taskids

**Good:**
```python
run(testscript='test_vlans.py', taskid='VLAN-Validation')
```

**Bad:**
```python
run(testscript='test_vlans.py', taskid='Task-1')
```

### 2. Load Testbed Once

**Good:**
```python
def main(runtime):
    testbed = load('testbed.yaml')  # Load once
    run('test1.py', testbed=testbed)
    run('test2.py', testbed=testbed)
```

**Avoid:**
```python
def main(runtime):
    run('test1.py', testbed=load('testbed.yaml'))
    run('test2.py', testbed=load('testbed.yaml'))  # Loading again!
```

### 3. Add Informative Messages

```python
def main(runtime):
    print(f"Starting job in: {runtime.directory}")
    print("Running connectivity tests...")
    run('test_connectivity.py')
    print("Connectivity tests completed!")
```

### 4. Handle Errors Gracefully

```python
def main(runtime):
    try:
        result = run('critical_test.py', runtime=runtime)
        if result.result != 'Passed':
            print("Critical test failed, stopping execution")
            return
    except Exception as e:
        print(f"Error during execution: {e}")
        raise
```

### 5. Use Meaningful File Names

**Good:**
- `network_validation_job.py`
- `daily_health_check_job.py`
- `vlan_audit_job.py`

**Bad:**
- `job1.py`
- `test_job.py`
- `my_job.py`

---

## Complete Working Example

```python
# complete_network_job.py

from pyats.easypy import run
from genie.testbed import load
import os

def main(runtime):
    """
    Complete network validation job file
    Demonstrates best practices and common patterns
    """
    
    # Print job information
    print("="*80)
    print(f"Job Name: Complete Network Validation")
    print(f"Runtime Directory: {runtime.directory}")
    print("="*80)
    
    # Load testbed
    testbed_file = os.path.join(os.path.dirname(__file__), 'testbed.yaml')
    testbed = load(testbed_file)
    
    # Task 1: Device Connectivity
    print("\n[1/4] Checking device connectivity...")
    connectivity_result = run(
        testscript='scripts/check_connectivity.py',
        taskid='01-Connectivity-Check',
        runtime=runtime,
        testbed=testbed
    )
    
    # Only continue if connectivity passed
    if connectivity_result.result != 'Passed':
        print("Connectivity check failed! Stopping execution.")
        return
    
    # Task 2: VLAN Validation
    print("\n[2/4] Validating VLANs...")
    run(
        testscript='scripts/validate_vlans.py',
        taskid='02-VLAN-Validation',
        runtime=runtime,
        testbed=testbed,
        vlan_file='data/vlans.yaml'
    )
    
    # Task 3: Interface Health
    print("\n[3/4] Checking interface health...")
    run(
        testscript='scripts/check_interfaces.py',
        taskid='03-Interface-Health',
        runtime=runtime,
        testbed=testbed
    )
    
    # Task 4: Routing Protocol Check
    print("\n[4/4] Verifying routing protocols...")
    run(
        testscript='scripts/check_routing.py',
        taskid='04-Routing-Verification',
        runtime=runtime,
        testbed=testbed
    )
    
    print("\n" + "="*80)
    print("Network validation job completed!")
    print(f"Results saved in: {runtime.directory}")
    print("="*80)
```

**Run it:**
```bash
pyats run job complete_network_job.py
```

---

## Key Takeaways

1. **Job file = orchestrator** that controls what runs and when
2. **Runtime = execution context** with directories, parameters, and job info
3. **One job file** can run multiple testscripts in sequence or parallel
4. **taskid** helps identify and filter specific tasks
5. **Testbed** can be passed via CLI or loaded manually in the job file
6. **Use descriptive names** for taskids and file names
7. **Add informative messages** to track execution progress

---

## Quick Reference

### Function Signatures

```python
# Job file structure
def main(runtime):
    # Your code here
    pass

# run() function
run(testscript, taskid=None, runtime=None, testbed=None, **kwargs)
```

### Common CLI Commands

```bash
# Basic execution
pyats run job <jobfile> --testbed-file <testbed>

# Run specific tasks
pyats run job <jobfile> --task-uids "<taskid1>,<taskid2>"

# Custom output directory
pyats run job <jobfile> --runinfo-dir <directory>

# Set log level
pyats run job <jobfile> --loglevel <DEBUG|INFO|WARNING|ERROR>
```

---

## Resources

- **Official pyATS Documentation**: https://pubhub.devnetcloud.com/media/pyats/docs/
- **Easypy Job Files**: https://pubhub.devnetcloud.com/media/pyats/docs/easypy/jobfile.html
- **run() API Reference**: https://pubhub.devnetcloud.com/media/pyats/docs/apidoc/easypy/index.html

---

**Created by:** Sushil  
**Date:** 2024  
**Purpose:** Learning pyATS Runtime & Job Files