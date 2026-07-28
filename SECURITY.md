# Security Policy

## Supported versions

Archiscope is currently in beta. Security fixes are applied to the latest `0.5.x` release line.

| Version | Supported |
|---|---:|
| `0.5.x` | yes |
| `< 0.5` | no |

## Reporting a vulnerability

Please do not open a public Issue for suspected vulnerabilities.

Use GitHub’s private vulnerability reporting flow:

<https://github.com/BladeDancer743/archiscope/security/advisories/new>

Include:

- affected version and platform;
- a minimal reproduction;
- expected and observed impact;
- any suggested mitigation;
- whether disclosure timing is sensitive.

You should receive an acknowledgement within 72 hours. Status updates will be provided while the report is being evaluated and fixed.

## Scope

Security-relevant areas include:

- unsafe file writes performed by Agent adapter installation;
- malicious or unexpectedly large `.archmap.yaml` input;
- terminal escape or control-character injection;
- packaging or dependency-chain compromise;
- accidental disclosure of private project information in examples or logs.

Archiscope does not upload source code or architecture data. Rendering and validation run locally.
