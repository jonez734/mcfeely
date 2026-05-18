# e-mail handling
## Mr. McFeely was the postman on Mr. Rogers Neighborbood

- http://www.postfix.org/PGSQL_README.html
- https://www.digitalocean.com/community/tutorials/how-to-set-up-a-postfix-email-server-with-dovecot-dynamic-maildirs-and-lmtp
- https://serverfault.com/questions/859599/postfix-dovecot-lmtp-configuration-confusion

## shared mailbox (support@bbsengine.org)
https://www.google.com/search?q=dovecot+shared+mailbox&client=firefox-b-1-d&channel=tus5&sxsrf=ALiCzsb2OglovkjNBVgjaO5M2FHCEnoPdw%3A1656037142022&ei=Fh-1YrOOAcygkPIP98aoqAE&ved=0ahUKEwiz8daMg8X4AhVMEEQIHXcjChUQ4dUDCA0&uact=5&oq=dovecot+shared+mailbox&gs_lcp=Cgdnd3Mtd2l6EAMyBQgAEIAEMgUIABCABDIGCAAQHhAWMgYIABAeEBYyBggAEB4QFjIGCAAQHhAWMgYIABAeEBYyBggAEB4QFjIGCAAQHhAWMgYIABAeEBY6BwgAEEcQsAM6BQghEKABOggIIRCgARCLAzoFCAAQhgM6CAgAEB4QFhAKSgQIQRgASgQIRhgAUKUGWOgLYOsNaAFwAXgAgAGkAYgB6ASSAQM0LjKYAQCgAQHIAQi4AQLAAQE&sclient=gws-wiz
https://doc.dovecot.org/configuration_manual/shared_mailboxes/public_shared/#public-shared-mailboxes
https://linux.die.net/man/5/virtual

- each mailbox/member combo should have a password field
- password scheme that works between dovecot, postfix, php, and python (bcrypt?) (@since 20220626)
    * https://www.php.net/manual/en/function.password-hash.php
    * https://doc.dovecot.org/configuration_manual/authentication/password_schemes/ (BLF-CRYPT)
    * https://www.google.com/search?channel=tus5&client=firefox-b-1-d&q=dovecot+bcrypt
    * https://pypi.org/project/bcrypt/
    * https://pypi.org/project/blowfish/
    * https://docs.python.org/3/library/crypt.html
- make sure that dovecot@merlin listens to IMAP_SSL_PORT (993) (@since 20220627)
- https://www.postfix.org/PGSQL_README.html
- https://www.postfix.org/postconf.5.html#alias_maps
- https://www.google.com/search?channel=tus5&client=firefox-b-1-d&q=python3+imap+examples
- https://skeptric.com/python-imap/
- https://coderzcolumn.com/tutorials/python/imaplib-simple-guide-to-manage-mailboxes-using-python
- https://wiki.gentoo.org/wiki/Complete_Virtual_Mail_Server/Postfix_to_Database
- https://www.google.com/search?channel=tus5&client=firefox-b-1-d&q=postfix+mailbox_location+pgsql

- https://python-packaging-tutorial.readthedocs.io/en/latest/setup_py.html
- https://stackoverflow.com/questions/61965070/i-am-trying-to-print-multiple-lines-at-once-with-each-line-having-a-delayed-pri

- https://docs.python.org/3/library/imaplib.html
- testimapssl.py (which no longer uses ssl) is now working. imap.starttls() fixed it.
- https://python.readthedocs.io/en/v2.7.2/library/email.html#module-email

https://serverfault.com/questions/732285/dovecot-doesnt-create-var-spool-postfix-private-auth
https://python.readthedocs.io/en/v2.7.2/library/email.parser.html#email.parser.FeedParser
https://serverfault.com/questions/571191/postfix-fatal-no-sasl-authentication-mechanisms
https://doc.dovecot.org/configuration_manual/namespace/
(https://dovecot.org/pipermail/dovecot/2020-March/118386.html)[how to create Drafts, Junk, Sent, Trash folders after user already created]
https://docs.python.org/3/library/imaplib.html
https://github.com/tonioo/sievelib/blob/master/setup.py
https://thejimmyg.github.io/goodingredients/recipe/articles/email3/postfix-gateway.html#the-relay-table

https://brokkr.net/2019/10/31/lets-do-dovecot-slowly-and-properly-part-3-lmtp/
https://serverfault.com/questions/1045230/disable-postfix-server-tls-for-specific-clients
https://www.postfix.org/TLS_README.html
https://bobcares.com/blog/unknown-mail-transport-error/
https://workaround.org/ispmail/jessie/postfix-dovecot
https://dovecot.dovecot.narkive.com/4sESGDcO/lmtp-does-not-work
https://codentium.com/guides/alpine/dovecot-lmtp/
https://doc.dovecot.org/configuration_manual/howto/postfix_dovecot_lmtp/
https://wiki.dovecot.org/HowTo/Virtual+Postfix+Dspam+Dovecot

- postoffice
    - first off, figure a way to query flags like \unseen on messages (imap)
    - at the postoffice prompt, show a proper emoji to indicate if there are unseen messages.
    - https://emojipedia.org/closed-mailbox-with-raised-flag/
    - https://stackoverflow.com/questions/52875116/reading-seen-unseen-flags-using-imaplib-in-python -- peeks BODY[HEADER] but has no actual imap flags like \unseen
    - https://regex101.com/r/GZNgNY/1
    - https://stackoverflow.com/questions/52875116/reading-seen-unseen-flags-using-imaplib-in-python
    - https://stackoverflow.com/questions/3283460/fetch-an-email-with-imaplib-but-do-not-mark-it-as-seen
    - https://stackoverflow.com/questions/28550298/using-imaplib-to-fetch-only-the-headers-of-the-emails
    - https://stackoverflow.com/questions/606191/convert-bytes-to-a-string
    - https://programtalk.com/python-examples/imaplib.ParseFlags/
    - https://stackoverflow.com/questions/72235158/imaplib-how-can-i-limit-the-number-of-messages-fetched
    - https://www.programcreek.com/python/example/2875/imaplib
