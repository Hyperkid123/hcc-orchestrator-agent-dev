# Clowder V2 Migration — Requirement Set (draft v3, for review)

Status: draft for human review, 2026-10-22 (rev 3). Rev 3 applies field rulings on
`authenticated`, the SDK gate, and bearer acceptance; rev 2 was the initial distillation.
The persona files are now the operative contract. This document is the requirement
catalog and rationale record for review.
Source persona set: `personas/clowder-v2-assessment`, `personas/clowder-v2/migration-common.md`,
`personas/clowder-v2-migration-kessel`, `personas/clowder-v2/provisioning.md`.

Conventions: **MUST** / **MUST NOT** are normative. `[NEW]` marks a requirement absent from the
current persona text. `[CHANGED]` marks one that contradicts or materially narrows it.

---

## 1. Entry gates

| ID | Requirement |
|---|---|
| G1 `[NEW]` | **Kessel SDK presence is the gate.** If the application does not already have the Kessel SDK available, make **no changes**, record the finding, and recommend a follow-up ticket to add the SDK. Do not act under this persona. SDK presence is judged by the dependency being present — not by credential wiring. |
| G2 `[NEW]` | If the application exclusively uses environment variables with no Clowder implementation, make **no changes**. Record the finding and stop. |
| G3 | Scope is RBAC, Kessel, Export service, Sources only. Other tenant dependencies are excluded unless Jira assigns separate work. |
| G4 | A dependency is eligible only when the effective client already obtains it through the Clowder endpoint API. Dead declarations, unused dependencies, and Clowder used only for Kafka/DB do not establish eligibility. |
| G5 | G1, G2, and G4 are hard prerequisites. Failing any of them means "no implementation required" under this persona — not a partial migration and not a packet. `[CHANGED]` — the current scope gate treats env/config-only discovery as merely *out of scope* while still allowing other dependencies to proceed. |
| G6 | Do not install, add, upgrade, or reconfigure the Kessel SDK as part of this work. SDK presence is a precondition, not an outcome. |

Note: G1 + G5 removed `clowder-v2-migration-no-kessel`; the assessment gate note replaces it. See D1.

---

## 2. Authentication

### 2.0 Credential semantics

| Credential | Function |
|---|---|
| `x-rh-identity` | End-user context. Does not authenticate the calling service. |
| Bearer | Authenticates the calling service for cross-cluster calls through the gateway. |
| PSK | Authenticates the calling service to an in-cluster private API. |

Service-to-service calls are either unauthenticated (identity only) or PSK-authenticated (identity optional). Migration adds bearer authentication for cross-cluster calls.

### 2.1 Bearer issuance

| ID | Requirement |
|---|---|
| A1 | **Reuse the Kessel SDK's `OAuth2ClientCredentials` to obtain the bearer token.** `[NEW]` |
| A2 | **Do not** hand-roll a token client, token cache, refresh loop, or credential provider. `[NEW]` — narrow the current ban on "inventing OAuth client credentials" to *hand-rolled* clients, since A1 mandates the SDK helper. |
| A3 | Use the SDK's established client construction and lifecycle patterns; do not restructure them. |
| A4 | SDK presence satisfies G1. If the client-credentials inputs the SDK needs are not wired for a workload, that is a packet gap to raise (clarification), not an entry-gate failure and not a reason to invent wiring. |

### 2.2 Attaching the token

| ID | Requirement |
|---|---|
| A5 | Keep `x-rh-identity` when present. It is end-user context, not service authentication; never replace it or treat it as a service credential. `[NEW]` |
| A6 | `authenticated: true` → send the bearer. If the call sends PSK, the bearer replaces PSK; do not send both. Any other existing credential → preserve unless the packet says otherwise. |
| A6b | The bearer is validated by the gateway. `sources-api-go` does not parse `Authorization`; a call that bypasses the gateway path requires confirmation (`Decision required`). |
| A7 | Never send two competing credentials *of the same scheme*. One bearer, not two. |
| A8 | Apply the token at the shared request boundary so every caller workload uses it, not at individual call sites. |
| A9 | Every independently deployed server, worker, and job that can execute the call MUST receive the credential wiring. A server-only change is incomplete. |

### 2.3 When authentication is mandatory

| ID | Requirement |
|---|---|
| A10 | When the resolved V2 endpoint has `authenticated: true`, **every existing call** to RBAC, Sources, Export service, or Kessel MUST carry the SDK-issued bearer. There is no case where such a call is left untouched, apart from 2.4. `[NEW]` |
| A11 | When the resolved V2 endpoint has `authenticated: false`, do **NOT** add a bearer. Preserve existing auth only, and record the occurrence in the packet. |
| A12 | `authenticated: true` is the expected norm for all current apps and use cases. `authenticated: false` is possible but not expected; if it appears, do not attach a bearer and record it. The flag is authoritative. |
| A13 | `authenticated` is a signal only: it is not credentials and does not name a scheme. The scheme is fixed by A1 regardless of flag value. |
| A14 | Do not attach a bearer to a call that does not exist yet. A10 governs existing calls; it does not authorize new call paths. |

All observed in-scope calls are HTTPS. Plaintext-HTTP in-cluster calls are not covered by
A10 as written — see Q2.

### 2.4 Skip criteria

| ID | Requirement |
|---|---|
| A15 | The only permitted exception to A10 is an enumerated skip criterion. Skips MUST be recorded in the packet and surfaced in PR *Human Verification Required*, with the criterion cited. |
| A16 | **Closed skip list**: (a) G1/G2 failed — no work at all; (b) `authenticated: false` (A11); (c) V2 endpoint absent and the packet specifies no fallback. No other skip exists. `[CHANGED]` |
| A17 | "Downstream does not validate a bearer" is **not** a skip criterion. `[CHANGED]` `sources-api-go` main performs no `Authorization`/JWT/JWKS parsing; the gateway validates the bearer. `x-rh-identity` remains end-user context, not service authentication. See 7.1. |

### 2.5 Preserved prohibitions

| ID | Requirement |
|---|---|
| A18 | Do not invent OAuth client credentials, bearer-token environment variables, PSK values, identity forwarding, or token-refresher sidecars. |
| A19 | Do not swap, remove, or reconfigure an existing authentication mechanism. |

---

## 3. Remote resources (`ClowdAppRef` and cross-cluster)

| ID | Requirement |
|---|---|
| R1 | V2 endpoints are `{uri, authenticated, ca_certificate}`. Use `uri` directly; never rebuild scheme, hostname, or port. |
| R2 | `ca_certificate` is a filesystem path, not PEM. Use system trust when absent. Never disable TLS verification. |
| R3 | `ClowdAppRef` provides **no custom CA path**. Remote certificates MUST be system-trusted. |
| R4 | `metadata.name` = consumer-declared dependency string (first V2 map key); `deployments[].name` = second key; `hostname` is host/IP only, no scheme or port. |
| R5 | Enable only the `public`/`private` webService actually consumed. TLS requires `webServices.<svc>.tls: true` **and** both `remoteEnvironment.tls.port` and `.privatePort`, even for public-only use. The CRD does not validate these relationships. |
| R6 | `serves` lists consumer `ClowdApp.metadata.name` values only. `serves` is **not** authorization, and its absence does not prevent Clowder from selecting the ref. |
| R7 | Gradual cutover per consumer: empty `serves` → add one consumer → inspect that consumer's generated `cdappconfig.json` → verify V2 URI, TLS, **authentication**, and live connectivity → continue. |
| R8 | After deleting a ref, force or await consumer reconciliation and recheck generated config. |
| R9 `[NEW]` | A remote consumer is subject to 2.1–2.4 in full. When its resolved endpoint reports `authenticated: true`, it needs the SDK-issued bearer even though the endpoint is cross-cluster and even though the ref itself carries no CA path. |

---

## 4. Packet weight

| ID | Requirement |
|---|---|
| P1 `[NEW]` | Do not build a migration packet for an application that fails G1 or G2. Emit a short gate note (repo, observed discovery mechanism, which gate failed, follow-up ticket reference for G1) and stop. |
| P2 | A full packet is required only when G1–G5 pass. It MUST contain verified or explicitly-assumed values for: persona, app/deployment keys, public/private, fallback, existing auth + credential wiring, TLS/CA, request boundaries, all caller workloads, effective SDK version and helper API, eligibility evidence, and internal basepath. |
| P3 | Any `Decision required` field blocks handoff. The implementer has no decision authority; silence in the packet is not permission to infer. |
| P4 | Fallback defaults to none. Add a V1/rollout fallback only with cited evidence a target cluster lacks V2. An absent V2 endpoint at runtime is a misconfiguration to surface. |
| P5 | Basepath changes apply only to Export service and Sources, only when the provider declares a private webService the consumer actually resolves to. Use the packet's exact basepath; never re-derive it. |
| P6 | Cheap local validation only: focused unit tests per behavior-matrix row, lint, syntax/import check, `assess.py --phase after`. Do not stand up DB/broker or run the full suite locally; CI is authoritative. |

---

## 5. Deltas vs current persona text

| # | Current text | Draft v3 | Effect |
|---|---|---|---|
| D1 | `no-kessel` persona migrated RBAC/Sources/Export discovery without any Kessel integration | G1: no SDK → no changes; persona deleted | Gate note in the assessment replaces it. No separate implementation path exists. |
| D2 | "Do not introduce, swap, or remove an authentication mechanism" (`common:57`) | A1 mandates Kessel SDK `OAuth2ClientCredentials` | Auth is no longer purely "preserve existing"; a specific mechanism is prescribed. |
| D3 | Warn-and-skip when downstream does not validate a bearer (`assessment:111`) | A17: non-validation is expected and never justifies a skip | `sources-api-go`-style cases get the bearer attached; the gateway validates it. |
| D4 | Env/config-only discovery is "out of scope," other deps may still migrate (`common:47-49`) | G2: no Clowder implementation → no changes at all | Whole-ticket stop instead of partial migration. |
| D5 | Discovery-only packet allowed when auth is scoped out (`common:117`) | A10 removes that exception when `authenticated: true` | Discovery-only now survives only via A11 (`authenticated: false`). |
| D6 | `no-kessel` persona required an "existing non-Kessel mechanism" | A1 requires the Kessel SDK mechanism | Resolved by deleting the persona. |

---

## 6. Decisions

### 6.1 Resolved

| # | Question | Ruling |
|---|---|---|
| Q1 | Does G1 stop the whole ticket? | Yes. No changes under this persona; recommend a follow-up ticket to add the SDK. |
| Q4 | What is the closed skip list? | G1/G2 failure; `authenticated: false`; endpoint absent with no fallback. See A16. |
| Q5 | Is discovery-only migration still allowed? | Only when `authenticated: false`. Since none has been observed, assume not. |
| Q7 | Is the SDK token accepted by RBAC, Sources, and Export as well as Kessel? | Yes — the bearer authenticates the service to the cluster. Recorded as operator field evidence, not independently code-verified per service. |
| Q8 | Is SDK presence alone enough, or are wired credentials required? | Presence alone satisfies G1. Missing credential wiring is a packet gap, not an entry-gate stop (A4). |
| Q9 | Export callers use `x-rh-exports-psk`; is bearer + PSK intended? | No. PSK is service authentication; the bearer replaces it for the cross-cluster gateway. `x-rh-identity` is user context and is retained. |
| Q11 | Is `authenticated: false` expected? | No. `true` is the norm for current apps and use cases; `false` is possible in principle but not expected. The flag stays authoritative (A11/A12). |

### 6.2 Still open

| # | Question | Why it matters |
|---|---|---|
| Q2 | A10 is silent on existing **plaintext HTTP** in-cluster calls to these services. Bearer or leave alone? | The original instruction keyed on HTTPS; the flag-based rule has no transport case. |
| Q3 | How is `authenticated` known before implementation — sampled `cdappconfig.json`, provider manifest, or live endpoint? | Determines whether A10 can be applied mechanically or becomes a packet fact to verify. |
| Q6 | Does "no Clowder implementation" (G2) include **manual `cdappconfig.json` parsing** and legacy `LoadedConfig.endpoints`, or only pure env vars? | Inventory shows both patterns (manual parse in malware-detection; legacy endpoints map in several repos). |
| Q10 | If the SDK is present but the workload has no client-credentials wired, does the packet block or proceed unauthenticated? | A4 says raise a gap; A10 says the bearer is mandatory. Needs a precedence answer. |

---

## 7. Verification log

### 7.1 `sources-api-go` bearer acceptance — checked 2026-10-22

Repo `github.com/RedHatInsights/sources-api-go`, default branch `main` at `59837a7`.

- `middleware/authorization.go` — `PermissionCheck` accepts, in order: `bypassRbac`, `x-rh-sources-psk`, `x-rh-identity` (including cert-based identity). The default branch returns 401 with `Authentication required by either [x-rh-identity] or [x-rh-sources-psk]`.
- `middleware/headers.go` — `ParseHeaders` reads PSK, account number, org ID, request IDs, and `x-rh-identity`. It never reads `Authorization`.
- No `Bearer`, JWT, JWKS, or OIDC handling exists on `main`.
- PR #962 "RHCLOUD-40797 Introduce OIDC authentication" was **closed unmerged** on 2026-02-25 (15 commits, 16 files). The last review comment reads "I moved this to internal routes only."
- `middleware/internal_auth.go` from that work is **not** on `main` and has no commit history on the default branch. Internal routes use the same `PermissionCheck`.
- Internal route groups on `main`: `/internal/{v1.0,v2.0}` and `/internal/sources/{v1.0,v2.0}` (`routes.go:161-182`).

**Conclusion:** the app does not parse the bearer, by design — the gateway validates it. `x-rh-identity` carries end-user context; PSK is the in-cluster service credential. A5/A17 are safe.

### 7.2 Basepath drift — checked 2026-10-22

`main` registers the standard internal path as `/internal/sources/v2.0` (with the `.0`), while
`references/ewgw-internal-api-basepath.md` gives the example `/internal/sources/v2` and lists
Sources as `/internal/v2.0`. Since P5 requires the packet's exact basepath, this is a reference
maintenance item: confirm whether the platform standard is `v2` or `v2.0` before using either form.

---

## 8. Source map

| Requirement area | Current source |
|---|---|
| Gates, scope, eligibility | `clowder-v2/migration-common.md:45-49`; `clowder-v2-assessment/prompt.md:63-68` |
| Packet authority, clarification | `clowder-v2/migration-common.md:3-26, 51-70` |
| Endpoint/TLS contract | `clowder-v2/migration-common.md:28-43`; assessment `:95-107` |
| Auth (current) | `migration-common.md:57, 113-118`; `clowder-v2-migration-kessel/prompt.md:20-26`; assessment `:106-123, 170-171` |
| Remote/ref | `clowder-v2/provisioning.md:5-71` |
| Instruments | `skills/clowder-v2-assess/scripts/assess.py:302-627` |
