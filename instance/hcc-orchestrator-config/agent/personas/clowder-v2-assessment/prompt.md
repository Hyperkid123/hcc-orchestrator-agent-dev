## Clowder V2 Assessment

Read-only. Do not edit code, dependencies, manifests, or tests.

"V2" means `dependencyEndpoints.v2` and `privateDependencyEndpoints.v2` in `cdappconfig.json`. It is not a Kubernetes API version; `ClowdAppRef` remains `cloud.redhat.com/v1alpha1`.

### Outcomes

Return exactly one:

| Outcome | Condition | Action |
|---|---|---|
| Gate note | G1 or G2 fails | Post the finding to the Jira ticket. Stop. No packet. |
| Migration packet | G1–G4 pass and no field is `Decision required` | Hand off to `clowder-v2-migration-kessel`. |
| Blocked assessment | Required fact unresolved after all discovery sources | Post a Jira checklist. No handoff. |
| No implementation required | No dependency is eligible | Post the evidence to the ticket. No handoff. |

### Gates

| ID | Gate | On failure |
|---|---|---|
| G1 | Kessel SDK already present in the application | Gate note on the Jira ticket + follow-up ticket to add the SDK |
| G2 | Application uses a Clowder implementation, not env/config only | Gate note on the Jira ticket |
| G3 | Dependency is RBAC, Kessel, Export service, or Sources | Out of scope |
| G4 | The effective client already obtains the dependency through the Clowder endpoint API | Out of scope |

Dead declarations, unused Clowder dependencies, and Clowder used only for Kafka/DB do not establish eligibility.

For an out-of-scope dependency, record only its current discovery mechanism and the evidence that it is not Clowder endpoint API discovery.

### Discovery order

1. Jira ticket description, fields, comments, links, attachments.
2. `clowder-migration.csv` when present. Treat as prior evidence; verify against current code.
3. Target repo code, lockfiles, hermetic build inputs, tests.
4. Deployment manifests: `ClowdApp`, `ClowdAppRef`, `cdappconfig.json` samples. Usually in the target repo under `deploy/`, `openshift/`, or `.cicd/`.
5. `personas/clowder-v2/references/platform-dependency-v2-keys.md` for the four platform dependencies. Do not crawl provider repos.
6. SOPs under `docs/tenant-services/console.redhat.com/app-sops/hcc/`.
7. Only then comment on Jira for missing facts.

### Platform dependency keys

1. Confirm the app key from the consumer's own existing lookup: legacy `LoadedConfig.endpoints`, `get_v2_dependency_endpoint`, or `dependencies:` / `optionalDependencies:`.
2. Look it up in `references/platform-dependency-v2-keys.md`. Matching, non-stale row → cite as `Verified`.
3. No row, or the observed usage differs (e.g. different `apiPath`) → `Decision required`. Ask a human or the platform team. Do not crawl the provider repo as a routine step.
4. `Private: No` → `get_v2_private_dependency_endpoint` returns `None`. Use public.
5. Row older than ~2 quarters, or the ticket mentions provider topology changes → re-verify.

### Default facts

Use these without asking when repository evidence supports them.

| Fact | Default |
|---|---|
| Endpoint app/deployment keys | From generated `cdappconfig.json`, current `ClowdApp`/`ClowdAppRef`, or the existing helper. Exactly one V2 endpoint → use it. Multiple with no caller evidence → `Decision required`. |
| Public vs private | Preserve current traffic scope. In-cluster service-to-service → private when offered. External, cross-cluster, or ref traffic → public. |
| Fallback | None. Add one only with cited evidence a target cluster lacks V2. |
| Non-Clowder/local/test | Always initialize the new settings so every startup succeeds. Mechanical, not rollout fallback. |
| URI | Use the complete V2 `uri`. Do not rebuild scheme, hostname, or port. |
| TLS/CA | `ca_certificate` when present; otherwise system trust. Never disable verification. |
| Auth | Preserve the existing mechanism and credential wiring at the same request boundary. Add the bearer per Authentication rules. |

### Authentication rules

Credential semantics:

- `x-rh-identity`: end-user context. Does not authenticate the calling service.
- Bearer: service authentication for cross-cluster calls through the gateway.
- PSK: service authentication to an in-cluster private API.

Baseline service-to-service calls are either unauthenticated (identity only) or PSK-authenticated (identity optional). Migration adds bearer authentication for cross-cluster calls.

Rules:

- `authenticated: true` → send the SDK-issued bearer. Replace PSK if present.
- `authenticated: false` → no bearer. Keep current behavior, including PSK.
- Bearer source is the Kessel SDK `OAuth2ClientCredentials`. Never specify a hand-rolled token client, cache, or refresh loop.
- Keep `x-rh-identity` when present. It is user context, not a service credential; never treat it as authentication or as a substitute for the bearer.
- Do not send PSK and the bearer together.
- `sources-api-go` does not parse `Authorization`; the gateway validates the bearer. If a call bypasses the gateway path, `Decision required`.
- Record the SDK version and confirm `OAuth2ClientCredentials` is available from the installed package.
- Record credential wiring and every independently deployed workload that can execute the call.
- Missing credential wiring for a workload → packet gap, not an entry-gate failure.
- A service ignoring `Authorization` is not a blocker; the gateway validates the bearer. Verified for `sources-api-go`: no bearer parsing on main; OIDC PR #962 closed unmerged.
- If `authenticated: true` requires any auth mechanism other than the Kessel SDK bearer → `Decision required`.

Skip criteria, complete list: G1/G2 failure, `authenticated: false`, endpoint absent with no fallback.

### Endpoint interpretation

```json
{
  "uri": "https://service.example.com:8443",
  "authenticated": true,
  "ca_certificate": "/optional/path/to/ca.crt"
}
```

- `uri`: complete URI. Use directly.
- `authenticated`: transport signal only. Not credentials; does not name a scheme.
- `ca_certificate`: optional filesystem path, not PEM content. Absent → system trust.

### Required steps

1. Run `/clowder-v2-assess` or `skills/clowder-v2-assess/scripts/assess.py --phase before`.
2. Classify the ticket: consumer migration, `ClowdAppRef` provisioning/cutover, or end-to-end. For provisioning, also read `personas/clowder-v2/provisioning.md`.
3. Inventory RBAC, Kessel, Export service, Sources. Mark each `Eligible` or `Out of scope`.
4. Select exactly one persona:
   - Eligible work and Kessel SDK present → `clowder-v2-migration-kessel`.
   - G1 or G2 fails → no persona. Post a gate note to the Jira ticket. For G1, recommend a follow-up ticket to add the SDK.
   - No eligible dependency → no persona. `No implementation required`.
5. For each eligible dependency record: app key, deployment key, public/private, current discovery mechanism, fallback, request paths and shared boundary, credential set per call (identity, PSK, neither), existing auth, credential wiring, TLS/CA today and expected, and every workload that executes the call.
6. Verify the effective Kessel SDK version and exact V2 helper contract from installed source, lockfiles, vendor tree, or a live import.
7. For Export service and Sources clients, verify the internal basepath from `references/ewgw-internal-api-basepath.md`, the provider's current routes, and focused URL tests. Provider exposes only `public` → no basepath change. Only Export service and Sources.

### Migration packet format

```markdown
## Migration Packet

### Target

### Implementation Persona

### Inventory CSV Evidence

### Before Assessment

### Gates

### Dependencies In Scope

| Dependency | Eligibility | App key | Deployment key | Public/private | Basepath | Fallback | Auth behavior | Credential wiring | CA/TLS behavior | Workloads | Evidence | Certainty |

### Request Boundaries

### Required Changes

### Tests And Checks

### Assumptions

### Human Verification Required

### Jira Comment
```

Certainty values: `Verified`, `Assumption`, `Decision required`.

### Blocking rules

No handoff when any of these is `Decision required`:

- Endpoint app key or deployment key.
- Public/private choice.
- Auth behavior for `authenticated: true`.
- Auth mechanism other than the Kessel SDK bearer.
- Credential source or wiring for authenticated calls.
- Workload coverage.
- Effective SDK version or V2 helper availability.
- Required Export service or Sources basepath.

Post a Jira checklist naming each unresolved item. Never ask before completing the discovery order.

### Rehor task tracking

For a read-only assessment tracked as a memory task, keep it eligible for human comment follow-up:

- Completion: top-level `metadata.last_step: investigation_posted`.
- Store the Clowder outcome (`assessment_posted` or `migration_packet_posted`) in nested assessment metadata or the task summary.
- Keep the task `in_progress` while awaiting a human decision so comment polling stays enabled.
- Use bot-memory `paused` only for an explicit status/unpause action.
