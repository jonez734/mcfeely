PROJECT = mistermcfeely
MEDIA = /run/media/jam/BEA6-BBCE/work/$(PROJECT)/

VERSION = $(shell date +%Y%m%d%H%M)

PYTHON ?= python3.12

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
	@echo "  install-venv       Create venv and install mistermcfeely wheel at /var/lib/postoffice/venv"
	@echo "  uninstall-venv     Remove /var/lib/postoffice/venv"
	@echo "  restorecon         Relabel venv binaries for SELinux (Fedora/RHEL)"
	@echo "  install-systemd    Copy mcfeely-authd.service to /usr/lib/systemd/system/ and daemon-reload"
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
	install -m 0644 $(SYSUSERS_SRC) $(SYSUSERS_DST)
	systemd-sysusers
	@echo "Created postoffice user and group via $(SYSUSERS_DST)"

uninstall-sysusers:
	-rm -f $(SYSUSERS_DST)
	@echo "Removed $(SYSUSERS_DST)"

TMPFILES_SRC = etc-postoffice/postoffice.tmpfiles
TMPFILES_DST = /usr/lib/tmpfiles.d/postoffice.conf

install-tmpfiles: install-sysusers
	install -m 0644 $(TMPFILES_SRC) $(TMPFILES_DST)
	systemd-tmpfiles --create
	@echo "Created directories via $(TMPFILES_DST)"

uninstall-tmpfiles:
	-rm -f $(TMPFILES_DST)
	@echo "Removed $(TMPFILES_DST)"

VENV_DIR = /var/lib/postoffice/venv

WHEEL_DIR = /tmp/$(PROJECT)-$$
BBSENGINE_DIR = $(CURDIR)/../bbsengine6/py
GETDATE_DIR = $(CURDIR)/../getdate_next

install-venv:
	@command -v sudo >/dev/null 2>&1 || { echo "Error: sudo required"; exit 1; }
	@sudo -u postoffice test -d "$(VENV_DIR)" || sudo -u postoffice $(PYTHON) -m venv "$(VENV_DIR)"
	sudo -u postoffice $(VENV_DIR)/bin/pip install --upgrade pip
	$(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true
	$(PYTHON) -m pip install --quiet --user build setuptools wheel
	mkdir -p $(WHEEL_DIR)
	rm -f $(WHEEL_DIR)/*.whl
	$(MAKE) -C $(BBSENGINE_DIR) version
	$(PYTHON) -m build --no-isolation --wheel --outdir $(WHEEL_DIR) $(GETDATE_DIR)
	$(PYTHON) -m build --no-isolation --wheel --outdir $(WHEEL_DIR) $(BBSENGINE_DIR)
	$(MAKE) version
	$(PYTHON) -m build --no-isolation --wheel --outdir $(WHEEL_DIR) $(CURDIR)
	sudo -u postoffice $(VENV_DIR)/bin/pip install $(WHEEL_DIR)/*.whl
	rm -rf $(WHEEL_DIR)
	@command -v semanage >/dev/null 2>&1 && \
		sudo semanage fcontext -a -t bin_t "$(VENV_DIR)/bin(/.*)?" 2>/dev/null || true
	@command -v restorecon >/dev/null 2>&1 && sudo restorecon -R $(VENV_DIR)/bin/ || true
	@echo "Installed $(PROJECT) into $(VENV_DIR)"

uninstall-venv:
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
	install -m 0644 $(UNIT_SRC) $(UNIT_DST)
	systemctl daemon-reload
	@echo "Installed $(UNIT_DST)"

uninstall-systemd:
	-systemctl stop mcfeely-authd 2>/dev/null
	-systemctl disable mcfeely-authd 2>/dev/null
	-rm -f $(UNIT_DST)
	-systemctl daemon-reload
	@echo "Removed $(UNIT_DST)"

MCFEELY_ETCDIR = /etc/postoffice
FACTORY_DIR = usr/share/factory/etc/postoffice
SASL_ETCDIR = /etc/sasl2
SASL_SYSCONFIG = /etc/sysconfig
PAM_ETCDIR = /etc/pam.d

install-etc:
	install -d $(MCFEELY_ETCDIR)
	install -m 0640 $(FACTORY_DIR)/mcfeely-authd.conf $(MCFEELY_ETCDIR)/mcfeely-authd.conf
	@echo "Installed $(MCFEELY_ETCDIR)/mcfeely-authd.conf from factory defaults"
	install -m 0640 etc-postoffice/saslauthd.conf $(SASL_ETCDIR)/saslauthd.conf
	[ -f /etc/debian_version ] && \
		install -m 0644 etc-postoffice/saslauthd.sysconfig /etc/default/saslauthd || \
		install -m 0644 etc-postoffice/saslauthd.sysconfig $(SASL_SYSCONFIG)/saslauthd
	install -m 0644 etc-postoffice/pam.d-saslauthd $(PAM_ETCDIR)/saslauthd
	@echo "Installed saslauthd support files"

uninstall-etc:
	-rm -f $(MCFEELY_ETCDIR)/mcfeely-authd.conf
	-rm -f $(SASL_ETCDIR)/saslauthd.conf
	[ -f /etc/debian_version ] && \
		rm -f /etc/default/saslauthd || \
		rm -f $(SASL_SYSCONFIG)/saslauthd
	-rm -f $(PAM_ETCDIR)/saslauthd
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
