import argparse

import ttyio5 as ttyio
import bbsengine5 as bbsengine

def init(args=None):
    return

def buildargs(args=None):
    parser = argparse.ArgumentParser("empyre")
    parser.add_argument("--verbose", action="store_true", dest="verbose")
    parser.add_argument("--debug", action="store_true", dest="debug")

    defaults = {"databasename": "zoidweb5", "databasehost":"localhost", "databaseuser": None, "databaseport":5432, "databasepassword":None}
    bbsengine.buildargdatabasegroup(parser, defaults)

    return parser

def setarea(args, left):
  def right():
    currentmember = bbsengine.getcurrentmember(args)
    if currentmember is None:
      return ""
    rightbuf = "| %s | %s" % (currentmember["name"], bbsengine.pluralize(currentmember["credits"], "credit", "credits"))
    if args.debug is True:
      rightbuf += " | debug"
    return rightbuf
  bbsengine.setarea(left, right)

def main(args, **kwargs):
    if args is not None and "debug" in args and args.debug is True:
        ttyio.echo("postmaster.main.100: args=%r" % (args))

    bbsengine.title("postmaster")
    ttyio.echo("database: %s host: %s:%s" % (args.databasename, args.databasehost, args.databaseport), level="debug")

if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    time.tzset()

    parser = buildargs()
    args = parser.parse_args()

    ttyio.echo("{f6:3}{cursorup:3}") # curpos:%d,0}" % (ttyio.getterminalheight()-3))
    bbsengine.initscreen(bottommargin=1)

    try:
        main(args)
    except KeyboardInterrupt:
        ttyio.echo("{/all}{bold}INTR{bold}")
    except EOFError:
        ttyio.echo("{/all}{bold}EOF{/bold}")
    finally:
        ttyio.echo("{decsc}{curpos:%d,0}{el}{decrc}{reset}{/all}" % (ttyio.getterminalheight()))
