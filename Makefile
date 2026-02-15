SKILL_NAME := bagakit-long-run
CODEX_HOME ?= $(HOME)/.codex
SKILL_DIR := $(CODEX_HOME)/skills/$(SKILL_NAME)
PACKAGE := dist/$(SKILL_NAME).skill

.PHONY: install-skill package-skill clean codex-locale

install-skill:
	rm -rf "$(SKILL_DIR)"
	mkdir -p "$(SKILL_DIR)"
	cp -R SKILL.md README.md references scripts "$(SKILL_DIR)/"
	find "$(SKILL_DIR)/scripts" -type f -name "*.sh" -exec chmod +x {} +
	chmod +x "$(SKILL_DIR)/scripts/bagakit_long_run_features.py"
	@echo "installed: $(SKILL_DIR)"

package-skill: clean
	mkdir -p dist
	zip -r "$(PACKAGE)" SKILL.md README.md references scripts >/dev/null
	@echo "packaged: $(PACKAGE)"

clean:
	rm -rf dist

codex-locale:
	@echo "CODEX_HOME=$(PWD)/.codex"
	@echo "Running codex with CODEX_HOME=$(PWD)/.codex"
	codex -m gpt-5.3-codex -c model_reasoning_effort="xhigh" -c model_reasoning_summary_format=experimental --search --dangerously-bypass-approvals-and-sandbox
