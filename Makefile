PROJECT = mistermcfeely
MEDIA = /run/media/jam/BEA6-BBCE/work/$(PROJECT)/

VERSION = $(shell date +%Y%m%d%H%M)

PYTHON ?= python3.12
PIP ?= $(PYTHON) -m pip

# Local wheel output directory. Defaults to `dist/` (relative to the
# project root) so wheels land in the project's own tree and the
# operator doesn't need to be in the `repo` group to write them.
# Override with OUTDIR= on the make command line or in the shell env
# to write elsewhere (e.g. the cross-project /srv/repo/mistermcfeely/
# location used by bed/casino/zoid6/bbsengine6).
OUTDIR ?= dist/
WHEEL_PACKAGES := bbsengine6 mistermcfeely

DEPLOY_EDITABLE ?=
DEPLOY_WITH_DEPS ?=
DEPLOY_UPGRADE ?=
PIP_UPGRADE_FLAG := $(if $(filter 1,$(DEPLOY_UPGRADE)),--upgrade,)

OPERATOR_VENV ?= $(or $(VIRTUAL_ENV),$(sys.prefix))
OPERATOR_PYTHON ?= $(if $(VIRTUAL_ENV),$(VIRTUAL_ENV)/bin/python,$(PYTHON))

WHEEL_DIR = /tmp/$(PROJECT)-$$
BBSENGINE_DIR = $(CURDIR)/../bbsengine6/py

.PHONY: all help clean deep-clean backup version build
.PHONY: install uninstall
.PHONY: install-sysusers uninstall-sysusers
.PHONY: install-tmpfiles uninstall-tmpfiles
.PHONY: install-venv uninstall-venv restorecon
.PHONY: install-systemd uninstall-systemd
.PHONY: install-etc uninstall-etc
.PHONY: deploy-tui deploy-prod

all: help

help:
	@echo "$(PROJECT) - Post Office email management for BBS"
	@echo ""
	@echo "Targets:"
	@echo "  install            Full install: sysusers + tmpfiles + venv + systemd + etc"
	@echo "  uninstall          Full uninstall"
	@echo "  deploy-tui         Operator-side (no sudo): install into \$$VIRTUAL_ENV (active venv)"
	@echo "  deploy-prod        Sudo umbrella: sysusers + tmpfiles + systemd + etc + wheel install"
	@echo "  build              Build bbsengine6 + mistermcfeely wheels into \$$(OUTDIR) (default: dist/)"
	@echo "  version            Stamp src/postoffice/_version.py with date + git hash"
	@echo "  clean              Remove build artifacts (operator-owned only; safe, non-interactive)"
	@echo "  deep-clean         Like clean, plus renames foreign-owned build/ to build.to_remove.<pid>"
	@echo "                     (operator can't rm-rf foreign-owned trees; needs privileged cleanup)"
	@echo "  backup             Rsync project to $(MEDIA)"
	@echo ""
	@echo "  install-sysusers   Create postoffice user and group via systemd-sysusers"
	@echo "  uninstall-sysusers Remove sysusers.d/postoffice.conf"
	@echo "  install-tmpfiles   Create /var/lib/postoffice and /var/run/mcfeely-authd via systemd-tmpfiles"
	@echo "  uninstall-tmpfiles Remove tmpfiles.d/postoffice.conf"
	@echo "  install-venv       Build bbsengine6 + mistermcfeely wheels and pip install into \$$VIRTUAL_ENV"
	@echo "  uninstall-venv     N/A — wheel installs are removed by 'pip uninstall' (no shared venv)"
	@echo "  restorecon         Relabel venv binaries for SELinux (Fedora/RHEL)"
	@echo "  install-systemd    Install mcfeely-authd.service and daemon-reload"
	@echo "  uninstall-systemd  Stop, disable, and remove the mcfeely-authd.service unit"
	@echo "  install-etc        Install mcfeely-authd.conf and saslauthd config files"
	@echo "  uninstall-etc      Remove installed config files"
	@echo ""
	@echo "Environment variables:"
	@echo "  OUTDIR=/path/to/   Wheel output directory (default: dist/, i.e. local project tree)."
	@echo "                     Override to write to the cross-project /srv/repo/mistermcfeely/"
	@echo "                     location when /srv/repo/ is writable (e.g. operator in repo group)."
	@echo "  DEPLOY_EDITABLE=1  deploy-tui installs editable from src/ (set by 'deploytool --editable')"
	@echo "  DEPLOY_WITH_DEPS=1 precheck-editable warns instead of hard-failing (set by 'deploytool --with-deps')"
	@echo "  DEPLOY_UPGRADE=1   pass --upgrade to pip install (default; set by 'deploytool --upgrade')"
	@echo "  VIRTUAL_ENV        target venv for pip install (auto-detected from active shell)"

version:
	@echo '__version__ = "0.0.1.dev$(VERSION)"' > src/postoffice/_version.py
	@echo '__datestamp__ = "$(VERSION)"' >> src/postoffice/_version.py
	@echo '__githash__ = "'`git log -1 --format='%H' 2>/dev/null | cut -c 1-16`'"' >> src/postoffice/_version.py
	@cat src/postoffice/_version.py

# Make sure $(1)/build/ exists with mode 1775 (sticky + rwxrwxr-x) before
# invoking `python -m build`. Mirrors bed/Makefile PREPARE_BUILD; see
# TODO.md for the cross-project standardization rationale.
#
# When the existing `build/` is foreign-owned, rename it to a unique
# `build.stale.XXXXXX` suffix (each invocation gets its own suffix via
# `mktemp -u`) so the `mv` is a rename (atomic, only needs write on
# the parent — works through a foreign-owned sticky bit) rather than
# a move-into (which fails on the second run because the first run
# created the destination dir).
PREPARE_BUILD = \
	if [ -d $(1)/build ] && [ ! -O $(1)/build ]; then \
		STALE_SUFFIX=$$(mktemp -u -p $(1) build.stale.XXXXXX) && \
			mv $(1)/build "$$STALE_SUFFIX" 2>/dev/null || true; \
	fi; \
	mkdir -p $(1)/build && chmod g-s,+t $(1)/build

# Build bbsengine6 + mistermcfeely wheels into $(OUTDIR). Operator-side
# (no sudo) — the wheels are inputs to both deploy-tui and deploy-prod.
# Mirrors the bed/casino/zoid6 build target shape.
build: clean version
	$(call PREPARE_BUILD,$(BBSENGINE_DIR))
	$(call PREPARE_BUILD,$(CURDIR))
	@mkdir -p $(OUTDIR)
	$(PYTHON) -m build --no-isolation --wheel --outdir $(OUTDIR) $(BBSENGINE_DIR)
	$(PYTHON) -m build --no-isolation --wheel --outdir $(OUTDIR) $(CURDIR)
	@echo "$(PROJECT) wheels built into $(OUTDIR)"

# Hard-fail precondition for `deploy-tui` (non-editable branch).
#
# PEP 660 / setuptools' `__editable___<pkg>_*_finder` `.pth` hook
# makes an editable install of `<pkg>` in a venv mutually exclusive
# with a wheel install of the same `<pkg>` into the same venv.
# Mirrors bbsengine6/py/src/Makefile precheck-editable; iterates
# over $(WHEEL_PACKAGES) so a single macro call covers the batch.
#
# The macro runs from operator context (no sudo). It reads
# dist-info/direct_url.json directly per PEP 610 (no `pip show`,
# which would need sudo to query a foreign-owned venv). When the
# target is the operator's active venv, this stays no-sudo end-to-end.
#
# Behavior branches on DEPLOY_WITH_DEPS:
#   - unset (default): hard-fail with the two clean remedies.
#   - 1: warn-and-proceed; verify-install becomes the correctness check.
define precheck-editable
	@for pkg in $(WHEEL_PACKAGES); do \
		DISTINFO_DIR=$$($(OPERATOR_PYTHON) -c "import sysconfig,glob,os; \
purelib=sysconfig.get_paths()['purelib']; \
candidates=glob.glob(os.path.join(purelib, '$$pkg-*.dist-info')); \
print(candidates[0] if candidates else '')" 2>/dev/null); \
		if [ -z "$$DISTINFO_DIR" ]; then continue; fi; \
		DIRECT_URL="$$DISTINFO_DIR/direct_url.json"; \
		if [ -f "$$DIRECT_URL" ] && grep -q '"editable": true' "$$DIRECT_URL"; then \
			EDITABLE_SRC=$$($(OPERATOR_PYTHON) -c "import json; \
print(json.load(open('$$DIRECT_URL')).get('url',''))" 2>/dev/null); \
			if [ "$(DEPLOY_WITH_DEPS)" = "1" ]; then \
				echo "deploy-tui: WARNING: $$pkg is installed editable in the operator venv" >&2; \
				echo "  editable source: $$EDITABLE_SRC" >&2; \
				echo >&2; \
				echo "DEPLOY_WITH_DEPS=1 is set (deploy --with-deps), so precheck-editable is" >&2; \
				echo "proceeding with the wheel install. If the editable .pth finder shadows it" >&2; \
				echo "(the common case), verify-install will abort with a precise diagnosis." >&2; \
			else \
				echo "deploy-tui: $$pkg is installed editable in the operator venv" >&2; \
				echo "  editable source: $$EDITABLE_SRC" >&2; \
				echo >&2; \
				echo "Editable and wheel installs of the same distribution name can't coexist in" >&2; \
				echo "one venv (the editable .pth finder shadows subsequent wheel installs), so" >&2; \
				echo "this Makefile refuses to silently no-op. Pick one:" >&2; \
				echo >&2; \
				echo "  1) Stay in editable mode: deploy --editable mistermcfeely.tui" >&2; \
				echo "  2) Switch to wheel mode: pip uninstall $$pkg && deploy mistermcfeely.tui" >&2; \
				echo "  3) Override for this run only: deploy --with-deps mistermcfeely.tui" >&2; \
				echo >&2; \
				echo "(The Makefile intentionally doesn't 'fix' this for you — see" >&2; \
				echo " precheck-editable in mistermcfeely/Makefile.)" >&2; \
				exit 1; \
			fi; \
		fi; \
	done
endef

# Post-install triple-check (filename / METADATA / dist-info Version).
# Catches silent no-ops where `pip install <wheel>` exits 0 without
# replacing the prior install. Runs from operator context (no sudo),
# reading dist-info/METADATA directly per PEP 376. Editable installs
# (DEPLOY_EDITABLE=1) skip this — pip show for an editable install
# reports the source-tree version, not a wheel version.
#
# Takes the wheel directory as $(1) (default: $(OUTDIR)). Iterates
# over $(WHEEL_PACKAGES) so the macro covers the batch install.
define verify-install
	@for pkg in $(WHEEL_PACKAGES); do \
		WHEEL=$$(ls -t $(1)/$$pkg-*.whl 2>/dev/null | head -1); \
		if [ -z "$$WHEEL" ]; then \
			echo "verify-install: no wheel matching $$pkg-*.whl in $(1)" >&2; \
			exit 1; \
		fi; \
		EXPECTED_FROM_FILENAME=$$(basename "$$WHEEL" | sed -E 's/^$$pkg-(.+)-py3-none-any\.whl$$/\1/'); \
		EXPECTED_FROM_METADATA=$$(unzip -p "$$WHEEL" '*/METADATA' 2>/dev/null | awk -F': ' '/^Version: / {print $$2; exit}'); \
		echo "=== verify-install ($$pkg) ==="; \
		echo "  wheel filename Version: $$EXPECTED_FROM_FILENAME"; \
		echo "  wheel METADATA Version: $$EXPECTED_FROM_METADATA"; \
		DISTINFO_META=$$($(OPERATOR_PYTHON) -c "import sysconfig,glob,os; \
purelib=sysconfig.get_paths()['purelib']; \
candidates=glob.glob(os.path.join(purelib, '$$pkg-*.dist-info', 'METADATA')); \
print(candidates[0] if candidates else '')" 2>/dev/null); \
		if [ -z "$$DISTINFO_META" ] || [ ! -r "$$DISTINFO_META" ]; then \
			echo "verify-install FAILED: $$pkg dist-info/METADATA not readable at $$DISTINFO_META" >&2; \
			exit 1; \
		fi; \
		INSTALLED=$$(awk -F': ' '/^Version: / {print $$2; exit}' "$$DISTINFO_META"); \
		echo "  dist-info Version:    $$INSTALLED"; \
		if [ "$$INSTALLED" != "$$EXPECTED_FROM_FILENAME" ] \
			|| [ "$$INSTALLED" != "$$EXPECTED_FROM_METADATA" ]; then \
			echo "verify-install FAILED: $$WHEEL was installed but dist-info METADATA does not agree" >&2; \
			echo "  expected filename:  $$EXPECTED_FROM_FILENAME" >&2; \
			echo "  expected METADATA:  $$EXPECTED_FROM_METADATA" >&2; \
			echo "  dist-info Version:  $$INSTALLED" >&2; \
			exit 1; \
		fi; \
		echo "verify-install OK: dist-info reports $$INSTALLED"; \
	done
endef

# Operator-side install path (no sudo). Builds wheels into $(OUTDIR),
# then either installs editable from source or installs the freshly-
# built wheel into the operator's active venv. Mirrors casino.tui /
# bbsengine6.tui.
deploy-tui: build
ifeq ($(DEPLOY_EDITABLE),1)
	$(PIP) install $(PIP_UPGRADE_FLAG) --no-cache-dir -e .
	-rm -rf *.egg-info
else
	@$(precheck-editable)
	@WHEEL=$$(ls -t $(OUTDIR)/$(PROJECT)-*.whl 2>/dev/null | head -1); \
	if [ -z "$$WHEEL" ]; then \
		echo "no wheel found in $(OUTDIR); run \`make build\` first" >&2; \
		exit 1; \
	fi; \
	echo "installing $$WHEEL into $$(realpath $(VIRTUAL_ENV) 2>/dev/null || echo $$VIRTUAL_ENV)"; \
	$(PIP) install $(PIP_UPGRADE_FLAG) --no-cache-dir "$$WHEEL"
	@$(call verify-install,$(OUTDIR))
endif
	@echo "$(PROJECT) installed into operator venv"

# Sudo umbrella — everything that needs sudo (sysusers, tmpfiles,
# systemd, /etc config) plus the wheel install into the operator's
# active venv. Forward DEPLOY_EDITABLE / DEPLOY_WITH_DEPS /
# DEPLOY_UPGRADE so the operator's CLI choices propagate.
deploy-prod:
	$(MAKE) install DEPLOY_EDITABLE=$(DEPLOY_EDITABLE) DEPLOY_WITH_DEPS=$(DEPLOY_WITH_DEPS) DEPLOY_UPGRADE=$(DEPLOY_UPGRADE)
	@echo "$(PROJECT) installed (production)"

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

install-venv:
	@mkdir -p $(WHEEL_DIR)
	@rm -f $(WHEEL_DIR)/*.whl
	$(MAKE) -C $(BBSENGINE_DIR) version
	$(call PREPARE_BUILD,$(BBSENGINE_DIR))
	$(PYTHON) -m build --no-isolation --wheel --outdir $(WHEEL_DIR) $(BBSENGINE_DIR)
	$(MAKE) version
	$(call PREPARE_BUILD,$(CURDIR))
	$(PYTHON) -m build --no-isolation --wheel --outdir $(WHEEL_DIR) $(CURDIR)
	@$(precheck-editable)
	$(PIP) install $(PIP_UPGRADE_FLAG) $(WHEEL_DIR)/*.whl
	@$(call verify-install,$(WHEEL_DIR))
	rm -rf $(WHEEL_DIR)
	@echo "Installed $(PROJECT) wheel into $(OPERATOR_VENV)"

uninstall-venv:
	@echo "$(PROJECT) installs into the operator venv (\$$VIRTUAL_ENV / sys.prefix)."
	@echo "Remove via: $(PIP) uninstall mistermcfeely bbsengine6"
	@echo "(This Makefile does not maintain a per-project venv directory.)"

restorecon:
	@if [ -n "$(VIRTUAL_ENV)" ]; then \
		command -v semanage >/dev/null 2>&1 && \
			sudo semanage fcontext -a -t bin_t "$(VIRTUAL_ENV)/bin(/.*)?" 2>/dev/null || true; \
		command -v restorecon >/dev/null 2>&1 && sudo restorecon -R $(VIRTUAL_ENV)/bin/ || true; \
		echo "Relabeled $(VIRTUAL_ENV)/bin/ for SELinux"; \
	else \
		echo "restorecon: VIRTUAL_ENV not set; skipping"; \
	fi

UNIT_SRC = etc-postoffice/mcfeely-authd.service
UNIT_DST = /usr/lib/systemd/system/mcfeely-authd.service

install-systemd:
	sed 's|@VENV_DIR@|$(OPERATOR_VENV)|g' $(UNIT_SRC) | sudo tee $(UNIT_DST) > /dev/null
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
		-sudo rm -f /etc/default/saslauthd || \
		-sudo rm -f $(SASL_SYSCONFIG)/saslauthd
	-sudo rm -f $(PAM_ETCDIR)/saslauthd
	@echo "Removed mcfeely-authd and saslauthd config files"

install: build install-sysusers install-tmpfiles install-venv install-systemd install-etc
	@echo "$(PROJECT) fully installed. Run: systemctl enable --now mcfeely-authd"

uninstall: uninstall-systemd uninstall-venv uninstall-tmpfiles uninstall-sysusers uninstall-etc
	@echo "$(PROJECT) fully uninstalled"

clean:
	-rm -rf build dist
	-rm -rf *.egg-info
	-find . -type d -name __pycache__ -exec rm -rf {} +
	-find . -type d -name .pytest_cache -exec rm -rf {} +
	-find . -type d -name .ruff_cache -exec rm -rf {} +
	-find . -type d -name .mypy_cache -exec rm -rf {} +
	-rm -rf build.stale.* build.old.*
	-rm -rf *.egg-info.old.* *.egg-info.stale.*
	$(MAKE) -C src clean
	$(MAKE) -C sql clean

# deep-clean: the same as `clean` PLUS tries to remove foreign-owned
# build/ directories (those created by another user / under a
# different login) that `clean` can't rm-rf because the files inside
# are not owned by the operator. Each `build/` is renamed to
# `build.to_remove.<pid>` first (cheap; rename only needs write on
# the parent dir), and the actual rm-rf of the renamed tree is left
# to a cron / cleanup script that runs as a privileged user. This
# keeps the operator's `make` flow non-interactive while still
# surfacing the foreign-owned dirs in a predictable place.
deep-clean: clean
	@for d in build build.stale.* build.old.*; do \
		if [ -e "$$d" ] && [ ! -O "$$d" ]; then \
			TARGET="$${d}.to_remove.$$$$"; \
			echo "deep-clean: foreign-owned $$d, renaming to $$TARGET (operator can't rm-rf; needs privileged cleanup)"; \
			mv "$$d" "$$TARGET" 2>/dev/null || true; \
		fi; \
	done

backup:
	rsync --recursive --verbose --exclude=.venv . $(MEDIA)
