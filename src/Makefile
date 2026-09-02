# mistermcfeely/src/Makefile
# Inner build/sdist packaging. Mirrors zoidoffice/src/Makefile shape
# (root owns env + deploy, src owns build/sdist/PREPARE_BUILD/clean).
# The root Makefile forwards `make build` / `make sdist` /
# `make version` here with VERSION/VERSION_PREFIX propagated, so the
# wheel filename uses a single per-second stamp computed once at the
# root Makefile's parse time.

PROJECT = mistermcfeely
OUTDIR ?= /srv/repo/$(PROJECT)/
# VERSION_PREFIX and VERSION are normally inherited from the parent
# Makefile via `make -C src ... VERSION_PREFIX=... VERSION=...`
# so the prefix lives in exactly one place (mistermcfeely/Makefile)
# and the build/install chain uses a single stamp even across
# minute boundaries.
#
# The `?=` fallbacks make a bare `make -C src` (no override)
# still work standalone: VERSION_PREFIX defaults to the same
# value the parent would have used, VERSION is built from it
# with a per-second timestamp. `:=` is kept as defense in depth
# to guarantee single eval at parse time. See
# mistermcfeely/Makefile for the source of truth.
VERSION_PREFIX ?= 0.0.1.dev
VERSION ?= $(VERSION_PREFIX)$(shell date +%Y%m%d%H%M%S)

PYTHON ?= python3.12
PIP ?= $(PYTHON) -m pip

# When the operator is in a venv, use that venv's python (not the
# system python3.12) so the wheel's `requires-python` matches what pip
# will later run with. Without this, `python3.12` from system PATH can
# be a different version than the active venv, which makes pip reject
# the wheel at deploy time.
ifneq ($(VIRTUAL_ENV),)
PYTHON := $(VIRTUAL_ENV)/bin/python
endif

# DEPLOY_EDITABLE / DEPLOY_WITH_DEPS / DEPLOY_UPGRADE are documented in
# the parent Makefile. They are accepted here so this file can be
# consumed standalone as well as via the root Makefile (e.g. a CI
# invocation that only builds wheels).
DEPLOY_EDITABLE ?=
DEPLOY_WITH_DEPS ?=
DEPLOY_UPGRADE ?=
PIP_UPGRADE_FLAG := $(if $(filter 1,$(DEPLOY_UPGRADE)),--upgrade,)

# Mirrors zoidoffice/src/Makefile's dist pattern: build artifacts land
# in $(DISTDIR) (../dist), a writable per-project dir. The
# read-only /srv/repo/$(PROJECT) is published to by the separate
# `repo` target via rsync, not by `python -m build` directly - that
# way the PEP 517 mkdtemp() works against a writable filesystem.
DISTDIR = $(CURDIR)/../dist

# Make sure $(1)/build/ exists with mode 1775 (sticky + rwxrwxr-x)
# before invoking `python -m build`. Mode 1775 is intentional:
#   - sticky (t): only the owner of a file inside may delete/rename
#     it, so concurrent builds under a shared group can't stomp each
#     other.
#   - setgid (s) is intentionally NOT set: setuptools' shutil.copystat
#     mirrors build/'s mode onto the freshly-created dist-info dir, and
#     a setgid'd dist-info EPERMs the subsequent bdist_wheel step in
#     SELinux-enforcing + NoNewPrivs containers (we lack CAP_FSETID).
#   - group write (g+w): any user in the build group can rebuild
#     without needing to chown.
# The chmod is expressed as `chmod g-s,+t` (drop the setgid bit the
# parent dir inherited onto the freshly-mkdir'd build/, then add the
# sticky bit). The numeric form `chmod 1775` is functionally equivalent
# but fails on BTRFS+SELinux setups where the parent directory's
# setgid bit blocks the owner from clearing it via the numeric mode
# (`chmod: Operation not permitted` on a dir the caller owns). The
# symbolic form works because the kernel only restricts numeric-mode
# changes that would remove the inherited setgid bit; `g-s` is
# permitted regardless of where the bit came from.
#
# If $(1)/build/ exists but is owned by a different user (e.g. left
# over from a prior build run as a different uid), rename it out of
# the way first. The parent dir is group-writable in this tree so the
# rename is permitted even when we don't own the build/ contents.
# Without this, the subsequent chmod fails with EPERM and the build
# aborts. Mirrors bed/Makefile:163-185.
PREPARE_BUILD = \
	if [ -d $(1)/build ] && [ ! -O $(1)/build ]; then \
		mv $(1)/build $(1)/build.stale.$$ 2>/dev/null || true; \
	fi; \
	mkdir -p $(1)/build && chmod g-s,+t $(1)/build

.PHONY: all build sdist repo version clean clean-egg-info

all:

# Stamp src/postoffice/_version.py with the current build identity.
# The double-underscore `__datestamp__` and `__githash__` field
# names match the existing mistermcfeely convention; cross-project
# normalization to single-underscore `datestamp` / `githash` is
# tracked separately (see casino/src/casino/Makefile TODO at the
# bottom). VERSION_PREFIX is read but not written into the file -
# `__version__` is the prefix-stripped datestamp only, matching the
# pre-existing on-disk shape. The wheel filename carries the prefix
# (`$(VERSION_PREFIX)$(VERSION)`); only the file content differs.
# Derive DATESTAMP from VERSION by stripping the VERSION_PREFIX
# prefix. Defined as a Make variable (not a recipe-time shell sub) so
# it's available to both the recipe and to any downstream consumer
# that wants to inspect the stamp without re-parsing VERSION.
DATESTAMP := $(VERSION:$(VERSION_PREFIX)%=%)

version:
	@echo '__version__ = "$(VERSION)"' > postoffice/_version.py
	@echo '__datestamp__ = "$(DATESTAMP)"' >> postoffice/_version.py
	@echo '__githash__ = "'`git log -1 --format='%H' 2>/dev/null | cut -c 1-16`'"' >> postoffice/_version.py

# Wipe any egg-info directory left over from a prior `pip install
# -e .` (root or under src/). setuptools writes the absolute paths of
# the editable install into SOURCES.txt, which then poisons the next
# `python -m build` invocation. Mirrors bed/Makefile:189-194.
clean-egg-info:
	-rm -rf *.egg-info
	-rm -rf $(PROJECT).egg-info


build: version clean-egg-info
	@mkdir -p $(DISTDIR)
	$(call PREPARE_BUILD,$(CURDIR))
	$(PYTHON) -m build --outdir $(DISTDIR)

sdist: version clean-egg-info
	@mkdir -p $(DISTDIR)
	$(call PREPARE_BUILD,$(CURDIR))
	$(PYTHON) -m build --sdist --outdir $(DISTDIR)

# rsync the freshly-built wheel + sdist from $(DISTDIR) into $(OUTDIR)
# so downstream consumers can pick them up via
# `ls -t $(OUTDIR)/<pkg>-*.whl | head -1`. The root Makefile forwards
# OUTDIR via `make -C src repo OUTDIR=$(WHEEL_DIR)` (deploy-venv) or
# `make -C src repo OUTDIR=$(OUTDIR)` (build/sdist via the root). The
# `--delete` flag is the standard zoidoffice/src/Makefile pattern:
# stale artifacts from a prior build at the same OUTDIR get pruned.
# Operator note: $(OUTDIR) is mounted read-only on this host, so this
# target only works on a machine where the mount is writable (or with
# sudo).
repo:
	rsync -av --delete $(DISTDIR)/ $(OUTDIR)/

clean: clean-egg-info
	-rm -rf build build.stale.*
	-rm -rf $(DISTDIR)/*.whl $(DISTDIR)/*.tar.gz
	-rm *~
	-rm -f postoffice/_version.py
	$(MAKE) -C postoffice clean
