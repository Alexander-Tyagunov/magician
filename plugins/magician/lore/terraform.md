Common AI mistakes: hardcoding credentials in .tf files; not using remote state; missing `lifecycle` rules to prevent accidental deletion; not pinning provider versions.
Commands: init: `terraform init`, plan: `terraform plan`, apply: `terraform apply`, fmt: `terraform fmt`.
Gotchas: always run `plan` before `apply`; use `terraform.tfvars` for environment-specific values; `data` sources read existing resources; `output` exposes values to other modules.
