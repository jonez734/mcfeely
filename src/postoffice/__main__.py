import time
import locale

from bbsengine6 import io, screen

from . import lib


def init(args=None) -> bool:
    return True


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    time.tzset()

    parser = lib.buildargs()
    args = parser.parse_args()

    screen.init(args)

    init(args)

    try:
        lib.runmodule(args, "main")  # main(args)
    except KeyboardInterrupt:
        io.echo("{/all}{bold}INTR{bold}")
    except EOFError:
        io.echo("{/all}{bold}EOF{/bold}")
    finally:
        io.echo(
            "{decsc}{curpos:%d,0}{eraseline}{decrc}{reset}{/all}"
            % (io.getterminalheight())
        )
