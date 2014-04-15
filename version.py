# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import sys
if not hasattr(sys, 'frozen'):
  import wxversion
  import platform
  if platform.system() == "Windows":
    wxversion._EM_DEBUG=True
    try:
      # the initial 3.0 release has a defective wx.propgrid module on windows
      wxversion.ensureMinimal("3.0.0")
    except:
      wxversion.ensureMinimal("2.9.4")
  elif platform.system() == "Darwin":
    wxversion.select("3.0")
#    wxversion.select("2.9.4")
  else:
    wxversion.select("3.0")


try:
  from __version import *
except:
  version="2.x"
  modDate=revDate=tagDate=None
  revLocalChange=True
  revDirty=True
  revOriginChange=True


description="4th generation\nAdministration Tool\n"
vendor="PSE"
vendorDisplay="PSE Consulting"
copyright="(c) 2013-2014 PSE Consulting Andreas Pflug"
license="Apache License V2.0"
author="PSE Consulting Andreas Pflug"