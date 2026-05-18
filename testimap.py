import ttyio5 as ttyio
import bbsengine5 as bbsengine

import re
import time
import email
import imaplib

def getmessageflags(args, imap, msgid):
    res, data = imap.fetch(msgid, '(FLAGS.PEEK)')
#    ttyio.echo("data=%r type=%r" % (data, type(data)), level="debug")
    for d in data:
        flags = str(d)
#        ttyio.echo("flags=%r" % (flags), level="debug")
        match = re.search(r"b'\d{,3} \(FLAGS \((\\\\)?(.*)\)\)'", flags)
        flags = match.group(2)
        flags = flags.split(" ")
#        ttyio.echo("flags=%r type=%r" % (flags, type(flags)), level="debug")
    return flags

def init(args=None, **kw):
    return True

def access(args, op, **kw):
    return True

def main(args=None):

    bbsengine.title("post office")

    start = time.time()
    host = "merlin.zoidtechnologies.com"
    login = f"jam@{host}"
    password = bbsengine.inputpassword("imap password: ")

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

    print("Logging in...")
    try:
        resp_code, response = imap.login(login, password)
    except Exception as e:
        print("ErrorType : {}, Error : {}".format(type(e).__name__, e))
        resp_code, response = None, None

    if response is None and resp_code is None:
        print("unable to login")
        return

#    print("response=%r" % (response))
#    print("Response Code : {}".format(resp_code))
#    print("Response      : {}\n".format(response[0].decode()))

#    print(imap.namespace())

    imap.select()
    typ, data = imap.search(None, 'UNSEEN')
    for num in data[0].split():
#        res, data = imap.fetch(num, "(BODY.PEEK[HEADER])", criteria=imap.AND(seen=False), mark_seen=False, bulk=True)
#        ttyio.echo("res=%r" % (res), level="debug")
#        if res != "OK":
#            ttyio.echo("error fetching message", level="error")
#            continue
        typ, data = imap.fetch(num, '(RFC822)', mark_seen=False, bulk=True)
        ttyio.echo("data=%r" % (data[0][1]), level="debug")
#        print("message=%r" % (message))
#        print("get_unixfrom=%r" % (message.get_unixfrom()))
#        print("Date=%r" % (message["date"]))
        flags = getmessageflags(None, imap, num)
        if "$label1" not in flags:
#            ttyio.echo("skipped")
            continue
        message = email.message_from_bytes(data[0][1])
        print("Subject=%r" % (message["subject"]))
        ttyio.echo("flags=%r" % (flags), level="debug")
        if "Seen" in flags:
            print("seen already")
        if "NonJunk" in flags:
            print("not junk")
#        break
    #    print('Message %s\n%s\n' % (num, data[0][1]))

    imap.close()
    imap.logout()
    #imap.select()

if __name__ == "__main__":
    main()
