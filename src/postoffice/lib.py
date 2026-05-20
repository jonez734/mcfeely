import argparse

from bbsengine6 import module, io, member, util, screen, database

PACKAGENAME = "postoffice"

# import ttyio5 as ttyio
# import bbsengine5 as bbsengine


def setarea(args, left, dirty=False):
    def right():
        currentmember = member.getcurrent(args)
        if currentmember is None:
            return ""
        rightbuf = "| %s | %s" % (
            currentmember["moniker"],
            util.pluralize(currentmember["credits"], "credit", "credits"),
        )
        if args.debug is True:
            rightbuf += " | debug"
        if dirty is True:
            rightbuf += " | dirty"
        return rightbuf

    screen.setarea(left, right)


def getmessageflags(args, imap, msgid):
    res = imap.fetch(msgid, "(FLAGS)")
    flags = res.replace("\\\\", "")
    flags = flags.split(" ")
    return flags


# @since 20220628 copied from bbsengine5
def setmailboxpassword(
    args, memberid: int, plaintextpassword: str, address: str
) -> bool:
    dbh = database.connect(args)
    cur = dbh.cursor()
    encryptedpassword = util.getencryptedpassword(args, plaintextpassword)
    sql = "update postoffice.map_mailbox_memberid set password=%s where address=%s and memberid=%s"
    dat = (encryptedpassword, address, memberid)
    cur.execute(sql, dat)
    if cur.rowcount == 0:
        return False
    return True


def checkmodule(args, modulename, **kw):
    return module.check(args, f"{PACKAGENAME}.{modulename}", **kw)


def runmodule(args, modulename, **kw):
    x = f"{PACKAGENAME}.{modulename}"
    if args.debug is True:
        io.echo(f"postoffice.lib.runmodule.100: {x=}", level="debug")

    if checkmodule(args, modulename) is False:
        io.echo(
            f"postoffice.lib.runmodule.120: module {x} not available", level="error"
        )
        return

    return module.runmodule(args, x, **kw)


def get_db_connection(args, **kwargs):
    """
    Extract or create database connection from kwargs.

    Implements CONN_POOL_PATTERN: handles both conn and pool parameters.

    Args:
        args: bbsengine6 args object
        **kwargs: May contain 'conn' (database connection) or 'pool' (connection pool)

    Returns:
        Tuple of (use_conn, should_close)
        - use_conn: Database connection object (or None if unavailable)
        - should_close: Boolean indicating if caller should close the connection
    """
    conn = kwargs.get("conn")
    pool = kwargs.get("pool")

    use_conn = conn
    should_close = False

    if use_conn is None and pool is not None:
        try:
            use_conn = database.connect(args, pool=pool)
            should_close = True
        except Exception as e:
            io.echo(f"lib.get_db_connection: {e}", level="error")
            return None, False

    return use_conn, should_close


def buildargs(args=None, **kw):
    parser = argparse.ArgumentParser("skel")
    parser.add_argument("--verbose", action="store_true", dest="verbose")
    parser.add_argument("--debug", action="store_true", dest="debug")

    defaults = {
        "databasename": "zoid6",
        "databasehost": "localhost",
        "databaseuser": None,
        "databaseport": 5432,
        "databasepassword": None,
    }
    database.buildargdatabasegroup(parser, defaults)

    return parser
