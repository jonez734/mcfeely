# Makefile for installing Cyrus IMAP configuration files
# Usage: make install [DESTDIR=/path/to/staging]

DESTDIR ?=

# Target paths
ETCDIR := $(DESTDIR)/etc
POSTOFFICE := $(ETCDIR)/postoffice
SYSTEMD := $(DESTDIR)/usr/lib/systemd/system

# Installation directories
CYRUS_ETCDIR := $(POSTOFFICE)
SASL_ETCDIR := $(ETCDIR)/sasl2
SASL_SYSCONFIG := $(ETCDIR)/sysconfig
PAM_ETCDIR := $(ETCDIR)/pam.d

# Configuration files
CONFIG_FILES := cyrus.conf imapd.conf imapd.annotations
SASL_FILES := saslauthd.conf
SYSCONFIG_FILES := saslauthd.sysconfig
PAM_FILES := pam.d-saslauthd
SYSTEMD_FILES := cyrus-imapd.service saslauthd.service

.PHONY: all install uninstall check help

all: help

help:
	@echo "Cyrus IMAP Configuration Installer"
	@echo ""
	@echo "Targets:"
	@echo "  make install       Install all configuration files"
	@echo "  make uninstall     Remove installed configuration files"
	@echo "  make check         Show what would be installed where"
	@echo ""
	@echo "Variables:"
	@echo "  DESTDIR=/path      Set staging directory for packaging (default: /)"
	@echo ""
	@echo "Example:"
	@echo "  make install DESTDIR=/mnt/system"

install: $(CONFIG_FILES) $(SASL_FILES) $(SYSCONFIG_FILES) $(PAM_FILES) $(SYSTEMD_FILES)
	@echo "Installing Cyrus IMAP configuration files..."
	@echo ""
	@echo "Creating directories..."
	@sudo mkdir -p "$(CYRUS_ETCDIR)" "$(SASL_ETCDIR)" "$(PAM_ETCDIR)" "$(SYSTEMD)"
	@echo ""
	@echo "Installing cyrus.conf..."
	@install -o root -g mail -m 640 cyrus.conf "$(CYRUS_ETCDIR)/cyrus.conf"
	@echo "  -> $(CYRUS_ETCDIR)/cyrus.conf"
	@echo ""
	@echo "Installing imapd.conf..."
	@install -o root -g mail -m 640 imapd.conf "$(CYRUS_ETCDIR)/imapd.conf"
	@echo "  -> $(CYRUS_ETCDIR)/imapd.conf"
	@echo ""
	@echo "Installing imapd.annotations..."
	@install -o root -g mail -m 640 imapd.annotations "$(CYRUS_ETCDIR)/imapd.annotations"
	@echo "  -> $(CYRUS_ETCDIR)/imapd.annotations"
	@echo ""
	@echo "Installing saslauthd.conf..."
	@install -o root -g root -m 640 saslauthd.conf "$(SASL_ETCDIR)/saslauthd.conf"
	@echo "  -> $(SASL_ETCDIR)/saslauthd.conf"
	@echo ""
	@echo "Installing saslauthd.sysconfig..."
	@install -o root -g root -m 644 saslauthd.sysconfig "$(SASL_SYSCONFIG)/saslauthd"
	@echo "  -> $(SASL_SYSCONFIG)/saslauthd"
	@echo ""
	@echo "Installing pam.d-saslauthd..."
	@install -o root -g root -m 644 pam.d-saslauthd "$(PAM_ETCDIR)/saslauthd"
	@echo "  -> $(PAM_ETCDIR)/saslauthd"
	@echo ""
	@echo "Installing cyrus-imapd.service..."
	@install -o root -g root -m 644 cyrus-imapd.service "$(SYSTEMD)/cyrus-imapd.service"
	@echo "  -> $(SYSTEMD)/cyrus-imapd.service"
	@echo ""
	@echo "Installing saslauthd.service..."
	@install -o root -g root -m 644 saslauthd.service "$(SYSTEMD)/saslauthd.service"
	@echo "  -> $(SYSTEMD)/saslauthd.service"
	@echo ""
	@echo "Creating cyrus system user..."
	@id cyrus 2>/dev/null || sudo useradd -r -d /var/lib/imap -s /sbin/nologin -c "Cyrus IMAP Server" cyrus
	@echo ""
	@echo "Creating mail directories..."
	@sudo mkdir -p /var/spool/imap /var/lib/imap
	@sudo chown cyrus:mail /var/spool/imap /var/lib/imap
	@echo ""
	@echo "Installation complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Reload systemd:         sudo systemctl daemon-reload"
	@echo "  2. Enable saslauthd:       sudo systemctl enable --now saslauthd"
	@echo "  3. Restart Cyrus:          sudo systemctl restart cyrus-imapd"
	@echo "  4. Set cyrus password:     sudo passwd cyrus"
	@echo "  5. Create jam mailbox:      sudo cyradm -u cyrus localhost"
	@echo "     -> cm user.jam"
	@echo "     -> setacl user.jam jam lrs"
	@echo "     -> exit"

uninstall:
	@echo "Removing Cyrus IMAP configuration files..."
	@echo ""
	@echo "Removing cyrus.conf..."
	@rm -f $(CYRUS_ETCDIR)/cyrus.conf
	@echo "Removing imapd.conf..."
	@rm -f $(CYRUS_ETCDIR)/imapd.conf
	@echo "Removing imapd.annotations..."
	@rm -f $(CYRUS_ETCDIR)/imapd.annotations
	@echo "Removing saslauthd.conf..."
	@rm -f $(SASL_ETCDIR)/saslauthd.conf
	@echo "Removing saslauthd.sysconfig..."
	@rm -f $(SASL_SYSCONFIG)/saslauthd
	@echo "Removing pam.d/saslauthd..."
	@rm -f $(PAM_ETCDIR)/saslauthd
	@echo "Removing systemd units..."
	@rm -f $(SYSTEMD)/cyrus-imapd.service
	@rm -f $(SYSTEMD)/saslauthd.service
	@echo ""
	@echo "Uninstall complete!"

create-system-user:
	@echo "Creating cyrus system user (if not exists)..."
	@id cyrus 2>/dev/null || sudo useradd -r -d /var/lib/imap -s /sbin/nologin -c "Cyrus IMAP Server" cyrus
	@echo "Creating mail spool directory..."
	@sudo mkdir -p /var/spool/imap
	@sudo chown cyrus:mail /var/spool/imap
	@sudo mkdir -p /var/lib/imap
	@sudo chown cyrus:mail /var/lib/imap
	@echo "Done."

check:
	@echo "Cyrus IMAP Configuration - Installation Plan"
	@echo ""
	@echo "Config files to install:"
	@echo "  cyrus.conf         -> $(CYRUS_ETCDIR)/cyrus.conf"
	@echo "  imapd.conf         -> $(CYRUS_ETCDIR)/imapd.conf"
	@echo "  imapd.annotations  -> $(CYRUS_ETCDIR)/imapd.annotations"
	@echo "  saslauthd.conf     -> $(SASL_ETCDIR)/saslauthd.conf"
	@echo "  saslauthd.sysconfig-> $(SASL_SYSCONFIG)/saslauthd"
	@echo "  pam.d-saslauthd    -> $(PAM_ETCDIR)/saslauthd"
	@echo "  cyrus-imapd.service-> $(SYSTEMD)/cyrus-imapd.service"
	@echo "  saslauthd.service  -> $(SYSTEMD)/saslauthd.service"
	@echo ""
	@echo "Owner: root:mail (640 for config, 644 for sysconfig/pam/service)"