tcp_filters = [
  { name = "HTTP", port = 80 },
  { name = "HTTPS", port = 443 },
  { name = "Custom_HTTP", port = 8080 },
  { name = "Custom_HTTPS", port = 8443 }
]

contracts = [
  { name = "Web", filters = ["HTTP", "HTTPS"] },
  { name = "Custom_Web", filters = ["Custom_HTTP", "Custom_HTTPS"] }
]

bridgedomains = [
  { vrf = "INTERNAL", name = "NET-10.10.10.0" },
  { vrf = "EXTERNAL", name = "NET-198.51.100.0" },
  { vrf = "EXTERNAL", name = "NET-203.0.113.0" }
]

apps = {
  "CORP" = [
    { name = "SHAREPOINT", bd = "NET-10.10.10.0" },
    { name = "EXCHANGE", bd = "NET-10.10.10.0" }
  ],
  "DMZ" = [
    { name = "WEBSITE", bd = "NET-198.51.100.0" },
    { name = "API", bd = "NET-203.0.113.0" }
  ]
}
