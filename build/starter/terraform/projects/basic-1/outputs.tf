output "tenant_dn" {
  value = aci_tenant.main.id
}

output "vrf_dn" {
  value = aci_vrf.main.id
}

output "bd_dn" {
  value = aci_bridge_domain.main.id
}

output "app_profile_dn" {
  value = aci_application_profile.main.id
}

output "epg_dns" {
  value = { for k, v in aci_application_epg.epgs : k => v.id }
}
