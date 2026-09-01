PROJECT = mistermcfeely
MEDIA = /run/media/jam/BEA6-BBCE/work/$(PROJECT)/

VERSION = $(shell date +%Y%m%d%H%M)

PYTHON ?= python3.12

# DEPLOY_UPGRADE is set by `deploytool --upgrade` (default true) and
# unset by `--no-upgrade`. When "1", every `pip install` in this
# Makefile (except `pip install --upgrade pip`, which always upgrades
# pip itself — stale pip breaks everything downstream) passes
# `--upgrade`. Empty = prior no-op-if-version-matches behavior.
DEPLOY_UPGRADE ?=
PIP_UPGRADE_FLAG := $(if $(filter 1,$(DEPLOY_UPGRADE)),--upgrade,)

.PHONY: all help clean backup version
.PHONY: install uninstall deploy
.PHONY: install-sysusers uninstall-sysusers
.PHONY: install-tmpfiles uninstall-tmpfiles
.PHONY: install-venv uninstall-venv restorecon
.PHONY: install-systemd uninstall-systemd
.PHONY: install-etc uninstall-etc

deploy: install

all: help

help:
	@echo "$(PROJECT) - Post Office email management for BBS"
	@echo ""
	@echo "Targets:"
	@echo "  install            Full install: sysusers + tmpfiles + venv + systemd + etc"
	@echo "  uninstall          Full uninstall"
	@echo "  deploy             Full install (alias for install)"
	@echo "  version            Stamp src/postoffice/_version.py with date + git hash"
	@echo "  clean              Remove build artifacts"
	@echo "  backup             Rsync project to $(MEDIA)"
	@echo ""
	@echo "  install-sysusers   Create postoffice user and group via systemd-sysusers"
	@echo "  uninstall-sysusers Remove sysusers.d/postoffice.conf"
	@echo "  install-tmpfiles   Create /var/lib/postoffice and /var/run/mcfeely-authd via systemd-tmpfiles"
	@echo "  uninstall-tmpfiles Remove tmpfiles.d/postoffice.conf"
	@echo "  install-venv       Install mistermcfeely wheel into shared venv at $(VENV_DIR)"
	@echo "  uninstall-venv     Remove $(VENV_DIR)"
	@echo "  restorecon         Relabel venv binaries for SELinux (Fedora/RHEL)"
	@echo "  install-systemd    Install mcfeely-authd.service (@VENV_DIR@ templated) and daemon-reload"
	@echo "  uninstall-systemd  Stop, disable, and remove the mcfeely-authd.service unit"
	@echo "  install-etc        Install mcfeely-authd.conf and saslauthd config files"
	@echo "  uninstall-etc      Remove installed config files"

version:
	@echo '__version__ = "0.0.1.dev$(VERSION)"' > src/postoffice/_version.py
	@echo '__datestamp__ = "$(VERSION)"' >> src/postoffice/_version.py
	@echo '__githash__ = "'`git log -1 --format='%H' 2>/dev/null | cut -c 1-16`'"' >> src/postoffice/_version.py
	@cat src/postoffice/_version.py

SYSUSERS_SRC = etc-postoffice/postoffice.sysusers
SYSUSERS_DST = /usr/lib/sysusers.d/postoffice.conf

install-sysusers:
	sudo rsync --chmod=0644 $(SYSUSERS_SRC) $(SYSUSERS_DST)
	sudo systemd-sysusers
	@echo "Created postoffice user and group via $(SYSUSERS_DST)"

uninstall-sysusers:
	-sudo rm -f $(SYSUSERS_DST)
	@echo "Removed $(SYSUSERS_DST)"

TMPFILES_SRC = etc-postoffice/postoffice.tmpfiles
TMPFILES_DST = /usr/lib/tmpfiles.d/postoffice.conf

install-tmpfiles: install-sysusers
	sudo rsync --chmod=0644 $(TMPFILES_SRC) $(TMPFILES_DST)
	sudo systemd-tmpfiles --create
	@echo "Created directories via $(TMPFILES_DST)"

uninstall-tmpfiles:
	-sudo rm -f $(TMPFILES_DST)
	@echo "Removed $(TMPFILES_DST)"

VENV_DIR ?= /var/lib/zoid6/venv
VENV_OWNER ?= zoid6
VENV_GROUP ?= zoid6
VENV_SHARED ?= /var/lib/zoid6/venv

WHEEL_DIR = /tmp/$(PROJECT)-$$
BBSENGINE_DIR = $(CURDIR)/../bbsengine6/py

install-venv:
	@command -v sudo >/dev/null 2>&1 || { echo "Error: sudo required"; exit 1; }
	@sudo -u $(VENV_OWNER) test -d "$(VENV_DIR)" || sudo -u $(VENV_OWNER) $(PYTHON) -m venv "$(VENV_DIR)"
	sudo -u $(VENV_OWNER) $(VENV_DIR)/bin/pip install --upgrade pip
	sudo -u $(VENV_OWNER) $(VENV_DIR)/bin/pip install $(PIP_UPGRADE_FLAG) --quiet build setuptools wheel
	mkdir -p $(WHEEL_DIR)
	rm -f $(WHEEL_DIR)/*.whl
	$(MAKE) -C $(BBSENGINE_DIR) version
	$(VENV_DIR)/bin/python -m build --no-isolation --wheel --outdir $(WHEEL_DIR) $(BBSENGINE_DIR)
	$(MAKE) version
	$(VENV_DIR)/bin/python -m build --no-isolation --wheel --outdir $(WHEEL_DIR) $(CURDIR)
	sudo -u $(VENV_OWNER) $(VENV_DIR)/bin/pip install $(PIP_UPGRADE_FLAG) $(WHEEL_DIR)/*.whl
	rm -rf $(WHEEL_DIR)
	@command -v semanage >/dev/null 2>&1 && \
		sudo semanage fcontext -a -t bin_t "$(VENV_DIR)/bin(/.*)?" 2>/dev/null || true
	@command -v restorecon >/dev/null 2>&1 && sudo restorecon -R $(VENV_DIR)/bin/ || true
	@echo "Installed $(PROJECT) into $(VENV_DIR)"

uninstall-venv:
	@if [ "$(VENV_DIR)" = "$(VENV_SHARED)" ] && [ -z "$(VENV_FORCE_UNINSTALL)" ]; then \
		echo "Error: $(VENV_DIR) is the shared zoid6 venv"; \
		echo "Removing it would break other services. Use 'make -C ../zoid6/src uninstall-venv' instead,"; \
		echo "or set VENV_FORCE_UNINSTALL=1 to override."; \
		exit 1; \
	fi
	-rm -rf $(VENV_DIR)
	@echo "Removed $(VENV_DIR)"

restorecon:
	@command -v semanage >/dev/null 2>&1 && \
		sudo semanage fcontext -a -t bin_t "$(VENV_DIR)/bin(/.*)?" 2>/dev/null || true
	sudo restorecon -R $(VENV_DIR)/bin/
	@echo "Relabeled $(VENV_DIR)/bin/ for SELinux"

UNIT_SRC = etc-postoffice/mcfeely-authd.service
UNIT_DST = /usr/lib/systemd/system/mcfeely-authd.service

install-systemd:
	sed 's|@VENV_DIR@|$(VENV_DIR)|g' $(UNIT_SRC) | sudo tee $(UNIT_DST) > /dev/null
	sudo chmod 0644 $(UNIT_DST)
	sudo chown root:root $(UNIT_DST)
	sudo systemctl daemon-reload
	@echo "Installed $(UNIT_DST)"

uninstall-systemd:
	-sudo systemctl stop mcfeely-authd 2>/dev/null
	-sudo systemctl disable mcfeely-authd 2>/dev/null
	-sudo rm -f $(UNIT_DST)
	-sudo systemctl daemon-reload
	@echo "Removed $(UNIT_DST)"

MCFEELY_ETCDIR = /etc/postoffice
FACTORY_DIR = usr/share/factory/etc/postoffice
SASL_ETCDIR = /etc/sasl2
SASL_SYSCONFIG = /etc/sysconfig
PAM_ETCDIR = /etc/pam.d

install-etc:
	sudo install -d $(MCFEELY_ETCDIR)
	sudo rsync --chmod=0640 $(FACTORY_DIR)/mcfeely-authd.conf $(MCFEELY_ETCDIR)/mcfeely-authd.conf
	@echo "Installed $(MCFEELY_ETCDIR)/mcfeely-authd.conf from factory defaults"
	sudo rsync --chmod=0640 etc-postoffice/saslauthd.conf $(SASL_ETCDIR)/saslauthd.conf
	[ -f /etc/debian_version ] && \
		sudo rsync --chmod=0644 etc-postoffice/saslauthd.sysconfig /etc/default/saslauthd || \
		sudo rsync --chmod=0644 etc-postoffice/saslauthd.sysconfig $(SASL_SYSCONFIG)/saslauthd
	sudo rsync --chmod=0644 etc-postoffice/pam.d-saslauthd $(PAM_ETCDIR)/saslauthd
	@echo "Installed saslauthd support files"

uninstall-etc:
	-sudo rm -f $(MCFEELY_ETCDIR)/mcfeely-authd.conf
	-sudo rm -f $(SASL_ETCDIR)/saslauthd.conf
	[ -f /etc/debian_version ] && \
		sudo rm -f /etc/default/saslauthd || \
		sudo rm -f $(SASL_SYSCONFIG)/saslauthd
	-sudo rm -f $(PAM_ETCDIR)/saslauthd
	@echo "Removed mcfeely-authd and saslauthd config files"

install: install-sysusers install-tmpfiles install-venv install-systemd install-etc
	@echo "$(PROJECT) fully installed. Run: systemctl enable --now mcfeely-authd"

uninstall: uninstall-systemd uninstall-venv uninstall-tmpfiles uninstall-sysusers
	@echo "$(PROJECT) fully uninstalled"

clean:
	-rm -rf build dist
	-rm -rf *.egg-info
	-find . -type d -name __pycache__ -exec rm -rf {} +
	-find . -type d -name .pytest_cache -exec rm -rf {} +
	-find . -type d -name .ruff_cache -exec rm -rf {} +
	-find . -type d -name .mypy_cache -exec rm -rf {} +
	$(MAKE) -C src clean
	$(MAKE) -C sql clean

backup:
	rsync --recursive --verbose --exclude=.venv . $(MEDIA)
