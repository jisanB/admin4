# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
import logger
from wh import xlt
try:
  import ldap.schema
except:
  ldap=None
from . import AttrVal


class LdapServer:
  """
  LdapServer()

  openldap interface
  http://www.python-ldap.org/doc/html/ldap.html
  """
  def __init__(self, node):
    self.lastError=None
    self.wasConnected=False
    self.ldap=None
    self.node=node
    self.subschema=None
    self.base=None

    ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
    ldap.set_option(ldap.OPT_REFERRALS,0)


    if node.settings['security'] == "ssl":
      protocol="ldaps"
    else:
      protocol="ldap"
    uri="%s://%s:%d" % (protocol, node.settings['host'], node.settings['port'])

    try:
      spot="Connect"
      self.ldap=ldap.ldapobject.SimpleLDAPObject(uri)

      if node.settings['security'] == "tls":
        spot="StartTLS"
        self.ldap.start_tls_s()

      ldap.timeout=node.timeout
  
      spot=xlt("OptReferrals")
      self.ldap.set_option(ldap.OPT_REFERRALS,0)
      
      user=node.settings['user']
      spot=xlt("Bind")
      if user:
        self.ldap.simple_bind_s(user, node.password)
      else:
        self.ldap.simple_bind_s("", "")
    except Exception as e:
      self.ldap=None
      self.lastError = str(e)
      raise adm.ConnectionException(self.node, spot, self.lastError)

    try:
      result=self.ldap.search_s("", ldap.SCOPE_BASE, "(objectClass=*)", ['*','+'] )
      self.base=result[0][1]

      try:
        subschemaDN=self.base['subschemaSubentry'][0]

#        result=self.ldap.search_s(subschemaDN, ldap.SCOPE_BASE, "(objectClass=*)", ['*','+'] )
        result=self.ldap.search_s(subschemaDN, ldap.SCOPE_BASE, "(objectClass=*)",  ['ldapSyntaxes', 'attributeTypes', 'objectclasses', 'matchingRules', 'matchingRuleUse'] )
        self.subschema=ldap.schema.SubSchema(result[0][1])
      except Exception as e:
        logger.debug("Didn't get subschema: %s", str(e))
        pass
    except Exception as e:
      logger.debug("Didn't get config: %s", str(e))
      pass
  #  adm.StopWaiting(frame)


  def execute(self, proc, *args, **kargs):
    rc=None
    frame=adm.StartWaiting()
    try:
      rc=proc(*args, **kargs)
    except Exception as e:
      d=e[0]
      adm.StopWaiting(frame, d)
      raise e

    adm.StopWaiting(frame)
    return rc

  def raiseException(self, e, what):
    if isinstance(e.args[0], dict):
      info=e.args[0].get('info')
      if not info:
        info=e.args[0].get('desc')
      if not info:
        info="Exception: %s" % str(e)
    else:
      info="%s failed. %s - %s" % (what, type(e).__name__, str(e))
    fr=adm.GetCurrentFrame()
    if fr:
      adm.StopWaiting(fr, "LDAP Error: %s" % info)
    raise adm.ServerException(self.node, info)


  def _chkLst(self, lst):
    if lst == None:
      lst=[]
    elif isinstance(lst, dict):
      lst=AttrVal.CreateList(lst)
    elif not isinstance(lst, list):
      lst=[lst]
    return lst
  
  def Modify(self, dn, chgList, addList=None, delList=None):
    chgList=self._chkLst(chgList)
    addList=self._chkLst(addList)
    delList=self._chkLst(delList)
    logger.querylog("Modify %s: Chg %s, Add %s, Del %s" % (dn, map(str, chgList), map(str, addList), map(str, delList)))

    mods=[]
    for attr in delList:
      mods.append( (ldap.MOD_DELETE, attr.name, attr.value) )
    for attr in addList:
      mods.append( (ldap.MOD_ADD, attr.name, attr.value) )
    for attr in chgList:
      mods.append( (ldap.MOD_REPLACE, attr.name, attr.value) )

    try:
      self.execute(self.ldap.modify_s, dn.encode('utf8'), mods)
      return True
    except Exception as e:
      self.raiseException(e, "Modify")


  def Delete(self, dn):
    logger.querylog("Delete %s" % dn)
    try:
      self.execute(self.ldap.delete_s, dn.encode('utf8'))
      return True
    except Exception as e:
      self.raiseException(e, "Delete")


  def Add(self, dn, addList):
    mods=[]
    addList=self._chkLst(addList)
    logger.querylog("Add %s: %s" % (dn, map(str, addList)))
    for attr in addList:
      mods.append( (attr.name, attr.value) )

    try:
      self.execute(self.ldap.add_s, dn.encode('utf8'), mods)
      return True
    except Exception as e:
      self.raiseException(e, "Add")

  def Rename(self, dn, newRdn, newParentDn=None):
    logger.querylog("Rename %s to %s %s" % (dn, newRdn, newParentDn))
    if newParentDn:
      newParentDn=newParentDn.encode('utf8')
    try:
      self.execute(self.ldap.rename_s, dn.encode('utf8'), newRdn.encode('utf8'), newParentDn)
      return True
    except Exception as e:
      self.raiseException(e, "Rename")

  def SetPassword(self, dn, passwd):
    try:
      self.execute(self.ldap.passwd_s, dn.encode('utf8'), None, passwd.encode('utf8'))
      return True
    except Exception as e:
      self.raiseException(e, "SetPassword")


  def HasFailed(self):
    return self.ldap == None
  
  
  def GetSchema(self, typ, name):
    if not self.subschema:
      return None
    return self.subschema.get_obj(typ, name)

  def GetOid(self, typ, name):
    if not self.subschema:
      return None
    a=self.subschema.get_obj(typ, name)
    if a:
      return a.oid
    return None

  def _search(self, base, filter, scope, attrs):
    """
    _search(base, filter, scope)

    result:
    (dn, valueDict) utf-encoded str
    """

    def _searchAsync(base, scope, filter, attrs):
      msgid=self.ldap.search(base.encode('utf8'), scope, filter.encode('utf8'), map(str, attrs))
      response=self.ldap.result(msgid, 1, self.ldap.timeout)
      return response[1]
    
    err=None
    try:
      result=self.execute(_searchAsync, base, scope, filter, attrs)
    except (ldap.NO_SUCH_OBJECT,ldap.NO_SUCH_ATTRIBUTE, ldap.INSUFFICIENT_ACCESS) as e:
      result=None
      err=type(e).__name__
      
    logger.querylog("%s %s base=%s, scope=%s" % (filter, str(attrs), base, ['BASE','ONE','SUB'][scope]), None, err)
    return result
  
  def Search(self, base, filter, attrs=["*"], scope=ldap.SCOPE_SUBTREE):
    if not isinstance(attrs, list):
      attrs=attrs.split()
    return self._search(base, filter, scope, attrs)

  def SearchSub(self, base, filter="(objectClass=*)", attrs=["*"]):
    return self.Search(base, filter, attrs, ldap.SCOPE_SUBTREE)

  def SearchOne(self, base, filter="(objectClass=*)", attrs=["*"]):
    return self.Search(base, filter, attrs, ldap.SCOPE_ONELEVEL)
  
  def SearchBase(self, base, filter="(objectClass=*)", attrs=["*"]):
    return self.Search(base, filter, attrs, ldap.SCOPE_BASE)
  
