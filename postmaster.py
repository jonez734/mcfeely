import locale
import copy
import time
import argparse

import ttyio5 as ttyio
import bbsengine5 as bbsengine

def init(args=None):
  ttyio.setvariable("menuoption", "{white}{bggray}")
  ttyio.setvariable("menudesc", "{/all}")
  ttyio.setvariable("menuvalue", "{/bgcolor}{green}")
  ttyio.setvariable("promptcolor", "{/bgcolor}{lightgray}")
  ttyio.setvariable("inputcolor", "{/bgcolor}{green}")
  return

def buildargs(args=None):
    parser = argparse.ArgumentParser("empyre")
    parser.add_argument("--verbose", action="store_true", dest="verbose")
    parser.add_argument("--debug", action="store_true", dest="debug")

    defaults = {"databasename": "zoidweb5", "databasehost":"localhost", "databaseuser": None, "databaseport":15433, "databasepassword":None} # port=5432
    bbsengine.buildargdatabasegroup(parser, defaults)

    return parser

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

# @since 20220628
def getencryptedpassword(args, plaintextpassword):
  sql = "select crypt(%s, gen_salt('md5'))" # previously 'bf' which does not work with dovecot
  dat = (plaintextpassword,)
  dbh = bbsengine.databaseconnect(args)
  cur = dbh.cursor()
  cur.execute(sql, dat)
  res = cur.fetchone()
  return res["crypt"]

# @since 20220628 copied from bbsengine5
def setmailboxpassword(args, memberid, plaintextpassword, address):
  dbh = bbsengine.databaseconnect(args)
  cur = dbh.cursor()
  encryptedpassword = getencryptedpassword(args, plaintextpassword)
  sql = "update postoffice.map_mailbox_memberid set password=%s where address=%s and memberid=%s"
  dat = (encryptedpassword, address, memberid)
  cur.execute(sql, dat)
  if cur.rowcount == 0:
    return False
  return True

def _validatemailbox(mailbox):
  errors = []
  if "password" in mailbox and mailbox["password"] is None:
    errors.append("password must not be None")
  if "address" in mailbox and mailbox["address"] is None:
    errors.append("address must not be None")
  if "maillocation" in mailbox and mailbox["maillocation"] is None:
    errors.append("maillocation must not be None")
  if "memberid" in mailbox and mailbox["memberid"] is None:
    errors.append("memberid must not be None")
  return errors

def _editmailbox(mailbox, mode="NEEDINFO"):
  _mailbox = copy.deepcopy(mailbox)
  done = False
  while not done:
    if _mailbox != mailbox:
      dirty = True
    else:
      dirty = False
    setarea(args, "postoffice %s mailbox" % (mode), dirty=dirty)
    address = _mailbox["address"] if "address" in _mailbox else None
    ttyio.echo("{var:menuoption}[A]{var:menudesc}ddress: {var:menuvalue}%s" % (address))
    ttyio.echo("{var:menuoption}[E]{var:menudesc}nabled: {var:menuvalue}", end="")#%s" % (enabled))
    enabled = _mailbox["enabled"] if "enabled" in _mailbox else True
    if enabled == True:
      ttyio.echo("True", end="")
    else:
      ttyio.echo("False", end="")
    if enabled != mailbox["enabled"]:
      ttyio.echo(" {var:menudesc}(was: {var:menuvalue}%s{var:menudesc})" % (mailbox["enabled"]))
    else:
      ttyio.echo()

    maillocation = _mailbox["maillocation"] if "maillocation" in _mailbox else None
    ttyio.echo("{var:menuoption}[M]{var:menudesc}ail location: {var:menuvalue}%s" % (maillocation), end="")
    if maillocation != mailbox["maillocation"]:
      ttyio.echo(" {var:menudesc}(was: {var:menuvalue}%s{var:menudesc})" % (mailbox["maillocation"]))
    else:
      ttyio.echo()

    memberid = _mailbox["memberid"]
    ttyio.echo("{var:menudesc}member{var:menuoption}[I]{var:menudesc}d: {var:menuvalue}%s" % (memberid), end="")
    if memberid != mailbox["memberid"]:
      ttyio.echo(" {var:menudesc}(was: {var:menuvalue}%s{var:menudesc})" % (mailbox["memberid"]))
    else:
      ttyio.echo()

    ttyio.echo("{var:menuoption}[P]{var:menudesc}assword")

    ttyio.echo("{var:menuoption}[Q]{var:menudesc}uit{f6}")
    ch = ttyio.inputchar("{var:promptcolor}%s mailbox [AEIMPQ]: {var:inputcolor}" % (mode), "AEIMPQ", "")
    if ch == "Q":
      ttyio.echo("Q")
      errors = _validatemailbox(_mailbox)
      if len(errors) > 0:
        for e in errors:
          ttyio.echo(e, level="error")
        if ttyio.inputboolean("go back and fix it? [Yn]: ", "Y") is False:
          done = True
          break
        else:
          done = False
          continue
      else:
        done = True
        continue
    elif ch == "A":
      ttyio.echo("A")
      _mailbox["address"] = ttyio.inputstring("{var:promptcolor}address: {var:inputcolor}", _mailbox["address"])
    elif ch == "E":
      ttyio.echo("E - Enabled")
      _mailbox["enabled"] = 1 - _mailbox["enabled"]
    elif ch == "M":
      ttyio.echo("M - mail location")
      _mailbox["maillocation"] = ttyio.inputstring("{var:promptcolor}mail location: {var:inputcolor}", _mailbox["maillocation"])
    elif ch == "I":
      ttyio.echo("I - memberId")
      _mailbox["memberid"] = ttyio.inputinteger("{var:promptcolor}memberid: {var:inputcolor}", _mailbox["memberid"])
    elif ch == "P":
      ttyio.echo("P - password")
      _mailbox["password"] = ttyio.inputstring("{var:promptcolor}mailbox password: {var:inputcolor}")
  return _mailbox

def addmailbox(args):
  mailbox = {}
  mailbox["address"] = None
  mailbox["maillocation"] = None
  mailbox["enabled"] = True
  mailbox["memberid"] = bbsengine.getcurrentmemberid(args)
  mailbox["password"] = None

  _mailbox = _editmailbox(mailbox, "add")
  if mailbox != _mailbox:
    ch = ttyio.inputboolean("{var:promptcolor}add mailbox? [yN]: {var:inputcolor}", "N")
    if ch is True:
      memberid = _mailbox["memberid"]
      del _mailbox["memberid"]

      plaintextpassword = _mailbox["password"]
      del _mailbox["password"]
      dbh = bbsengine.databaseconnect(args)
      address = bbsengine.insert(dbh, "postoffice.mailbox", _mailbox, primarykey="address", mogrify=True)
      encryptedpassword = getencryptedpassword(args, plaintextpassword)
      _map = {}
      _map["address"] = address
      _map["memberid"] = memberid
      _map["password"] = encryptedpassword
      bbsengine.insert(dbh, "postoffice.map_mailbox_memberid", _map, primarykey="address", mogrify=True)
      dbh.commit()
      ttyio.echo("added.")

def main(args, **kwargs):
    if args is not None and "debug" in args and args.debug is True:
        ttyio.echo("postoffice.main.100: args=%r" % (args))

    done = False
    while not done:
      bbsengine.title("postoffice")
      ttyio.echo("database: %s host: %s:%s" % (args.databasename, args.databasehost, args.databaseport), level="debug")
      setarea(args, "post office main menu")
      ttyio.echo("{var:menuoption}[A]{var:menudesc}dd address")
      ttyio.echo("{f6}{var:menuoption}[Q]{var:menudesc}uit{f6}")
      ch = ttyio.inputchar("{var:promptcolor}postoffice [AQ]: {var:inputcolor}", "AQ", "")
      if ch == "A":
        ttyio.echo("A - add address")
        t = ttyio.inputchar("{var:promptcolor}Type {var:menuoption}[V]{var:menudesc}irtual or {var:menuoption}[M]{var:menudesc}ailbox: {var:inputcolor}", "VM", "")
        if t == "M":
          ttyio.echo("Mailbox")
          addmailbox(args)
        elif t == "V":
          ttyio.echo("Virtual")
          # addvirtual()
      elif ch == "Q":
        ttyio.echo("Q - Quit")
        done = True

if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    time.tzset()

    parser = buildargs()
    args = parser.parse_args()

    ttyio.echo("{f6:3}{cursorup:3}") # curpos:%d,0}" % (ttyio.getterminalheight()-3))
    bbsengine.initscreen(bottommargin=1)

    init(args)

    try:
        main(args)
    except KeyboardInterrupt:
        ttyio.echo("{/all}{bold}INTR{bold}")
    except EOFError:
        ttyio.echo("{/all}{bold}EOF{/bold}")
    finally:
        ttyio.echo("{decsc}{curpos:%d,0}{el}{decrc}{reset}{/all}" % (ttyio.getterminalheight()))
