from bbsengine6 import io, util
#import ttyio5 as ttyio
#import bbsengine5 as bbsengine

from . import lib

def init(args, **kw):
  return True

def access(args, op, **kw):
  return True

def buildargs(args=None, **kw):
  return None

def main(args, **kw):
    if args is not None and "debug" in args and args.debug is True:
        io.echo("postoffice.main.100: args=%r" % (args))

    loop = True
    while loop:
      util.heading("postoffice")
      io.terminal.title("terminal title")
      io.echo(f"{{var:labelcolor}}database:{{var:valuecolor}}{args.databasename} {{var:labelcolor}}host:{{var:valuecolor}} {args.databasehost}:{args.databaseport}")
      lib.setarea(args, "zoid postoffice main menu")
      io.echo("{var:optioncolor}[V]{var:labelcolor} Virtual")
      io.echo("{var:optioncolor}[M]{var:labelcolor} Mailbox")
      io.echo("{f6}{var:optioncolor}[Q]{var:labelcolor} Quit{f6}")
      ch = io.inputchar("{var:promptcolor}postoffice {var:optioncolor}[VMQ]{var:promptcolor}: {var:inputcolor}", "VMQX", "")
      if ch == "V":
        io.echo("Virtual")
        lib.runmodule(args, "virtual")
      elif ch == "M":
        io.echo("Mailboxes")
        lib.runmodule(args, "mailbox")
      elif ch == "Q" or ch == "X":
        io.echo("Quit")
        loop = False
        break
