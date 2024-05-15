import copy

from bbsengine6 import io, database, member, util, screen

from . import lib
    
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

def _editmailbox(args, mailbox, mode="NEEDINFO"):
  _mailbox = copy.deepcopy(mailbox)
  done = False
  while not done:
    if _mailbox != mailbox:
      dirty = True
    else:
      dirty = False
    lib.setarea(args, "postoffice %s mailbox" % (mode), dirty=dirty)
    address = _mailbox["address"] if "address" in _mailbox else None
    io.echo("{var:optioncolor}[A]{var:labelcolor}ddress: {var:valuecolor}%s" % (address))
    io.echo("{var:optioncolor}[E]{var:labelcolor}nabled: {var:valuecolor}", end="")#%s" % (enabled))
    enabled = _mailbox["enabled"] if "enabled" in _mailbox else True
    if enabled == True:
      io.echo("True", end="")
    else:
      io.echo("False", end="")
    if enabled != mailbox["enabled"]:
      io.echo(" {var:labelcolor}(was: {var:valuecolor}%s{var:labelcolor})" % (mailbox["enabled"]))
    else:
      io.echo()

    maillocation = _mailbox["maillocation"] if "maillocation" in _mailbox else "maildir:~/Maildir"
    io.echo("{var:optioncolor}[M]{var:labelcolor}ail location: {var:valuecolor}%s" % (maillocation), end="")
    if maillocation != mailbox["maillocation"]:
      io.echo(" {var:labelcolor}(was: {var:valuecolor}%s{var:labelcolor})" % (mailbox["maillocation"]))
    else:
      io.echo()

    memberid = _mailbox["memberid"]
    io.echo("{var:labelcolor}member{var:optioncolor}[I]{var:labelcolor}d: {var:valuecolor}%s" % (memberid), end="")
    if memberid != mailbox["memberid"]:
      io.echo(" {var:labelcolor}(was: {var:valuecolor}%s{var:labelcolor})" % (mailbox["memberid"]))
    else:
      io.echo()

    io.echo("{var:optioncolor}[P]{var:labelcolor}assword", end="")
    if _mailbox["password"] != mailbox["password"]:
      io.echo(" (changed)")
    else:
      io.echo()

    io.echo("{var:optioncolor}[Q]{var:labelcolor}uit{f6}")
    ch = io.inputchar("{var:promptcolor}%s mailbox {var:optioncolor}[AEIMPQ]{var:promptcolor}: {var:inputcolor}" % (mode), "AEIMPQ", "")
    if ch == "Q":
      io.echo("Q")
      errors = _validatemailbox(_mailbox)
      if len(errors) > 0:
        for e in errors:
          io.echo(e, level="error")
        if io.inputboolean("go back and fix it? [Yn]: ", "Y") is False:
          done = True
          break
        else:
          done = False
          continue
      else:
        done = True
        continue
    elif ch == "A":
      io.echo("A")
      _mailbox["address"] = io.inputstring("{var:promptcolor}address: {var:inputcolor}", _mailbox["address"])
    elif ch == "E":
      io.echo("E - Enabled")
      _mailbox["enabled"] = 1 - _mailbox["enabled"]
    elif ch == "M":
      io.echo("M - mail location")
      _mailbox["maillocation"] = io.inputstring("{var:promptcolor}mail location: {var:inputcolor}", _mailbox["maillocation"])
    elif ch == "I":
      io.echo("I - memberId")
      _mailbox["memberid"] = io.inputinteger("{var:promptcolor}memberid: {var:inputcolor}", _mailbox["memberid"])
    elif ch == "P":
      io.echo("P - password")
      passwd = util.inputpassword("{var:promptcolor}mailbox password: {var:inputcolor}")
      repeatpasswd = util.inputpassword("{promptcolor}repeat password: {var:inputcolor}")
      if passwd == repeatpasswd:
        _mailbox["password"] = passwd
      else:
        io.echo("passwords do not match", level="error")
      
  return _mailbox

def summary(args):
  sql = "select * from postoffice.mailbox"
  dat = ()
  dbh = database.connect(args)
  cur = dbh.cursor()
  cur.execute(sql, dat)
  if cur.rowcount == 0:
    io.echo("no mailboxes")
    return
  for rec in database.resultiter(cur):
    io.echo("Address: %r" % (rec["address"]), end="")
    enabled = rec["address"]
    if enabled is False:
      io.echo(" (disabled)")
    else:
      io.echo()

def add(args):
  mailbox = {}
  mailbox["address"] = None
  mailbox["maillocation"] = "maildir:~/Maildir"
  mailbox["enabled"] = True
  mailbox["memberid"] = member.getcurrentid(args)
  mailbox["password"] = None

  _mailbox = _editmailbox(args, mailbox, "add")
  if mailbox != _mailbox:
    ch = io.inputboolean("{var:promptcolor}add mailbox? {var:optioncolor}[yN]{var:promptcolor}: {var:inputcolor}", "N")
    if ch is True:
      memberid = _mailbox["memberid"]
      del _mailbox["memberid"]

      plaintextpassword = _mailbox["password"]
      del _mailbox["password"]
      dbh = database.connect(args)
      address = database.insert(args, "postoffice.mailbox", _mailbox, primarykey="address", mogrify=True)
      encryptedpassword = util.getencryptedpassword(args, plaintextpassword)

      _map = {}
      _map["address"] = address
      _map["memberid"] = memberid
      _map["password"] = encryptedpassword
      _map["kind"] = "inbound outbound"
      database.insert(args, "postoffice.mailbox_password", _map, primarykey="address", mogrify=True)
      dbh.commit()
      io.echo("added.")

def init(args, **kw):
  return True

def access(args, op, **kw):
  return True

def buildargs(args=None, **kw):
  return None

def main(args, **kw):
  loop = True
  while loop:
    screen.title("mailboxes")
    lib.setarea(args, "mailboxes")
    io.echo("{optioncolor}[S]{labelcolor} Summary")
    io.echo("{optioncolor}[E]{labelcolor} Edit")
    io.echo("{optioncolor}[A]{labelcolor} Add")
    io.echo("{f6}{optioncolor}[Q]{labelcolor} Quit{f6}")
    
    ch = io.inputchar("{var:promptcolor}mailbox {var:optioncolor}[SEAQ]{var:promptcolor}: {var:inputcolor}", "SEAQX", "Q")
    if ch == "S":
      io.echo("summary")
      summary(args)
    elif ch == "E":
      io.echo("edit")
      edit(args)
    elif ch == "A":
      io.echo("add")
      add(args)
    elif ch == "Q" or ch == "X":
      io.echo("quit")
      loop = False

  return True
