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

def init(args, **kw):
  return True

def access(args, op, **kw):
  return True

def main(args, **kw):
  return True
