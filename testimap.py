import time
import imaplib

start = time.time()
try:
    imap = imaplib.IMAP4(host="merlin.zoidtechnologies.com", port=143) # port=imaplib.IMAP4_SSL_PORT)
except Exception as e:
    print("ErrorType : {}, Error : {}".format(type(e).__name__, e))
    imap = None
print("connected to merlin")
imap.starttls()
print("TLS started")
#print("Connection Object : {}".format(imap_ssl))
#print("Total Time Taken  : {:,.2f} Seconds".format(time.time() - start))

print("Logging into mailbox...")
try:
    resp_code, response = imap.login("jam@merlin.zoidtechnologies.com", "12345")
except Exception as e:
    print("ErrorType : {}, Error : {}".format(type(e).__name__, e))
    resp_code, response = None, None

print("response=%r" % (response))
print("Response Code : {}".format(resp_code))
print("Response      : {}\n".format(response[0].decode()))

print(imap.namespace())

imap.select()
typ, data = imap.search(None, 'ALL')
for num in data[0].split():
    typ, data = imap.fetch(num, '(RFC822)')
    print('Message %s\n%s\n' % (num, data[0][1]))

imap.close()
imap.logout()
#imap.select()

