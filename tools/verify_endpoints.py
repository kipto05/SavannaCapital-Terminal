"""
tools/verify_endpoints.py

Verifies that every API endpoint called from the frontend (app.js)
is registered in the FastAPI backend.

Run:
    .\venv\Scripts\python.exe tools/verify_endpoints.py

Exit code 0 = all matched
Exit code 1 = mismatches found (use in CI to block broken builds)
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict


# ── Configuration ─────────────────────────────────────────────────────────────

FRONTEND_FILE   = Path("dashboard/static/app.js")
LOGIN_JS_FILE   = Path("dashboard/static/login.js")
BACKEND_APP     = "dashboard.app"       # dotted import path to FastAPI app object
IGNORE_PREFIXES = ["/static", "/login", "/"]  # non-API routes to skip
API_PREFIX      = "/api"


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FrontendCall:
    method:  str        # "GET" | "POST" | "PUT" | "DELETE" | "UNKNOWN"
    path:    str        # e.g. "/api/account/stats"
    source:  str        # which file it came from
    line:    int        # line number


@dataclass
class BackendRoute:
    methods: set[str]   # {"GET"} or {"POST", "PUT"}
    path:    str        # e.g. "/api/account/stats"
    name:    str        # FastAPI endpoint function name


@dataclass
class VerificationReport:
    matched:         list[str]                  = field(default_factory=list)
    missing_backend: list[FrontendCall]         = field(default_factory=list)
    missing_frontend: list[BackendRoute]        = field(default_factory=list)
    method_mismatch: list[tuple]                = field(default_factory=list)
    warnings:        list[str]                  = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            len(self.missing_backend) == 0
            and len(self.method_mismatch) == 0
        )


# ── Step 1: Extract frontend API calls ───────────────────────────────────────

# Patterns to match:
#   apiFetch('/api/account/stats')
#   apiFetch(`/api/strategies/${name}/toggle`)
#   apiFetch('/api/quant/backtest', { method: 'POST', ... })
#   fetch('/auth/login', { method: 'POST' })

FETCH_PATTERN = re.compile(
    r"""(?:apiFetch|fetch)\s*\(\s*[`'"]([^`'"]+)[`'"]"""
    r"""(?:\s*,\s*\{[^}]*?method\s*:\s*['"](GET|POST|PUT|DELETE|PATCH)['"]\s*[^}]*?\})?""",
    re.DOTALL,
)

# Template literal paths like `/api/strategies/${name}/params`
# → normalise to `/api/strategies/{name}/params`
TEMPLATE_PARAM = re.compile(r"\$\{[^}]+\}")


def normalise_path(path: str) -> str:
    """Convert JS template literal params to FastAPI path param format."""
    return TEMPLATE_PARAM.sub("{param}", path)


def extract_frontend_calls(files: list[Path]) -> list[FrontendCall]:
    calls = []
    for file in files:
        if not file.exists():
            print(f"  WARNING: frontend file not found: {file}")
            continue
        content = file.read_text(encoding="utf-8")
        lines   = content.splitlines()

        for match in FETCH_PATTERN.finditer(content):
            raw_path = match.group(1)
            method   = (match.group(2) or "GET").upper()

            # Only care about /api/* and /auth/* paths
            if not (raw_path.startswith("/api") or raw_path.startswith("/auth")):
                continue

            path = normalise_path(raw_path)

            # Find line number
            line_num = content[: match.start()].count("\n") + 1

            calls.append(FrontendCall(
                method=method,
                path=path,
                source=str(file),
                line=line_num,
            ))

    # Deduplicate — same method+path from same file counts once
    seen = set()
    unique = []
    for c in calls:
        key = (c.method, c.path)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return sorted(unique, key=lambda c: c.path)


# ── Step 2: Extract backend routes ───────────────────────────────────────────

def extract_backend_routes() -> list[BackendRoute]:
    """
    Import the FastAPI app and read its route table.
    FastAPI exposes all routes via app.routes.
    """
    import importlib
    try:
        module_name, app_name = BACKEND_APP.rsplit(".", 1)
        module = importlib.import_module(module_name)
        app    = getattr(module, app_name)
    except Exception as exc:
        print(f"FATAL: Could not import FastAPI app '{BACKEND_APP}': {exc}")
        sys.exit(1)

    routes = []
    for route in app.routes:
        # FastAPI APIRoute objects have: path, methods, name
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        if route.methods is None:
            continue

        path = route.path
        # Skip non-API routes
        if any(path == p or path.startswith(p + "/")
               for p in IGNORE_PREFIXES if p not in ("/api", "/auth")):
            continue
        if not (path.startswith("/api") or path.startswith("/auth")):
            continue

        # Normalise FastAPI path params: /api/strategies/{name} stays as-is
        # Frontend uses {param} after normalise_path() — these should match

        routes.append(BackendRoute(
            methods=set(m.upper() for m in route.methods),
            path=path,
            name=getattr(route, "name", "unknown"),
        ))

    return sorted(routes, key=lambda r: r.path)


# ── Step 3: Normalise and compare ─────────────────────────────────────────────

def normalise_backend_path(path: str) -> str:
    """
    Convert FastAPI path params {name}, {job_id}, {model_id}
    to generic {param} to match frontend normalisation.
    """
    return re.sub(r"\{[^}]+\}", "{param}", path)


def compare(
    frontend: list[FrontendCall],
    backend:  list[BackendRoute],
) -> VerificationReport:

    report = VerificationReport()

    # Build backend lookup: normalised_path -> BackendRoute
    backend_map: dict[str, BackendRoute] = {}
    for route in backend:
        norm = normalise_backend_path(route.path)
        if norm in backend_map:
            # Merge methods for routes at same normalised path
            backend_map[norm].methods |= route.methods
        else:
            # Store with normalised path as key but original route
            backend_map[norm] = route

    # Build frontend lookup: normalised_path -> [FrontendCall]
    frontend_map: dict[str, list[FrontendCall]] = defaultdict(list)
    for call in frontend:
        frontend_map[call.path].append(call)

    # Check every frontend call against backend
    matched_backend_paths = set()
    for norm_path, calls in frontend_map.items():
        if norm_path not in backend_map:
            for call in calls:
                report.missing_backend.append(call)
        else:
            backend_route = backend_map[norm_path]
            matched_backend_paths.add(norm_path)

            for call in calls:
                if call.method not in backend_route.methods:
                    report.method_mismatch.append((call, backend_route))
                else:
                    if norm_path not in [m for m in report.matched]:
                        report.matched.append(
                            f"{call.method:6} {norm_path}"
                        )

    # Check for backend routes with no frontend caller (informational)
    for norm_path, route in backend_map.items():
        if norm_path not in matched_backend_paths:
            report.missing_frontend.append(route)

    return report


# ── Step 4: Report ────────────────────────────────────────────────────────────

def print_report(report: VerificationReport) -> None:
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

    print(f"\n{BOLD}═══════════════════════════════════════════{RESET}")
    print(f"{BOLD}  ENDPOINT CONTRACT VERIFICATION{RESET}")
    print(f"{BOLD}═══════════════════════════════════════════{RESET}\n")

    # Matched
    if report.matched:
        print(f"{GREEN}✓ MATCHED ({len(report.matched)}){RESET}")
        for m in report.matched:
            print(f"  {GREEN}✓{RESET}  {m}")
        print()

    # Missing from backend (CRITICAL — frontend calls something that doesn't exist)
    if report.missing_backend:
        print(f"{RED}✗ MISSING FROM BACKEND ({len(report.missing_backend)}) — CRITICAL{RESET}")
        print(f"  Frontend calls these endpoints but they are not registered in FastAPI:\n")
        for call in report.missing_backend:
            print(f"  {RED}✗{RESET}  {call.method:6} {call.path}")
            print(f"         Source: {call.source}:{call.line}")
        print()

    # Method mismatch
    if report.method_mismatch:
        print(f"{RED}✗ METHOD MISMATCH ({len(report.method_mismatch)}) — CRITICAL{RESET}")
        for call, route in report.method_mismatch:
            print(f"  {RED}✗{RESET}  {call.path}")
            print(f"         Frontend expects: {call.method}")
            print(f"         Backend accepts:  {', '.join(sorted(route.methods))}")
            print(f"         Source: {call.source}:{call.line}")
        print()

    # Missing from frontend (informational — backend has endpoints nobody calls)
    if report.missing_frontend:
        print(f"{YELLOW}⚠ BACKEND ROUTES WITH NO FRONTEND CALLER ({len(report.missing_frontend)}){RESET}")
        print(f"  These exist in FastAPI but app.js never calls them.")
        print(f"  May be intentional (admin-only, CLI, future features).\n")
        for route in report.missing_frontend:
            methods = "/".join(sorted(route.methods))
            print(f"  {YELLOW}?{RESET}  {methods:10} {route.path}  [{route.name}]")
        print()

    # Warnings
    if report.warnings:
        for w in report.warnings:
            print(f"  {YELLOW}⚠{RESET}  {w}")
        print()

    # Summary
    total = len(report.matched) + len(report.missing_backend) + len(report.method_mismatch)
    print(f"{BOLD}─────────────────────────────────────────{RESET}")
    if report.passed:
        print(f"{GREEN}{BOLD}  ✓ ALL ENDPOINTS VERIFIED ({len(report.matched)} matched){RESET}")
    else:
        problems = len(report.missing_backend) + len(report.method_mismatch)
        print(f"{RED}{BOLD}  ✗ VERIFICATION FAILED — {problems} problem(s) found{RESET}")
    print(f"{BOLD}─────────────────────────────────────────{RESET}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("Scanning frontend files...")
    frontend_files = [FRONTEND_FILE, LOGIN_JS_FILE]
    frontend_calls = extract_frontend_calls(frontend_files)
    print(f"  Found {len(frontend_calls)} unique API calls in frontend\n")

    print("Loading FastAPI route table...")
    backend_routes = extract_backend_routes()
    print(f"  Found {len(backend_routes)} API routes in backend\n")

    print("Comparing...")
    report = compare(frontend_calls, backend_routes)
    print_report(report)

    # Optionally write machine-readable output
    output = {
        "passed":           report.passed,
        "matched_count":    len(report.matched),
        "missing_backend":  [{"method": c.method, "path": c.path, "source": c.source, "line": c.line}
                             for c in report.missing_backend],
        "method_mismatch":  [{"path": c.path, "frontend_method": c.method,
                               "backend_methods": list(r.methods)}
                             for c, r in report.method_mismatch],
        "uncalled_backend": [{"path": r.path, "methods": list(r.methods)}
                             for r in report.missing_frontend],
    }
    Path("tools/verification_report.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print("  Report written to tools/verification_report.json\n")

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())