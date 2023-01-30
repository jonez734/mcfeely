import argparse

import bbsengine5 as bbsengine

def init(args=None, **kw):
#  ttyio.setvariable("menuoption", "{white}{bggray}")
#  ttyio.setvariable("menudesc", "{/bgcolor}{white}")
#  ttyio.setvariable("menuvalue", "{/bgcolor}{green}")
#  ttyio.setvariable("promptcolor", "{/bgcolor}{lightgray}")
#  ttyio.setvariable("inputcolor", "{/bgcolor}{green}")
  return

def buildargs(args=None, **kw):
    parser = argparse.ArgumentParser("postoffice")
    parser.add_argument("--verbose", action="store_true", dest="verbose")
    parser.add_argument("--debug", action="store_true", dest="debug")

    defaults = {"databasename": "zoidweb5", "databasehost":"localhost", "databaseuser": None, "databaseport":15433, "databasepassword":None} # port=5432
#    defaults = {"databasename": "zoidweb5", "databasehost":"localhost", "databaseuser": None, "databaseport":5432, "databasepassword":None} # port=5432
    bbsengine.buildargdatabasegroup(parser, defaults)

    return parser
