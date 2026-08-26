CLAUDE_DIR   := $(HOME)/.claude
SKILLS_DIR   := $(CLAUDE_DIR)/skills
HOOKS_DIR    := $(CLAUDE_DIR)/hooks
SETTINGS     := $(CLAUDE_DIR)/settings.json
HOOK_SCRIPT  := enforce-python-pro-max.sh
HOOK_CMD     := $$HOME/.claude/hooks/$(HOOK_SCRIPT)

.PHONY: help install update-skill install-hook

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: update-skill install-hook ## Install the skill and the hook

update-skill: ## Copy python-pro-max into ~/.claude/skills/
	@mkdir -p "$(SKILLS_DIR)"
	cp -R ./python-pro-max "$(SKILLS_DIR)/"
	@echo "Updated $(SKILLS_DIR)/python-pro-max"

install-hook: ## Install the PreToolUse hook script and register it in settings.json
	@command -v jq >/dev/null || { echo "jq is required"; exit 1; }
	@mkdir -p "$(HOOKS_DIR)"
	cp ./hooks/$(HOOK_SCRIPT) "$(HOOKS_DIR)/$(HOOK_SCRIPT)"
	@chmod +x "$(HOOKS_DIR)/$(HOOK_SCRIPT)"
	@echo "Installed $(HOOKS_DIR)/$(HOOK_SCRIPT)"
	@if [ ! -f "$(SETTINGS)" ]; then echo '{}' > "$(SETTINGS)"; fi
	@if jq -e --arg cmd '$(HOOK_CMD)' \
		'[.hooks.PreToolUse[]?.hooks[]?.command] | any(. == $$cmd)' \
		"$(SETTINGS)" >/dev/null; then \
		echo "Hook already registered in $(SETTINGS)"; \
	else \
		cp "$(SETTINGS)" "$(SETTINGS).bak"; \
		jq --arg cmd '$(HOOK_CMD)' \
			'.hooks.PreToolUse = ((.hooks.PreToolUse // []) + [{ matcher: "Write|Edit", hooks: [{ type: "command", command: $$cmd }] }])' \
			"$(SETTINGS)" > "$(SETTINGS).tmp" \
			&& mv "$(SETTINGS).tmp" "$(SETTINGS)"; \
		echo "Registered hook in $(SETTINGS) (backup: $(SETTINGS).bak)"; \
	fi
