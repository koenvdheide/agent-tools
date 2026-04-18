#!/usr/bin/env bash
# test-session-mgr.sh — tests for session-mgr.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/session-mgr.sh"

PASS=0
FAIL=0
test_name=""

assert_eq() {
  if [[ "$1" == "$2" ]]; then
    ((++PASS))
  else
    ((++FAIL))
    echo "FAIL [$test_name]: expected '$2', got '$1'"
  fi
}

assert_exit() {
  local expected_exit="$1"; shift
  local actual_exit=0
  "$@" >/dev/null 2>&1 || actual_exit=$?
  if [[ "$actual_exit" -eq "$expected_exit" ]]; then
    ((++PASS))
  else
    ((++FAIL))
    echo "FAIL [$test_name]: expected exit $expected_exit, got $actual_exit"
  fi
}

# Setup temp dir
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# --- validate-slug tests ---
test_name="validate-slug: lowercase passthrough"
assert_eq "$(smgr_validate_slug "my-session")" "my-session"

test_name="validate-slug: uppercase normalized"
assert_eq "$(smgr_validate_slug "My-Session")" "my-session"

test_name="validate-slug: rejects spaces"
assert_exit 1 smgr_validate_slug "my session"

test_name="validate-slug: rejects underscores"
assert_exit 1 smgr_validate_slug "my_session"

test_name="validate-slug: rejects reserved name CON"
assert_exit 1 smgr_validate_slug "con"

test_name="validate-slug: rejects reserved name NUL"
assert_exit 1 smgr_validate_slug "NUL"

test_name="validate-slug: rejects >64 chars"
LONG_SLUG=$(printf 'a%.0s' {1..65})
assert_exit 1 smgr_validate_slug "$LONG_SLUG"

test_name="validate-slug: accepts 64 chars"
EXACT_SLUG=$(printf 'a%.0s' {1..64})
assert_eq "$(smgr_validate_slug "$EXACT_SLUG")" "$EXACT_SLUG"

# --- create/lookup tests ---
export SMGR_SESSIONS_DIR="$TEST_DIR/sessions"

test_name="create: creates record"
smgr_create "test-session" "uuid-123" "" >/dev/null
assert_eq "$(smgr_lookup "test-session")" "uuid-123"

test_name="create: fails on duplicate"
assert_exit 1 smgr_create "test-session" "uuid-456" ""

test_name="lookup: fails on missing"
assert_exit 1 smgr_lookup "nonexistent"

test_name="create: stores artifact path"
smgr_create "with-artifact" "uuid-789" "/path/to/file.md" >/dev/null
result=$(cat "$TEST_DIR/sessions/with-artifact.json")
echo "$result" | grep -q '"/path/to/file.md"'
assert_eq "$?" "0"

# --- update tests ---
test_name="update: updates last_used_at"
sleep 1
OLD_TIME=$(grep -o '"last_used_at":"[^"]*"' "$TEST_DIR/sessions/test-session.json")
smgr_update "test-session" >/dev/null
NEW_TIME=$(grep -o '"last_used_at":"[^"]*"' "$TEST_DIR/sessions/test-session.json")
if [[ "$OLD_TIME" != "$NEW_TIME" ]]; then ((++PASS)); else ((++FAIL)); echo "FAIL [$test_name]: time not updated"; fi

# --- update artifact tests ---
test_name="update-artifact: adds artifact to session without one"
smgr_update_artifact "test-session" "/new/artifact.md" >/dev/null
result=$(grep -o '"artifact_path": *"[^"]*"' "$TEST_DIR/sessions/test-session.json" | cut -d'"' -f4)
assert_eq "$result" "/new/artifact.md"

test_name="update-artifact: replaces existing artifact"
smgr_update_artifact "with-artifact" "/updated/path.md" >/dev/null
result=$(grep -o '"artifact_path": *"[^"]*"' "$TEST_DIR/sessions/with-artifact.json" | cut -d'"' -f4)
assert_eq "$result" "/updated/path.md"

# --- lock tests ---
test_name="lock: acquires lock"
smgr_lock "test-session" >/dev/null
assert_eq "$(test -f "$TEST_DIR/sessions/test-session.lock" && echo yes)" "yes"

test_name="lock: fails on live lock"
assert_exit 1 smgr_lock "test-session"

test_name="unlock: releases lock"
smgr_unlock "test-session" >/dev/null
assert_eq "$(test -f "$TEST_DIR/sessions/test-session.lock" && echo yes || echo no)" "no"

# --- stale lock detection ---
test_name="lock: reclaims stale lock (dead PID)"
echo "99999999 $(date +%s)" > "$TEST_DIR/sessions/test-session.lock"
smgr_lock "test-session" >/dev/null 2>&1
LOCK_PID=$(cut -d' ' -f1 "$TEST_DIR/sessions/test-session.lock")
assert_eq "$LOCK_PID" "$$"
smgr_unlock "test-session" >/dev/null

# --- delete tests ---
test_name="delete: removes record and stale lock"
echo "99999999 $(date +%s)" > "$TEST_DIR/sessions/test-session.lock"
smgr_delete "test-session" >/dev/null
assert_eq "$(test -f "$TEST_DIR/sessions/test-session.json" && echo yes || echo no)" "no"
assert_eq "$(test -f "$TEST_DIR/sessions/test-session.lock" && echo yes || echo no)" "no"

test_name="delete: fails on live lock"
smgr_create "locked-session" "uuid-locked" "" >/dev/null
smgr_lock "locked-session" >/dev/null
assert_exit 1 smgr_delete "locked-session"
smgr_unlock "locked-session" >/dev/null
smgr_delete "locked-session" >/dev/null

# --- list tests ---
test_name="list: shows sessions"
smgr_create "list-test-1" "uuid-l1" "" >/dev/null
smgr_create "list-test-2" "uuid-l2" "/some/path.md" >/dev/null
LIST_OUTPUT=$(smgr_list)
echo "$LIST_OUTPUT" | grep -q "list-test-1"
assert_eq "$?" "0"
echo "$LIST_OUTPUT" | grep -q "list-test-2"
assert_eq "$?" "0"

# --- Report ---
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then exit 1; fi
