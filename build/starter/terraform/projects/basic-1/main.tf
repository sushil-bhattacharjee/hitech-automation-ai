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

# Tenant
resource "aci_tenant" "main" {
  name        = var.tenant_name
  description = "Created by Terraform"
}

# VRF
resource "aci_vrf" "main" {
  tenant_dn = aci_tenant.main.id
  name      = var.vrf_name
}

# Bridge Domain
resource "aci_bridge_domain" "main" {
  tenant_dn          = aci_tenant.main.id
  name               = var.bd_name
  relation_fv_rs_ctx = aci_vrf.main.id
}

# Application Profile
resource "aci_application_profile" "main" {
  tenant_dn = aci_tenant.main.id
  name      = var.app_profile_name
}

# EPGs
resource "aci_application_epg" "epgs" {
  for_each               = toset(var.epg_names)
  application_profile_dn = aci_application_profile.main.id
  name                   = each.value
  relation_fv_rs_bd      = aci_bridge_domain.main.id
}
