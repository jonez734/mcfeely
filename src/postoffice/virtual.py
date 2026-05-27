from typing import Any

from bbsengine6 import io, database, member

from . import lib


def init(args, **kw):
    return True


def access(args, op, **kw):
    return True


def buildargs(args=None, **kw):
    return lib.buildargs(args)


class completeVirtualPattern:
    def __init__(self, args: Any, **kw: Any) -> None:
        self.args = args

    def complete(self, text: str, state: int) -> str | None:
        if self.args.debug is True:
            io.echo("completeVirtualPattern.140: complete called", level="debug")

        vocab = []
        sql = "select pattern from postoffice.virtual"
        dat = ()

        dbh = database.connect(self.args)

        cur = dbh.cursor()
        if self.args.debug is True:
            io.echo(f"completeVirtualPattern.120: {cur.mogrify(sql, dat)=}")
        cur.execute(sql, dat)

        for rec in database.resultiter(cur):
            vocab.append(rec["pattern"])

        results = [x for x in vocab if x.startswith(text)] + [None]
        return results[state]


def inputvirtualpattern(args, prompt, oldvalue=None, **kw):
    return io.inputstring(
        prompt, oldvalue, completer=completeVirtualPattern(args), completerdelims="\n, "
    )


def summary(args):
    sql = "select * from postoffice.virtual"
    dat = ()
    dbh = database.connect(args)
    cur = dbh.cursor()
    cur.execute(sql, dat)
    if cur.rowcount == 0:
        io.echo("no virtual mailboxes")
        return

    for rec in database.resultiter(cur):
        io.echo(
            f"{{var:valuecolor}}{rec['pattern']}{{var:labelcolor}} -> {{var:valuecolor}}{rec['result']}",
            end="",
        )
        if rec["enabled"] is False:
            io.echo("(disabled)")
        else:
            io.echo()


def edit(args, mogrify=True):
    pattern = inputvirtualpattern(
        args, "{var:promptcolor}virtual pattern: {var:inputcolor}", noneok=True
    )
    if pattern is None:
        io.echo("aborted")
        return

    sql = "select * from postoffice.virtual where pattern=%s"
    dat = (pattern,)

    dbh = database.connect(args)
    cur = dbh.cursor()
    cur.execute(sql, dat)
    if cur.rowcount == 0:
        io.echo(f"pattern {pattern} not found.", level="error")
        return
    res = cur.fetchone()

    #  pattern = ttyio.inputstring("{var:promptcolor}pattern: {var:inputcolor}", pattern, noneok=True)
    #  if pattern is None:
    #    ttyio.echo("aborted")
    #    return

    result = io.inputstring("result: ", res["result"])

    enabled = res["enabled"]
    if enabled is True:
        enabled = io.inputboolean(
            "{var:promptcolor}enabled? {var:optioncolor}[Yn]{var:promptcolor}: {var:inputcolor}",
            "Y",
        )
    else:
        enabled = io.inputboolean(
            "{var:promptcolor}enabled? {var:optioncolor}[yN]{var:promptcolor}: {var:inputcolor}",
            "N",
        )

    virtual = {}
    virtual["dateupdated"] = "now()"
    virtual["updatedbyid"] = member.getcurrentid(args)
    virtual["pattern"] = pattern
    virtual["result"] = result
    virtual["enabled"] = enabled

    io.echo(f"postoffice.virtual.edit.100: {virtual=}", level="debug")
    if (
        io.inputboolean(
            "{promptcolor}update? {optioncolor}[yN]{promptcolor}: {inputcolor}", "N"
        )
        is False
    ):
        io.echo("aborted")
        return

    database.update(args, "postoffice.virtual", pattern, virtual, primarykey="pattern")
    database.commit(args)
    io.echo("virtual mailbox updated")
    return


def add(args):
    pattern = io.inputstring("{var:promptcolor}pattern: {var:inputcolor}", noneok=True)
    if pattern is None:
        io.echo("aborted")
        return

    result = io.inputstring("{var:promptcolor}result: {var:inputcolor}", noneok=True)
    if result is None:
        io.echo("aborted")
        return

    enabled = io.inputboolean(
        "{var:promptcolor}enabled? {var:optioncolor}[Yn]{var:promptcolor}: {var:inputcolor}",
        "Y",
    )

    if (
        io.inputboolean(
            "{promptcolor}add? {optioncolor}[yN]{promptcolor}: {inputcolor}", "N"
        )
        is False
    ):
        io.echo("aborted")
        return

    virtual = {}
    virtual["datecreated"] = "now()"
    virtual["createdbymoniker"] = member.getcurrentmoniker(args)
    virtual["pattern"] = pattern
    virtual["result"] = result
    virtual["enabled"] = enabled

    id = database.insert(args, "postoffice.virtual", virtual, primarykey="pattern")
    database.commit(args)
    io.echo(f"{id=}", level="debug")
    io.echo("virtual address added", level="ok")
    return


def main(args, **kw):
    loop = True
    while loop:
        io.terminal.title("virtual mailboxes")
        lib.setarea(args, "virtual mailboxes")

        io.echo("{var:optioncolor}[A]{var:labelcolor} Add")
        io.echo("{var:optioncolor}[S]{var:labelcolor} Summary")
        io.echo("{var:optioncolor}[E]{var:labelcolor} Edit")
        io.echo("{f6}{var:optioncolor}[Q]{var:labelcolor} Quit{f6}")
        ch = io.inputchar("{var:promptcolor}virtual: {var:inputcolor}", "ASEQX", "Q")
        if ch == "A":
            io.echo("add")
            add(args)
        elif ch == "S":
            io.echo("summary")
            summary(args)
        elif ch == "E":
            io.echo("edit")
            edit(args)
        elif ch == "Q" or ch == "X":
            io.echo("quit")
            loop = False
