# full-aci-ansible — all files

Each section is one file. Create the path shown and paste the content. `admin.key` sits in the project root (in the zip).

# Full ACI Tenant with Ansible

Ansible version of the Terraform `full-tenant` lab: one tenant, 2 VRFs, 4 BDs,
2 app profiles / 5 EPGs, 7 filters, 7 contracts, 2 OSPF L3Outs.

## Layout

```
full-aci-ansible/
├── ansible.cfg
├── admin.key                     # private key for cert auth
├── site.yml                      # main playbook (all roles or a selection)
├── tasks/run_role.yml            # runs one role inside block/rescue
├── inventory/
│   ├── hosts.yml                 # apic1 + auth (cert, password fallback)
│   └── group_vars/all/
│       ├── 01_settings.yml       # aci_state (present by default)
│       ├── 02_tenant.yml
│       ├── 03_vrfs.yml
│       ├── 04_bds.yml
│       ├── 05_apps_epgs.yml
│       ├── 06_filters.yml
│       ├── 07_contracts.yml
│       ├── 08_bindings.yml
│       └── 09_l3outs.yml
└── roles/
    ├── aci_tenant/tasks/main.yml
    ├── aci_vrf/tasks/main.yml
    ├── aci_bd/tasks/main.yml         # BD + subnet + BD->L3Out
    ├── aci_app_epg/tasks/main.yml    # AP + EPG
    ├── aci_filter/tasks/main.yml     # filter + entry
    ├── aci_contract/tasks/main.yml   # contract + subject + subject->filter
    ├── aci_binding/tasks/main.yml    # EPG provider/consumer
    └── aci_l3out/tasks/
        ├── main.yml                  # includes the 4 files below
        ├── l3out.yml                 # L3Out + OSPF area
        ├── node.yml                  # node profile + leaf node
        ├── interface.yml             # int profile + path + OSPF interface
        └── ext_epg.yml               # ext EPG + subnets + contracts
```

Each role reads only its own vars file (e.g. `aci_bd` <-> `04_bds.yml`).

## Auth (set in inventory/hosts.yml)

| `aci_auth_mode` | Behaviour |
|---|---|
| `cert` (default) | Certificate `ansible` + `admin.key` (project root). If the key file is missing, falls back to username/password automatically |
| `password` | Always username/password (`-e aci_auth_mode=password`) |

Username/password default to `admin` / `1234QWer!`. `APIC_USERNAME` /
`APIC_PASSWORD` env vars override them if set. `admin.crt` is not needed by
Ansible; it only has to be uploaded to the APIC user as certificate `ansible`.

L3 domain `L3-Dom` (in `09_l3outs.yml`) must already exist under
Fabric > Access Policies > Physical and External Domains > L3 Domains.

## Run

| Command | What it does |
|---|---|
| `ansible-playbook site.yml` | Deploy everything |
| `ansible-playbook site.yml -e run_roles=vrf,bd` | Deploy only VRF and BD (order is fixed automatically) |
| `ansible-playbook site.yml --tags debug` | Show all variables only, nothing sent to APIC |
| `ansible-playbook site.yml --skip-tags debug` | Deploy without debug output |
| `ansible-playbook site.yml -e aci_state=absent -e confirm_destroy=yes` | Destroy (reverse order) |

Role keys: `tenant, vrf, bd, app_epg, filter, contract, binding, l3out`

## How failure isolation works

`site.yml` loops over the selected roles and runs each one through
`tasks/run_role.yml` (`block` / `rescue`). A failed role is recorded and the
next role still runs. The last task prints a summary:

```
"msg": { "tenant": "OK", "vrf": "OK", "l3out": "FAILED - ..." }
```

A child object still fails if its parent is missing (no tenant = no VRF),
but the run finishes and tells you which role broke.

## Destroy behaviour

Destroy reverses the order (l3out -> ... -> tenant). Each role deletes only its
top-level object; APIC removes the children (BD subnets, EPGs, filter entries,
L3Out node/interface/ext EPG) automatically.

## Fixes vs the Terraform version

| Issue in Terraform | Fix |
|---|---|
| Web BD in `External` VRF, App/DB in `Internal` -> Web-to-App needs inter-VRF leaking | 3-tier app + both L3Outs in `Prod-VRF`; Monitoring in `Mgmt-VRF` |
| `Internet-In` provided twice, never consumed; `Internet-Out` no provider | Ext EPG consumes Internet-In, provides Internet-Out |
| `Allow-SSH` / `Allow-ICMP` had no consumer | DC-Interconnect ext EPG consumes them |
| Prometheus/Grafana had no contract | Added `Grafana-to-Prometheus` (tcp 9090) |
| Filter ether type `ipv4` | `ip` (`unspecified` for Any) |
| OSPF area `0` / `10` | `backbone` / `0.0.0.10` |
| No L3 domain on L3Out -> interfaces never deploy | `l3_domain: L3-Dom` |
| BD subnets public but BD not linked to L3Out -> never advertised | BD -> L3Out link added |
| `export-rtctrl` on 0.0.0.0/0 would advertise default route out | External subnets use `import-security` only |
| Internet transit 192.168.1.0/30 overlaps DC ext subnet 192.168.0.0/16 | Transit moved to 203.0.113.0/30 |

## Module notes

Native cisco.aci modules for tenant, VRF, BD, subnet, AP, EPG, filter, contract,
binding, L3Out, ext EPG and ext subnet. `aci_rest` for OSPF area, node profile,
node, interface profile, path, OSPF interface and ext EPG contracts, so it works
on any cisco.aci version (including Ansible 2.9).

---

# Files

## `ansible.cfg`

```ini
[defaults]
inventory           = inventory/hosts.yml
roles_path          = ./roles
gathering           = explicit
host_key_checking   = False
retry_files_enabled = False

# Uncomment if you hit Python interpreter conflicts (point at your venv)
# interpreter_python = ~/DevnetExpert/ansible29-venv/bin/python

# Uncomment for easier-to-read debug output (Ansible 2.9)
# stdout_callback = yaml
```

## `site.yml`

```yaml
---
# Run everything:        ansible-playbook site.yml
# Pick roles:            ansible-playbook site.yml -e run_roles=vrf,bd
# Debug only (no APIC):  ansible-playbook site.yml --tags debug
# Deploy, no debug:      ansible-playbook site.yml --skip-tags debug
# Destroy:               ansible-playbook site.yml -e aci_state=absent -e confirm_destroy=yes
#
# Role keys: tenant, vrf, bd, app_epg, filter, contract, binding, l3out

- name: Full ACI Tenant
  hosts: apic1
  gather_facts: false

  vars:
    all_roles: [tenant, vrf, bd, app_epg, filter, contract, binding, l3out]
    run_roles: "{{ all_roles }}"
    role_results: {}

  tasks:
    # ---------- Auth: certificate first, password fallback ----------
    - name: Check the private key file exists
      stat:
        path: "{{ private_key }}"
      register: key_file
      delegate_to: localhost
      tags: always

    - name: Pick auth method
      set_fact:
        aci_use_cert: "{{ aci_auth_mode == 'cert' and key_file.stat.exists }}"
      tags: always

    - name: DEBUG Auth method
      debug:
        msg:
          - "Mode requested : {{ aci_auth_mode }}"
          - "Key file       : {{ private_key }} (exists: {{ key_file.stat.exists }})"
          - "Using          : {{ 'certificate (' ~ certificate_name ~ ')' if aci_use_cert | bool else 'username/password' }}"
          - "Username       : {{ apic_username }}"
      tags: debug

    - name: Build the list of roles to run (keeps the correct order)
      set_fact:
        selected_roles: "{{ all_roles | select('in', run_roles.split(',') if run_roles is string else run_roles) | list }}"
      tags: always

    - name: Reverse the order for destroy (children before parents)
      set_fact:
        selected_roles: "{{ selected_roles | reverse | list }}"
      when: aci_state == 'absent'
      tags: always

    - name: Safety check before destroy
      assert:
        that: confirm_destroy | default('no') | bool
        fail_msg: "Destroy needs: -e aci_state=absent -e confirm_destroy=yes"
      when: aci_state == 'absent'
      tags: always

    - name: DEBUG Run plan
      debug:
        msg:
          - "APIC user : {{ apic_username }}"
          - "State     : {{ aci_state }}"
          - "Roles     : {{ selected_roles | join(' -> ') }}"
      tags: debug

    - name: Run each role (a failed role is recorded, the rest still run)
      include_tasks: tasks/run_role.yml
      loop: "{{ selected_roles }}"
      loop_control:
        loop_var: role_item
        label: "{{ role_item }}"
      tags: always

    - name: Summary
      debug:
        msg: "{{ role_results }}"
      tags: always
```

## `tasks/run_role.yml`

```yaml
---
# Runs ONE role inside block/rescue so a failure does not stop the play.
# Only the include_role task is tagged "always". include_role is dynamic, so
# that tag does NOT pass down: role tasks keep their own tags (debug / none).
- name: "Role aci_{{ role_item }}"
  block:
    - name: "Run role aci_{{ role_item }}"
      include_role:
        name: "aci_{{ role_item }}"
      tags: always

    - name: "Record result: {{ role_item }}"
      set_fact:
        role_results: "{{ role_results | combine({role_item: 'OK'}) }}"
      tags: always

  rescue:
    - name: "Record failure: {{ role_item }}"
      set_fact:
        role_results: "{{ role_results | combine({role_item: 'FAILED - ' ~ (ansible_failed_result.msg | default('see output above'))}) }}"
      tags: always
```

## `inventory/hosts.yml`

```yaml
all:
  hosts:
    apic1:
      ansible_host: 192.168.89.95
      ansible_connection: local
      apic_hostname: 192.168.89.95
      validate_certs: false

      # ---------- Auth ----------
      # aci_auth_mode: cert     -> certificate, falls back to password if admin.key is missing
      # aci_auth_mode: password -> always username/password
      # Override on CLI: -e aci_auth_mode=password
      aci_auth_mode: cert

      # Certificate auth (APIC user "admin" -> certificate object "ansible")
      certificate_name: ansible
      private_key: "{{ playbook_dir }}/admin.key"

      # Username (both methods) / password (fallback). Env vars win if set.
      apic_username: "{{ lookup('env', 'APIC_USERNAME') | default('admin', true) }}"
      apic_password: "{{ lookup('env', 'APIC_PASSWORD') | default('1234QWer!', true) }}"

# All ACI data lives in inventory/group_vars/all/ (one small file per object)
```

## `inventory/group_vars/all/01_settings.yml`

```yaml
---
# Default action is DEPLOY.
# Destroy from the CLI:  -e aci_state=absent -e confirm_destroy=yes
aci_state: present
```

## `inventory/group_vars/all/02_tenant.yml`

```yaml
---
tenant_name: Production
tenant_description: Full tenant config by Ansible
```

## `inventory/group_vars/all/03_vrfs.yml`

```yaml
---
# FIX: Web/App/DB share one VRF, so their contracts work with the default
#      "context" scope (no inter-VRF leaking needed). Monitoring is isolated.
vrfs:
  - vrf_name: Prod-VRF
  - vrf_name: Mgmt-VRF
```

## `inventory/group_vars/all/04_bds.yml`

```yaml
---
# scope: public  = advertised out of the L3Out listed in "l3out"
# scope: private = stays inside the fabric
# FIX: BD must be linked to an L3Out, otherwise "public" is never advertised.
bridge_domains:
  - bd_name: BD-Web
    vrf: Prod-VRF
    subnet: 10.1.1.1/24
    scope: public
    l3out: Internet-L3Out

  - bd_name: BD-App
    vrf: Prod-VRF
    subnet: 10.2.1.1/24
    scope: public
    l3out: DC-Interconnect

  - bd_name: BD-Database
    vrf: Prod-VRF
    subnet: 10.3.1.1/24
    scope: public
    l3out: DC-Interconnect

  - bd_name: BD-Mgmt
    vrf: Mgmt-VRF
    subnet: 10.100.1.1/24
    scope: private
    l3out: ""
```

## `inventory/group_vars/all/05_apps_epgs.yml`

```yaml
---
applications:
  - app_name: 3-Tier-App
    epgs:
      - epg_name: Web-EPG
        bd: BD-Web
      - epg_name: App-EPG
        bd: BD-App
      - epg_name: DB-EPG
        bd: BD-Database

  - app_name: Monitoring
    epgs:
      - epg_name: Prometheus
        bd: BD-Mgmt
      - epg_name: Grafana
        bd: BD-Mgmt
```

## `inventory/group_vars/all/06_filters.yml`

```yaml
---
# FIX: ACI ether type is "ip" (not "ipv4"); ICMP / Any have no ports.
# ether_type is optional (default "ip"); dest_port "" = no port.
filters:
  - { filter_name: HTTP,           entry_name: http-entry,  protocol: tcp,  dest_port: "80" }
  - { filter_name: HTTPS,          entry_name: https-entry, protocol: tcp,  dest_port: "443" }
  - { filter_name: MySQL,          entry_name: mysql-entry, protocol: tcp,  dest_port: "3306" }
  - { filter_name: SSH,            entry_name: ssh-entry,   protocol: tcp,  dest_port: "22" }
  - { filter_name: ICMP,           entry_name: icmp-entry,  protocol: icmp, dest_port: "" }
  - { filter_name: Prometheus-API, entry_name: prom-entry,  protocol: tcp,  dest_port: "9090" }
  - { filter_name: Any,            entry_name: any-entry,   protocol: unspecified, dest_port: "", ether_type: unspecified }
```

## `inventory/group_vars/all/07_contracts.yml`

```yaml
---
# scope "context" = within one VRF (all EPG pairs here are same-VRF)
contracts:
  - contract_name: Web-to-App
    scope: context
    filters: [HTTP, HTTPS]

  - contract_name: App-to-DB
    scope: context
    filters: [MySQL]

  - contract_name: Allow-SSH
    scope: context
    filters: [SSH]

  - contract_name: Allow-ICMP
    scope: context
    filters: [ICMP]

  - contract_name: Internet-In
    scope: context
    filters: [HTTP, HTTPS]

  - contract_name: Internet-Out
    scope: context
    filters: [Any]

  - contract_name: Grafana-to-Prometheus
    scope: context
    filters: [Prometheus-API]
```

## `inventory/group_vars/all/08_bindings.yml`

```yaml
---
# EPG side of each contract. External EPG side is in 09_l3outs.yml.
# FIX: every contract now has BOTH a provider and a consumer.
contract_bindings:
  # Web -> App -> DB
  - { app: 3-Tier-App, epg: Web-EPG, contract: Web-to-App, type: consumer }
  - { app: 3-Tier-App, epg: App-EPG, contract: Web-to-App, type: provider }
  - { app: 3-Tier-App, epg: App-EPG, contract: App-to-DB,  type: consumer }
  - { app: 3-Tier-App, epg: DB-EPG,  contract: App-to-DB,  type: provider }

  # SSH / ICMP into all tiers (consumed by DC-Interconnect external EPG)
  - { app: 3-Tier-App, epg: Web-EPG, contract: Allow-SSH,  type: provider }
  - { app: 3-Tier-App, epg: App-EPG, contract: Allow-SSH,  type: provider }
  - { app: 3-Tier-App, epg: DB-EPG,  contract: Allow-SSH,  type: provider }
  - { app: 3-Tier-App, epg: Web-EPG, contract: Allow-ICMP, type: provider }
  - { app: 3-Tier-App, epg: App-EPG, contract: Allow-ICMP, type: provider }
  - { app: 3-Tier-App, epg: DB-EPG,  contract: Allow-ICMP, type: provider }

  # Internet: inbound to Web, outbound from Web (other side = Internet external EPG)
  - { app: 3-Tier-App, epg: Web-EPG, contract: Internet-In,  type: provider }
  - { app: 3-Tier-App, epg: Web-EPG, contract: Internet-Out, type: consumer }

  # Monitoring
  - { app: Monitoring, epg: Grafana,    contract: Grafana-to-Prometheus, type: consumer }
  - { app: Monitoring, epg: Prometheus, contract: Grafana-to-Prometheus, type: provider }
```

## `inventory/group_vars/all/09_l3outs.yml`

```yaml
---
# PREREQUISITE: this L3 (routed) domain must already exist under
# Fabric > Access Policies > Physical and External Domains > L3 Domains.
# FIX: Terraform version had no domain, so interfaces would never deploy.
l3_domain: L3-Dom

# FIX: OSPF area must be "backbone" or dotted format (0.0.0.10), not "0"/"10".
# FIX: external subnets use import-security only (classification). BD subnets
#      are advertised via the BD -> L3Out link, not export-rtctrl on 0.0.0.0/0.
# FIX: Internet transit moved to 203.0.113.0/30 so it no longer overlaps
#      the DC-Interconnect external subnet 192.168.0.0/16.
l3outs:
  - l3out_name: Internet-L3Out
    vrf: Prod-VRF
    node_id: "101"
    router_id: 1.1.1.1
    interface: eth1/1
    interface_type: ext-svi        # ext-svi (VLAN) or l3-port (routed)
    interface_ip: 203.0.113.1/30
    encap: vlan-100                # "unknown" for l3-port
    ospf_area: backbone
    external_subnets:
      - 0.0.0.0/0
    contracts:
      - { contract: Internet-In,  type: consumer }
      - { contract: Internet-Out, type: provider }

  - l3out_name: DC-Interconnect
    vrf: Prod-VRF
    node_id: "102"
    router_id: 2.2.2.2
    interface: eth1/2
    interface_type: l3-port
    interface_ip: 172.16.0.1/30
    encap: unknown
    ospf_area: 0.0.0.10
    external_subnets:
      - 172.16.0.0/16              # Remote DC networks
      - 192.168.0.0/16             # Branch offices
    contracts:
      - { contract: Allow-SSH,  type: consumer }
      - { contract: Allow-ICMP, type: consumer }
```

## `roles/aci_tenant/tasks/main.yml`

```yaml
---
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

- name: DEBUG Tenant
  debug:
    msg: "Tenant: {{ tenant_name }} | Desc: {{ tenant_description }} | State: {{ aci_state }}"
  tags: debug

- name: Tenant
  cisco.aci.aci_tenant:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    description: "{{ tenant_description }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
```

## `roles/aci_vrf/tasks/main.yml`

```yaml
---
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

- name: DEBUG VRFs
  debug:
    msg: "Tenant: {{ tenant_name }} | VRF: {{ vrf_data.vrf_name }}"
  loop: "{{ vrfs }}"
  loop_control:
    loop_var: vrf_data
    label: "{{ vrf_data.vrf_name }}"
  tags: debug

- name: VRFs
  cisco.aci.aci_vrf:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    vrf: "{{ vrf_data.vrf_name }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
  loop: "{{ vrfs }}"
  loop_control:
    loop_var: vrf_data
    label: "{{ vrf_data.vrf_name }}"
```

## `roles/aci_bd/tasks/main.yml`

```yaml
---
# Destroy deletes the BD only - APIC removes its subnet and L3Out link with it.
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- Bridge Domains ----------
- name: DEBUG Bridge Domains
  debug:
    msg: "BD: {{ bd_data.bd_name }} | VRF: {{ bd_data.vrf }}"
  loop: "{{ bridge_domains }}"
  loop_control:
    loop_var: bd_data
    label: "{{ bd_data.bd_name }}"
  tags: debug

- name: Bridge Domains
  cisco.aci.aci_bd:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    bd: "{{ bd_data.bd_name }}"
    vrf: "{{ bd_data.vrf }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
  loop: "{{ bridge_domains }}"
  loop_control:
    loop_var: bd_data
    label: "{{ bd_data.bd_name }}"

# ---------- BD Subnets (gateway) ----------
- name: DEBUG BD Subnets
  debug:
    msg: "BD: {{ bd_data.bd_name }} | Gateway: {{ bd_data.subnet.split('/')[0] }} | Mask: {{ bd_data.subnet.split('/')[1] }} | Scope: {{ bd_data.scope }}"
  loop: "{{ bridge_domains }}"
  loop_control:
    loop_var: bd_data
    label: "{{ bd_data.bd_name }}"
  when: bd_data.subnet != ""
  tags: debug

- name: BD Subnets
  cisco.aci.aci_bd_subnet:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    bd: "{{ bd_data.bd_name }}"
    gateway: "{{ bd_data.subnet.split('/')[0] }}"
    mask: "{{ bd_data.subnet.split('/')[1] }}"
    scope: ["{{ bd_data.scope }}"]
    state: present
  delegate_to: localhost
  loop: "{{ bridge_domains }}"
  loop_control:
    loop_var: bd_data
    label: "{{ bd_data.bd_name }} {{ bd_data.subnet }}"
  when: aci_state == 'present' and bd_data.subnet != ""

# ---------- BD -> L3Out (advertise public subnets) ----------
- name: DEBUG BD to L3Out
  debug:
    msg: "BD: {{ bd_data.bd_name }} -> L3Out: {{ bd_data.l3out }}"
  loop: "{{ bridge_domains }}"
  loop_control:
    loop_var: bd_data
    label: "{{ bd_data.bd_name }}"
  when: bd_data.l3out != ""
  tags: debug

- name: BD to L3Out
  cisco.aci.aci_bd_to_l3out:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    bd: "{{ bd_data.bd_name }}"
    l3out: "{{ bd_data.l3out }}"
    state: present
  delegate_to: localhost
  loop: "{{ bridge_domains }}"
  loop_control:
    loop_var: bd_data
    label: "{{ bd_data.bd_name }} -> {{ bd_data.l3out }}"
  when: aci_state == 'present' and bd_data.l3out != ""
```

## `roles/aci_app_epg/tasks/main.yml`

```yaml
---
# Destroy deletes the App Profile only - APIC removes its EPGs with it.
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- Application Profiles ----------
- name: DEBUG Application Profiles
  debug:
    msg: "AP: {{ ap_data.app_name }}"
  loop: "{{ applications }}"
  loop_control:
    loop_var: ap_data
    label: "{{ ap_data.app_name }}"
  tags: debug

- name: Application Profiles
  cisco.aci.aci_ap:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    ap: "{{ ap_data.app_name }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
  loop: "{{ applications }}"
  loop_control:
    loop_var: ap_data
    label: "{{ ap_data.app_name }}"

# ---------- EPGs (epg_data.0 = app, epg_data.1 = epg) ----------
- name: DEBUG EPGs
  debug:
    msg: "AP: {{ epg_data.0.app_name }} | EPG: {{ epg_data.1.epg_name }} | BD: {{ epg_data.1.bd }}"
  with_subelements:
    - "{{ applications }}"
    - epgs
  loop_control:
    loop_var: epg_data
    label: "{{ epg_data.0.app_name }} / {{ epg_data.1.epg_name }}"
  tags: debug

- name: EPGs
  cisco.aci.aci_epg:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    ap: "{{ epg_data.0.app_name }}"
    epg: "{{ epg_data.1.epg_name }}"
    bd: "{{ epg_data.1.bd }}"
    state: present
  delegate_to: localhost
  with_subelements:
    - "{{ applications }}"
    - epgs
  loop_control:
    loop_var: epg_data
    label: "{{ epg_data.0.app_name }} / {{ epg_data.1.epg_name }}"
  when: aci_state == 'present'
```

## `roles/aci_filter/tasks/main.yml`

```yaml
---
# Destroy deletes the filter only - APIC removes its entry with it.
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- Filters ----------
- name: DEBUG Filters
  debug:
    msg: "Filter: {{ filter_data.filter_name }}"
  loop: "{{ filters }}"
  loop_control:
    loop_var: filter_data
    label: "{{ filter_data.filter_name }}"
  tags: debug

- name: Filters
  cisco.aci.aci_filter:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    filter: "{{ filter_data.filter_name }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
  loop: "{{ filters }}"
  loop_control:
    loop_var: filter_data
    label: "{{ filter_data.filter_name }}"

# ---------- Filter Entries (one per filter) ----------
- name: DEBUG Filter Entries
  debug:
    msg: >-
      Filter: {{ filter_data.filter_name }} | Entry: {{ filter_data.entry_name }} |
      EtherType: {{ filter_data.ether_type | default('ip') }} |
      Proto: {{ filter_data.protocol }} |
      Port: {{ filter_data.dest_port if filter_data.dest_port != '' else 'none' }}
  loop: "{{ filters }}"
  loop_control:
    loop_var: filter_data
    label: "{{ filter_data.filter_name }}"
  tags: debug

- name: Filter Entries
  cisco.aci.aci_filter_entry:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    filter: "{{ filter_data.filter_name }}"
    entry: "{{ filter_data.entry_name }}"
    ether_type: "{{ filter_data.ether_type | default('ip') }}"
    ip_protocol: "{{ filter_data.protocol }}"
    dst_port: "{{ filter_data.dest_port if filter_data.dest_port != '' else omit }}"
    state: present
  delegate_to: localhost
  loop: "{{ filters }}"
  loop_control:
    loop_var: filter_data
    label: "{{ filter_data.filter_name }} / {{ filter_data.entry_name }}"
  when: aci_state == 'present'
```

## `roles/aci_contract/tasks/main.yml`

```yaml
---
# Destroy deletes the contract only - APIC removes subject + filter links with it.
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- Contracts ----------
- name: DEBUG Contracts
  debug:
    msg: "Contract: {{ contract_data.contract_name }} | Scope: {{ contract_data.scope }}"
  loop: "{{ contracts }}"
  loop_control:
    loop_var: contract_data
    label: "{{ contract_data.contract_name }}"
  tags: debug

- name: Contracts
  cisco.aci.aci_contract:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    contract: "{{ contract_data.contract_name }}"
    scope: "{{ contract_data.scope }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
  loop: "{{ contracts }}"
  loop_control:
    loop_var: contract_data
    label: "{{ contract_data.contract_name }}"

# ---------- Subjects (one per contract) ----------
- name: DEBUG Contract Subjects
  debug:
    msg: "Contract: {{ contract_data.contract_name }} | Subject: {{ contract_data.contract_name }}-subject"
  loop: "{{ contracts }}"
  loop_control:
    loop_var: contract_data
    label: "{{ contract_data.contract_name }}"
  tags: debug

- name: Contract Subjects
  cisco.aci.aci_contract_subject:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    contract: "{{ contract_data.contract_name }}"
    subject: "{{ contract_data.contract_name }}-subject"
    state: present
  delegate_to: localhost
  loop: "{{ contracts }}"
  loop_control:
    loop_var: contract_data
    label: "{{ contract_data.contract_name }}-subject"
  when: aci_state == 'present'

# ---------- Subject -> Filter (subj_data.0 = contract, subj_data.1 = filter name) ----------
- name: DEBUG Subject to Filter
  debug:
    msg: "Subject: {{ subj_data.0.contract_name }}-subject | Filter: {{ subj_data.1 }}"
  with_subelements:
    - "{{ contracts }}"
    - filters
  loop_control:
    loop_var: subj_data
    label: "{{ subj_data.0.contract_name }} / {{ subj_data.1 }}"
  tags: debug

- name: Subject to Filter
  cisco.aci.aci_contract_subject_to_filter:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    contract: "{{ subj_data.0.contract_name }}"
    subject: "{{ subj_data.0.contract_name }}-subject"
    filter: "{{ subj_data.1 }}"
    state: present
  delegate_to: localhost
  with_subelements:
    - "{{ contracts }}"
    - filters
  loop_control:
    loop_var: subj_data
    label: "{{ subj_data.0.contract_name }} / {{ subj_data.1 }}"
  when: aci_state == 'present'
```

## `roles/aci_binding/tasks/main.yml`

```yaml
---
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

- name: DEBUG EPG to Contract
  debug:
    msg: "{{ bind_data.app }} / {{ bind_data.epg }} --{{ bind_data.type }}--> {{ bind_data.contract }}"
  loop: "{{ contract_bindings }}"
  loop_control:
    loop_var: bind_data
    label: "{{ bind_data.epg }} {{ bind_data.type }} {{ bind_data.contract }}"
  tags: debug

- name: EPG to Contract
  cisco.aci.aci_epg_to_contract:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    ap: "{{ bind_data.app }}"
    epg: "{{ bind_data.epg }}"
    contract: "{{ bind_data.contract }}"
    contract_type: "{{ bind_data.type }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
  loop: "{{ contract_bindings }}"
  loop_control:
    loop_var: bind_data
    label: "{{ bind_data.epg }} {{ bind_data.type }} {{ bind_data.contract }}"
```

## `roles/aci_l3out/tasks/main.yml`

```yaml
---
# Order: L3Out -> Node -> Interface -> External EPG
# Destroy deletes the L3Out only - APIC removes everything under it.
- name: L3Out + OSPF area
  include_tasks: l3out.yml
  tags: always

- name: Node profile + leaf node
  include_tasks: node.yml
  when: aci_state == 'present'
  tags: always

- name: Interface profile + path + OSPF interface
  include_tasks: interface.yml
  when: aci_state == 'present'
  tags: always

- name: External EPG + subnets + contracts
  include_tasks: ext_epg.yml
  when: aci_state == 'present'
  tags: always
```

## `roles/aci_l3out/tasks/l3out.yml`

```yaml
---
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- L3Out ----------
- name: DEBUG L3Out
  debug:
    msg: "L3Out: {{ l3out_data.l3out_name }} | VRF: {{ l3out_data.vrf }} | Domain: {{ l3_domain }}"
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: L3Out
  cisco.aci.aci_l3out:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    l3out: "{{ l3out_data.l3out_name }}"
    vrf: "{{ l3out_data.vrf }}"
    domain: "{{ l3_domain }}"
    state: "{{ aci_state }}"
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"

# ---------- OSPF area (ospfExtP) ----------
- name: DEBUG OSPF Area
  debug:
    msg: "L3Out: {{ l3out_data.l3out_name }} | OSPF area: {{ l3out_data.ospf_area }} (regular)"
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: OSPF Area
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ l3out_data.l3out_name }}.json"
    method: post
    content:
      ospfExtP:
        attributes:
          areaId: "{{ l3out_data.ospf_area }}"
          areaType: regular
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }} area {{ l3out_data.ospf_area }}"
  when: aci_state == 'present'
```

## `roles/aci_l3out/tasks/node.yml`

```yaml
---
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- Node Profile (l3extLNodeP) ----------
- name: DEBUG Node Profile
  debug:
    msg: "L3Out: {{ l3out_data.l3out_name }} | Node profile: {{ l3out_data.l3out_name }}-nodeProf"
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: Node Profile
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ l3out_data.l3out_name }}.json"
    method: post
    content:
      l3extLNodeP:
        attributes:
          name: "{{ l3out_data.l3out_name }}-nodeProf"
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}-nodeProf"

# ---------- Leaf Node + Router ID (l3extRsNodeL3OutAtt) ----------
- name: DEBUG Leaf Node
  debug:
    msg: "Node: topology/pod-1/node-{{ l3out_data.node_id }} | Router ID: {{ l3out_data.router_id }}"
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: Leaf Node
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ l3out_data.l3out_name }}/lnodep-{{ l3out_data.l3out_name }}-nodeProf.json"
    method: post
    content:
      l3extRsNodeL3OutAtt:
        attributes:
          tDn: "topology/pod-1/node-{{ l3out_data.node_id }}"
          rtrId: "{{ l3out_data.router_id }}"
          rtrIdLoopBack: "yes"
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }} node-{{ l3out_data.node_id }}"
```

## `roles/aci_l3out/tasks/interface.yml`

```yaml
---
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- Interface Profile (l3extLIfP) ----------
- name: DEBUG Interface Profile
  debug:
    msg: "L3Out: {{ l3out_data.l3out_name }} | Interface profile: {{ l3out_data.l3out_name }}-intProf"
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: Interface Profile
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ l3out_data.l3out_name }}/lnodep-{{ l3out_data.l3out_name }}-nodeProf.json"
    method: post
    content:
      l3extLIfP:
        attributes:
          name: "{{ l3out_data.l3out_name }}-intProf"
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}-intProf"

# ---------- Routed Interface: SVI or routed port (l3extRsPathL3OutAtt) ----------
- name: DEBUG Routed Interface
  debug:
    msg: >-
      Path: topology/pod-1/paths-{{ l3out_data.node_id }}/pathep-[{{ l3out_data.interface }}] |
      Type: {{ l3out_data.interface_type }} | IP: {{ l3out_data.interface_ip }} |
      Encap: {{ l3out_data.encap }}
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: Routed Interface
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ l3out_data.l3out_name }}/lnodep-{{ l3out_data.l3out_name }}-nodeProf/lifp-{{ l3out_data.l3out_name }}-intProf.json"
    method: post
    content:
      l3extRsPathL3OutAtt:
        attributes:
          tDn: "topology/pod-1/paths-{{ l3out_data.node_id }}/pathep-[{{ l3out_data.interface }}]"
          ifInstT: "{{ l3out_data.interface_type }}"
          addr: "{{ l3out_data.interface_ip }}"
          encap: "{{ l3out_data.encap }}"
          mode: regular
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }} {{ l3out_data.interface }}"

# ---------- OSPF Interface Profile (ospfIfP, default OSPF policy) ----------
- name: DEBUG OSPF Interface Profile
  debug:
    msg: "Interface profile: {{ l3out_data.l3out_name }}-intProf | OSPF auth: none"
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: OSPF Interface Profile
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ l3out_data.l3out_name }}/lnodep-{{ l3out_data.l3out_name }}-nodeProf/lifp-{{ l3out_data.l3out_name }}-intProf.json"
    method: post
    content:
      ospfIfP:
        attributes:
          authType: none
          authKeyId: "1"
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
```

## `roles/aci_l3out/tasks/ext_epg.yml`

```yaml
---
- name: Set APIC authentication facts
  set_fact:
    apic_auth: &apic_auth
      hostname: "{{ apic_hostname }}"
      username: "{{ apic_username }}"
      private_key: "{{ private_key if aci_use_cert | bool else omit }}"
      certificate_name: "{{ certificate_name if aci_use_cert | bool else omit }}"
      password: "{{ omit if aci_use_cert | bool else apic_password }}"
      validate_certs: "{{ validate_certs }}"
  tags: always

# ---------- External EPG ----------
- name: DEBUG External EPG
  debug:
    msg: "L3Out: {{ l3out_data.l3out_name }} | Ext EPG: {{ l3out_data.l3out_name }}-ExtEPG"
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}"
  tags: debug

- name: External EPG
  cisco.aci.aci_l3out_extepg:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    l3out: "{{ l3out_data.l3out_name }}"
    extepg: "{{ l3out_data.l3out_name }}-ExtEPG"
    state: present
  delegate_to: localhost
  loop: "{{ l3outs }}"
  loop_control:
    loop_var: l3out_data
    label: "{{ l3out_data.l3out_name }}-ExtEPG"

# ---------- External Subnets (subnet_data.0 = l3out, subnet_data.1 = prefix) ----------
- name: DEBUG External Subnets
  debug:
    msg: "Ext EPG: {{ subnet_data.0.l3out_name }}-ExtEPG | Subnet: {{ subnet_data.1 }} | Scope: import-security"
  with_subelements:
    - "{{ l3outs }}"
    - external_subnets
  loop_control:
    loop_var: subnet_data
    label: "{{ subnet_data.0.l3out_name }} / {{ subnet_data.1 }}"
  tags: debug

- name: External Subnets
  cisco.aci.aci_l3out_extsubnet:
    <<: *apic_auth
    tenant: "{{ tenant_name }}"
    l3out: "{{ subnet_data.0.l3out_name }}"
    extepg: "{{ subnet_data.0.l3out_name }}-ExtEPG"
    network: "{{ subnet_data.1 }}"
    scope: [import-security]
    state: present
  delegate_to: localhost
  with_subelements:
    - "{{ l3outs }}"
    - external_subnets
  loop_control:
    loop_var: subnet_data
    label: "{{ subnet_data.0.l3out_name }} / {{ subnet_data.1 }}"

# ---------- External EPG Contracts (ext_c.0 = l3out, ext_c.1 = contract) ----------
- name: DEBUG External EPG Contracts
  debug:
    msg: "{{ ext_c.0.l3out_name }}-ExtEPG --{{ ext_c.1.type }}--> {{ ext_c.1.contract }}"
  with_subelements:
    - "{{ l3outs }}"
    - contracts
  loop_control:
    loop_var: ext_c
    label: "{{ ext_c.0.l3out_name }} {{ ext_c.1.type }} {{ ext_c.1.contract }}"
  tags: debug

- name: External EPG Contracts - provider (fvRsProv)
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ ext_c.0.l3out_name }}/instP-{{ ext_c.0.l3out_name }}-ExtEPG.json"
    method: post
    content:
      fvRsProv:
        attributes:
          tnVzBrCPName: "{{ ext_c.1.contract }}"
  delegate_to: localhost
  with_subelements:
    - "{{ l3outs }}"
    - contracts
  loop_control:
    loop_var: ext_c
    label: "{{ ext_c.0.l3out_name }} provider {{ ext_c.1.contract }}"
  when: ext_c.1.type == 'provider'

- name: External EPG Contracts - consumer (fvRsCons)
  cisco.aci.aci_rest:
    <<: *apic_auth
    path: "/api/mo/uni/tn-{{ tenant_name }}/out-{{ ext_c.0.l3out_name }}/instP-{{ ext_c.0.l3out_name }}-ExtEPG.json"
    method: post
    content:
      fvRsCons:
        attributes:
          tnVzBrCPName: "{{ ext_c.1.contract }}"
  delegate_to: localhost
  with_subelements:
    - "{{ l3outs }}"
    - contracts
  loop_control:
    loop_var: ext_c
    label: "{{ ext_c.0.l3out_name }} consumer {{ ext_c.1.contract }}"
  when: ext_c.1.type == 'consumer'
```

