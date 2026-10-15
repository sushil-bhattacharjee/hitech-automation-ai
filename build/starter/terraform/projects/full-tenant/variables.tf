# Provider
variable "apic_username" {
  type      = string
  sensitive = true
}

variable "apic_password" {
  type      = string
  sensitive = true
}

variable "apic_url" {
  type = string
}

# Tenant
variable "tenant_name" {
  type = string
}

# VRFs
variable "vrfs" {
  type = list(string)
}

# Bridge Domains
variable "bridge_domains" {
  type = list(object({
    name   = string
    vrf    = string
    subnet = string
  }))
}

# Applications with EPGs
variable "applications" {
  type = list(object({
    name = string
    epgs = list(object({
      name = string
      bd   = string
    }))
  }))
}

# Filters
variable "filters" {
  type = list(object({
    name       = string
    entry_name = string
    protocol   = string
    dest_port  = string
  }))
}

# Contracts
variable "contracts" {
  type = list(object({
    name    = string
    filters = list(string)
  }))
}

# Contract Bindings
variable "contract_bindings" {
  type = list(object({
    epg      = string
    contract = string
    type     = string
  }))
}

# L3Outs
variable "l3outs" {
  type = list(object({
    name             = string
    vrf              = string
    node_id          = string
    router_id        = string
    interface        = string
    interface_type   = string       # "ext-svi" or "l3-port"
    interface_ip     = string
    encap            = string       # "vlan-100" or "unknown" for routed port
    routing_protocol = string       # "ospf" or "bgp"
    ospf_area        = string
    external_subnets = list(string)
    contract         = string
  }))
  default = []
}
