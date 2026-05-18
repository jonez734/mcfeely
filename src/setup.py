#!/usr/bin/env python

import os
import time
from setuptools import setup

r = 1
v = time.strftime("%Y%m%d%H%M")

projectname = "postoffice"

# os.system("./updateversion.sh") use Makefile!

setup(
  name=projectname,
  version=v,
  url=f"https://repo.zoidtechnologies.com/{projectname}/",
  author="zoidtechnologies.com",
  author_email=f"{projectname}@projects.zoidtechnologies.com",
  requires=["bbsengine6", ],
  scripts=["bin/postoffice"],
  license="GPLv2",
  provides=[projectname,],
  long_description = """postoffice -- maintain virtual and mailbox email accounts""",
  include_package_data = True
)
