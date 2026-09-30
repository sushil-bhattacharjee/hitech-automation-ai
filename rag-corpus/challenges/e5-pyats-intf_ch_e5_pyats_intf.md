# Challenge: e5-pyats-intf — Interface Status Checker

## TODO Tasks

- **TODO-1:** Create the subsection and method to connect to all devices using testbed `routers.yml`
- **TODO-2:** Add the decorator to loop the test for two devices `cat8Kv71` and `cat8Kv72`
- **TODO-3:** Collect and parse the output of the command `show interfaces`
- **TODO-4:** Using steps, assert that every **enabled** interface has `oper_status == 'up'` (use `continue_=True`)
- **TODO-5:** Create the CommonCleanup class with a subsection to disconnect from all devices
- **TODO-6:** Create the job file that loads testbed `routers.yml`, runs `interface_checker.py` with taskid `intf_check`, and executes via:
  ```
  uv run pyats run job job_intf_chck.py --task-uids "Or('intf_check')" --archive-dir . --archive-name testresult.zip --no-archive-subdir
  ```

---

## Expected Result

<details><summary>Click to reveal expected result</summary>

```
+------------------------------------------------------------------------------+
|                             Task Result Summary                              |
+------------------------------------------------------------------------------+
intf_check: interface_checker                                             FAILED
intf_check: interface_checker.common_setup                                PASSED
intf_check: interface_checker.Tests                                       FAILED
intf_check: interface_checker.common_cleanup                              PASSED

+------------------------------------------------------------------------------+
|                             Task Result Details                              |
+------------------------------------------------------------------------------+
intf_check: interface_checker                                             FAILED
|-- common_setup                                                          PASSED
|   `-- connect_all                                                       PASSED
|-- Tests                                                                 FAILED
|   |-- check_interfaces[device=cat8Kv71]                                 FAILED
|   |   |-- STEP 1: Checking cat8Kv71 interface GigabitEthernet1          PASSED
|   |   |-- STEP 2: Checking cat8Kv71 interface GigabitEthernet2          PASSED
|   |   |-- STEP 3: Checking cat8Kv71 interface GigabitEthernet2.10       PASSED
|   |   |-- STEP 4: Checking cat8Kv71 interface GigabitEthernet2.101      PASSED
|   |   |-- STEP 5: Checking cat8Kv71 interface GigabitEthernet3          PASSED
|   |   |-- STEP 6: Checking cat8Kv71 interface GigabitEthernet3.10       PASSED
|   |   |-- STEP 7: Checking cat8Kv71 interface GigabitEthernet3.103      PASSED
|   |   |-- STEP 8: Checking cat8Kv71 interface GigabitEthernet3.104      PASSED
|   |   |-- STEP 9: Checking cat8Kv71 interface GigabitEthernet4          PASSED
|   |   |-- STEP 10: Checking cat8Kv71 interface GigabitEthernet5         PASSED
|   |   |-- STEP 11: Checking cat8Kv71 interface GigabitEthernet6         PASSED
|   |   |-- STEP 12: Checking cat8Kv71 interface GigabitEthernet7         PASSED
|   |   |-- STEP 13: Checking cat8Kv71 interface GigabitEthernet8         PASSED
|   |   |-- STEP 14: Checking cat8Kv71 interface GigabitEthernet8.1010    PASSED
|   |   |-- STEP 15: Checking cat8Kv71 interface Loopback0                PASSED
|   |   |-- STEP 16: Checking cat8Kv71 interface Loopback221              PASSED
|   |   |-- STEP 17: Checking cat8Kv71 interface Loopback222              PASSED
|   |   |-- STEP 18: Checking cat8Kv71 interface Loopback404              PASSED
|   |   |-- STEP 19: Checking cat8Kv71 interface Loopback10093            PASSED
|   |   |-- STEP 20: Checking cat8Kv71 interface Loopback10410            PASSED
|   |   |-- STEP 21: Checking cat8Kv71 interface Loopback13111            PASSED
|   |   |-- STEP 22: Checking cat8Kv71 interface Vlan3                    FAILED
|   |   |-- STEP 23: Checking cat8Kv71 interface Vlan88                   FAILED
|   |   |-- STEP 24: Checking cat8Kv71 interface Vlan3199                 FAILED
|   |   |-- STEP 25: Checking cat8Kv71 interface Vlan3299                 FAILED
|   |   `-- STEP 26: Checking cat8Kv71 interface Vlan3399                 FAILED
|   `-- check_interfaces[device=cat8Kv72]                                 FAILED
|       |-- STEP 1: Checking cat8Kv72 interface GigabitEthernet1          PASSED
|       |-- STEP 2: Checking cat8Kv72 interface GigabitEthernet2          PASSED
|       |-- STEP 3: Checking cat8Kv72 interface GigabitEthernet2.10       PASSED
|       |-- STEP 4: Checking cat8Kv72 interface GigabitEthernet2.101      PASSED
|       |-- STEP 5: Checking cat8Kv72 interface GigabitEthernet3          PASSED
|       |-- STEP 6: Checking cat8Kv72 interface GigabitEthernet3.10       PASSED
|       |-- STEP 7: Checking cat8Kv72 interface GigabitEthernet3.103      PASSED
|       |-- STEP 8: Checking cat8Kv72 interface GigabitEthernet4          PASSED
|       |-- STEP 9: Checking cat8Kv72 interface GigabitEthernet5          PASSED
|       |-- STEP 10: Checking cat8Kv72 interface GigabitEthernet6         PASSED
|       |-- STEP 11: Checking cat8Kv72 interface GigabitEthernet7         PASSED
|       |-- STEP 12: Checking cat8Kv72 interface GigabitEthernet8         PASSED
|       |-- STEP 13: Checking cat8Kv72 interface Loopback0                PASSED
|       |-- STEP 14: Checking cat8Kv72 interface Loopback221              PASSED
|       |-- STEP 15: Checking cat8Kv72 interface Loopback222              PASSED
|       |-- STEP 16: Checking cat8Kv72 interface Loopback404              PASSED
|       |-- STEP 17: Checking cat8Kv72 interface Loopback10410            PASSED
|       |-- STEP 18: Checking cat8Kv72 interface Loopback13111            PASSED
|       |-- STEP 19: Checking cat8Kv72 interface Vlan3                    FAILED
|       |-- STEP 20: Checking cat8Kv72 interface Vlan88                   FAILED
|       |-- STEP 21: Checking cat8Kv72 interface Vlan3199                 FAILED
|       |-- STEP 22: Checking cat8Kv72 interface Vlan3299                 FAILED
|       `-- STEP 23: Checking cat8Kv72 interface Vlan3399                 FAILED
`-- common_cleanup                                                        PASSED
    `-- disconnect_all                                                    PASSED
```

</details>

---

## Initial Files

### `interface_checker.py`

```python
from genie import testbed
from pyats import aetest
import logging

class Setup(aetest.CommonSetup):
    #! TODO-1: Create the subsection and method to connect to all devices using testbed routers.yml
    #TODO-1
    #TODO-1

class Tests(aetest.Testcase):
    #! TODO-2: Add the decorator to loop the test for two devices 'cat8Kv71' and 'cat8Kv72'
    #TODO-2
    def check_interfaces(self, testbed, device, steps):
        #! TODO-3: Collect and parse the output of the command "show interfaces"
        #TODO-3
        for if_name, if_details in interfaces.items():
            #! TODO-4: Using steps, assert that every enabled interface has oper_status == 'up' (use continue_=True)
            

#! TODO-5: Create the CommonCleanup class with a subsection to disconnect from all devices

class #TODO
```

### `job_intf_chck.py`

```python
#! TODO-6: Create the job file which will load the testbed 'routers.yml' and will run with following command
"""
uv run pyats run job job_intf_chck.py --task-uids "Or('intf_check')" --archive-dir . --archive-name testresult.zip --no-archive-subdir
    """
#! TODO-6: This job file will run script "interface_checker.py"



```

### `routers.yml`

```yaml
testbed:
    name: IOS_Testbed
    credentials:
        default:
            username: expert
            password: 1234QWer!
devices:
    cat8Kv71:
        os: ios
        type: ios
        connections:
            vty:
                protocol: ssh
                ip: 192.168.89.71
    cat8Kv72:
        os: ios
        type: ios
        connections:
            vty:
                protocol: ssh
                ip: 192.168.89.72
```

---

## Solution

<details><summary>Click to reveal solution</summary>

### `interface_checker.py`

```python
from genie import testbed
from pyats import aetest
import logging

class Setup(aetest.CommonSetup):
    #! TODO-1: Create the subsection and method to connect to all devices using testbed routers.yml
    @aetest.subsection
    def connect_all(self, testbed):
        testbed.connect()

class Tests(aetest.Testcase):
    #! TODO-2: Add the decorator to loop the test for two devices 'cat8Kv71' and 'cat8Kv72'
    @aetest.test.loop(device=("cat8Kv71", "cat8Kv72"))
    def check_interfaces(self, testbed, device, steps):
        #! TODO-3: Collect and parse the output of the command "show interfaces"
        interfaces = testbed.devices[device].parse('show interfaces')
        for if_name, if_details in interfaces.items():
            #! TODO-4: Using steps, assert that every enabled interface has oper_status == 'up' (use continue_=True)
            with steps.start(f"Checking {device} interface {if_name}", continue_=True) as step:
                if if_details['enabled']:
                    assert if_details['oper_status'] == 'up'

#! TODO-5: Create the CommonCleanup class with a subsection to disconnect from all devices
class Cleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_all(self, testbed):
        for device in testbed.devices.values():
            device.disconnect()


# if __name__ == '__main__':
#     aetest.main(testbed = testbed.load('routers.yml'))
```

### `job_intf_chck.py`

```python
#! TODO-6: Create the job file which will load the testbed 'routers.yml' and will run with following command
"""
uv run pyats run job job_intf_chck.py --task-uids "Or('intf_check')" --archive-dir . --archive-name testresult.zip --no-archive-subdir
    """
#! TODO-6: This job file will run script "interface_checker.py"
from pyats.easypy import run
from genie.testbed import load

def main(runtime):
    run(testscript="interface_checker.py", taskid="intf_check", testbed=load('routers.yml'), runtime=runtime)
```

</details>