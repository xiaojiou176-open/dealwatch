# Security

Do not report security vulnerabilities in public issues or pull requests.

## Private Reporting

Use one of these private channels:

1. GitHub private vulnerability reporting for this repository
2. The private maintainer contact associated with the repository owner

## Sensitive Inputs

- `DATABASE_URL`
- `OWNER_BOOTSTRAP_TOKEN`
- `POSTMARK_SERVER_TOKEN`

Secret scanning is enforced in CI. Local scans remain recommended developer-side checks, not the
primary enforcement layer.
