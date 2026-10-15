terraform {
  required_providers {
    aci = {
      source  = "CiscoDevNet/aci"
      version = "2.17.0"
    }
  }
}

provider "aci" {
  username = var.apic_username
  password = var.apic_password
  url      = "https://192.168.89.95"
  insecure = true
}

# === VARIABLES ===
# =============================================================================
# TODO-1: There is APIC secrets file named secrets.tfvars. Change the file name
# So that terraform take the secrets from that file automatically
# =============================================================================
variable "apic_username" {
  type      = string
  sensitive = true
}

variable "apic_password" {
  type      = string
  sensitive = true
}

variable "tcp_filters" {
  type = list(object({
    name = string
    port = number
  }))
}

variable "contracts" {
  type = list(object({
    name    = string
    filters = list(string)
  }))
}

variable "bridgedomains" {
  type = list(object({
    vrf  = string
    name = string
  }))
}

variable "apps" {
  type = map(list(object({
    name = string
    bd   = string
  })))
}



# =============================================================================
# TODO-2: TENANT AND VRFs
# Create tenant=e2-sim-Devnet-tenant
# Create three VRFs "Devnet-vrf", "INTERNAL" and "EXTERNAL" [using manual method]
# =============================================================================

resource "aci_tenant" "devnet_tenant" {
  name        = "p7_e2-sim-Devnet-tenant"
  description = "P7 ver Tenant Creation by Terraform e2-terraform"
}

resource "aci_vrf" "devnet_vrf" {
  parent_dn = aci_tenant.devnet_tenant.id
  name      = "Devnet-vrf"
}

resource "aci_vrf" "internal" {
  parent_dn =  aci_tenant.devnet_tenant.id
  name      = "INTERNAL"
}

resource "aci_vrf" "external" {
  parent_dn =  "uni/tn-p7_e2-sim-Devnet-tenant"
  name      = "external"
}
# =============================================================================
# TODO-3: BRIDGE DOMAINS
# =============================================================================
# Create a standalone bridgedomain name=Devnet-BD and relate it to "devnet_vrf", 
# that was created at the begining
resource "aci_bridge_domain" "devnet_vrf_bd" {
  parent_dn = aci_tenant.devnet_tenant.id
  name               = "Devnet-BD"
  relation_to_vrf = { 
    vrf_name = aci_vrf.devnet_vrf.name
  }
}
# Crate bridgedomain using variable "var.bridgedomains", and relate to vrf.internal/external
resource "aci_bridge_domain" "bridge_domains" {
  for_each           = {for entry in var.bridgedomains: entry.name=>entry}
  parent_dn          = aci_tenant.devnet_tenant.id
  name               = each.key
  relation_to_vrf = {
    vrf_name = each.value.vrf == "INTERNAL" ? aci_vrf.internal.name : aci_vrf.external.name
    }
}

# =============================================================================
# TODO-4: APPLICATION PROFILES
# Crate application-profile=Devnet-app
# =============================================================================

resource "aci_application_profile" "devnet_app" {
  parent_dn =  aci_tenant.devnet_tenant.id
  name      = "Devnet-app"
}

variable "apps_and_epgs" {
  default = [
    { prf_name = "App1", epgs = ["A", "B"] },
    { prf_name = "App2", epgs = ["C", "A"] }
  ]
}

# Create App Profiles from structured var.apps_epgs data using for_each
resource "aci_application_profile" "apps" {
  for_each  = {for entry in var.apps_and_epgs: entry.prf_name=>entry}
  parent_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}


# # =============================================================================
# # TODO-5: EPGs FROM LIST
# # Create 3-epgs from var.epgs and keep them under "aci_application_profile" "devnet_app"
# # =============================================================================
variable "epgs" {
  default = ["Associate", "Professional", "Expert"]
}
resource "aci_application_epg" "simple_epgs" {
  for_each               = toset(var.epgs)
  parent_dn              = aci_application_profile.devnet_app.id
  name                   = each.value
}


# # =============================================================================
# # TODO-6: EPGs FROM NESTED DATA (flatten)
# # Restructure the var.apps_and_epgs ==> local.epg_map with unique key
# # =============================================================================
# /*
# variable "apps_and_epgs" {
#   default = [
#     { prf_name = "App1", epgs = ["A", "B"] },
#     { prf_name = "App2", epgs = ["C", "A"] }
#   ]
# }
# */
locals {
  epg_map = flatten([
    for entry in var.apps_and_epgs: [
        for epg in entry.epgs: {
            key="${entry.prf_name}_${epg}"
            app_name=entry.prf_name 
            epg_name=epg 
        }
    ]
  ])
}
# Create application_epg using local.epg_map, and keep them under "aci_application_profile" "apps"
# Create the relation_to_bridge_domain with "aci_bridge_domain" "devnet_vrf_bd", which created under TODO-3
resource "aci_application_epg" "structured_epgs" {
  for_each               = {for entry in local.epg_map: entry.key=>entry}
  parent_dn              =  aci_application_profile.apps[each.value.app_name].id
  name                   = each.value.epg_name
  relation_to_bridge_domain = {
    bridge_domain_name = aci_bridge_domain.devnet_vrf_bd.name
  }      
}

# =============================================================================
# TODO-7: FILTERS AND FILTER ENTRIES
# Create aci_filter and aci_filter_entry based on tcp_filters
# Each filter_entry name would be TCP_port, where port=80,443 etc
# destination and source ports are same as var.tcp_filters
# =============================================================================

resource "aci_filter" "tcp_filters" {
  for_each  = {for entry in var.tcp_filters: entry.name=>entry}
  tenant_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}

resource "aci_filter_entry" "tcp_filter_entries" {
  for_each    = {for entry in var.tcp_filters: entry.name=>entry}
  filter_dn   = aci_filter.tcp_filters[each.key].id
  name        = "TCP_${each.value.port}"
  ether_t     = "ip"
  prot        = "tcp"
  d_from_port = each.value.port
  d_to_port   = each.value.port
}

# # =============================================================================
# # TODO-8: CONTRACTS AND SUBJECTS
# # Create aci_contract and aci_contract_subject based on variable "contracts"
# # relation_vz_rs_subj_filt_att with "aci_filter" "tcp_filters" for contract_subject
# # =============================================================================

resource "aci_contract" "contracts" {
  for_each  = {for entry in var.contracts: entry.name=>entry}
  tenant_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}

resource "aci_contract_subject" "contract_subjects" {
  for_each    = {for entry in var.contracts: entry.name=>entry}
  contract_dn = aci_contract.contracts[each.key].id
  name        = "permit"
  apply_both_directions = "no"
  consumer_to_provider {
    prio        = "unspecified"
    target_dscp = "unspecified"
    dynamic "relation_vz_rs_filt_att" {
    for_each = each.value.filters
    content {
        action = "permit"
        filter_dn = aci_filter.tcp_filters[relation_vz_rs_filt_att.value].id
        }
    }
  } 
    provider_to_consumer {
    prio        = "unspecified"
    target_dscp = "unspecified"
    
    dynamic "relation_vz_rs_filt_att" {
      for_each = each.value.filters
      content {
        action    = "permit"
        filter_dn = aci_filter.tcp_filters[relation_vz_rs_filt_att.value].id
      }
    }
  }
}

# ****OLD WAY STILL WORKS
# relation_vz_rs_subj_filt_att = [for filter in each.value.filters : aci_filter.tcp_filters[filter].id]

# # =============================================================================
# # TODO-9: CORP/DMZ APP PROFILES AND EPGs
# # =============================================================================
# Create application profile using variable var.apps
resource "aci_application_profile" "corp_dmz_apps" {
  for_each  = tomap(var.apps)
  parent_dn = aci_tenant.devnet_tenant.id
  name      = each.key
}
# Restructure the var.apps under local.corp_dmz_epgs with unique key; so that it creates list of objects
locals {
  corp_dmz_epgs = flatten([
    for key, value in var.apps: [
        for entry in value: {
            key="${key}_${entry.name}"
            app_name=key
            epg_name=entry.name
            bd_name=entry.bd
        }
    ]
  ])
}
# Create aci_aaplication_epg and fill the relation with bridgedomain in TODO-3;
# "aci_bridge_domain" "bridge_domains" 
resource "aci_application_epg" "corp_dmz_epgs" {
  for_each               = {for entry in local.corp_dmz_epgs: entry.key=>entry}
  parent_dn              = aci_application_profile.corp_dmz_apps[each.value.app_name].id
  name                   = each.value.epg_name
  relation_to_bridge_domain      = {
    bridge_domain_name = aci_bridge_domain.bridge_domains[each.value.bd_name].name
  }
}


# # =============================================================================
# # TODO-10: CONTRACT ALLOCATIONS
# # =============================================================================

# Allocate Web contract to structured_epgs["App1-A"] [TODO-6, application_epgs]as consumer
resource "aci_epg_to_contract" "web_contract_app1_a" {
  application_epg_dn = aci_application_epg.structured_epgs["App1_A"].id
  contract_dn        = aci_contract.contracts["Web"].id
  contract_type      = "consumer"
}

# Allocate Custom_Web contract to corp_dmz_epgs["DMZ-WEBSITE"] as consumer
resource "aci_epg_to_contract" "custom_web_website" {
  application_epg_dn = aci_application_epg.corp_dmz_epgs["DMZ_WEBSITE"].id
  contract_dn        = aci_contract.contracts["Custom_Web"].id
  contract_type      = "consumer"
}


# # =============================================================================
# # OUTPUTS
# # =============================================================================

output "tenant_id" {
  value = aci_tenant.devnet_tenant.id
}

output "vrf_ids" {
  value = {
    devnet   = aci_vrf.devnet_vrf.id
    internal = aci_vrf.internal.id
    external = aci_vrf.external.id
  }
}

output "application_profiles" {
  value = { for k, v in aci_application_profile.apps : k => v.id }
}

output "epg_map_debug" {
  description = "Shows the flattened EPG map structure"
  value       = local.epg_map
}

output "corp_dmz_epgs_debug" {
  description = "Shows the flattened CORP/DMZ EPG structure"
  value       = local.corp_dmz_epgs
}
