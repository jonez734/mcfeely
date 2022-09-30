PACKAGENAME = "postoffice"

import ttyio5 as ttyio
import bbsengine5 as bbsengine

def setarea(args, left, dirty=False):
  def right():
    currentmember = bbsengine.getcurrentmember(args)
    if currentmember is None:
      return ""
    rightbuf = "| %s | %s" % (currentmember["name"], bbsengine.pluralize(currentmember["credits"], "credit", "credits"))
    if args.debug is True:
      rightbuf += " | debug"
    if dirty is True:
      rightbuf += " | dirty"
    return rightbuf
  bbsengine.setarea(left, right)

def getmessageflags(args, imap, msgid):
        res = imap.fetch(msgid, '(FLAGS)')
        flags = res.replace("\\\\", "")
        flags = flags.split(" ")
        return flags

# @since 20220628
def getencryptedpassword(args, plaintextpassword:str) -> str:
  sql = "select crypt(%s, gen_salt('md5'))" # previously 'bf' which does not work with dovecot
  dat = (plaintextpassword,)
  dbh = bbsengine.databaseconnect(args)
  cur = dbh.cursor()
  cur.execute(sql, dat)
  res = cur.fetchone()
  return res["crypt"]

# @since 20220628 copied from bbsengine5
def setmailboxpassword(args, memberid:int, plaintextpassword:str, address:str) -> bool:
  dbh = bbsengine.databaseconnect(args)
  cur = dbh.cursor()
  encryptedpassword = getencryptedpassword(args, plaintextpassword)
  sql = "update postoffice.map_mailbox_memberid set password=%s where address=%s and memberid=%s"
  dat = (encryptedpassword, address, memberid)
  cur.execute(sql, dat)
  if cur.rowcount == 0:
    return False
  return True

def checkmodule(args, module, **kw):
    module = PACKAGENAME + "." + module
    return bbsengine.checkmodule(args, module, **kw)

def runmodule(args, submodule, **kw):
    x = "%s.%s" % (PACKAGENAME, submodule)
    if args.debug is True:
        ttyio.echo("postoffice.lib.runmodule.100: x=%r" % (x), level="debug")

    if checkmodule(args, submodule) is False:
        ttyio.echo("postoffice.lib.runmodule.120: module %r not available" % (x), level="error")
        return

    return bbsengine.runmodule(args, x, **kw)

def runsubmodule(args, submodule, **kw):
    return runmodule(args, submodule, buildargs=False, **kw)
