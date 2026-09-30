# Challenge: pyATS Steps & Substeps

## TODO List

| TODO | Description |
|------|-------------|
| TODO-1 | Loop through SOTH and assert `adminSt`, `mtu`, and `mac` values |
| TODO-2 | Create STEP 1 to check VLAN existence with `continue_=True` |
| TODO-3 | Create STEP 2.1 substep to check `adminSt` is "up" |
| TODO-4 | Create STEP 2.2 substep to check `mtu` >= 9000 |
| TODO-5 | Create STEP 2.3.1 sub-substep to check MAC address |
| TODO-6 | Create STEP 2.3.2 sub-substep to check description |
| TODO-7 | Create substeps_job.py to run following
| $ uv run pyats run job substeps_job.py -t testbed.yml --task-uids "Or('substeps_test')" |
| $ uv run pyats run job substeps_job.py -t testbed.yml --task-uids "Or('connection_test')" |

---

## Expected Output

```
+------------------------------------------------------------------------------+
|                            Detailed Results                                  |
+------------------------------------------------------------------------------+
SECTIONS/TESTCASES                                                      RESULT
--------------------------------------------------------------------------------
.
|-- common_setup                                                        PASSED
|   `-- connect                                                         PASSED
|-- InterfaceValidation[device=nx9K73]                                  FAILED
|   |-- get_interfaces                                                  PASSED
|   |-- verify_interface_state[vlan=vlan3199]                           FAILED
|   |-- verify_interface_state[vlan=vlan3299]                           PASSED
|   |-- verify_interface_state[vlan=vlan999]                            PASSED
|   |-- verify_interface_state[vlan=vlan3399]                           FAILED
|   |-- verify_interface_state_step[vlan=vlan3199]                      FAILED
|   |   |-- Step 1: Check VLAN vlan3199 exists                          PASSED
|   |   |-- Step 2: Check VLAN vlan3199 attributes                      FAILED
|   |   |   |-- Step 2.1: Check adminSt                                 PASSED
|   |   |   |-- Step 2.2: Check MTU                                     PASSED
|   |   |   |-- Step 2.3: Check details                                 FAILED
|   |   |   |   |-- Step 2.3.1: Check MAC address                       FAILED
|   |   |   |   `-- Step 2.3.2: Check description                       PASSED
|   |-- verify_interface_state_step[vlan=vlan3299]                      FAILED
|   |   |-- Step 1: Check VLAN vlan3299 exists                          PASSED
|   |   |-- Step 2: Check VLAN vlan3299 attributes                      FAILED
|   |   |   |-- Step 2.1: Check adminSt                                 PASSED
|   |   |   |-- Step 2.2: Check MTU                                     PASSED
|   |   |   |-- Step 2.3: Check details                                 FAILED
|   |   |   |   |-- Step 2.3.1: Check MAC address                       PASSED
|   |   |   |   `-- Step 2.3.2: Check description                       FAILED
|   |-- verify_interface_state_step[vlan=vlan999]                       SKIPPED
|   `-- verify_interface_state_step[vlan=vlan3399]                      FAILED
|       |-- Step 1: Check VLAN vlan3399 exists                          PASSED
|       |-- Step 2: Check VLAN vlan3399 attributes                      FAILED
|       |   |-- Step 2.1: Check adminSt                                 PASSED
|       |   |-- Step 2.2: Check MTU                                     FAILED
|       |   |-- Step 2.3: Check details                                 PASSED
|       |   |   |-- Step 2.3.1: Check MAC address                       PASSED
|       |   |   `-- Step 2.3.2: Check description                       PASSED
`-- common_cleanup                                                      PASSED
    `-- disconnect                                                      PASSED
```

---

## Initial Files-1/2: substep.py

```python
from pyats import aetest
from genie.testbed import load
import yaml

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        testbed.connect()

@aetest.loop(device=['nx9K73'])
class InterfaceValidation(aetest.Testcase):
    
    @aetest.setup
    def get_interfaces(self):
        with open('svi_soth.yml') as f:
            self.soth = yaml.safe_load(f)['svi_interfaces']
    
    @aetest.test.loop(vlan=['vlan3199', 'vlan3299', 'vlan999', 'vlan3399'])
    def verify_interface_state(self, vlan):
        # TODO-1: Loop through SOTH and assert adminSt=up, mtu>=9000, and mac=52:A9:BD:A7:1B:08 values
        """
        |-- verify_interface_state[vlan=vlan3199]             FAILED
        |-- verify_interface_state[vlan=vlan3299]             PASSED
        |-- verify_interface_state[vlan=vlan999]              PASSED
        |-- verify_interface_state[vlan=vlan3399]             FAILED
        """
        for TODO:
            if TODO:
    
    @aetest.test.loop(vlan=['vlan3199', 'vlan3299', 'vlan999', 'vlan3399'])
    def verify_interface_state_step(self, vlan, steps):
        
        # Check if VLAN exists in SOTH
        if vlan not in self.soth:
            self.skipped(f"{vlan} doesn't exist in SOTH")
            return
        detail = self.soth[vlan]
        # TODO-2: Create step with continue_=True, mark as passed
        # STEP 1: Check VLAN existence
        """
        |-- Step 1: Check VLAN vlan3199 exists               PASSED
        |-- Step 1: Check VLAN vlan3299 exists               PASSED
        |-- Step 1: Check VLAN vlan3399 exists               PASSED
        """
        with TODO:

        # STEP 2: Check VLAN attributes (with substeps)
        """
        |-- Step 2: Check VLAN vlan3199 attributes           FAILED
        """
        with steps.start(f"Check VLAN {vlan} attributes", continue_=True) as step:
            # TODO-3: Create substep, check if adminSt == "up"
            # STEP 2.1: Check adminSt
            """
            |-- Step 2.1: Check adminSt                      PASSED
            """
            with TODO:
                

            # TODO-4: Create substep, check if mtu >= 9000
            # STEP 2.2: Check MTU
            """
            |-- Step 2.2: Check MTU                          PASSED
            """
            with TODO:
                
            
            # STEP 2.3: Check details (with subsubsteps)
            """
            |-- Step 2.3: Check details                       FAILED
            """
            with step.start(f"Check details", continue_=True) as substep:
                # TODO-5: Create sub-substep, check if mac == "52:A9:BD:A7:1B:08"
                # STEP 2.3.1: Check MAC address
                """
                |-- Step 2.3.1: Check MAC address              PASSED
                """
                with TODO:
                     
                """
                #! It is possible to use assert instead of if statement. The only difference is you lose the custom messages ("MAC Address is correct" / "MAC Address is wrong"). With bare assert, a pass is silent and a failure just shows AssertionError. 
                """
                # TODO-6: Create sub-substep, check if descr is not empty
                # STEP 2.3.2: Check description
                """
                |-- Step 2.3.2: Check description                       PASSED
                """
                with TODO:
                    

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect(self, testbed):
        testbed.disconnect()
#aetest.main(testbed=load('testbed.yml'))
```
## Initial Files-2/2: substeps_job.py

```python

```

### svi_soth.yml

```yaml
svi_interfaces:
  vlan3299:
    adminSt: up
    mtu: 9000
    details:
      descr: 
      mac: "52:A9:BD:A7:1B:08"
  vlan3399:
    adminSt: up
    mtu: 1500         # ← FAIL: expected >= 9000
    details:
      descr: prod99
      mac: "52:A9:BD:A7:1B:08"
  vlan3199:
    adminSt: down     # ← FAIL: expected up
    mtu: 9048
    details:
      descr: dev99
      mac: "52:A9:BD:A7:1B:09"  # ← FAIL: expected 52:A9:BD:A7:1B:08
```

---

## Run Command

```bash
pyats run genie substep.py --testbed testbed.yml
```

---

<details>
<summary><strong>Solution (click to expand)</strong></summary>

```python
from pyats import aetest
from genie.testbed import load
import yaml


class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        testbed.connect()

@aetest.loop(device=['nx9K73'])
class InterfaceValidation(aetest.Testcase):
    
    @aetest.setup
    def get_interfaces(self):
        with open('svi_soth.yml') as f:
            self.soth = yaml.safe_load(f)['svi_interfaces']
    
    @aetest.test.loop(vlan=['vlan3199', 'vlan3299', 'vlan999', 'vlan3399'])
    def verify_interface_state(self, vlan):
        # TODO-1: Loop through SOTH and assert adminSt=up, mtu>=9000, and mac=52:A9:BD:A7:1B:08 values
        """
        |-- verify_interface_state[vlan=vlan3199]             FAILED
        |-- verify_interface_state[vlan=vlan3299]             PASSED
        |-- verify_interface_state[vlan=vlan999]              PASSED
        |-- verify_interface_state[vlan=vlan3399]             FAILED
        """
        for key, value in self.soth.items():
            if key==vlan:
                assert value['adminSt']=='up'
                assert value['mtu'] >=9000
                assert value['details']['mac']=='52:A9:BD:A7:1B:08'
    
    @aetest.test.loop(vlan=['vlan3199', 'vlan3299', 'vlan999', 'vlan3399'])
    def verify_interface_state_step(self, vlan, steps):
        
        # Check if VLAN exists in SOTH
        if vlan not in self.soth:
            self.skipped(f"{vlan} doesn't exist in SOTH")
            return
        detail = self.soth[vlan]
        # TODO-2: Create step with continue_=True, mark as passed
        # STEP 1: Check VLAN existence
        """
        |-- Step 1: Check VLAN vlan3199 exists               PASSED
        |-- Step 1: Check VLAN vlan3299 exists               PASSED
        |-- Step 1: Check VLAN vlan3399 exists               PASSED
        """
        with steps.start(f"Check VLAN {vlan} exists", continue_=True) as step:
            step.passed(f"{vlan} exist")
        # STEP 2: Check VLAN attributes (with substeps)
        """
        |-- Step 2: Check VLAN vlan3199 attributes           FAILED
        """
        with steps.start(f"Check VLAN {vlan} attributes", continue_=True) as step:
            # TODO-3: Create substep, check if adminSt == "up"
            # STEP 2.1: Check adminSt
            """
            |-- Step 2.1: Check adminSt                                 PASSED
            """
            with step.start(f"Check adminSt", continue_=True) as substep:
                assert detail['adminSt']=='up'

            # TODO-4: Create substep, check if mtu >= 9000
            # STEP 2.2: Check MTU
            """
            |-- Step 2.2: Check MTU                                     PASSED
            """
            with step.start(f"Check MTU", continue_=True) as substep:
                assert detail['mtu']>=9000
            
            # STEP 2.3: Check details (with subsubsteps)
            """
            |-- Step 2.3: Check details                                 FAILED
            """
            with step.start(f"Check details", continue_=True) as substep:
                # TODO-5: Create sub-substep, check if mac == "52:A9:BD:A7:1B:08"
                # STEP 2.3.1: Check MAC address
                """
                |-- Step 2.3.1: Check MAC address                       PASSED
                """
                with substep.start("Check MAC address", continue_=True) as subsubstep:
                    assert detail['details']['mac']=='52:A9:BD:A7:1B:08' 
                """
                #! It is possible to use assert instead of if statement. The only difference is you lose the custom messages ("MAC Address is correct" / "MAC Address is wrong"). With bare assert, a pass is silent and a failure just shows AssertionError. 
                """
                # TODO-6: Create sub-substep, check if descr is not empty
                # STEP 2.3.2: Check description
                """
                |-- Step 2.3.2: Check description                       PASSED
                """
                with substep.start("Check description", continue_=True) as subsubstep:
                    if detail['details']['descr']:
                        subsubstep.passed("Description is given")
                    else:
                        subsubstep.failed("Description is not given")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect(self, testbed):
        testbed.disconnect()
#aetest.main(testbed=load('testbed.yml'))

```

</details>

---

<details>
<summary><strong>Helpful Info: Steps & Substeps Reference (click to expand)</strong></summary>

# pyATS Steps, Substeps & continue_=True

A simple guide to organizing test validations in pyATS.

---

## What Are Steps?

Steps break a single test into multiple checkpoints. Instead of one pass/fail, you get granular results.

```python
@aetest.test
def my_test(self, steps):
    
    with steps.start("Check A"):
        # validation logic
        pass
    
    with steps.start("Check B"):
        # validation logic
        pass
```

**Output:**
```
STEP 1 - Check A    Passed
STEP 2 - Check B    Passed
```

---

## What Are Substeps?

Substeps nest validations under a parent step using `as step`:

```python
@aetest.test
def my_test(self, steps):
    
    with steps.start("VLAN 10 Validation") as step:
        
        with step.start("Check exists"):
            pass
        
        with step.start("Check MTU"):
            pass
```

**Output:**
```
STEP 1 - VLAN 10 Validation    Passed
STEP 1.1 - Check exists        Passed
STEP 1.2 - Check MTU           Passed
```

---

## Deep Nesting (Sub-substeps)

You can nest further using unique variable names:

```python
@aetest.test
def my_test(self, steps):
    
    with steps.start("VLAN Validation") as step:
        
        with step.start("Check attributes") as substep:
            
            with substep.start("Check MAC"):
                pass
            
            with substep.start("Check description"):
                pass
```

**Output:**
```
STEP 1 - VLAN Validation           Passed
STEP 1.1 - Check attributes        Passed
STEP 1.1.1 - Check MAC             Passed
STEP 1.1.2 - Check description     Passed
```

---

## The `as` Keyword Rule

| Code | Result |
|------|--------|
| `with steps.start("Step 1"):` | No variable - can't create substeps |
| `with steps.start("Step 1") as step:` | `step` variable created - can create substeps |

---

## Variable Naming Matters

Always use **unique names** at each level:

```python
# CORRECT - unique names
with steps.start("Step 1") as step:
    with step.start("Substep 1.1") as substep:
        with substep.start("Sub-substep 1.1.1"):
            pass
    with step.start("Substep 1.2"):      # Still child of Step 1 ✓
        pass
```

```python
# WRONG - reusing 'step' name
with steps.start("Step 1") as step:
    with step.start("Substep 1.1") as step:    # Overwrites step!
        pass
    with step.start("Substep 1.2"):            # Now child of 1.1 ✗
        pass
```

---

## What Is `continue_=True`?

By default, if a step fails, subsequent steps **don't run**.

### Without `continue_=True`

```python
with steps.start("Step 1") as step:
    step.failed("Something broke")          # Fails here

with steps.start("Step 2") as step:         # Never runs!
    step.passed("You won't see this")
```

### With `continue_=True`

```python
with steps.start("Step 1", continue_=True) as step:
    step.failed("Something broke")          # Fails here

with steps.start("Step 2") as step:         # Still runs!
    step.passed("I ran anyway")
```

---

## `continue_=True` Placement

Put it on the step that **might fail**, not the next one:

```python
# CORRECT
with steps.start("Step 1", continue_=True) as step:    # If I fail, continue
    step.failed("error")

with steps.start("Step 2") as step:                    # I will run
    step.passed("ok")
```

---

## Quick Reference

| Concept | Syntax | Purpose |
|---------|--------|---------|
| Step | `steps.start("name")` | Top-level checkpoint |
| Substep | `step.start("name")` | Nested under step |
| Sub-substep | `substep.start("name")` | Nested under substep |
| `as step` | `with steps.start() as step:` | Capture reference for nesting |
| `continue_=True` | `steps.start("name", continue_=True)` | Run next step even if this fails |
| `step.passed()` | Inside step context | Mark step as passed |
| `step.failed()` | Inside step context | Mark step as failed |
| `step.skipped()` | Inside step context | Mark step as skipped |

---

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Missing `as step` | Can't create substeps | Add `as step` |
| Reusing variable name | Wrong nesting | Use unique names: `step`, `substep`, `subsubstep` |
| `continue_=True` on wrong step | Next step still won't run | Put on the step that might fail |
| Using `steps.start()` for substeps | Creates sibling, not child | Use `step.start()` for substeps |

</details>