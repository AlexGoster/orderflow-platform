"""Локальная проверка конфигов платформы: YAML / JSON / TOML + структура.

Запуск:  python scripts/check_configs.py
Выход: 0 — все проверки прошли, 1 — есть ошибки (подробности в stdout).
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

YAML_FILES = [
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/dependabot.yml",
    "deploy/site.yml",
    "infra/docker-compose.prod.yml",
    "observability/prometheus/prometheus.yml",
    "observability/prometheus/rules.yml",
    "observability/grafana/alerts.yml",
    "observability/grafana/provisioning/datasources/prometheus.yml",
    "observability/grafana/provisioning/dashboards/provider.yml",
]
JSON_FILES = [
    "observability/grafana/dashboard.json",
]
TOML_FILES = [
    "pyproject.toml",
    "security/.gitleaks.toml",
]

REQUIRED_SERVICES = {"api", "nginx", "prometheus", "grafana", "postgres", "migrate"}
RESTART_SERVICES = {"api", "nginx", "prometheus", "grafana", "postgres"}
PLAYBOOK_KEYWORDS = {
    "name",
    "when",
    "loop",
    "vars",
    "environment",
    "register",
    "notify",
    "changed_when",
    "failed_when",
    "no_log",
    "tags",
    "retries",
    "delay",
    "until",
    "with_items",
    "run_once",
    "ignore_errors",
    "become",
    "args",
}


def _load_yaml(rel: str) -> tuple[Any | None, str | None]:
    path = ROOT / rel
    if not path.exists():
        return None, f"{rel}: file not found"
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except yaml.YAMLError as exc:
        return None, f"{rel}: invalid YAML -> {exc}"


def check_compose(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["docker-compose.prod.yml: root must be a mapping"]
    services = doc.get("services")
    if not isinstance(services, dict):
        return ["docker-compose.prod.yml: 'services' must be a mapping"]

    missing = REQUIRED_SERVICES - set(services)
    if missing:
        errors.append(f"docker-compose.prod.yml: missing services {sorted(missing)}")

    for name in sorted(RESTART_SERVICES & set(services)):
        if "restart" not in services[name]:
            errors.append(f"docker-compose.prod.yml: service '{name}' has no restart policy")

    for name in ("api", "postgres"):
        service = services.get(name)
        if isinstance(service, dict) and "healthcheck" not in service:
            errors.append(f"docker-compose.prod.yml: service '{name}' has no healthcheck")

    api = services.get("api")
    if isinstance(api, dict):
        if not api.get("read_only"):
            errors.append("docker-compose.prod.yml: 'api' must run with read_only: true")
        image = str(api.get("image", ""))
        if "${" not in image:
            errors.append(
                "docker-compose.prod.yml: 'api' image must be parameterized by ${IMAGE_TAG}"
            )
    return errors


def check_playbook(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, list):
        return ["deploy/site.yml: root must be a list of plays"]

    handlers: set[str] = set()
    for index, play in enumerate(doc):
        if not isinstance(play, dict):
            errors.append(f"deploy/site.yml: play #{index} is not a mapping")
            continue
        if "hosts" not in play:
            errors.append(f"deploy/site.yml: play #{index} has no 'hosts'")
        for handler in play.get("handlers") or []:
            if isinstance(handler, dict) and handler.get("name"):
                handlers.add(handler["name"])
        for task in play.get("tasks") or []:
            if not isinstance(task, dict):
                errors.append("deploy/site.yml: task is not a mapping")
                continue
            if not task.get("name"):
                errors.append("deploy/site.yml: every task must have a 'name'")
            modules = [key for key in task if key not in PLAYBOOK_KEYWORDS and key != "block"]
            if len(modules) != 1:
                errors.append(
                    f"deploy/site.yml: task '{task.get('name')}' must call exactly one module, "
                    f"found {modules}"
                )
            notified = task.get("notify")
            if notified:
                names = notified if isinstance(notified, list) else [notified]
                for handler_name in names:
                    if handler_name not in handlers:
                        errors.append(
                            f"deploy/site.yml: notify '{handler_name}' has no matching handler"
                        )
    return errors


def check_dashboard(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["grafana/dashboard.json: root must be an object"]
    panels = doc.get("panels")
    if not isinstance(panels, list) or not panels:
        return ["grafana/dashboard.json: 'panels' must be a non-empty list"]
    seen_ids: set[int] = set()
    for panel in panels:
        if not isinstance(panel, dict):
            errors.append("grafana/dashboard.json: panel is not an object")
            continue
        for field in ("id", "title", "type", "gridPos"):
            if field not in panel:
                errors.append(
                    f"grafana/dashboard.json: panel '{panel.get('title')}' lacks '{field}'"
                )
        panel_id = panel.get("id")
        if isinstance(panel_id, int):
            if panel_id in seen_ids:
                errors.append(f"grafana/dashboard.json: duplicate panel id {panel_id}")
            seen_ids.add(panel_id)
    if not isinstance(doc.get("schemaVersion"), int):
        errors.append("grafana/dashboard.json: 'schemaVersion' must be an integer")
    return errors


def check_rules(doc: Any) -> list[str]:
    errors: list[str] = []
    groups = doc.get("groups") if isinstance(doc, dict) else None
    if not isinstance(groups, list) or not groups:
        return ["prometheus rules: root must contain a non-empty 'groups' list"]
    names: set[str] = set()
    for group in groups:
        for rule in (group or {}).get("rules", []):
            alert = (rule or {}).get("alert")
            if not alert:
                errors.append("prometheus rules: every rule must have an 'alert' name")
            elif alert in names:
                errors.append(f"prometheus rules: duplicate alert '{alert}'")
            else:
                names.add(alert)
    expected = {"HighErrorRate", "HighP95Latency", "ApiDown"}
    if expected - names:
        errors.append(f"prometheus rules: missing alerts {sorted(expected - names)}")
    return errors


def check_prometheus(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["prometheus.yml: root must be a mapping"]
    jobs = (doc.get("scrape_configs") or []) if isinstance(doc, dict) else []
    job_names = {job.get("job_name") for job in jobs if isinstance(job, dict)}
    if "api" not in job_names:
        errors.append("prometheus.yml: missing scrape job 'api'")
    if not doc.get("rule_files"):
        errors.append("prometheus.yml: 'rule_files' must point to rules.yml")
    return errors


def main() -> int:
    errors: list[str] = []
    checked = 0

    for rel in YAML_FILES:
        doc, error = _load_yaml(rel)
        if error:
            errors.append(error)
            continue
        checked += 1
        if rel == "infra/docker-compose.prod.yml":
            errors.extend(check_compose(doc))
        elif rel == "deploy/site.yml":
            errors.extend(check_playbook(doc))
        elif rel == "observability/prometheus/prometheus.yml":
            errors.extend(check_prometheus(doc))
        elif rel == "observability/prometheus/rules.yml":
            errors.extend(check_rules(doc))

    for rel in JSON_FILES:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"{rel}: file not found")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON -> {exc}")
            continue
        checked += 1
        if rel.endswith("dashboard.json"):
            errors.extend(check_dashboard(doc))

    for rel in TOML_FILES:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"{rel}: file not found")
            continue
        try:
            tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{rel}: invalid TOML -> {exc}")
            continue
        checked += 1

    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        print(f"\n{len(errors)} problem(s) found in {checked} file(s)", file=sys.stderr)
        return 1

    print(f"All config checks passed ({checked} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
