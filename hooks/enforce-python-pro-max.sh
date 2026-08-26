#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

if [[ "$tool_name" =~ ^(Write|Edit)$ ]] && [[ "$file_path" == *.py ]]; then
  skill_path="$HOME/.claude/skills/python-pro-max/SKILL.md"

  if [[ -f "$skill_path" ]]; then
    skill_content=$(cat "$skill_path")
    context="Apply the python-pro-max skill conventions to this Python file:\n\n${skill_content}"
  else
    context="Reminder: apply the python-pro-max skill conventions (naming, typing, structure) to this Python file. (Warning: SKILL.md not found at $skill_path — check if it was moved.)"
  fi

  # No `permissionDecision` on purpose: this hook only injects the skill conventions. Returning
  # "allow" here would also grant the write outright, silently bypassing the permission prompt for
  # every .py file in every project. Omitting it leaves normal permission checking in place.
  jq -n --arg ctx "$context" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $ctx
    }
  }'
fi