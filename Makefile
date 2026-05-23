all:

install-imapd-conf:
	sudo cp etc-postoffice-imapd.conf /etc/postoffice/imapd.conf

clean:
	-rm *~
	$(MAKE) -C src clean
	$(MAKE) -C sql clean
