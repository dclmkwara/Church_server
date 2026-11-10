# Remote Database Access Diagnosis

**Date:** 10 November 2026  
**Target:** development Supabase database, read-only diagnostics

## Findings

- The configured session pooler is `aws-1-eu-central-1.pooler.supabase.com:5432`. It resolves to three IPv4 addresses using the Windows system resolver, Cloudflare DNS (`1.1.1.1`), and Google DNS (`8.8.8.8`). TCP connections to all three resolved addresses succeeded. `pg_isready` reported that the pooler accepts PostgreSQL connections.
- The direct database host, derived from the configured project reference, resolves to one IPv6 address only. This machine returned no IPv4 address for it. The machine has no usable IPv6 route to that endpoint, so direct-host access is not viable here.
- PostgreSQL dump traffic through the IPv4 session pooler succeeded after a slow handshake; the fresh archive was created and fully verified. The initial dump attempt stalled and left a zero-byte file, which was discarded. The successful retry used the same configured session-pooler host and migration credentials.
- The brief earlier pooler resolution failures are consistent with intermittent local DNS/network availability. They were not reproducible during the successful retry. The use of multiple public resolvers produced the same A records, so this was not a stale resolver cache.

## Practical connection guidance

Use the Supabase Dashboard's **Connect** dialog and select the **Session pooler** connection method for migrations and backups from this machine. Keep the region and project reference from that dialog; use the session pooler host and port `5432`. The direct host may be used only from an IPv6-capable network. Do not substitute the transaction pooler for migrations.

No DNS settings or database configuration were changed.
