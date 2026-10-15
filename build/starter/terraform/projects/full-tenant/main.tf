terraform {
  required_providers {
    aci = {
      source  = "CiscoDevNet/aci"
      version = ">=2.0.0"
    }
  }
}

provider "aci" {
  username = var.apic_username
  password = var.apic_password
  url      = var.apic_url
  insecure = true
}

#=============================================================================
# TENANT
#=============================================================================
resource "aci_tenant" "main" {
  name        = var.tenant_name
  description = "Full tenant config by Terraform"
}

#=============================================================================
# VRFs
#=============================================================================
resource "aci_vrf" "vrfs" {
  for_each  = toset(var.vrfs)
  tenant_dn = aci_tenant.main.id
  name      = each.value
}

#=============================================================================
# BRIDGE DOMAINS (with subnets)
#=============================================================================
resource "aci_bridge_domain" "bds" {
  for_each           = { for bd in var.bridge_domains : bd.name => bd }
  tenant_dn          = aci_tenant.main.id
  name               = each.value.name
  relation_fv_rs_ctx = aci_vrf.vrfs[each.value.vrf].id
}

resource "aci_subnet" "bd_subnets" {
  for_each  = { for bd in var.bridge_domains : bd.name => bd if bd.subnet != "" }
  parent_dn = aci_bridge_domain.bds[each.key].id
  ip        = each.value.subnet
  scope     = ["public"]
}

#=============================================================================
# APPLICATION PROFILES & EPGs
#=============================================================================
resource "aci_application_profile" "apps" {
  for_each  = { for app in var.applications : app.name => app }
  tenant_dn = aci_tenant.main.id
  name      = each.value.name
}

locals {
  epgs_flat = flatten([
    for app in var.applications : [
      for epg in app.epgs : {
        app_name = app.name
        epg_name = epg.name
        bd_name  = epg.bd
        key      = "${app.name}-${epg.name}"
      }
    ]
  ])
}

resource "aci_application_epg" "epgs" {
  for_each               = { for epg in local.epgs_flat : epg.key => epg }
  application_profile_dn = aci_application_profile.apps[each.value.app_name].id
  name                   = each.value.epg_name
  relation_fv_rs_bd      = aci_bridge_domain.bds[each.value.bd_name].id
}

#=============================================================================
# FILTERS & FILTER ENTRIES
#=============================================================================
resource "aci_filter" "filters" {
  for_each  = { for f in var.filters : f.name => f }
  tenant_dn = aci_tenant.main.id
  name      = each.value.name
}

resource "aci_filter_entry" "entries" {
  for_each    = { for f in var.filters : f.name => f }
  filter_dn   = aci_filter.filters[each.key].id
  name        = each.value.entry_name
  ether_t     = "ipv4"
  prot        = each.value.protocol
  d_from_port = each.value.dest_port
  d_to_port   = each.value.dest_port
}

#=============================================================================
# CONTRACTS & SUBJECTS
#=============================================================================
resource "aci_contract" "contracts" {
  for_each  = { for c in var.contracts : c.name => c }
  tenant_dn = aci_tenant.main.id
  name      = each.value.name
}

resource "aci_contract_subject" "subjects" {
  for_each    = { for c in var.contracts : c.name => c }
  contract_dn = aci_contract.contracts[each.key].id
  name        = "${each.value.name}-subject"
  relation_vz_rs_subj_filt_att = [
    for f in each.value.filters : aci_filter.filters[f].id
  ]
}

#=============================================================================
# CONTRACT ASSIGNMENTS (Provider/Consumer)
#=============================================================================
resource "aci_epg_to_contract" "providers" {
  for_each           = { for c in var.contract_bindings : "${c.epg}-prov-${c.contract}" => c if c.type == "provider" }
  application_epg_dn = aci_application_epg.epgs[each.value.epg].id
  contract_dn        = aci_contract.contracts[each.value.contract].id
  contract_type      = "provider"
}

resource "aci_epg_to_contract" "consumers" {
  for_each           = { for c in var.contract_bindings : "${c.epg}-cons-${c.contract}" => c if c.type == "consumer" }
  application_epg_dn = aci_application_epg.epgs[each.value.epg].id
  contract_dn        = aci_contract.contracts[each.value.contract].id
  contract_type      = "consumer"
}

#=============================================================================
# L3OUT - OSPF to External Router
#=============================================================================
resource "aci_l3_outside" "l3outs" {
  for_each      = { for l3 in var.l3outs : l3.name => l3 }
  tenant_dn     = aci_tenant.main.id
  name          = each.value.name
  relation_l3ext_rs_ectx = aci_vrf.vrfs[each.value.vrf].id
}

# L3Out Node Profile
resource "aci_logical_node_profile" "node_profiles" {
  for_each   = { for l3 in var.l3outs : l3.name => l3 }
  l3_outside_dn = aci_l3_outside.l3outs[each.key].id
  name          = "${each.value.name}-nodeProf"
}

# L3Out Node (Leaf switch)
resource "aci_logical_node_to_fabric_node" "nodes" {
  for_each                = { for l3 in var.l3outs : l3.name => l3 }
  logical_node_profile_dn = aci_logical_node_profile.node_profiles[each.key].id
  tdn                     = "topology/pod-1/node-${each.value.node_id}"
  rtr_id                  = each.value.router_id
}

# L3Out Interface Profile
resource "aci_logical_interface_profile" "int_profiles" {
  for_each                = { for l3 in var.l3outs : l3.name => l3 }
  logical_node_profile_dn = aci_logical_node_profile.node_profiles[each.key].id
  name                    = "${each.value.name}-intProf"
}

# L3Out Routed Interface (SVI or Routed Port)
resource "aci_l3out_path_attachment" "paths" {
  for_each                  = { for l3 in var.l3outs : l3.name => l3 }
  logical_interface_profile_dn = aci_logical_interface_profile.int_profiles[each.key].id
  target_dn                 = "topology/pod-1/paths-${each.value.node_id}/pathep-[${each.value.interface}]"
  if_inst_t                 = each.value.interface_type  # "ext-svi" or "l3-port"
  addr                      = each.value.interface_ip
  encap                     = each.value.encap
}

# OSPF Interface Policy (if using OSPF)
resource "aci_l3out_ospf_interface_profile" "ospf" {
  for_each                     = { for l3 in var.l3outs : l3.name => l3 if l3.routing_protocol == "ospf" }
  logical_interface_profile_dn = aci_logical_interface_profile.int_profiles[each.key].id
  auth_key                     = ""
  auth_key_id                  = "1"
  auth_type                    = "none"
}

# OSPF External Policy
resource "aci_l3out_ospf_external_policy" "ospf_ext" {
  for_each   = { for l3 in var.l3outs : l3.name => l3 if l3.routing_protocol == "ospf" }
  l3_outside_dn = aci_l3_outside.l3outs[each.key].id
  area_id       = each.value.ospf_area
  area_type     = "regular"
}

# External EPG (defines external networks)
resource "aci_external_network_instance_profile" "ext_epgs" {
  for_each      = { for l3 in var.l3outs : l3.name => l3 }
  l3_outside_dn = aci_l3_outside.l3outs[each.key].id
  name          = "${each.value.name}-ExtEPG"
}

# External Subnets (what external networks to route)
locals {
  ext_subnets = flatten([
    for l3 in var.l3outs : [
      for subnet in l3.external_subnets : {
        l3out_name = l3.name
        subnet     = subnet
        key        = "${l3.name}-${replace(subnet, "/", "-")}"
      }
    ]
  ])
}

resource "aci_l3_ext_subnet" "ext_subnets" {
  for_each                         = { for s in local.ext_subnets : s.key => s }
  external_network_instance_profile_dn = aci_external_network_instance_profile.ext_epgs[each.value.l3out_name].id
  ip                               = each.value.subnet
  scope                            = ["import-security", "export-rtctrl"]
}

# Contract on External EPG (Provider)
resource "aci_rest_managed" "ext_epg_contract" {
  for_each   = { for l3 in var.l3outs : l3.name => l3 if l3.contract != "" }
  dn         = "${aci_external_network_instance_profile.ext_epgs[each.key].id}/rsprov-${each.value.contract}"
  class_name = "fvRsProv"
  content = {
    tnVzBrCPName = each.value.contract
  }
  depends_on = [aci_contract.contracts]
}
