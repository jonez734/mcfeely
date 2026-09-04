# Makefile for etc-postfix configuration deployment

TARGET ?= /tmp/staged-deploy
SYSTEM_ETC ?= /etc

# Auto-run postmap after install-system / install-staged so operators
# don't ship configs without their hash database files. Set AUTO_POSTMAP=0
# to opt out for unusual deployment flows.
AUTO_POSTMAP ?= 1

# Auto-chown root:root and chmod 0644 on installed configs and .db
# files. Set AUTO_FIXUP=0 if your packaging flow already sets perms.
AUTO_FIXUP ?= 1

# Auto-run postfix check after install-system to surface syntax
# errors before the first reload. Set AUTO_VALIDATE=0 to skip.
AUTO_VALIDATE ?= 1

# Name of the Postfix hash-map source files we generate .db from.
POSTMAP_SOURCES = postfix/virtual postfix/projects_static

.PHONY: all list install-staged install-system validate status clean help postmap-projects postmap-virtual postmap install-cyrus-runtime verify-postfix

all: list

list:
	@echo "etc-postfix configuration files:"
	@find . -type f \( -name "*.cf" -o -name "*.script" -o -name "projects_*" \) 2>/dev/null | grep -v ".git" | sort

# Common snippet: chown root:root + chmod 0644 on installed configs.
# Used by both install-staged (no sudo) and install-system (sudo).
define fixup-config-perms
	@chown -R root:root $(1) 2>/dev/null || sudo chown -R root:root $(1); \
	chmod 0644 $(1)/main.cf $(1)/master.cf 2>/dev/null || sudo chmod 0644 $(1)/main.cf $(1)/master.cf; \
	for src in $(POSTMAP_SOURCES); do \
		base=$$(basename $$src); \
		if [ -f "$(1)/$$base" ]; then \
			chown root:root "$(1)/$$base" 2>/dev/null || sudo chown root:root "$(1)/$$base"; \
			chmod 0644 "$(1)/$$base" 2>/dev/null || sudo chmod 0644 "$(1)/$$base"; \
		fi; \
		if [ -f "$(1)/$$base.db" ]; then \
			chown root:root "$(1)/$$base.db" 2>/dev/null || sudo chown root:root "$(1)/$$base.db"; \
			chmod 0644 "$(1)/$$base.db" 2>/dev/null || sudo chmod 0644 "$(1)/$$base.db"; \
		fi; \
	done
endef

# Common snippet: postmap each source file (and update its .db mtime).
# Used by both install-staged (no sudo) and install-system (sudo).
define run-postmap
	@cd $(1) && for src in $(POSTMAP_SOURCES); do \
		base=$$(basename $$src); \
		if [ -f "$$base" ]; then \
			postmap "$$base" 2>/dev/null || sudo postmap "$$base"; \
		fi; \
	done
endef

install-staged:
	@echo "Installing to $(TARGET)..."
	@mkdir -p $(TARGET)/postfix
	@cp -r postfix/* $(TARGET)/postfix/
ifeq ($(AUTO_POSTMAP),1)
	$(call run-postmap,$(TARGET)/postfix)
	@echo "postmap: regenerated hash databases in $(TARGET)/postfix"
endif
ifeq ($(AUTO_FIXUP),1)
	$(call fixup-config-perms,$(TARGET)/postfix)
endif
	@echo "Done. Review in $(TARGET)"

install-system:
	@echo "Installing to system..."
	@mkdir -p $(SYSTEM_ETC)/postfix
	@sudo cp -r postfix/* $(SYSTEM_ETC)/postfix/
ifeq ($(AUTO_POSTMAP),1)
	$(call run-postmap,$(SYSTEM_ETC)/postfix)
	@echo "postmap: regenerated hash databases in $(SYSTEM_ETC)/postfix"
endif
ifeq ($(AUTO_FIXUP),1)
	$(call fixup-config-perms,$(SYSTEM_ETC)/postfix)
endif
ifeq ($(AUTO_VALIDATE),1)
	@sudo postfix check 2>/dev/null && echo "postfix check: OK" || { echo "postfix check: FAILED" >&2; exit 1; }
endif
	@echo "Done."
	@echo "Run: newaliases && systemctl reload postfix"

validate:
	@echo "Validating Postfix config..."
	@postconf -c postfix -n 2>/dev/null && echo "main.cf: OK" || echo "main.cf: check failed"

status:
	@echo "=== Postfix ==="
	@postconf -n 2>/dev/null | grep mailbox_transport || echo "LMTP transport not configured"

postmap-projects:
	@echo "Generating projects_static.db..."
	@postmap hash:postfix/projects_static

postmap-virtual:
	@echo "Generating virtual.db..."
	@postmap hash:postfix/virtual

postmap: postmap-projects postmap-virtual

# Provisions /run/cyrus/socket so the LMTP transport in main.cf has
# somewhere to land. The distro cyrus-imapd package ships a tmpfiles
# file at /usr/lib/tmpfiles.d/cyrus-imapd.conf that already creates
# /run/cyrus/{socket,db,lock,proc}; if that file exists, this target
# is a no-op aside from confirming the directories are present.
#
# Use this target when:
#   - You're installing the postfix configs onto a box without the
#     cyrus-imapd package (e.g. a Postfix-only front-end relay).
#   - You're hand-rolling Cyrus without the distro package.
install-cyrus-runtime:
	@if [ -f /usr/lib/tmpfiles.d/cyrus-imapd.conf ]; then \
		echo "install-cyrus-runtime: /usr/lib/tmpfiles.d/cyrus-imapd.conf present"; \
		echo "  /run/cyrus/socket will be provisioned by systemd-tmpfiles on boot"; \
		if [ ! -d /run/cyrus/socket ]; then \
			echo "  WARNING: /run/cyrus/socket does not exist yet; run:" >&2; \
			echo "    sudo systemd-tmpfiles --create" >&2; \
			exit 1; \
		fi; \
		echo "  OK: /run/cyrus/socket exists"; \
	else \
		echo "install-cyrus-runtime: distro cyrus-imapd package not detected"; \
		echo "  creating /run/cyrus/socket by hand"; \
		sudo mkdir -p /run/cyrus/socket; \
		sudo chown cyrus:mail /run/cyrus /run/cyrus/socket; \
		sudo chmod 0750 /run/cyrus /run/cyrus/socket; \
		echo "  WARNING: these directories will not survive reboot." >&2; \
		echo "  Install a tmpfiles.d/ snippet, e.g.:" >&2; \
		echo "    echo 'd /run/cyrus/socket 0750 cyrus mail -' | sudo tee /etc/tmpfiles.d/cyrus-imapd-local.conf" >&2; \
		echo "    sudo systemd-tmpfiles --create" >&2; \
	fi

# Post-install sanity check. Verifies the installed main.cf has the
# LMTP transport line we expect and that the runtime socket dir is
# provisioned. Run after install-system.
verify-postfix:
	@echo "=== verify-postfix ==="
	@postconf -n 2>/dev/null | grep -q '^mailbox_transport' && echo "  mailbox_transport: configured" || { echo "  mailbox_transport: MISSING" >&2; exit 1; }
	@postconf -n 2>/dev/null | grep '^mailbox_transport' | sed 's/^/  /'
	@if [ -d /run/cyrus/socket ]; then \
		echo "  /run/cyrus/socket: present"; \
		ls -ld /run/cyrus/socket | sed 's/^/    /'; \
	else \
		echo "  /run/cyrus/socket: MISSING — run: make install-cyrus-runtime" >&2; \
		exit 1; \
	fi
	@sudo postfix check 2>/dev/null && echo "  postfix check: OK" || { echo "  postfix check: FAILED" >&2; exit 1; }

clean:
	rm -rf $(TARGET)
	rm -f postfix/projects_static.db postfix/virtual.db
	@(echo "Cleaned" )

help:
	@echo "etc-postfix - Stage Postfix configurations for LMTP/Cyrus deployment"
	@echo ""
	@echo "Note: Cyrus and Sieve configs are in ../etc-postoffice/"
	@echo ""
	@echo "Targets:"
	@echo "  list                  - List config files"
	@echo "  install-staged        - Install to $(TARGET) (with auto-postmap + fixup)"
	@echo "  install-system        - Install to $(SYSTEM_ETC)/postfix (with auto-postmap + fixup + validate)"
	@echo "  install-cyrus-runtime - Provision /run/cyrus/socket (no-op if distro cyrus-imapd is installed)"
	@echo "  verify-postfix        - Post-install sanity check (LMTP transport + socket dir + postfix check)"
	@echo "  validate              - Validate local config syntax (postconf -c postfix -n)"
	@echo "  status                - Show current system config"
	@echo "  postmap               - Generate .db files for hash maps"
	@echo "  postmap-projects      - Generate projects_static.db"
	@echo "  postmap-virtual       - Generate virtual.db"
	@echo "  clean                 - Clean staged files"
	@echo ""
	@echo "Variables (override on command line):"
	@echo "  TARGET=/path/         Staged install destination (default: /tmp/staged-deploy)"
	@echo "  SYSTEM_ETC=/path/     System etc prefix (default: /etc)"
	@echo "  AUTO_POSTMAP=0        Skip automatic postmap in install-* (default: 1)"
	@echo "  AUTO_FIXUP=0          Skip automatic chown/chmod in install-* (default: 1)"
	@echo "  AUTO_VALIDATE=0       Skip postfix check after install-system (default: 1)"
