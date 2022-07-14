import ttyio5 as ttyio
import time
import email
import imaplib

def main(args=None):
    start = time.time()
    host = "merlin.zoidtechnologies.com"
    login = "jam@%s" % (host)
    password = "123456"

    ttyio.echo("welcome to the postoffice!")
    try:
        imap = imaplib.IMAP4(host, port=143) # port=imaplib.IMAP4_SSL_PORT)
    except Exception as e:
        print("ErrorType : {}, Error : {}".format(type(e).__name__, dir(e)))
        imap = None
    if imap is None:
        print("unable to connect to host")
        return
    print("connected to %s" % (host))

    imap.starttls()
    print("TLS started")
    #print("Total Time Taken  : {:,.2f} Seconds".format(time.time() - start))

    print("Logging into mailbox...")
    try:
        resp_code, response = imap.login(login, password)
    except Exception as e:
        print("ErrorType : {}, Error : {}".format(type(e).__name__, e))
        resp_code, response = None, None

    if response is None and resp_code is None:
        print("unable to login")
        return

    print("response=%r" % (response))
    print("Response Code : {}".format(resp_code))
    print("Response      : {}\n".format(response[0].decode()))

    print(imap.namespace())

    imap.select()
    typ, data = imap.search(None, 'ALL')
    for num in data[0].split():
        typ, data = imap.fetch(num, '(RFC822)')
        ttyio.echo("data=%r" % (data[0][1]), level="debug")
        message = email.message_from_bytes(data[0][1])
        print("message=%r" % (message))
        print("get_unixfrom=%r" % (message.get_unixfrom()))
        print("Subject=%r" % (message["subject"]))
        print("Date=%r" % (message["date"]))
        break
    #    print('Message %s\n%s\n' % (num, data[0][1]))

    imap.close()
    imap.logout()
    #imap.select()

if __name__ == "__main__":
    main()
