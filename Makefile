PROJECT = mistermcfeely
MEDIA = /run/media/jam/BEA6-BBCE/work/$(PROJECT)/

VERSION = $(shell date +%Y%m%d%H%M)

PYTHON ?= python3.12

# Canonical cross-project OUTDIR. Wheel artifacts for both bbsengine6
# (a runtime dep) and mistermcfeely are published here so downstream
# consumers (deploy-tui, deploy-prod, other repos) can pick them up
# via `ls -t $(OUTDIR)/<pkg>-*.whl | head -1`. Mirrors
# bed/OUTDIR=/srv/repo/bed/, casino/OUTDIR=/srv/repo/casino/, etc.
OUTDIR = /srv/repo/$(PROJECT)/
# Per-build scratch dir. Kept distinct from OUTDIR so the published
# /srv/repo tree is never partially-populated mid-build. The build
# target (operator permissions, no sudo) writes here; the deploy-prod
# target copies wheels from OUTDIR (post-publish) into the shared
# zoid6 venv via sudo.
WHEEL_DIR = /tmp/$(PROJECT)-$$
BBSENGINE_DIR = $(CURDIR)/../bbsengine6/py

# Packages whose wheels land in $(OUTDIR)/$(PROJECT)-*.whl during a
# build. Precheck-editable and verify-install iterate over this list
# so a single macro covers the batch install (bbsengine6 wheel +
# mistermcfeely wheel) that deploy-venv writes into the shared zoid6
# venv. Adding a new transitive dep whose wheel is also installed by
# deploy-venv is a one-line change here.
WHEEL_PACKAGES := bbsengine6 mistermcfeely

# DEPLOY_EDITABLE is set by `deploytool --editable`. When set to 1,
# deploy-tui installs from the source tree (`pip install -e .`)
# instead of from the wheel in $(OUTDIR). Live edits to src/ become
# visible to the active venv without a rebuild. Mirrors the
# DEPLOY_EDITABLE shape in bbsengine6/py/src/Makefile,
# casino/Makefile, and zoidoffice/src/Makefile.
DEPLOY_EDITABLE ?=

# DEPLOY_WITH_DEPS is set by `deploytool --with-deps`. Empty by
# default. When set to 1, precheck-editable switches from hard-fail
# to warn-and-proceed for the editable-in-venv case: a `--with-deps`
# invocation semantically promises "rebuild the venv, no questions
# asked", so blocking on an editable install the operator may have
# placed there on purpose is wrong-headed. The verify-install macro
# then becomes the correctness contract — if the editable .pth finder
# shadows the wheel install, the dist-info Version check fails and
# the deploy aborts with a precise diagnosis. Without `--with-deps`,
# precheck-editable hard-fails (most operators are not consciously
# managing a mixed editable/wheel state).
DEPLOY_WITH_DEPS ?=

# DEPLOY_UPGRADE is set by `deploytool --upgrade` (default true) and
# unset by `--no-upgrade`. When "1", every `pip install` in this
# Makefile (except `pip install --upgrade pip`, which always upgrades
# pip itself — stale pip breaks everything downstream) passes
# `--upgrade`. Empty = prior no-op-if-version-matches behavior.
DEPLOY_UPGRADE ?=
PIP_UPGRADE_FLAG := $(if $(filter 1,$(DEPLOY_UPGRADE)),--upgrade,)

.PHONY: all help clean backup version
.PHONY: install uninstall deploy deploy-tui deploy-prod
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
	@echo "  deploy-tui         Build wheels into $(OUTDIR) and install into active venv (no sudo; matches casino.tui shape)"
	@echo "  deploy-prod        sudo umbrella: install-sysusers + install-tmpfiles + install-venv + install-systemd + install-etc"
	@echo "  deploy-tui DEPLOY_EDITABLE=1    Install editable from src/ (live edits; set by deploytool --editable)"
	@echo "  version            Stamp src/postoffice/_version.py with date + git hash"
	@echo "  clean              Remove build artifacts"
	@echo "  backup             Rsync project to $(MEDIA)"
	@echo ""
	@echo "  install-sysusers   Create postoffice user and group via systemd-sysusers"
	@echo "  uninstall-sysusers Remove sysusers.d/postoffice.conf"
	@echo "  install-tmpfiles   Create /var/lib/postoffice and /var/run/mcfeely-authd via systemd-tmpfiles"
	@echo "  uninstall-tmpfiles Remove tmpfiles.d/postoffice.conf"
	@echo "  install-venv       Install bbsengine6 + mistermcfeely wheels into shared venv at $(VENV_DIR) (sudo)"
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

# Hard-fail precondition for the wheel-install branch of deploy-tui
# (and the sudo install-venv below). Mirrors the canonical shape in
# bbsengine6/py/src/Makefile precheck-editable (line 146), but
# generalized to iterate over every package in WHEEL_PACKAGES, and
# implemented without sudo so it can run from operator context.
#
# PEP 660 / setuptools' __editable___<pkg>_*_finder .pth hook makes
# an editable install of <pkg> in a venv mutually exclusive with a
# wheel install of the same <pkg> into the same venv: the editable
# hook wins on import, so a subsequent `pip install <wheel>` writes
# a fresh dist-info but is shadowed on import, and the operator's
# running process keeps seeing the source tree. Wheels accumulate in
# OUTDIR; dist-info keeps reporting the source-tree version. There
# is no in-place fix — the two install modes can't coexist.
#
# Implementation note: this macro does NOT call pip show (which would
# need sudo to query the shared venv as zoid6 user). Instead it reads
# the dist-info's direct_url.json directly (PEP 610), which is
# world-readable in a normal pip install. Wheel installs write
# {"url": "file:///path/to/wheel.whl"}; PEP 660 editable installs
# write {"dir_info": {"editable": true}, "url": "file:///path/to/src"}.
# The grep below catches the editable case.
#
# Reads assume the operator can read the venv's site-packages and
# dist-info. If the install creates more restrictive permissions, the
# macro silently skips (the subsequent verify-install also skips with
# a message) rather than fail with permission-denied. The operator
# sees the skip and can investigate.
#
# Behavior branches on DEPLOY_WITH_DEPS (set by deploytool --with-deps;
# empty by default):
#   - DEPLOY_WITH_DEPS unset: hard fail with editable source path and
#     the three remedies.
#   - DEPLOY_WITH_DEPS=1: warn-and-proceed. --with-deps semantically
#     promises "rebuild the venv, no questions asked", so blocking on
#     an editable install the operator may have placed there on
#     purpose is wrong-headed. The post-install verify-install macro
#     then becomes the correctness contract — if the editable .pth
#     finder shadows the wheel install, the dist-info Version check
#     fails and the deploy aborts with a precise diagnosis naming
#     the editable-install cause.
#
# Used by deploy-tui (operator venv) and install-venv (shared zoid6
# venv). The calling recipe sets the VENV_PYTHON shell env var before
# invoking the macro — deploy-tui sets it to operator's `python`
# (so sysconfig.get_paths() reports the operator's site-packages);
# install-venv sets it to $(VENV_DIR)/bin/python (so sysconfig reports
# the shared zoid6 venv's site-packages). Either way, the macro runs
# as the operator (no sudo) — site-packages and dist-info are
# world-readable in a normal pip install.
define precheck-editable
	@for pkg in $(WHEEL_PACKAGES); do \
		SITE_PACKAGES=$$( $$VENV_PYTHON -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' 2>/dev/null ); \
		if [ -z "$$SITE_PACKAGES" ]; then continue; fi; \
		DIST_INFO=$$(ls -d $$SITE_PACKAGES/$$pkg-*.dist-info 2>/dev/null | head -1); \
		if [ -z "$$DIST_INFO" ]; then continue; fi; \
		DIRECT_URL=$$(cat $$DIST_INFO/direct_url.json 2>/dev/null); \
		if echo "$$DIRECT_URL" | grep -q '"editable":[[:space:]]*true'; then \
			EDITABLE_SRC=$$(echo "$$DIRECT_URL" | $$VENV_PYTHON -c 'import json, sys; d=json.load(sys.stdin); print(d.get("url", "?"))' 2>/dev/null); \
			if [ "$(DEPLOY_WITH_DEPS)" = "1" ]; then \
				echo "deploy: WARNING: $$pkg is installed editable in $$SITE_PACKAGES" >&2; \
				echo "  editable source: $$EDITABLE_SRC" >&2; \
				echo >&2; \
				echo "DEPLOY_WITH_DEPS=1 is set (deploy --with-deps), so precheck-editable is" >&2; \
				echo "proceeding with the wheel install. If the editable .pth finder shadows it" >&2; \
				echo "(the common case), verify-install will abort with a precise diagnosis." >&2; \
				echo "To switch permanently, run one of:" >&2; \
				echo >&2; \
				echo "  - Stay in editable mode:  deploy --editable mistermcfeely.tui" >&2; \
				echo "  - Force a wheel rebuild:  pip uninstall $$pkg && deploy mistermcfeely.tui" >&2; \
				echo >&2; \
			else \
				echo "deploy: $$pkg is installed editable in $$SITE_PACKAGES" >&2; \
				echo "  editable source: $$EDITABLE_SRC" >&2; \
				echo >&2; \
				echo "Editable and wheel installs of the same distribution name can't coexist in" >&2; \
				echo "one venv (the editable .pth finder shadows subsequent wheel installs), so" >&2; \
				echo "this Makefile refuses to silently no-op. Pick one:" >&2; \
				echo >&2; \
				echo "  1) Stay in editable mode:  deploy --editable mistermcfeely.tui" >&2; \
				echo "  2) Switch to wheel mode:   pip uninstall $$pkg && deploy mistermcfeely.tui" >&2; \
				echo "  3) Override for this run:  deploy --with-deps mistermcfeely.tui" >&2; \
				echo >&2; \
				echo "(The Makefile intentionally doesn't 'fix' this for you — see precheck-editable.)" >&2; \
				exit 1; \
			fi; \
		fi; \
	done
endef

# Verify that each wheel installed by deploy-tui / install-venv
# matches what `pip show` reports as installed. Catches the
# silent-no-op case where `pip install <wheel>` exits 0 without
# actually replacing an existing install (different venv, orphaned
# .dist-info, permission-denied mid-install, etc.).
#
# Mirrors the reference implementation in bbsengine6/py/src/Makefile
# verify-install (line 82) and zoidoffice/src/Makefile VERIFY_INSTALL
# (line 87), but generalized to iterate over WHEEL_PACKAGES so a
# single macro covers the batch install. Three values are compared
# per package:
#   - filename:  regex-extracted from the wheel filename
#   - METADATA:  Version: line from the wheel's METADATA (unzip -p)
#   - dist-info: Version: line from `<pkg>-*.dist-info/METADATA` in
#     the target venv's site-packages (no pip show — we read the
#     file directly so the macro runs without sudo)
#
# All three must agree. Editable installs (DEPLOY_EDITABLE=1) skip
# this — dist-info for an editable install reports the *source-tree*
# version, not a wheel version, and the comparison semantics differ.
define verify-install
	@for pkg in $(WHEEL_PACKAGES); do \
		WHEEL_PATH=$$(ls -t $(OUTDIR)/$$pkg-*.whl 2>/dev/null | head -1); \
		if [ -z "$$WHEEL_PATH" ]; then \
			echo "verify-install: no wheel matching $(OUTDIR)/$$pkg-*.whl" >&2; \
			echo "  (run \`make build\` first to populate $(OUTDIR))" >&2; \
			exit 1; \
		fi; \
		EXPECTED_FROM_FILENAME=$$(basename "$$WHEEL_PATH" | sed -E 's/^$$pkg-(.+)-py3-none-any\.whl$$/\1/'); \
		EXPECTED_FROM_METADATA=$$(unzip -p "$$WHEEL_PATH" '*/METADATA' 2>/dev/null | awk -F': ' '/^Version: / {print $$2; exit}'); \
		echo "=== verify-install ($$pkg) ==="; \
		echo "  wheel filename Version: $$EXPECTED_FROM_FILENAME"; \
		echo "  wheel METADATA Version: $$EXPECTED_FROM_METADATA"; \
		SITE_PACKAGES=$$( $$VENV_PYTHON -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])' 2>/dev/null ); \
		if [ -z "$$SITE_PACKAGES" ]; then \
			echo "verify-install SKIPPED ($$pkg): $$VENV_PYTHON unreachable from operator context" >&2; \
			continue; \
		fi; \
		DIST_INFO=$$(ls -d $$SITE_PACKAGES/$$pkg-*.dist-info 2>/dev/null | head -1); \
		if [ -z "$$DIST_INFO" ]; then \
			echo "verify-install SKIPPED ($$pkg): no dist-info in $$SITE_PACKAGES" >&2; \
			continue; \
		fi; \
		INSTALLED=$$(grep '^Version:' $$DIST_INFO/METADATA 2>/dev/null | head -1 | awk '{print $$2}'); \
		echo "--- dist-info METADATA Version ($$pkg) ---"; \
		echo "  $$INSTALLED"; \
		echo "--- end ---"; \
		if [ "$$INSTALLED" != "$$EXPECTED_FROM_FILENAME" ] \
			|| [ "$$INSTALLED" != "$$EXPECTED_FROM_METADATA" ]; then \
			echo "verify-install FAILED ($$pkg): $$WHEEL_PATH was installed but dist-info does not agree" >&2; \
			echo "  expected filename:  $$EXPECTED_FROM_FILENAME" >&2; \
			echo "  expected METADATA:  $$EXPECTED_FROM_METADATA" >&2; \
			echo "  dist-info Version:  $$INSTALLED" >&2; \
			exit 1; \
		fi; \
		echo "verify-install OK ($$pkg): dist-info reports $$INSTALLED"; \
	done
endef

# Build both bbsengine6 (transitive runtime dep) and mistermcfeely
# wheels into the canonical cross-project OUTDIR. Runs as the
# operator (no sudo) — `python -m build` is a regular local build,
# the result is published to /srv/repo/mistermcfeely/ which is
# operator-writable (or owned by the build group; see the
# OUTDIR/ensure-build-dir pattern in casino/Makefile if more
# rigor is needed later). Idempotent: each invocation overwrites
# the prior wheels for the current timestamp.
#
# The bbsengine6 sub-build runs with --no-isolation so it uses the
# already-installed bbsengine6 build deps (pyproject.toml declared
# them in [build-system]). The mistermcfeely build does the same.
build: version
	@mkdir -p $(OUTDIR)
	$(MAKE) -C $(BBSENGINE_DIR) version
	$(PYTHON) -m build --no-isolation --wheel --outdir $(OUTDIR) $(BBSENGINE_DIR)
	$(PYTHON) -m build --no-isolation --wheel --outdir $(OUTDIR) $(CURDIR)
	@echo "Built bbsengine6 + $(PROJECT) wheels into $(OUTDIR)"

# `make deploy-tui` builds the wheels (via `build`) then installs
# them into the operator's active venv. Matches casino.tui's shape
# exactly (casino/Makefile:241): precheck-editable runs first to
# refuse silently-no-op'ing over an existing editable install, then
# either installs editable from the source tree (DEPLOY_EDITABLE=1)
# or installs the freshly-built wheel from $(OUTDIR). Verify-install
# runs post-install to catch the silent-no-op case.
#
# No sudo: this target is the operator-side install path. The
# sudo-required install into /var/lib/zoid6/venv lives in
# `install-venv` below, which is invoked by `deploy-prod`.
deploy-tui: build
	@export VENV_PYTHON=$(PYTHON); $(precheck-editable)
ifeq ($(DEPLOY_EDITABLE),1)
	$(MAKE) version
	$(PYTHON) -m pip install $(PIP_UPGRADE_FLAG) --no-cache-dir -e .
	-rm -rf src/$(PROJECT).egg-info
else
	@WHEEL=$$(ls -t $(OUTDIR)/$(PROJECT)-*.whl 2>/dev/null | head -1); \
	if [ -z "$$WHEEL" ]; then \
		echo "no wheel found in $(OUTDIR); run \`make build\` first" >&2; \
		exit 1; \
	fi; \
	echo "installing $$WHEEL"; \
	$(PYTHON) -m pip install $(PIP_UPGRADE_FLAG) --no-cache-dir "$$WHEEL"
	@export VENV_PYTHON=$(PYTHON); $(verify-install)
endif

# sudo umbrella — the production install path. Alias for the full
# install chain (sysusers + tmpfiles + venv + systemd + etc). Mirrors
# zoid6/src/Makefile:deploy-prod:install-fhs and bed/Makefile:deploy-prod:install.
# Forward DEPLOY_EDITABLE / DEPLOY_WITH_DEPS / DEPLOY_UPGRADE to
# `install` so the sub-makes (install-venv, deploy-tui) inherit the
# same env-var contract the operator set on the deploytool CLI.
deploy-prod:
	$(MAKE) install DEPLOY_EDITABLE=$(DEPLOY_EDITABLE) DEPLOY_WITH_DEPS=$(DEPLOY_WITH_DEPS) DEPLOY_UPGRADE=$(DEPLOY_UPGRADE)

# Sudo-required install into the shared zoid6 venv. Consumes
# wheels from $(OUTDIR) (which the operator populated via
# `make build` or `make deploy-tui` first). Re-runs the build via
# `$(MAKE) build` so the wheels in $(OUTDIR) reflect the current
# source — `deploy mistermcfeely.prod` is self-contained, the
# operator doesn't have to run `deploy-tui` first.
#
# Precheck-editable + verify-install run as the operator (no sudo).
# Both query the shared venv's dist-info directly because
# site-packages and dist-info are world-readable in a normal pip
# install. If they're not readable (e.g. umask tightened the venv),
# the macros SKIP with a message rather than fail — the operator sees
# the skip and can investigate.
install-venv:
	@command -v sudo >/dev/null 2>&1 || { echo "Error: sudo required"; exit 1; }
	@sudo -u $(VENV_OWNER) test -d "$(VENV_DIR)" || sudo -u $(VENV_OWNER) $(PYTHON) -m venv "$(VENV_DIR)"
	sudo -u $(VENV_OWNER) $(VENV_DIR)/bin/pip install --upgrade pip
	sudo -u $(VENV_OWNER) $(VENV_DIR)/bin/pip install $(PIP_UPGRADE_FLAG) --quiet build setuptools wheel
	@export VENV_PYTHON=$(VENV_DIR)/bin/python; $(precheck-editable)
	@$(MAKE) build DEPLOY_EDITABLE=$(DEPLOY_EDITABLE) DEPLOY_WITH_DEPS=$(DEPLOY_WITH_DEPS) DEPLOY_UPGRADE=$(DEPLOY_UPGRADE)
	@WHEELS=$$(ls -t $(OUTDIR)/*.whl 2>/dev/null); \
	if [ -z "$$WHEELS" ]; then \
		echo "no wheels found in $(OUTDIR); \`make build\` failed?" >&2; \
		exit 1; \
	fi; \
	echo "installing $$WHEELS into $(VENV_DIR)"; \
	sudo -u $(VENV_OWNER) $(VENV_DIR)/bin/pip install $(PIP_UPGRADE_FLAG) $$WHEELS
	@export VENV_PYTHON=$(VENV_DIR)/bin/python; $(verify-install)
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
