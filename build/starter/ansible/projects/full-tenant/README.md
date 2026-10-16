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
