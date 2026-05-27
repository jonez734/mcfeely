from . import lib, startup


def init(args, **kw: dict) -> bool:
    pool = kw.get("pool")
    if pool and not startup.startup_main(args, pool=pool):
        return False
    return True


def access(args, op: str, **kw: dict) -> bool:
    return True


def buildargs(args, **kw: dict) -> bool:
    return None


def main(args, **kw):
    lib.runmodule(args, "main", **kw)
    return True
