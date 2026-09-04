from . import lib, startup


def init(args, **kw: dict) -> bool:
    """bbsengine6 module-conventional init hook.

    Mirrors casino's pattern: casino's __init__.py exposes ``init``
    which is the bbsengine6 module-conventional hook. We delegate to
    postoffice.startup.startup_main when given a pool, identical in
    shape to casino delegating to casino.startup.checkcasino.

    The bbsengine6 startup chain reaches the schema setup via
    ``runmodule(args, "startup", package="postoffice")`` which loads
    ``postoffice.startup`` (the submodule) and dispatches into its
    ``main()`` entry point -- which in turn delegates to
    ``startup_main()``. This module's ``init`` is the project-level
    hook for callers that already have a pool (e.g., bed's module
    loader), matching casino's pattern.
    """
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
