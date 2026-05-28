# Makefile for installing Cyrus IMAP configuration files
# Usage: make install [DESTDIR=/path/to/staging]

DESTDIR ?=

# Target paths
ETCDIR := $(DESTDIR)/etc
SBINDIR := $(DESTDIR)/usr/sbin

# Installation directories
CYRUS_ETCDIR := $(ETCDIR)
SASL_ETCDIR := $(ETCDIR)/sasl2
SASL_SYSCONFIG := $(ETCDIR)/sysconfig
PAM_ETCDIR := $(ETCDIR)/pam.d

# Configuration files
CONFIG_FILES := cyrus.conf imapd.conf imapd.annotations
SASL_FILES := saslauthd.conf
SYSCONFIG_FILES := saslauthd.sysconfig
PAM_FILES := pam.d-saslauthd

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

install: $(CONFIG_FILES) $(SASL_FILES) $(SYSCONFIG_FILES) $(PAM_FILES)
	@echo "Installing Cyrus IMAP configuration files..."
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
	@echo "Installation complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Set sasldb permissions:  chown cyrus:mail /etc/sasldb2"
	@echo "  2. Restart Cyrus:           systemctl restart cyrus-imapd"
	@echo "  3. Set admin password:      saslpasswd2 -c cyrus"
	@echo "  4. Create user mailbox:     cyradm -u cyrus localhost; cm user.jam"

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
	@echo ""
	@echo "Uninstall complete!"

check:
	@echo "Cyrus IMAP Configuration - Installation Plan"
	@echo ""
	@echo "Base path: $(ETCDIR)"
	@echo ""
	@echo "Config files to install:"
	@echo "  cyrus.conf         -> $(CYRUS_ETCDIR)/cyrus.conf"
	@echo "  imapd.conf         -> $(CYRUS_ETCDIR)/imapd.conf"
	@echo "  imapd.annotations  -> $(CYRUS_ETCDIR)/imapd.annotations"
	@echo "  saslauthd.conf     -> $(SASL_ETCDIR)/saslauthd.conf"
	@echo "  saslauthd.sysconfig-> $(SASL_SYSCONFIG)/saslauthd"
	@echo "  pam.d-saslauthd    -> $(PAM_ETCDIR)/saslauthd"
	@echo ""
	@echo "Owner: root:mail (640 for config, 644 for sysconfig/pam)"