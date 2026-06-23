# Security Policy

## Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**DO NOT create public GitHub issues for security vulnerabilities.**

### How to Report

Email security reports to: **sergio.canales.e@gmail.com**

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

### Response Timeline

- **Acknowledgement**: Within 48 hours
- **Initial assessment**: Within 7 days
- **Fix development**: Within 14-30 days (depending on severity)
- **Coordinated disclosure**: After fix is released

### Security Features

WOS is designed with security as a core principle:

- **Local-first execution**: Your data and code never leave your premises
- **No telemetry by default**: No data sent to external servers
- **Auditable decisions**: Full moral trace via OCE (Operational Conscience Engine)
- **Quality gates**: Security validation at every checkpoint
- **Sandboxed agents**: Command whitelist prevents malicious operations
- **Open source**: All code is inspectable (Apache 2.0)

### Vulnerability Disclosure Timeline

1. **Day 0**: Report received, acknowledgement sent
2. **Day 1-7**: Investigation and severity assessment
3. **Day 7-30**: Fix development and testing
4. **Day 30+**: Coordinated public disclosure after fix is released

### Security Best Practices

When using WOS:

1. **Review agent commands**: Inspect `.workspace-os/` logs regularly
2. **Use command whitelist**: Configure allowed commands in `.workspace-os.json`
3. **Keep updated**: Apply security patches promptly
4. **Audit trail**: Enable logging for compliance requirements
5. **Secure API keys**: Never commit API keys to git

## Security Hall of Fame

We recognize security researchers who responsibly disclose vulnerabilities:

*(No vulnerabilities reported yet)*

---

**Last updated**: 2026-06-23  
**Contact**: sergio.canales.e@gmail.com
