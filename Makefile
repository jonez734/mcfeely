PROJECT = mistermcfeely
MEDIA = /run/media/jam/BEA6-BBCE/work/$(PROJECT)/

all:

install-imapd-conf:
	sudo cp etc-postoffice/imapd.conf /etc/postoffice/imapd.conf

install-etc-postoffice:
	sudo cp etc-postoffice/* /etc/postoffice/

install-saslauthd-conf:
	sudo cp etc-postoffice/saslauthd.conf /etc/sasl2/saslauthd.conf

install-saslauthd-sysconfig:
	[ -f /etc/debian_version ] && \
		sudo cp etc-postoffice/saslauthd.sysconfig /etc/default/saslauthd || \
		sudo cp etc-postoffice/saslauthd.sysconfig /etc/sysconfig/saslauthd

install-saslauthd-pam:
	sudo cp etc-postoffice/pam.d-saslauthd /etc/pam.d/saslauthd

install-saslauthd: install-saslauthd-conf install-saslauthd-sysconfig install-saslauthd-pam
	sudo mkdir -p /var/run/saslauthd
	sudo chmod 755 /var/run/saslauthd

install-auth: install-saslauthd
	@echo "saslauthd configuration complete"
	@echo "Start with: sudo systemctl enable --now saslauthd"

clean:
	-rm *~
	$(MAKE) -C src clean
	$(MAKE) -C sql clean

backup:
	rsync --recursive --verbose --exclude=.venv . $(MEDIA)
