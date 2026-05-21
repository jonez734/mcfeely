from . import lib


def init(args, **kw: dict) -> bool:
    return True


def access(args, op: str, **kw: dict) -> bool:
    return True


def buildargs(args, **kw: dict) -> bool:
    return None


def main(args, **kw):
    # util.heading("post office")
    lib.runmodule("main", **kw)
    return True
