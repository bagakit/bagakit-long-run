SKILL_NAME := bagakit-long-run
BAGAKIT_HOME ?= $(HOME)/.bagakit
SKILL_DIR := $(BAGAKIT_HOME)/skills/$(SKILL_NAME)
PACKAGE := dist/$(SKILL_NAME).skill
AGENT_CLI ?= bagakit-agent
AGENT_FLAGS ?=

.PHONY: install-skill package-skill clean agent-locale

install-skill:
	rm -rf "$(SKILL_DIR)"
	mkdir -p "$(SKILL_DIR)"
	cp -R SKILL.md SKILL_PAYLOAD.json README.md references scripts "$(SKILL_DIR)/"
	find "$(SKILL_DIR)/scripts" -type f -name "*.sh" -exec chmod +x {} +
	chmod +x "$(SKILL_DIR)/scripts/long-run-features.py"
	chmod +x "$(SKILL_DIR)/scripts/long-run-execution.py"
	chmod +x "$(SKILL_DIR)/scripts/long-run-heartbeat.py"
	@echo "installed: $(SKILL_DIR)"

package-skill: clean
	mkdir -p dist
	zip -r "$(PACKAGE)" SKILL.md SKILL_PAYLOAD.json README.md references scripts >/dev/null
	@echo "packaged: $(PACKAGE)"

clean:
	rm -rf dist

agent-locale:
	@echo "BAGAKIT_HOME=$(PWD)/.bagakit"
	@echo "Running $(AGENT_CLI) with BAGAKIT_HOME=$(PWD)/.bagakit"
	$(AGENT_CLI) $(AGENT_FLAGS)
