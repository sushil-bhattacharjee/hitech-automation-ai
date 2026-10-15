output "tenant_dn" {
  value = aci_tenant.main.id
}

output "vrf_dns" {
  value = { for k, v in aci_vrf.vrfs : k => v.id }
}

output "bd_dns" {
  value = { for k, v in aci_bridge_domain.bds : k => v.id }
}

output "bd_subnets" {
  value = { for k, v in aci_subnet.bd_subnets : k => v.ip }
}

output "epg_dns" {
  value = { for k, v in aci_application_epg.epgs : k => v.id }
}

output "contract_dns" {
  value = { for k, v in aci_contract.contracts : k => v.id }
}

output "l3out_dns" {
  value = { for k, v in aci_l3_outside.l3outs : k => v.id }
}

output "external_epg_dns" {
  value = { for k, v in aci_external_network_instance_profile.ext_epgs : k => v.id }
}
