## Clowder V2 Migration

Use only after `clowder-v2-assessment` emits a migration packet that selects `clowder-v2-migration-kessel`. Read `personas/clowder-v2/migration-common.md` in full before editing.

### Gate

Before any edit, confirm from the repository:

- The Kessel SDK is present as an installed dependency.
- The packet names its effective version, imported API, credential wiring, request boundary, and every caller workload.
- The application already obtains the in-scope dependency through the Clowder endpoint API.

If the SDK is absent: make no changes. Post a gate note to the Jira ticket and recommend a follow-up ticket to add the SDK.

If the packet selects this persona but the repository lacks the verified integration, or the installed API or credential wiring differs from the packet: raise a Clarification Request and stop the affected item.

### Hard limits

- Do not install, add, upgrade, replace, or reconfigure the Kessel SDK.
- Do not create a new Kessel integration.
- Do not infer a replacement API from the packet or from another language's contract.
- Do not expand Kessel usage to new request paths or workloads.
- Do not replace env/config discovery with Clowder.

### Authentication

- Obtain the bearer with the SDK's `OAuth2ClientCredentials`. Do not hand-roll token acquisition, refresh, or caching.
- `authenticated: true` → send the bearer; replace PSK if present.
- `authenticated: false` → no bearer; keep current behavior, including PSK.
- Keep `x-rh-identity` when present. It is end-user context, not service authentication.
- Do not send PSK and the bearer together.
- Wire every independently deployed workload that can execute the call.

All endpoint, TLS, fallback, basepath, implementation, validation, PR, and completion rules come from `personas/clowder-v2/migration-common.md`.
