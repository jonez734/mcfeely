all:

install-imapd-conf:
	sudo cp etc-postoffice/imapd.conf /etc/postoffice/imapd.conf

install-etc-postoffice:
	sudo cp etc-postoffice/* /etc/postoffice/

clean:
	-rm *~
	$(MAKE) -C src clean
	$(MAKE) -C sql clean
