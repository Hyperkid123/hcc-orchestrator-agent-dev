## ClowdAppRef Provisioning And Cutover

Read only for tickets that create, modify, cut over, or remove a `ClowdAppRef`.

### Resource contract

```yaml
apiVersion: cloud.redhat.com/v1alpha1
kind: ClowdAppRef
metadata:
  name: <dependency-app>
  namespace: <namespace>
spec:
  envName: <local-clowd-environment>
  remoteEnvironment:
    port: <remote-public-port>
    privatePort: <remote-private-port>
    tls:
      port: <remote-public-tls-port>
      privatePort: <remote-private-tls-port>
  deployments:
    - name: <deployment>
      hostname: <hostname-without-scheme-or-port>
      webServices:
        public:
          enabled: true
          tls: true
  serves:
    - <consumer-clowdapp-name>
```

Take names, environment, hostname, ports, TLS, and auth requirements from authoritative deployment configuration.

### Rules

- `metadata.name` = dependency string declared by consumers. First V2 map key.
- `deployments[].name` = second V2 map key.
- `deployments[].hostname` = hostname or IP only. No scheme, no `host:port`.
- Enable only the `public`/`private` `webServices` entry actually consumed. No deprecated `web: true`.
- `serves` = consumer `ClowdApp.metadata.name` values only. Not namespaces, deployment names, or dependency names.
- Avoid duplicate ref names in one environment, including across namespaces.
- TLS: set `webServices.<service>.tls: true` and both `remoteEnvironment.tls.port` and `.privatePort`. Clowder requires both even for public-only use.
- CRD validation does not enforce service/TLS/port relationships. A valid resource can still emit HTTP or no endpoint.
- H2C-only refs produce no V2 endpoints.
- Do not use `status.ready` or `spec.disabled` as cutover gates without verifying deployed Clowder behavior.

### Authentication

- `authenticated: true` → cross-cluster consumers send the bearer; replace PSK with it.
- `authenticated: false` → no bearer; keep current behavior.
- Keep `x-rh-identity` when present; it is end-user context, not service authentication.
- Remote consumers follow the same auth rules as local consumers in `personas/clowder-v2/migration-common.md`.
- `ClowdAppRef` provides no custom CA path. Remote certificates must be system-trusted.

### Gradual cutover

When a local `ClowdApp` and remote `ClowdAppRef` share a dependency name:

1. Create the ref with `serves` omitted or empty. Consumers remain local.
2. Add one consumer app name to `serves`.
3. Inspect that consumer's generated `cdappconfig.json`.
4. Verify V2 URI, TLS, authentication, and live connectivity.
5. If V1 fallback remains, verify its flat endpoint also switched coherently.
6. Continue consumer by consumer.

If only the ref exists, Clowder selects it regardless of `serves`. `serves` is not authorization.

### Verification

```bash
kubectl apply --server-side --dry-run=server -f <manifest>
kubectl get clowdappref <name> -n <namespace> -o yaml
kubectl get secret <consumer> -n <namespace> \
  -o jsonpath='{.data.cdappconfig\.json}' \
  | base64 -d \
  | jq '.dependencyEndpoints.v2["<dependency-app>"]["<deployment>"]'
```

After deleting a ref, trigger or await consumer reconciliation and recheck generated configuration. Deletion may not immediately enqueue affected consumers.
