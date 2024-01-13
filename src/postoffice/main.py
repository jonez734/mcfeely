import ttyio5 as ttyio
import bbsengine5 as bbsengine

from . import lib

def init(args, **kw):
  return True

def access(args, op, **kw):
  return True

def main(args, **kw):
    if args is not None and "debug" in args and args.debug is True:
        ttyio.echo("postoffice.main.100: args=%r" % (args))

    loop = True
    while loop:
      bbsengine.title("postoffice")
      ttyio.echo("database: %s host: %s:%s" % (args.databasename, args.databasehost, args.databaseport), level="debug")
      lib.setarea(args, "post office main menu")
      ttyio.echo("{var:optioncolor}[V]{var:labelcolor}irtual")
      ttyio.echo("{var:optioncolor}[M]{var:labelcolor}ailbox")
      ttyio.echo("{f6}{var:optioncolor}[Q]{var:labelcolor}uit{f6}")
      ch = ttyio.inputchar("{var:promptcolor}postoffice {var:optioncolor}[VMQ]{var:promptcolor}: {var:inputcolor}", "VMQ", "")
      if ch == "V":
        ttyio.echo("Virtual")
        lib.runsubmodule(args, "virtual")
      elif ch == "M":
        ttyio.echo("Mailboxes")
        lib.runsubmodule(args, "mailbox")
      elif ch == "Q":
        loop = False
        break
