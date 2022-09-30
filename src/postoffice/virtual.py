import ttyio5 as ttyio
import bbsengine5 as bbsengine

from . import lib

def init(args, **kw):
  return True
  
def access(args, op, **kw):
  return True

def summary(args):
  sql = "select * from postoffice.virtual"
  dat = ()
  dbh = bbsengine.databaseconnect(args)
  cur = dbh.cursor()
  cur.execute(sql, dat)
  if cur.rowcount == 0:
    ttyio.echo("no virtual mailboxes")
    return

  for rec in bbsengine.resultiter(cur):
    ttyio.echo("%s -> %s" % (rec["pattern"], rec["result"]), end="")
    if rec["enabled"] is False:
      ttyio.echo("(disabled)")
    else:
      ttyio.echo()

def edit(args, mogrify=True):
  pattern = ttyio.inputstring("{var:promptcolor}pattern: {var:inputcolor}", noneok=True)
  if pattern is None:
    ttyio.echo("aborted")
    return

  sql = "select * from postoffice.virtual where pattern=%s"
  dat = (pattern,)
  
  dbh = bbsengine.databaseconnect(args)
  cur = dbh.cursor()
  cur.execute(sql, dat)
  if cur.rowcount == 0:
    ttyio.echo("pattern %r not found." % (pattern), level="error")
    return
  res = cur.fetchone()

#  pattern = ttyio.inputstring("{var:promptcolor}pattern: {var:inputcolor}", pattern, noneok=True)
#  if pattern is None:
#    ttyio.echo("aborted")
#    return

  result = ttyio.inputstring("result: ", res["result"])

  enabled = res["enabled"]
  if enabled is True:
    enabled = ttyio.inputboolean("{var:promptcolor}enabled? {var:optioncolor}[Yn]{var:promptcolor}: {var:inputcolor}", "Y")
  else:
    enabled = ttyio.inputboolean("{var:promptcolor}enabled? {var:optioncolor}[yN]{var:promptcolor}: {var:inputcolor}", "N")
  
  virtual = {}
  virtual["dateupdated"] = "now()"
  virtual["updatedbyid"] = bbsengine.getcurrentmemberid(args)
  virtual["pattern"] = pattern
  virtual["result"] = result
  virtual["enabled"] = enabled
  
  ttyio.echo("postoffice.virtual.edit.100: virtual=%r" % (virtual), level="debug")
  if ttyio.inputboolean("update? [yN]: ", "N") is False:
    ttyio.echo("aborted")
    return

  bbsengine.update(dbh, "postoffice.virtual", pattern, virtual, primarykey="pattern")
  dbh.commit()
  ttyio.echo("virtual mailbox updated")
  return
  

def add(args):
  pattern = ttyio.inputstring("{var:promptcolor}pattern: {var:inputcolor}", noneok=True)
  if pattern is None:
    ttyio.echo("aborted")
    return

  result =  ttyio.inputstring("{var:promptcolor}result: {var:inputcolor}", noneok=True)
  if result is None:
    ttyio.echo("aborted")
    return
  
  enabled = ttyio.inputboolean("{var:promptcolor}enabled? {var:optioncolor}[Yn]{var:promptcolor}: {var:inputcolor}", "Y")
  
  if ttyio.inputboolean("add? [yN]: ", "N") is False:
    ttyio.echo("aborted")
    return

  virtual = {}
  virtual["datecreated"] = "now()"
  virtual["createdbyid"] = bbsengine.getcurrentmemberid(args)
  virtual["pattern"] = pattern
  virtual["result"] = result
  virtual["enabled"] = enabled
  
  dbh = bbsengine.databaseconnect(args)
  id = bbsengine.insert(dbh, "postoffice.virtual", virtual, primarykey="pattern")
  dbh.commit()
  ttyio.echo("id=%r" % (id), level="debug")
  ttyio.echo("virtual address added", level="ok")
  return
  
def main(args, **kw):
  loop = True
  while loop:
    bbsengine.title("virtual mailboxes")
    lib.setarea(args, "virtual mailboxes")
    
    ttyio.echo("[A]dd")
    ttyio.echo("[S]ummary")
    ttyio.echo("[E]dit")
    ttyio.echo("{f6}[Q]uit{f6}")
    ch = ttyio.inputchar("{var:promptcolor}virtual: {var:inputcolor}", "ASEQ", "Q")
    if ch == "A":
      ttyio.echo("add")
      add(args)
    elif ch == "S":
      ttyio.echo("summary")
      summary(args)
    elif ch == "E":
      ttyio.echo("edit")
      edit(args)
    elif ch == "Q":
      ttyio.echo("quit")
      loop = False
  