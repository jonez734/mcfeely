# Makefile for installing Cyrus IMAP configuration files
# Usage: make install [DESTDIR=/path/to/staging]

DESTDIR ?=

# Target paths
ETCDIR := $(DESTDIR)/etc
POSTOFFICE := $(ETCDIR)/postoffice
SYSTEMD := $(DESTDIR)/usr/lib/systemd/system

# Installation directories
CYRUS_ETCDIR := $(ETCDIR)
POSTOFFICE := $(ETCDIR)/postoffice
SASL_ETCDIR := $(ETCDIR)/sasl2
SASL_SYSCONFIG := $(ETCDIR)/sysconfig
PAM_ETCDIR := $(ETCDIR)/pam.d

# Configuration files
CONFIG_FILES := cyrus.conf imapd.conf imapd.annotations
COPY_TO_ETC := cyrus.conf imapd.conf
SASL_FILES := saslauthd.conf
SYSCONFIG_FILES := saslauthd.sysconfig
PAM_FILES := pam.d-saslauthd pam.d-imap
SYSTEMD_FILES := cyrus-imapd.service saslauthd.service mcfeely-authd.service
MCFEELY_FILES := mcfeely-authd.conf

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
	@sudo mkdir -p "$(ETCDIR)" "$(POSTOFFICE)" "$(SASL_ETCDIR)" "$(PAM_ETCDIR)" "$(SYSTEMD)"
	@echo ""
	@echo "Copying cyrus.conf to /etc/..."
	@install -o root -g mail -m 640 cyrus.conf "$(ETCDIR)/cyrus.conf"
	@echo "  -> $(ETCDIR)/cyrus.conf"
	@echo ""
	@echo "Copying imapd.conf to /etc/..."
	@install -o root -g mail -m 640 imapd.conf "$(ETCDIR)/imapd.conf"
	@echo "  -> $(ETCDIR)/imapd.conf"
	@echo ""
	@echo "Installing cyrus.conf to postoffice..."
	@install -o root -g mail -m 640 cyrus.conf "$(POSTOFFICE)/cyrus.conf"
	@echo "  -> $(POSTOFFICE)/cyrus.conf"
	@echo ""
	@echo "Installing imapd.conf to postoffice..."
	@install -o root -g mail -m 640 imapd.conf "$(POSTOFFICE)/imapd.conf"
	@echo "  -> $(POSTOFFICE)/imapd.conf"
	@echo ""
	@echo "Installing imapd.annotations..."
	@install -o root -g mail -m 640 imapd.annotations "$(POSTOFFICE)/imapd.annotations"
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
	@echo "Installing pam.d-imap..."
	@install -o root -g root -m 644 pam.d-imap "$(PAM_ETCDIR)/imap"
	@echo "  -> $(PAM_ETCDIR)/imap"
	@echo ""
	@echo "Installing cyrus-imapd.service..."
	@install -o root -g root -m 644 cyrus-imapd.service "$(SYSTEMD)/cyrus-imapd.service"
	@echo "  -> $(SYSTEMD)/cyrus-imapd.service"
	@echo ""
	@echo "Installing saslauthd.service..."
	@install -o root -g root -m 644 saslauthd.service "$(SYSTEMD)/saslauthd.service"
	@echo "  -> $(SYSTEMD)/saslauthd.service"
	@echo ""
	@echo "Installing mcfeely-authd.service..."
	@install -o root -g root -m 644 mcfeely-authd.service "$(SYSTEMD)/mcfeely-authd.service"
	@echo "  -> $(SYSTEMD)/mcfeely-authd.service"
	@echo ""
	@echo "Installing mcfeely-authd.conf..."
	@install -o root -g root -m 640 mcfeely-authd.conf "$(ETCDIR)/mcfeely-authd.conf"
	@echo "  -> $(ETCDIR)/mcfeely-authd.conf"
	@echo ""
	@echo "Creating postoffice system user..."
	@id postoffice 2>/dev/null || sudo useradd -r -d /var/lib/postoffice -s /sbin/nologin -c "Postoffice SASL Auth Daemon" postoffice
	@echo ""
	@echo "Creating postoffice directories..."
	@sudo mkdir -p /var/lib/postoffice /var/log
	@sudo chown postoffice:postoffice /var/lib/postoffice
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
	@echo "Removing cyrus.conf from /etc/..."
	@rm -f "$(ETCDIR)/cyrus.conf"
	@echo "Removing imapd.conf from /etc/..."
	@rm -f "$(ETCDIR)/imapd.conf"
	@echo "Removing cyrus.conf from postoffice..."
	@rm -f "$(POSTOFFICE)/cyrus.conf"
	@echo "Removing imapd.conf from postoffice..."
	@rm -f "$(POSTOFFICE)/imapd.conf"
	@echo "Removing imapd.annotations..."
	@rm -f "$(POSTOFFICE)/imapd.annotations"
	@echo "Removing saslauthd.conf..."
	@rm -f "$(SASL_ETCDIR)/saslauthd.conf"
	@echo "Removing saslauthd.sysconfig..."
	@rm -f "$(SASL_SYSCONFIG)/saslauthd"
	@echo "Removing pam.d/saslauthd..."
	@rm -f "$(PAM_ETCDIR)/saslauthd"
	@echo "Removing pam.d/imap..."
	@rm -f "$(PAM_ETCDIR)/imap"
	@echo "Removing systemd units..."
	@rm -f "$(SYSTEMD)/cyrus-imapd.service"
	@rm -f "$(SYSTEMD)/saslauthd.service"
	@rm -f "$(SYSTEMD)/mcfeely-authd.service"
	@echo "Removing mcfeely-authd.conf..."
	@rm -f "$(ETCDIR)/mcfeely-authd.conf"
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
	@echo "  cyrus.conf         -> $(ETCDIR)/cyrus.conf"
	@echo "  imapd.conf         -> $(ETCDIR)/imapd.conf"
	@echo "  cyrus.conf         -> $(POSTOFFICE)/cyrus.conf"
	@echo "  imapd.conf         -> $(POSTOFFICE)/imapd.conf"
	@echo "  imapd.annotations  -> $(POSTOFFICE)/imapd.annotations"
	@echo "  saslauthd.conf     -> $(SASL_ETCDIR)/saslauthd.conf"
	@echo "  saslauthd.sysconfig-> $(SASL_SYSCONFIG)/saslauthd"
	@echo "  pam.d-saslauthd    -> $(PAM_ETCDIR)/saslauthd"
	@echo "  pam.d-imap         -> $(PAM_ETCDIR)/imap"
	@echo "  cyrus-imapd.service-> $(SYSTEMD)/cyrus-imapd.service"
	@echo "  saslauthd.service  -> $(SYSTEMD)/saslauthd.service"
	@echo "  mcfeely-authd.service -> $(SYSTEMD)/mcfeely-authd.service"
	@echo "  mcfeely-authd.conf -> $(ETCDIR)/mcfeely-authd.conf"
	@echo ""
	@echo "Owner: root:mail (640 for config, 644 for sysconfig/pam/service)"