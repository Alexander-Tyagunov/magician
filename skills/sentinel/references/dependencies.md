# sentinel — dependency audit details

Detail for steps 2 and 2.5 of [`../SKILL.md`](../SKILL.md).

## Step 2: what each audit tool sends

These audit tools reach the network: `npm audit` sends the dependency list to the npm registry; `pip-audit` sends package names and versions to PyPI (or OSV, if you choose it); `safety check` downloads Safety's vulnerability database and, when you use a Safety API key, sends the package list to Safety's servers; `govulncheck` asks the Go vulnerability database at vuln.go.dev about the modules you use, and the go command downloads any module missing from its cache from your module proxy (proxy.golang.org by default); and `cargo audit` downloads the RustSec advisory database from GitHub and, to spot yanked versions, fetches the crates.io index entry of each crate in Cargo.lock. Skip any the user doesn't want run.

## Step 2.5: supply-chain check
Known-CVE audits miss supply-chain attacks — the vector behind recent registry compromises where installing a package was enough to steal SSH keys, cloud credentials, and other secrets. Check the install-time surface:
- **Install-time scripts** — flag lifecycle hooks that run arbitrary code on install:
  ```bash
  grep -rEn '"(preinstall|install|postinstall)"\s*:' package.json 2>/dev/null
  ```
  (Python equivalent: custom `setup.py`/`pyproject.toml` build hooks.)
- **Newly added / unfamiliar deps** — review new lockfile entries and dependencies that are typosquats of popular packages.
- **Exfiltration shape** — a dependency that reads credentials (`~/.ssh`, `~/.aws`, env vars, wallets) *and* reaches the network is high-risk; escalate as Critical.
- Prefer lockfile integrity in CI (`npm ci`, not `npm install`) and pinned versions.
