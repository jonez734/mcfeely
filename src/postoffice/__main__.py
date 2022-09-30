import time
import locale

import ttyio5 as ttyio

from .boot import *

from . import lib

if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    time.tzset()

    parser = buildargs()
    args = parser.parse_args()

    ttyio.echo("{f6:3}{cursorup:3}") # curpos:%d,0}" % (ttyio.getterminalheight()-3))
    bbsengine.initscreen(bottommargin=1)

    init(args)

    try:
        lib.runsubmodule(args, "main")  # main(args)
    except KeyboardInterrupt:
        ttyio.echo("{/all}{bold}INTR{bold}")
    except EOFError:
        ttyio.echo("{/all}{bold}EOF{/bold}")
    finally:
        ttyio.echo("{decsc}{curpos:%d,0}{eraseline}{decrc}{reset}{/all}" % (ttyio.getterminalheight()))
