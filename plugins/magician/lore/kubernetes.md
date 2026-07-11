Common AI mistakes: not setting resource requests/limits; missing liveness/readiness probes; storing secrets in ConfigMaps; not using namespaces.
Commands: apply: `kubectl apply -f .`, get: `kubectl get pods`, logs: `kubectl logs <pod>`.
Gotchas: Deployments manage ReplicaSets — never edit ReplicaSets directly; use `kubectl rollout status` to verify deployments; `kubectl exec -it` for debugging.
