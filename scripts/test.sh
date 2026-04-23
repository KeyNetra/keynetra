#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -t 1 ]; then
  COLOR_RED="$(printf '\033[31m')"
  COLOR_GREEN="$(printf '\033[32m')"
  COLOR_YELLOW="$(printf '\033[33m')"
  COLOR_BLUE="$(printf '\033[34m')"
  COLOR_BOLD="$(printf '\033[1m')"
  COLOR_RESET="$(printf '\033[0m')"
else
  COLOR_RED=""
  COLOR_GREEN=""
  COLOR_YELLOW=""
  COLOR_BLUE=""
  COLOR_BOLD=""
  COLOR_RESET=""
fi

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
SUMMARY_LINES=()
CURRENT_STAGE=""
CURRENT_STAGE_STARTED_AT=0
RUNNER_STARTED_AT="$(date +%s)"

PYTHON_BIN=""
KEYNETRA_BIN=""

log() {
  printf "%b\n" "$*"
}

section() {
  log ""
  log "${COLOR_BOLD}${COLOR_BLUE}$1${COLOR_RESET}"
}

duration_seconds() {
  local started_at="$1"
  local finished_at="$2"
  echo $((finished_at - started_at))
}

record_result() {
  local status="$1"
  local name="$2"
  local seconds="$3"
  SUMMARY_LINES+=("${status}|${name}|${seconds}")
  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    SKIP) SKIP_COUNT=$((SKIP_COUNT + 1)) ;;
  esac
}

print_summary() {
  local total_seconds
  total_seconds="$(duration_seconds "$RUNNER_STARTED_AT" "$(date +%s)")"

  section "📋 Summary"
  log "Passed: ${COLOR_GREEN}${PASS_COUNT}${COLOR_RESET}"
  log "Failed: ${COLOR_RED}${FAIL_COUNT}${COLOR_RESET}"
  log "Skipped: ${COLOR_YELLOW}${SKIP_COUNT}${COLOR_RESET}"
  log "Total time: ${total_seconds}s"

  if [ "${#SUMMARY_LINES[@]}" -gt 0 ]; then
    log ""
    for line in "${SUMMARY_LINES[@]}"; do
      local status name seconds
      status="${line%%|*}"
      name="${line#*|}"
      seconds="${name##*|}"
      name="${name%|*}"
      case "$status" in
        PASS) log "${COLOR_GREEN}PASS${COLOR_RESET} ${name} (${seconds}s)" ;;
        FAIL) log "${COLOR_RED}FAIL${COLOR_RESET} ${name} (${seconds}s)" ;;
        SKIP) log "${COLOR_YELLOW}SKIP${COLOR_RESET} ${name} (${seconds}s)" ;;
      esac
    done
  fi
}

on_exit() {
  local exit_code="$?"
  if [ -n "$CURRENT_STAGE" ]; then
    record_result "FAIL" "$CURRENT_STAGE" "$(duration_seconds "$CURRENT_STAGE_STARTED_AT" "$(date +%s)")"
    log ""
    log "${COLOR_RED}✖ Stage failed:${COLOR_RESET} $CURRENT_STAGE"
    CURRENT_STAGE=""
  fi
  print_summary
  exit "$exit_code"
}

trap on_exit EXIT

find_python() {
  if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
    return
  fi
  log "${COLOR_RED}Python is required but was not found.${COLOR_RESET}"
  exit 1
}

find_tool() {
  local tool="$1"
  if [ -x "$REPO_ROOT/.venv/bin/$tool" ]; then
    echo "$REPO_ROOT/.venv/bin/$tool"
    return 0
  fi
  if command -v "$tool" >/dev/null 2>&1; then
    command -v "$tool"
    return 0
  fi
  return 1
}

require_tool() {
  local tool="$1"
  local label="$2"
  local path
  if ! path="$(find_tool "$tool")"; then
    log "${COLOR_RED}Missing required tool:${COLOR_RESET} $tool ($label)"
    exit 1
  fi
  log "  • $label: $path"
}

start_stage() {
  CURRENT_STAGE="$1"
  CURRENT_STAGE_STARTED_AT="$(date +%s)"
  section "🚀 $CURRENT_STAGE"
}

finish_stage() {
  local seconds
  seconds="$(duration_seconds "$CURRENT_STAGE_STARTED_AT" "$(date +%s)")"
  record_result "PASS" "$CURRENT_STAGE" "$seconds"
  log "${COLOR_GREEN}✔ Completed${COLOR_RESET} in ${seconds}s"
  CURRENT_STAGE=""
}

skip_stage() {
  local seconds
  seconds="$(duration_seconds "$CURRENT_STAGE_STARTED_AT" "$(date +%s)")"
  record_result "SKIP" "$CURRENT_STAGE" "$seconds"
  log "${COLOR_YELLOW}↷ Skipped${COLOR_RESET} in ${seconds}s"
  CURRENT_STAGE=""
}

run_stage() {
  local name="$1"
  shift
  start_stage "$name"
  "$@"
  finish_stage
}

run_optional_stage() {
  local name="$1"
  local flag="$2"
  shift 2
  start_stage "$name"
  if [ "$flag" != "1" ]; then
    log "Set the related env flag to 1 to enable this stage."
    skip_stage
    return
  fi
  "$@"
  finish_stage
}

run_python_module() {
  local module="$1"
  shift
  "$PYTHON_BIN" -m "$module" "$@"
}

resolve_keynetra_bin() {
  if [ -x "$REPO_ROOT/.venv/bin/keynetra" ]; then
    KEYNETRA_BIN="$REPO_ROOT/.venv/bin/keynetra"
    return
  fi
  if command -v keynetra >/dev/null 2>&1; then
    KEYNETRA_BIN="$(command -v keynetra)"
    return
  fi
  KEYNETRA_BIN=""
}

run_keynetra_cli() {
  if [ -n "$KEYNETRA_BIN" ]; then
    "$KEYNETRA_BIN" "$@"
    return
  fi
  "$PYTHON_BIN" -m keynetra "$@"
}

stage_environment() {
  find_python
  resolve_keynetra_bin
  log "  • python: $PYTHON_BIN"
  if [ -n "$KEYNETRA_BIN" ]; then
    log "  • keynetra: $KEYNETRA_BIN"
  else
    log "  • keynetra: using python -m keynetra fallback"
  fi
  require_tool "ruff" "ruff"
  require_tool "black" "black"
  require_tool "isort" "isort"
  require_tool "mypy" "mypy"
  require_tool "pytest" "pytest"
  if [ -f "$REPO_ROOT/.importlinter" ]; then
    require_tool "lint-imports" "import-linter"
  fi
  run_keynetra_cli --help >/dev/null
}

stage_lint() {
  "$(find_tool ruff)" check .
}

stage_format() {
  "$(find_tool black)" --check .
  "$(find_tool isort)" --check-only .
}

stage_mypy() {
  "$(find_tool mypy)" keynetra
}

stage_import_linter() {
  local lint_imports
  if [ ! -f "$REPO_ROOT/.importlinter" ]; then
    log "No .importlinter configuration found."
    return 0
  fi
  lint_imports="$(find_tool lint-imports)"
  "$lint_imports"
}

stage_pytest() {
  "$(find_tool pytest)" --no-cov
}

stage_coverage() {
  "$(find_tool pytest)" --cov=keynetra --cov-branch --cov-report=term-missing --cov-report=json --cov-fail-under=90
}

stage_openapi() {
  run_keynetra_cli generate-openapi --output /tmp/keynetra-openapi.json --yaml-output /tmp/keynetra-openapi.yaml
  run_keynetra_cli check-openapi --contract contracts/openapi.json
  run_keynetra_cli check-openapi --contract contracts/openapi.yaml
  cmp -s contracts/openapi.json /tmp/keynetra-openapi.json
  cmp -s contracts/openapi.yaml /tmp/keynetra-openapi.yaml
}

stage_build() {
  rm -rf dist build keynetra.egg-info
  run_python_module build --no-isolation
}

stage_twine() {
  if ! "$PYTHON_BIN" -c "import twine" >/dev/null 2>&1; then
    log "Twine is not installed in the active Python environment."
    return 1
  fi
  run_python_module twine check dist/*
}

stage_docker() {
  require_tool "docker" "docker"
  docker compose config >/tmp/keynetra-docker-compose.rendered.yaml
  docker build -t keynetra:test .
}

stage_helm() {
  require_tool "helm" "helm"
  helm lint deploy/helm/keynetra
  helm template keynetra-local deploy/helm/keynetra >/tmp/keynetra-helm-template.yaml
}

stage_pip_audit() {
  if ! "$PYTHON_BIN" -c "import pip_audit" >/dev/null 2>&1; then
    log "pip-audit is not installed in the active Python environment."
    return 1
  fi
  run_python_module pip_audit
}

stage_flaky() {
  "$(find_tool pytest)" --no-cov
  "$(find_tool pytest)" --no-cov
}

stage_secret_scan() {
  if command -v gitleaks >/dev/null 2>&1; then
    gitleaks detect --no-banner --source .
    return
  fi
  if command -v trufflehog >/dev/null 2>&1; then
    trufflehog filesystem --no-update .
    return
  fi
  log "No supported secret scanner found (checked gitleaks, trufflehog)."
  return 0
}

run_stage "🧰 Environment Checks" stage_environment
run_stage "🧹 Lint" stage_lint
run_stage "🎨 Formatting" stage_format
run_stage "🧠 Mypy" stage_mypy
run_stage "🧱 Import Linter" stage_import_linter
run_stage "🧪 Pytest" stage_pytest
run_optional_stage "🎲 Flaky Test Probe" "${FLAKY:-${FULL:-0}}" stage_flaky
run_stage "📊 Coverage" stage_coverage
run_stage "📜 OpenAPI" stage_openapi
run_stage "📦 Package Build" stage_build
run_optional_stage "📮 Twine Check" "${TWINE:-${FULL:-0}}" stage_twine
run_optional_stage "🐳 Docker Build" "${DOCKER:-${FULL:-0}}" stage_docker
run_optional_stage "⛵ Helm Checks" "${HELM:-${FULL:-0}}" stage_helm
run_optional_stage "🛡️ pip-audit" "${SECURITY:-0}" stage_pip_audit
run_optional_stage "🔐 Secret Scan" "${SECURITY:-0}" stage_secret_scan

log ""
log "${COLOR_GREEN}${COLOR_BOLD}All enabled stages passed.${COLOR_RESET}"
