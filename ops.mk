# Sudo / FHS operations for mistermcfeely. Included by Makefile.
# These targets write to system locations (/usr/lib, /etc, /run) and
# need sudo. The operator-side deploy path (stage, deploy-tui) never
# calls them; deploy-prod and install reach them through the chain.

.PHONY: install-sysusers uninstall-sysusers
.PHONY: install-tmpfiles uninstall-tmpfiles
.PHONY: install-systemd uninstall-systemd
.PHONY: install-etc uninstall-etc restorecon

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

UNIT_SRC = etc-postoffice/postoffice-authd.service
UNIT_DST = /usr/lib/systemd/system/postoffice-authd.service

install-systemd:
	sed 's|@VENV_DIR@|$(OPERATOR_VENV)|g' $(UNIT_SRC) | sudo tee $(UNIT_DST) > /dev/null
	sudo chmod 0644 $(UNIT_DST)
	sudo chown root:root $(UNIT_DST)
	sudo systemctl daemon-reload
	@echo "Installed $(UNIT_DST)"

uninstall-systemd:
	-sudo systemctl stop postoffice-authd 2>/dev/null
	-sudo systemctl disable postoffice-authd 2>/dev/null
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
	@echo "  (NOTE: config filename keeps the historical 'mcfeely-authd' name; it is the binary name that was renamed.)"
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
	@echo "Removed postoffice-authd and saslauthd config files"

restorecon:
	@if [ -n "$(VIRTUAL_ENV)" ]; then \
		command -v semanage >/dev/null 2>&1 && \
			sudo semanage fcontext -a -t bin_t "$(VIRTUAL_ENV)/bin(/.*)?" 2>/dev/null || true; \
		command -v restorecon >/dev/null 2>&1 && sudo restorecon -R $(VIRTUAL_ENV)/bin/ || true; \
		echo "Relabeled $(VIRTUAL_ENV)/bin/ for SELinux"; \
	else \
		echo "restorecon: VIRTUAL_ENV not set; skipping"; \
	fi
