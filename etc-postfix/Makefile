# Makefile for etc-postfix configuration deployment

TARGET ?= /tmp/staged-deploy
SYSTEM_ETC ?= /etc

.PHONY: all list install-staged install-system validate status clean help postmap-projects postmap-virtual

all: list

list:
	@echo "etc-postfix configuration files:"
	@find . -type f \( -name "*.cf" -o -name "*.script" -o -name "projects_*" \) 2>/dev/null | grep -v ".git" | sort

install-staged:
	@echo "Installing to $(TARGET)..."
	@mkdir -p $(TARGET)/postfix
	@cp -r postfix/* $(TARGET)/postfix/
	@echo "Done. Review in $(TARGET)"

install-system:
	@echo "Installing to system..."
	@mkdir -p $(SYSTEM_ETC)/postfix
	@cp -r postfix/* $(SYSTEM_ETC)/postfix/
	@echo "Done."
	@echo "Run: postmap /etc/postfix/virtual && newaliases"

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
	@echo "  list            - List config files"
	@echo "  install-staged  - Install to $(TARGET)"
	@echo "  install-system  - Install to $(SYSTEM_ETC)/postfix"
	@echo "  validate        - Validate config syntax"
	@echo "  status          - Show current system config"
	@echo "  postmap         - Generate .db files for hash maps"
	@echo "  postmap-projects - Generate projects_static.db"
	@echo "  postmap-virtual  - Generate virtual.db"
	@echo "  clean           - Clean staged files"