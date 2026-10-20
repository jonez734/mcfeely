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
PAM_ETCDIR := $(ETCDIR)/pam.d

# Configuration files
CONFIG_FILES := cyrus.conf imapd.conf imapd.annotations
COPY_TO_ETC := cyrus.conf imapd.conf
PAM_FILES := pam.d-imap pam.d-bbsengine6
# SASL2_FILES: libsasl2 auxprop-sql config (Mode C) and the empty 0600
# placeholder for the dovecot Postgres role password.
SASL2_FILES := sasl2-sql.conf sasl2-sql.dbnpass.template
# name (config keys, not the user-facing daemon binary name).
SYSTEMD_FILES := cyrus-imapd.service

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

install: $(CONFIG_FILES) $(PAM_FILES) $(SASL2_FILES) $(SYSTEMD_FILES)
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
	@echo "Installing pam.d-imap..."
	@install -o root -g root -m 644 pam.d-imap "$(PAM_ETCDIR)/imap"
	@echo "  -> $(PAM_ETCDIR)/imap"
	@echo ""
	@echo "Installing pam.d-bbsengine6..."
	@install -o root -g root -m 644 pam.d-bbsengine6 "$(PAM_ETCDIR)/bbsengine6"
	@echo "  -> $(PAM_ETCDIR)/bbsengine6"
	@echo ""
	@echo "Installing sasl2-sql.conf..."
	@install -o root -g root -m 640 sasl2-sql.conf "$(SASL_ETCDIR)/sql.conf"
	@echo "  -> $(SASL_ETCDIR)/sql.conf"
	@echo ""
	@echo "Installing sasl2-sql.dbnpass.template (placeholder, mode 0600)..."
	@[ -f "$(SASL_ETCDIR)/sql.dbnpass" ] || install -o root -g root -m 600 sasl2-sql.dbnpass.template "$(SASL_ETCDIR)/sql.dbnpass"
	@echo "  -> $(SASL_ETCDIR)/sql.dbnpass (operator must set the password)"
	@echo ""
	@echo "Installing cyrus-imapd.service..."
	@install -o root -g root -m 644 cyrus-imapd.service "$(SYSTEMD)/cyrus-imapd.service"
	@echo "  -> $(SYSTEMD)/cyrus-imapd.service"
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
	@echo "  2. Restart Cyrus:          sudo systemctl restart cyrus-imapd"
	@echo "  3. Set cyrus password:     sudo passwd cyrus"
	@echo "  4. Create jam mailbox:      sudo cyradm -u cyrus localhost"
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
	@echo "Removing pam.d/imap..."
	@rm -f "$(PAM_ETCDIR)/imap"
	@echo "Removing pam.d/bbsengine6..."
	@rm -f "$(PAM_ETCDIR)/bbsengine6"
	@echo "Removing /etc/sasl2/sql.conf..."
	@rm -f "$(SASL_ETCDIR)/sql.conf"
	@echo "Removing /etc/sasl2/sql.dbnpass..."
	@rm -f "$(SASL_ETCDIR)/sql.dbnpass"
	@echo "Removing systemd units..."
	@rm -f "$(SYSTEMD)/cyrus-imapd.service"
	@rm -f "$(SYSTEMD)/mcfeely-authd.service"
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
	@echo "  pam.d-imap         -> $(PAM_ETCDIR)/imap"
	@echo "  cyrus-imapd.service-> $(SYSTEMD)/cyrus-imapd.service"
	@echo ""
	@echo "Owner: root:mail (640 for config, 644 for pam/service)"