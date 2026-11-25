#!/usr/bin/env bash
set -euo pipefail

image=${1:?image required}
output=${2:?output directory required}
mkdir -p "$output"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
artifact=trivy_0.76.2_Linux-64bit.tar.gz
curl -fsSLo "$scratch/$artifact" --retry 3 --connect-timeout 20 \
    "https://github.com/aquasecurity/trivy/releases/download/v0.76.2/$artifact"
printf 'bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf  %s\n' \
    "$scratch/$artifact" | sha256sum --check
tar -xzf "$scratch/$artifact" -C "$scratch" trivy
# Ubuntu runners supply Docker. Use only the already-built local image as the scan target.
"$scratch/trivy" image --image-src docker --cache-dir "$scratch/cache" --timeout 8m \
    --scanners vuln --format json --output "$output/vulnerabilities.json" "$image"
"$scratch/trivy" image --image-src docker --cache-dir "$scratch/cache" --timeout 8m \
    --format cyclonedx --output "$output/sbom.cdx.json" "$image"
"$scratch/trivy" image --image-src docker --cache-dir "$scratch/cache" --timeout 8m \
    --scanners secret --format json --output "$scratch/secret-report.json" "$image"
python - "$output" "$scratch/secret-report.json" <<'PY'
import collections
import json
import sys
from pathlib import Path

output = Path(sys.argv[1])
report = json.loads((output / "vulnerabilities.json").read_text())
total = collections.Counter()
affected = collections.Counter()
high_packages = collections.Counter()
for result in report.get("Results") or []:
    for item in result.get("Vulnerabilities") or []:
        severity = item["Severity"]
        total[severity] += 1
        affected[result["Type"]] += 1
        if severity in {"HIGH", "CRITICAL"}:
            high_packages[(result["Type"], item["PkgName"], severity)] += 1
secret_report = json.loads(Path(sys.argv[2]).read_text())
secret_matches = sum(len(row.get("Secrets") or []) for row in secret_report.get("Results") or [])
sbom = json.loads((output / "sbom.cdx.json").read_text())
summary = {
    "scanner": "Trivy 0.76.2",
    "image_id": report["Metadata"]["ImageID"],
    "types": sorted({row["Type"] for row in report.get("Results") or []}),
    "components_in_sbom": len(sbom.get("components") or []),
    "vulnerabilities_by_severity": dict(sorted(total.items())),
    "vulnerabilities_by_ecosystem": dict(sorted(affected.items())),
    "high_or_critical_by_package": [
        {"ecosystem": ecosystem, "package": name, "severity": severity, "count": count}
        for (ecosystem, name, severity), count in sorted(high_packages.items())
    ],
    "secret_matches": secret_matches,
}
text = json.dumps(summary, indent=2) + "\n"
(output / "scan-summary.json").write_text(text)
print(text, end="")
if secret_matches:
    raise SystemExit("Secret matches require private triage; raw matches were not published")
PY
