#!/usr/bin/env bash
# session-mgr.sh — Session record management for codex/gemini skill wrappers.
# Source this file, then call smgr_* functions.
# Set SMGR_SESSIONS_DIR before calling, or call smgr_init_dir.
# NOTE: This file is sourced, not executed. Callers set their own shell options.

# --- Configuration ---

smgr_init_dir() {
  local provider="${1:?Usage: smgr_init_dir <codex|gemini>}"
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  SMGR_SESSIONS_DIR="$root/.claude/.${provider}-sessions"
  mkdir -p "$SMGR_SESSIONS_DIR"
  echo "$SMGR_SESSIONS_DIR"
}

# --- Slug Validation ---

smgr_validate_slug() {
  local slug="${1:?Usage: smgr_validate_slug <slug>}"
  slug=$(echo "$slug" | tr '[:upper:]' '[:lower:]')

  if [[ ! "$slug" =~ ^[a-z0-9-]+$ ]]; then
    echo "ERROR: Slug must contain only [a-z0-9-], got: '$slug'" >&2
    return 1
  fi

  if [[ ${#slug} -gt 64 ]]; then
    echo "ERROR: Slug must be ≤64 characters (got ${#slug})" >&2
    return 1
  fi

  local reserved="CON PRN AUX NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9"
  local upper_slug
  upper_slug=$(echo "$slug" | tr '[:lower:]' '[:upper:]')
  for name in $reserved; do
    if [[ "$upper_slug" == "$name" ]]; then
      echo "ERROR: '$slug' is a Windows reserved name" >&2
      return 1
    fi
  done

  echo "$slug"
}

# --- Record CRUD ---

smgr_create() {
  local slug="${1:?}" cli_id="${2:?}" artifact_path="${3:-}"
  local record_file="$SMGR_SESSIONS_DIR/${slug}.json"

  if [[ -f "$record_file" ]]; then
    echo "ERROR: Session '$slug' already exists. Use --session to resume." >&2
    return 1
  fi

  local branch
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "none")
  local now
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  local artifact_line=""
  if [[ -n "$artifact_path" ]]; then
    artifact_line=",
  \"artifact_path\":\"$artifact_path\""
  fi

  local json
  json=$(cat <<ENDJSON
{
  "cli_session_id":"$cli_id",
  "created_at":"$now",
  "last_used_at":"$now",
  "branch":"$branch"$artifact_line
}
ENDJSON
)
  mkdir -p "$SMGR_SESSIONS_DIR"
  echo "$json" > "$record_file"
  echo "Session '$slug' created (CLI ID: $cli_id)"
}

smgr_lookup() {
  local slug="${1:?}"
  local record_file="$SMGR_SESSIONS_DIR/${slug}.json"

  if [[ ! -f "$record_file" ]]; then
    echo "ERROR: Session '$slug' not found. Use --new-session to create." >&2
    return 1
  fi

  grep -o '"cli_session_id": *"[^"]*"' "$record_file" | head -1 | cut -d'"' -f4
}

smgr_update() {
  local slug="${1:?}"
  local record_file="$SMGR_SESSIONS_DIR/${slug}.json"
  local tmp_file="$SMGR_SESSIONS_DIR/${slug}.json.tmp"

  if [[ ! -f "$record_file" ]]; then
    echo "ERROR: Session '$slug' not found" >&2
    return 1
  fi

  local now
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  sed "s/\"last_used_at\": *\"[^\"]*\"/\"last_used_at\":\"$now\"/" "$record_file" > "$tmp_file"
  mv "$tmp_file" "$record_file"
}

smgr_update_artifact() {
  local slug="${1:?}" artifact_path="${2:?}"
  local record_file="$SMGR_SESSIONS_DIR/${slug}.json"
  local tmp_file="$SMGR_SESSIONS_DIR/${slug}.json.tmp"

  if [[ ! -f "$record_file" ]]; then
    echo "ERROR: Session '$slug' not found" >&2
    return 1
  fi

  if grep -q '"artifact_path"' "$record_file"; then
    # Replace existing artifact_path
    sed "s|\"artifact_path\": *\"[^\"]*\"|\"artifact_path\":\"$artifact_path\"|" "$record_file" > "$tmp_file"
  else
    # Add artifact_path before closing brace
    sed "s|}|,\n  \"artifact_path\":\"$artifact_path\"\n}|" "$record_file" > "$tmp_file"
  fi
  mv "$tmp_file" "$record_file"
}

smgr_delete() {
  local slug="${1:?}"
  local record_file="$SMGR_SESSIONS_DIR/${slug}.json"
  local lock_file="$SMGR_SESSIONS_DIR/${slug}.lock"

  # Check for live lock
  if [[ -f "$lock_file" ]]; then
    local lock_pid
    lock_pid=$(cut -d' ' -f1 "$lock_file")
    if kill -0 "$lock_pid" 2>/dev/null; then
      echo "ERROR: Session '$slug' is locked by PID $lock_pid. Cannot delete while in use." >&2
      return 1
    fi
    # Stale lock — remove it
    rm -f "$lock_file"
  fi

  if [[ ! -f "$record_file" ]]; then
    echo "ERROR: Session '$slug' not found" >&2
    return 1
  fi

  rm -f "$record_file"
  echo "Session '$slug' deleted"
}

smgr_list() {
  if [[ ! -d "$SMGR_SESSIONS_DIR" ]]; then
    echo "No sessions found."
    return 0
  fi

  local found=0
  for record_file in "$SMGR_SESSIONS_DIR"/*.json; do
    [[ -f "$record_file" ]] || continue
    found=1
    local slug
    slug=$(basename "$record_file" .json)
    local cli_id created_at last_used_at branch artifact_path
    cli_id=$(grep -o '"cli_session_id": *"[^"]*"' "$record_file" | head -1 | cut -d'"' -f4)
    created_at=$(grep -o '"created_at": *"[^"]*"' "$record_file" | head -1 | cut -d'"' -f4)
    last_used_at=$(grep -o '"last_used_at": *"[^"]*"' "$record_file" | head -1 | cut -d'"' -f4)
    branch=$(grep -o '"branch": *"[^"]*"' "$record_file" | head -1 | cut -d'"' -f4)
    artifact_path=$(grep -o '"artifact_path": *"[^"]*"' "$record_file" | head -1 | cut -d'"' -f4 || echo "")

    local status="healthy"
    local lock_file="$SMGR_SESSIONS_DIR/${slug}.lock"
    if [[ -f "$lock_file" ]]; then
      local lock_pid
      lock_pid=$(cut -d' ' -f1 "$lock_file")
      if kill -0 "$lock_pid" 2>/dev/null; then
        status="locked (PID $lock_pid)"
      else
        status="stale-lock"
      fi
    fi

    echo "  $slug"
    echo "    status:     $status"
    echo "    branch:     $branch"
    echo "    created:    $created_at"
    echo "    last used:  $last_used_at"
    if [[ -n "$artifact_path" ]]; then
      echo "    artifact:   $artifact_path"
    fi
    echo ""
  done

  if [[ "$found" -eq 0 ]]; then
    echo "No sessions found."
  fi
}

# --- Locking ---

smgr_lock() {
  local slug="${1:?}"
  local lock_file="$SMGR_SESSIONS_DIR/${slug}.lock"

  mkdir -p "$SMGR_SESSIONS_DIR"

  if [[ -f "$lock_file" ]]; then
    local lock_pid lock_time
    lock_pid=$(cut -d' ' -f1 "$lock_file")
    lock_time=$(cut -d' ' -f2 "$lock_file")

    if kill -0 "$lock_pid" 2>/dev/null; then
      echo "ERROR: Session '$slug' is in use by PID $lock_pid (locked at $(date -d @"$lock_time" 2>/dev/null || echo "$lock_time"))" >&2
      return 1
    fi

    # PID is dead — stale lock, reclaim
    echo "WARNING: Reclaiming stale lock from dead PID $lock_pid" >&2
    rm -f "$lock_file"
  fi

  echo "$$ $(date +%s)" > "$lock_file"
}

smgr_unlock() {
  local slug="${1:?}"
  local lock_file="$SMGR_SESSIONS_DIR/${slug}.lock"
  rm -f "$lock_file"
}
