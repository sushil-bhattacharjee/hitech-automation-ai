# Provider
apic_url = "https://192.168.89.95"

# Tenant
tenant_name = "Production"

# VRFs
vrfs = ["Internal", "External"]

# Bridge Domains (with gateway subnets)
bridge_domains = [
  { name = "BD-Web",      vrf = "External", subnet = "10.1.1.1/24" },
  { name = "BD-App",      vrf = "Internal", subnet = "10.2.1.1/24" },
  { name = "BD-Database", vrf = "Internal", subnet = "10.3.1.1/24" },
  { name = "BD-Mgmt",     vrf = "Internal", subnet = "10.100.1.1/24" }
]

# Applications with EPGs
applications = [
  {
    name = "3-Tier-App"
    epgs = [
      { name = "Web-EPG", bd = "BD-Web" },
      { name = "App-EPG", bd = "BD-App" },
      { name = "DB-EPG",  bd = "BD-Database" }
    ]
  },
  {
    name = "Monitoring"
    epgs = [
      { name = "Prometheus", bd = "BD-Mgmt" },
      { name = "Grafana",    bd = "BD-Mgmt" }
    ]
  }
]

# Filters
filters = [
  { name = "HTTP",    entry_name = "http-entry",    protocol = "tcp", dest_port = "80" },
  { name = "HTTPS",   entry_name = "https-entry",   protocol = "tcp", dest_port = "443" },
  { name = "MySQL",   entry_name = "mysql-entry",   protocol = "tcp", dest_port = "3306" },
  { name = "SSH",     entry_name = "ssh-entry",     protocol = "tcp", dest_port = "22" },
  { name = "ICMP",    entry_name = "icmp-entry",    protocol = "icmp", dest_port = "unspecified" },
  { name = "Any",     entry_name = "any-entry",     protocol = "unspecified", dest_port = "unspecified" }
]

# Contracts
contracts = [
  { name = "Web-to-App",    filters = ["HTTP", "HTTPS"] },
  { name = "App-to-DB",     filters = ["MySQL"] },
  { name = "Allow-SSH",     filters = ["SSH"] },
  { name = "Allow-ICMP",    filters = ["ICMP"] },
  { name = "Internet-In",   filters = ["HTTP", "HTTPS"] },
  { name = "Internet-Out",  filters = ["Any"] }
]

# Contract Bindings (epg key = "AppProfile-EPGName")
contract_bindings = [
  # Web-to-App
  { epg = "3-Tier-App-Web-EPG", contract = "Web-to-App", type = "consumer" },
  { epg = "3-Tier-App-App-EPG", contract = "Web-to-App", type = "provider" },

  # App-to-DB
  { epg = "3-Tier-App-App-EPG", contract = "App-to-DB", type = "consumer" },
  { epg = "3-Tier-App-DB-EPG",  contract = "App-to-DB", type = "provider" },

  # SSH to all servers
  { epg = "3-Tier-App-Web-EPG", contract = "Allow-SSH", type = "provider" },
  { epg = "3-Tier-App-App-EPG", contract = "Allow-SSH", type = "provider" },
  { epg = "3-Tier-App-DB-EPG",  contract = "Allow-SSH", type = "provider" },

  # Internet access for Web tier
  { epg = "3-Tier-App-Web-EPG", contract = "Internet-In",  type = "provider" },
  { epg = "3-Tier-App-Web-EPG", contract = "Internet-Out", type = "consumer" }
]

# L3Outs (realistic configuration)
l3outs = [
  {
    name             = "Internet-L3Out"
    vrf              = "External"
    node_id          = "101"
    router_id        = "1.1.1.1"
    interface        = "eth1/1"
    interface_type   = "ext-svi"        # SVI for VLAN trunk
    interface_ip     = "192.168.1.1/30"
    encap            = "vlan-100"
    routing_protocol = "ospf"
    ospf_area        = "0"
    external_subnets = ["0.0.0.0/0"]    # Default route
    contract         = "Internet-In"
  },
  {
    name             = "DC-Interconnect"
    vrf              = "Internal"
    node_id          = "102"
    router_id        = "2.2.2.2"
    interface        = "eth1/2"
    interface_type   = "l3-port"        # Routed port (no VLAN)
    interface_ip     = "172.16.0.1/30"
    encap            = "unknown"
    routing_protocol = "ospf"
    ospf_area        = "10"
    external_subnets = [
      "172.16.0.0/16",   # Remote DC networks
      "192.168.0.0/16"   # Branch offices
    ]
    contract         = ""
  }
]
