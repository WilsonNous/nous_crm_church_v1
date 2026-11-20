# Enzonic deployment gate — NOUS CRM Church

## Verified
- Enzonic `main` contains 25 tables (reported from live SQL Editor by operator).
- `crm_automation_settings.boas_vindas` has `enabled=0` (reported by operator).
- GitHub branch includes verified-TLS option and mocked unit tests.

## Still required before production
1. Run `migrations/20261120_enzonic_verify_readonly.sql` and check missing-columns query returns zero rows; investigate any mismatch. Confirm the expected spaces exist; a blank `spaces` table means scheduling cannot accept requests.
2. Run `python -m unittest tests.test_enzonic_tls` and existing relevant tests in a clean Python environment. Do not run destructive MySQL integration tests against Enzonic; `tests/test_agendamento_mysql.py` drops tables.
3. Rotate Enzonic database password (previous credential was exposed in chat). Never store it in GitHub or test logs.
4. Set Render environment variables: `MYSQL_HOST=nouscrmchurch-m8z8p0.db.enzonic.com`, `MYSQL_PORT=3306`, `MYSQL_DB=main`, `MYSQL_USER=u_jzv9cxehdu`, `MYSQL_PASSWORD=<rotated secret>`, `MYSQL_SSL_REQUIRED=1`. If provider uses a private CA, set `MYSQL_SSL_CA` to the certificate file path; do not disable verification.
5. Deploy only after merge and after database verification. Do not start the background queue/WhatsApp workers until smoke tests pass. The welcome automation defaults to disabled, but this does not disable every other queue worker.
6. Smoke test: login; public visitor registration; visitor list; member list; agenda list and one controlled booking; IA read endpoints; conversation display; queue dashboard. Ensure no automatic WhatsApp sends.
7. Preserve old HostGator variables securely for later data recovery. Empty Enzonic database has no historical data.

## Rollback
Restore previous Render environment variables and prior deployment if new service fails; old HostGator remains blocked, so rollback is not a guarantee of service restoration.

## Limitations
Static inspection and mock tests do not prove full application compatibility. No direct Render access or Enzonic query execution was available to the assistant. No production credentials changed.
