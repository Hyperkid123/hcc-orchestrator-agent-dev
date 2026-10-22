#!/usr/bin/env python3
"""Inventory and mechanically validate a Clowder V2 consumer migration."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

HELPERS = {"get_v2_dependency_endpoint", "get_v2_private_dependency_endpoint"}
GO_MODULE = "github.com/redhatinsights/app-common-go"
GO_HELPERS = {"GetV2DependencyEndpoint", "GetV2PrivateDependencyEndpoint"}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "node_modules",
}
SOURCE_SUFFIXES = {".py", ".rb", ".go", ".java", ".kt", ".js", ".ts", ".tsx"}
TEXT_SUFFIXES = SOURCE_SUFFIXES | {
    ".gradle",
    ".json",
    ".kts",
    ".lock",
    ".md",
    ".mod",
    ".properties",
    ".sum",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {"pipfile"}
VERSION_RE = re.compile(
    r"app-common-python[^0-9\n]*([0-9]+\.[0-9]+(?:\.[0-9]+)?)", re.IGNORECASE
)
UV_VERSION_RE = re.compile(
    r'name\s*=\s*["\']app-common-python["\'][\s\S]{0,300}?version\s*=\s*["\']([0-9]+\.[0-9]+(?:\.[0-9]+)?)["\']',
    re.IGNORECASE,
)
GO_VERSION_RE = re.compile(
    rf"(?m)^\s*(?:require\s+|#\s+)?{re.escape(GO_MODULE)}\s+(v[^\s]+)"
)
GO_HELPER_RE = re.compile(
    rf"\b(?:\w+\.)?({'|'.join(sorted(GO_HELPERS))})\s*\("
)
KESSEL_SDK_RE = re.compile(r"kessel[-_. ]?sdk|@project-kessel/", re.IGNORECASE)
OAUTH2_CC_RE = re.compile(
    r"oauth2.{0,24}client.{0,24}credentials", re.IGNORECASE
)


@dataclass(frozen=True)
class Finding:
    message: str
    evidence: str = ""


@dataclass
class Assessment:
    repo: str
    phase: str
    changed_files: list[str] = field(default_factory=list)
    helper_calls: list[str] = field(default_factory=list)
    dependency_versions: dict[str, list[str]] = field(default_factory=dict)
    go_dependency_versions: dict[str, list[str]] = field(default_factory=dict)
    verified: list[str] = field(default_factory=list)
    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    gate_evidence: dict[str, list[str]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.errors


def _iter_text_files(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file() or (
            path.suffix.lower() not in TEXT_SUFFIXES
            and path.name.lower() not in TEXT_FILENAMES
        ):
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(repo).parts):
            continue
        yield path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _git_changed_files(repo: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    changed = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        name = line[3:]
        if " -> " in name:
            name = name.split(" -> ", 1)[1]
        changed.append(name.strip('"'))
    return sorted(set(changed))


def _dependency_versions(repo: Path, files: dict[Path, str]) -> dict[str, list[str]]:
    versions: dict[str, list[str]] = {}
    for path, text in files.items():
        relative = path.relative_to(repo)
        name = path.name.lower()
        if name == "pipfile.lock":
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {}
            found = set()
            for section in ("default", "develop"):
                version = (
                    data.get(section, {})
                    .get("app-common-python", {})
                    .get("version")
                )
                if version:
                    found.add(version.removeprefix("=="))
            if found:
                versions[str(relative)] = sorted(found)
            continue
        if not (
            name in {"pyproject.toml", "uv.lock", "poetry.lock", "pipfile"}
            or "requirements" in name
        ):
            continue
        if name in {"uv.lock", "poetry.lock"}:
            project_file = path.parent / "pyproject.toml"
            project_text = files.get(project_file, "")
            if (
                project_file != repo / "pyproject.toml"
                and "app-common-python" not in project_text
            ):
                continue
        found = set(VERSION_RE.findall(text))
        if name in {"uv.lock", "poetry.lock"}:
            found.update(UV_VERSION_RE.findall(text))
        if found:
            versions[str(relative)] = sorted(found)
    return versions


def _python_clowder_evidence(repo: Path, files: dict[Path, str]) -> list[str]:
    evidence: list[str] = []
    package_files = {
        "pipfile",
        "pipfile.lock",
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
    }
    for path, text in files.items():
        relative = path.relative_to(repo)
        name = path.name.lower()
        if name in package_files or "requirements" in name:
            if "app-common-python" in text:
                evidence.append(f"{relative} references app-common-python")
        if path.suffix != ".py":
            continue
        if "app_common_python" in text:
            evidence.append(f"{relative} imports app_common_python")
        if re.search(r"\bLoadedConfig\.(?:endpoints|privateEndpoints)\b", text):
            evidence.append(f"{relative} reads legacy LoadedConfig endpoints")
        if "DependencyEndpoints" in text or "PrivateDependencyEndpoints" in text:
            evidence.append(f"{relative} references dependency endpoint globals")
    return sorted(set(evidence))


def _kessel_env_discovery(repo: Path, files: dict[Path, str]) -> list[str]:
    evidence: list[str] = []
    env_pattern = re.compile(
        r"\b(?:[A-Z0-9_]*KESSEL[A-Z0-9_]*(?:URL|HOST|ENDPOINT|SERVER)|KESSEL_URL)\b"
    )
    for path, text in files.items():
        if path.suffix not in SOURCE_SUFFIXES and path.suffix.lower() not in {
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".md",
        }:
            continue
        if env_pattern.search(text):
            evidence.append(str(path.relative_to(repo)))
    return sorted(set(evidence))


def _helper_call_targets(helper_calls: list[str]) -> str:
    return "\n".join(helper_calls).lower()


def _go_dependency_versions(repo: Path, files: dict[Path, str]) -> dict[str, list[str]]:
    versions: dict[str, list[str]] = {}
    for path, text in files.items():
        if path.name != "go.mod" and not (
            path.name == "modules.txt" and path.parent.name == "vendor"
        ):
            continue
        found = sorted(set(GO_VERSION_RE.findall(text)))
        if found:
            versions[str(path.relative_to(repo))] = found
    return versions


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [item.id for item in target.elts if isinstance(item, ast.Name)]
    return []


def _python_helper_usage(repo: Path, files: dict[Path, str]):
    helper_calls: list[str] = []
    endpoint_attributes: set[str] = set()
    all_attributes: set[str] = set()
    wrong_object_access: list[str] = []

    for path, text in files.items():
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue

        endpoint_vars: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Call) or _call_name(value) not in HELPERS:
                continue
            endpoint_vars.update(_assigned_names(node))
            args = []
            for arg in value.args[:2]:
                args.append(
                    repr(arg.value) if isinstance(arg, ast.Constant) else "<dynamic>"
                )
            helper_calls.append(
                f"{path.relative_to(repo)}:{node.lineno} {_call_name(value)}({', '.join(args)})"
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                all_attributes.add(node.attr)
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in endpoint_vars
            ):
                endpoint_attributes.add(node.attr)
                if node.attr == "get":
                    wrong_object_access.append(
                        f"{path.relative_to(repo)}:{node.lineno} uses .get()"
                    )
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id in endpoint_vars
            ):
                wrong_object_access.append(
                    f"{path.relative_to(repo)}:{node.lineno} uses dictionary indexing"
                )

    return helper_calls, endpoint_attributes | all_attributes, wrong_object_access


def _go_helper_usage(repo: Path, files: dict[Path, str]):
    helper_calls: list[str] = []
    fields: set[str] = set()
    bool_results = 0
    checked_bool_results = 0
    for path, text in files.items():
        if path.suffix != ".go":
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            code = line.split("//", 1)[0]
            if re.match(r"^\s*func\s+", code):
                continue
            for match in GO_HELPER_RE.finditer(code):
                helper_calls.append(
                    f"{path.relative_to(repo)}:{line_number} {match.group(1)}(...)"
                )
                assignment = re.search(
                    rf"\b\w+\s*,\s*(\w+)\s*:=.*{match.group(1)}\s*\(", code
                )
                if assignment:
                    bool_results += 1
                    bool_name = assignment.group(1)
                    if len(re.findall(rf"\b{re.escape(bool_name)}\b", text)) > 1:
                        checked_bool_results += 1
        for field_name in ("Uri", "CaCertificate", "Authenticated"):
            if re.search(rf"\.{field_name}\b", text):
                fields.add(field_name)
    return helper_calls, fields, bool_results, checked_bool_results


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def analyze(repo: Path, phase: str) -> Assessment:
    repo = repo.resolve()
    if not repo.is_dir():
        raise ValueError(f"repository does not exist: {repo}")

    text_files = {path: _read_text(path) for path in _iter_text_files(repo)}
    assessment = Assessment(
        repo=str(repo), phase=phase, changed_files=_git_changed_files(repo)
    )
    assessment.dependency_versions = _dependency_versions(repo, text_files)
    assessment.go_dependency_versions = _go_dependency_versions(repo, text_files)

    helper_calls, attributes, wrong_access = _python_helper_usage(repo, text_files)
    go_helper_calls, go_fields, go_bool_results, checked_go_bool_results = (
        _go_helper_usage(repo, text_files)
    )
    assessment.helper_calls = sorted(helper_calls + go_helper_calls)
    all_text = "\n".join(text_files.values())

    def _evidence(pattern: re.Pattern[str]) -> list[str]:
        hits = [
            f"{path.relative_to(repo)}:{line_number} {line.strip()[:120]}"
            for path, text in text_files.items()
            for line_number, line in enumerate(text.splitlines(), start=1)
            if pattern.search(line)
        ]
        return hits[:8]

    sdk_hits = _evidence(KESSEL_SDK_RE)
    oauth_hits = _evidence(OAUTH2_CC_RE)
    assessment.gate_evidence["G1_kessel_sdk"] = sdk_hits
    assessment.gate_evidence["oauth2_client_credentials"] = oauth_hits
    if not sdk_hits:
        assessment.warnings.append(
            Finding(
                "No Kessel SDK evidence found (gate G1). If the SDK is absent, make no changes; emit a gate note and recommend a follow-up ticket to add it.",
                "Searched dependency manifests, lockfiles, vendor trees, and imports.",
            )
        )
    elif not oauth_hits:
        assessment.warnings.append(
            Finding(
                "Kessel SDK found but no OAuth2ClientCredentials usage detected. Confirm the installed SDK exposes it before planning authenticated calls.",
            )
        )

    kessel_env_discovery = _kessel_env_discovery(repo, text_files)
    kessel_helper_targets = _helper_call_targets(assessment.helper_calls)
    kessel_v2_helper = any(
        target in kessel_helper_targets
        for target in ("kessel", "inventory-api", "inventory_api")
    )
    python_clowder_evidence = _python_clowder_evidence(repo, text_files)
    python_clowder = bool(assessment.dependency_versions) or bool(
        python_clowder_evidence
    )
    go_clowder = bool(assessment.go_dependency_versions) or any(
        path.suffix == ".go" and GO_MODULE in text
        for path, text in text_files.items()
    )

    if helper_calls:
        assessment.verified.append(
            f"Found {len(helper_calls)} Python V2 helper call(s)."
        )
    elif phase == "after" and python_clowder:
        assessment.errors.append(
            Finding(
                "No Python Clowder V2 helper calls found after migration.",
                "; ".join(python_clowder_evidence[:5]),
            )
        )
    elif phase == "after" and go_clowder:
        assessment.verified.append(
            "No Python Clowder consumer detected; Go V2 checks were applied."
        )
    elif phase == "after":
        assessment.warnings.append(
            Finding(
                "No Python Clowder consumer detected; language-specific V2 API checks were not applied.",
                "Human must verify the client library contract for this repository's language.",
            )
        )
    else:
        assessment.verified.append("No Python V2 helper calls found before migration.")

    for evidence in wrong_access:
        assessment.errors.append(
            Finding(
                "V2 endpoint object is accessed as a dictionary; use object attributes.",
                evidence,
            )
        )

    if helper_calls:
        for attribute in ("uri", "ca_certificate", "authenticated"):
            if attribute not in attributes:
                severity = (
                    assessment.errors if attribute == "uri" else assessment.warnings
                )
                severity.append(
                    Finding(
                        f"V2 endpoint attribute '.{attribute}' is not consumed by the helper result.",
                        "Confirm metadata reaches the request boundary."
                        if attribute != "uri"
                        else "",
                    )
                )
            else:
                assessment.verified.append(f"V2 endpoint '.{attribute}' is referenced.")

    if go_helper_calls:
        assessment.verified.append(
            f"Found {len(go_helper_calls)} Go V2 helper call(s)."
        )
        if go_bool_results != len(go_helper_calls):
            assessment.warnings.append(
                Finding(
                    "A Go V2 helper result is not assigned as (endpoint, bool).",
                    "Verify absent endpoints cannot be consumed as zero values.",
                )
            )
        elif checked_go_bool_results != go_bool_results:
            assessment.warnings.append(
                Finding(
                    "A Go V2 helper availability boolean is not obviously checked.",
                    "Verify fallback and empty-endpoint behavior.",
                )
            )
        else:
            assessment.verified.append(
                "Go V2 helper availability booleans are referenced."
            )
        for field_name in ("Uri", "CaCertificate", "Authenticated"):
            if field_name not in go_fields:
                severity = assessment.errors if field_name == "Uri" else assessment.warnings
                severity.append(
                    Finding(
                        f"Go V2 endpoint field '.{field_name}' is not consumed by the helper result.",
                        "Confirm metadata reaches the request boundary."
                        if field_name != "Uri"
                        else "",
                    )
                )
            else:
                assessment.verified.append(
                    f"Go V2 endpoint '.{field_name}' is referenced."
                )
    elif phase == "after" and go_clowder:
        assessment.errors.append(
            Finding("No app-common-go V2 helper calls found after migration.")
        )

    if assessment.go_dependency_versions:
        assessment.verified.append(
            "Found app-common-go versions in "
            + ", ".join(sorted(assessment.go_dependency_versions))
            + "."
        )
    if go_helper_calls and not assessment.go_dependency_versions:
        assessment.warnings.append(
            Finding(
                "Could not determine the app-common-go version used by V2 helper calls.",
                "Inspect replacements or generated dependency inputs and compile the production build.",
            )
        )
    elif go_helper_calls:
        assessment.warnings.append(
            Finding(
                "Verify the selected app-common-go revision exports the V2 endpoint API.",
                json.dumps(assessment.go_dependency_versions, sort_keys=True),
            )
        )

    flat_versions = {
        version
        for versions in assessment.dependency_versions.values()
        for version in versions
    }
    if assessment.dependency_versions:
        assessment.verified.append(
            "Found app-common-python versions in "
            + ", ".join(sorted(assessment.dependency_versions))
            + "."
        )
    elif python_clowder_evidence:
        assessment.verified.append(
            "Found Python Clowder evidence: "
            + "; ".join(python_clowder_evidence[:5])
            + ("." if len(python_clowder_evidence) <= 5 else "; ...")
        )
    if helper_calls and any(
        _version_tuple(version) < (0, 3, 0) for version in flat_versions
    ):
        assessment.errors.append(
            Finding(
                "A dependency input pins app-common-python below 0.3.0 while V2 helpers are imported.",
                json.dumps(assessment.dependency_versions, sort_keys=True),
            )
        )
    if len(flat_versions) > 1:
        assessment.errors.append(
            Finding(
                "app-common-python versions disagree across dependency inputs.",
                json.dumps(assessment.dependency_versions, sort_keys=True),
            )
        )

    source_files = {
        path: text
        for path, text in text_files.items()
        if path.suffix in SOURCE_SUFFIXES
    }
    auth_files = [
        str(path.relative_to(repo))
        for path, text in source_files.items()
        if "authenticated" in text.lower()
        and any(
            marker in text.lower()
            for marker in ("authorization", "headers", "session", "request")
        )
    ]
    if assessment.helper_calls and (
        "authenticated" in attributes or "Authenticated" in go_fields
    ) and not auth_files:
        assessment.warnings.append(
            Finding(
                "Authentication metadata is found only during resolution, not in an obvious request path.",
                "Human must verify authenticated true/false behavior at the transport boundary.",
            )
        )
    elif auth_files:
        assessment.verified.append(
            "Authentication-aware request code: " + ", ".join(sorted(auth_files))
        )

    credential_functions = []
    for path, text in source_files.items():
        if "Authorization" in text and "psk" in text.lower():
            credential_functions.append(str(path.relative_to(repo)))
    if credential_functions:
        assessment.warnings.append(
            Finding(
                "Files contain both bearer and PSK logic; verify the bearer is sent alongside the existing PSK/identity credential and does not replace it.",
                ", ".join(sorted(credential_functions)),
            )
        )

    if kessel_env_discovery and not kessel_v2_helper:
        assessment.verified.append(
            "Kessel environment/config discovery remains outside the Clowder V2 scope: "
            + ", ".join(kessel_env_discovery[:8])
        )

    if assessment.helper_calls and (
        "ca_certificate" in attributes or "CaCertificate" in go_fields
    ):
        request_tls_files = [
            str(path.relative_to(repo))
            for path, text in source_files.items()
            if any(marker in text.lower() for marker in ("verify", "rootcas", "certpool"))
            and any(
                marker in text.lower()
                for marker in (
                    "ca_certificate",
                    "ca_cert",
                    "ca_path",
                    "cacertificate",
                )
            )
        ]
        if not request_tls_files:
            assessment.warnings.append(
                Finding(
                    "CA metadata is resolved but no obvious request TLS verification use was found.",
                    "Human must trace the CA path to the client request.",
                )
            )
        else:
            assessment.verified.append(
                "Endpoint-aware TLS code: " + ", ".join(sorted(request_tls_files))
            )

    kessel_detected = (
        "get_kessel_oauth2_credentials" in all_text
        or "KESSEL_AUTH_CLIENT_ID" in all_text
    )
    if helper_calls and kessel_detected:
        yaml_with_credentials = [
            str(path.relative_to(repo))
            for path, text in text_files.items()
            if path.suffix in {".yaml", ".yml"} and "KESSEL_AUTH_CLIENT_ID" in text
        ]
        assessment.warnings.append(
            Finding(
                "Kessel/workload authentication is present; verify every independent caller workload receives credentials.",
                "Credential-bearing manifests: "
                + (", ".join(sorted(yaml_with_credentials)) or "none found"),
            )
        )

    if phase == "after":
        changed_tests = [
            name for name in assessment.changed_files if "test" in name.lower()
        ]
        if assessment.changed_files and not changed_tests:
            assessment.warnings.append(
                Finding(
                    "No changed test files detected for the migration.",
                    "Add or identify existing contract coverage.",
                )
            )
        elif changed_tests:
            assessment.verified.append(
                "Changed test files: " + ", ".join(changed_tests)
            )
        else:
            assessment.verified.append(
                "Working tree is clean; changed-test check is not applicable."
            )

    return assessment


def render_markdown(assessment: Assessment) -> str:
    status = "PASS" if assessment.passed else "MECHANICAL ERRORS"
    lines = [
        "## Clowder V2 Deterministic Assessment",
        "",
        f"- Phase: `{assessment.phase}`",
        f"- Status: **{status}**",
        f"- Repository: `{assessment.repo}`",
        "",
        "### Gates",
        "",
    ]
    sdk_hits = assessment.gate_evidence.get("G1_kessel_sdk", [])
    lines.append(
        "- G1 Kessel SDK present: **PASS**"
        if sdk_hits
        else "- G1 Kessel SDK present: **UNKNOWN** — no SDK evidence; no migration work is permitted."
    )
    for hit in sdk_hits[:3]:
        lines.append(f"  - `{hit}`")
    oauth_hits = assessment.gate_evidence.get("oauth2_client_credentials", [])
    if sdk_hits:
        lines.append(
            "- OAuth2ClientCredentials usage: **PASS**"
            if oauth_hits
            else "- OAuth2ClientCredentials usage: **UNKNOWN** — confirm the installed SDK exposes it."
        )
        for hit in oauth_hits[:3]:
            lines.append(f"  - `{hit}`")

    lines.extend(["", "### Verified Evidence", ""])
    lines.extend(f"- {item}" for item in assessment.verified)
    if not assessment.verified:
        lines.append("- None detected.")

    lines.extend(["", "### Mechanical Errors", ""])
    if assessment.errors:
        for finding in assessment.errors:
            suffix = f" Evidence: `{finding.evidence}`" if finding.evidence else ""
            lines.append(f"- {finding.message}{suffix}")
    else:
        lines.append("- None detected.")

    lines.extend(["", "### Human Verification Required", ""])
    if assessment.warnings:
        for finding in assessment.warnings:
            suffix = f" Evidence: {finding.evidence}" if finding.evidence else ""
            lines.append(f"- {finding.message}{suffix}")
    else:
        lines.append(
            "- No static warnings. Application semantics still require review."
        )

    lines.extend(["", "### Changed Files", ""])
    lines.extend(f"- `{name}`" for name in assessment.changed_files)
    if not assessment.changed_files:
        lines.append("- None detected or repository is not Git-managed.")

    lines.extend(["", "### Helper Calls", ""])
    lines.extend(f"- `{call}`" for call in assessment.helper_calls)
    if not assessment.helper_calls:
        lines.append("- None detected.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        assessment = analyze(args.repo, args.phase)
    except (OSError, ValueError) as exc:
        print(f"assessment failed: {exc}", file=sys.stderr)
        return 2

    output = (
        json.dumps(asdict(assessment), indent=2) + "\n"
        if args.as_json
        else render_markdown(assessment)
    )
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if assessment.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
