# Provider variables
variable "apic_username" {
  type        = string
  description = "APIC username"
}

variable "apic_password" {
  type        = string
  description = "APIC password"
  sensitive   = true
}

variable "apic_url" {
  type        = string
  description = "APIC URL"
}

# ACI object variables
variable "tenant_name" {
  type        = string
  description = "Tenant name"
}

variable "vrf_name" {
  type        = string
  description = "VRF name"
}

variable "bd_name" {
  type        = string
  description = "Bridge Domain name"
}

variable "app_profile_name" {
  type        = string
  description = "Application Profile name"
}

variable "epg_names" {
  type        = list(string)
  description = "List of EPG names"
}
