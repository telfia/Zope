##############################################################################
# 
# Zope Public License (ZPL) Version 1.0
# -------------------------------------
# 
# Copyright (c) Digital Creations.  All rights reserved.
# 
# This license has been certified as Open Source(tm).
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
# 1. Redistributions in source code must retain the above copyright
#    notice, this list of conditions, and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions, and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
# 
# 3. Digital Creations requests that attribution be given to Zope
#    in any manner possible. Zope includes a "Powered by Zope"
#    button that is installed by default. While it is not a license
#    violation to remove this button, it is requested that the
#    attribution remain. A significant investment has been put
#    into Zope, and this effort will continue if the Zope community
#    continues to grow. This is one way to assure that growth.
# 
# 4. All advertising materials and documentation mentioning
#    features derived from or use of this software must display
#    the following acknowledgement:
# 
#      "This product includes software developed by Digital Creations
#      for use in the Z Object Publishing Environment
#      (http://www.zope.org/)."
# 
#    In the event that the product being advertised includes an
#    intact Zope distribution (with copyright and license included)
#    then this clause is waived.
# 
# 5. Names associated with Zope or Digital Creations must not be used to
#    endorse or promote products derived from this software without
#    prior written permission from Digital Creations.
# 
# 6. Modified redistributions of any form whatsoever must retain
#    the following acknowledgment:
# 
#      "This product includes software developed by Digital Creations
#      for use in the Z Object Publishing Environment
#      (http://www.zope.org/)."
# 
#    Intact (re-)distributions of any official Zope release do not
#    require an external acknowledgement.
# 
# 7. Modifications are encouraged but must be packaged separately as
#    patches to official Zope releases.  Distributions that do not
#    clearly separate the patches from the original work must be clearly
#    labeled as unofficial distributions.  Modifications which do not
#    carry the name Zope may be packaged in any form, as long as they
#    conform to all of the clauses above.
# 
# 
# Disclaimer
# 
#   THIS SOFTWARE IS PROVIDED BY DIGITAL CREATIONS ``AS IS'' AND ANY
#   EXPRESSED OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
#   PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL DIGITAL CREATIONS OR ITS
#   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#   SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#   LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
#   USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#   ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#   OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
#   OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
#   SUCH DAMAGE.
# 
# 
# This software consists of contributions made by Digital Creations and
# many individuals on behalf of Digital Creations.  Specific
# attributions are listed in the accompanying credits file.
# 
##############################################################################

"""WebDAV xml request objects."""

__version__='$Revision: 1.13 $'[11:-2]

import sys, os, string
from common import absattr, aq_base, urlfix, urlbase
from OFS.PropertySheets import DAVProperties
from LockItem import LockItem
from WriteLockInterface import WriteLockInterface
from Acquisition import aq_parent
from xmltools import XmlParser
from cStringIO import StringIO
from urllib import quote
from AccessControl import getSecurityManager

def safe_quote(url, mark=r'%', find=string.find):
    if find(url, mark) > -1:
        return url
    return quote(url)

class DAVProps(DAVProperties):
    """Emulate required DAV properties for objects which do
       not themselves support properties. This is mainly so
       that non-PropertyManagers can appear to support DAV
       PROPFIND requests."""
    def __init__(self, obj):
        self.__obj__=obj
    def v_self(self):
        return self.__obj__
    p_self=v_self



class PropFind:
    """Model a PROPFIND request."""
    def __init__(self, request):
        self.request=request
        self.depth='infinity'
        self.allprop=0
        self.propname=0
        self.propnames=[]
        self.parse(request)
        
    def parse(self, request, dav='DAV:'):
        self.depth=request.get_header('Depth', 'infinity')
        if not (self.depth in ('0','1','infinity')):
            raise 'Bad Request', 'Invalid Depth header.'
        body=request.get('BODY', '')
        self.allprop=(not len(body))
        if not body: return
        try:    root=XmlParser().parse(body)
        except: raise 'Bad Request', sys.exc_info()[1]
        e=root.elements('propfind', ns=dav)
        if not e: raise 'Bad Request', 'Invalid xml request.'
        e=e[0]
        if e.elements('allprop', ns=dav):
            self.allprop=1
            return
        if e.elements('propname', ns=dav):
            self.propname=1
            return
        prop=e.elements('prop', ns=dav)
        if not prop: raise 'Bad Request', 'Invalid xml request.'
        prop=prop[0]
        for val in prop.elements():
            self.propnames.append((val.name(), val.namespace()))
        if (not self.allprop) and (not self.propname) and \
           (not self.propnames):
            raise 'Bad Request', 'Invalid xml request.'
        return

    def apply(self, obj, url=None, depth=0, result=None, top=1):
        if result is None:
            result=StringIO()
            depth=self.depth
            url=urlfix(self.request['URL'], 'PROPFIND')
            url=urlbase(url)
            result.write('<?xml version="1.0" encoding="utf-8"?>\n' \
                         '<d:multistatus xmlns:d="DAV:">\n')
        iscol=hasattr(obj, '__dav_collection__')
        if iscol and url[-1] != '/': url=url+'/'
        result.write('<d:response>\n<d:href>%s</d:href>\n' % safe_quote(url))
        if hasattr(aq_base(obj), 'propertysheets'):
            propsets=obj.propertysheets.values()
            obsheets=obj.propertysheets
        else:
            davprops=DAVProps(obj)
            propsets=(davprops,)
            obsheets={'DAV:': davprops}
        if self.allprop:
            stats=[]
            for ps in propsets:
                if hasattr(aq_base(ps), 'dav__allprop'):
                    stats.append(ps.dav__allprop())
            stats=string.join(stats, '') or '<d:status>200 OK</d:status>\n'
            result.write(stats)            
        elif self.propname:
            stats=[]
            for ps in propsets:
                if hasattr(aq_base(ps), 'dav__propnames'):
                    stats.append(ps.dav__propnames())
            stats=string.join(stats, '') or '<d:status>200 OK</d:status>\n'
            result.write(stats)
        elif self.propnames:
            rdict={}
            for name, ns in self.propnames:
                ps=obsheets.get(ns, None)
                if ps is not None and hasattr(aq_base(ps), 'dav__propstat'):
                    stat=ps.dav__propstat(name, rdict)
                else:
                    prop='<n:%s xmlns:n="%s"/>' % (name, ns)
                    code='404 Not Found'
                    if not rdict.has_key(code):
                        rdict[code]=[prop]
                    else: rdict[code].append(prop)
            keys=rdict.keys()
            keys.sort()
            for key in keys:
                result.write('<d:propstat>\n' \
                             '  <d:prop>\n' \
                             )
                map(result.write, rdict[key])
                result.write('  </d:prop>\n' \
                             '  <d:status>HTTP/1.1 %s</d:status>\n' \
                             '</d:propstat>\n' % key
                             )
        else: raise 'Bad Request', 'Invalid request'
        result.write('</d:response>\n')        
        if depth in ('1', 'infinity') and iscol:
            for ob in obj.objectValues():
                if hasattr(ob,"meta_type"):
                    if ob.meta_type=="Broken Because Product is Gone": continue
                dflag=hasattr(ob, '_p_changed') and (ob._p_changed == None)
                if hasattr(ob, '__locknull_resource__'):
                    # Do nothing, a null resource shouldn't show up to DAV
                    if dflag: ob._p_deactivate()
                elif hasattr(ob, '__dav_resource__'):
                    uri=os.path.join(url, absattr(ob.id))
                    depth=depth=='infinity' and depth or 0
                    self.apply(ob, uri, depth, result, top=0)
                    if dflag: ob._p_deactivate()
        if not top: return result
        result.write('</d:multistatus>')
        return result.getvalue()



class PropPatch:
    """Model a PROPPATCH request."""
    def __init__(self, request):
        self.request=request
        self.values=[]
        self.parse(request)

    def parse(self, request, dav='DAV:'):
        body=request.get('BODY', '')
        try:    root=XmlParser().parse(body)
        except: raise 'Bad Request', sys.exc_info()[1]
        vals=self.values
        e=root.elements('propertyupdate', ns=dav)
        if not e: raise 'Bad Request', 'Invalid xml request.'
        e=e[0]
        for ob in e.elements():
            if ob.name()=='set' and ob.namespace()==dav:
                proptag=ob.elements('prop', ns=dav)
                if not proptag: raise 'Bad Request', 'Invalid xml request.'
                proptag=proptag[0]
                for prop in proptag.elements():
                    # We have to ensure that all tag attrs (including
                    # an xmlns attr for all xml namespaces used by the
                    # element and its children) are saved, per rfc2518.
                    name, ns=prop.name(), prop.namespace()
                    e, attrs=prop.elements(), prop.attrs()
                    if (not e) and (not attrs):
                        # simple property
                        item=(name, ns, prop.strval(), {})
                        vals.append(item)
                    else:
                        # xml property
                        attrs={}
                        prop.remap({ns:'n'})
                        prop.del_attr('xmlns:n')
                        for attr in prop.attrs():
                            attrs[attr.qname()]=attr.value()
                        md={'__xml_attrs__':attrs}
                        item=(name, ns, prop.strval(), md)
                        vals.append(item)
            if ob.name()=='remove' and ob.namespace()==dav:
                proptag=ob.elements('prop', ns=dav)
                if not proptag: raise 'Bad Request', 'Invalid xml request.'
                proptag=proptag[0]
                for prop in proptag.elements():
                    item=(prop.name(), prop.namespace())
                    vals.append(item)

    def apply(self, obj):
        url=urlfix(self.request['URL'], 'PROPPATCH')
        if hasattr(obj, '__dav_collection__'):
            url=url+'/'
        result=StringIO()
        errors=[]
        result.write('<?xml version="1.0" encoding="utf-8"?>\n' \
                     '<d:multistatus xmlns:d="DAV:">\n' \
                     '<d:response>\n' \
                     '<d:href>%s</d:href>\n' % quote(url))
        propsets=obj.propertysheets
        for value in self.values:
            status='200 OK'
            if len(value) > 2:
                name, ns, val, md=value
                propset=propsets.get(ns, None)
                if propset is None:
                    propsets.manage_addPropertySheet('', ns)
                    propset=propsets.get(ns)
                propdict=propset._propdict()
                if propset.hasProperty(name):
                    try: propset._updateProperty(name, val, meta=md)
                    except:
                        errors.append(str(sys.exc_info()[1]))
                        status='409 Conflict'
                else:
                    try: propset._setProperty(name, val, meta=md)
                    except:
                        errors.append(str(sys.exc_info()[1]))
                        status='409 Conflict'
            else:
                name, ns=value
                propset=propsets.get(ns, None)
                if propset is None or not propset.hasProperty(name):
                    errors.append('Property not found: %s' % name)
                    status='404 Not Found'
                else:
                    try: propset._delProperty(name)
                    except:
                        errors.append('%s cannot be deleted.' % name)
                        status='409 Conflict'
            if result != '200 OK': abort=1
            result.write('<d:propstat xmlns:n="%s">\n' \
                         '  <d:prop>\n' \
                         '  <n:%s/>\n' \
                         '  </d:prop>\n' \
                         '  <d:status>HTTP/1.1 %s</d:status>\n' \
                         '</d:propstat>\n' % (ns, name, status))
        errmsg=string.join(errors, '\n') or 'The operation succeded.'
        result.write('<d:responsedescription>\n' \
                     '%s\n' \
                     '</d:responsedescription>\n' \
                     '</d:response>\n' \
                     '</d:multistatus>' % errmsg)
        result=result.getvalue()
        if not errors: return result
        # This is lame, but I cant find a way to keep ZPublisher
        # from sticking a traceback into my xml response :(
        get_transaction().abort()
        result=string.replace(result, '200 OK', '424 Failed Dependency')
        return result





class Lock:
    """Model a LOCK request."""
    def __init__(self, request):
        self.request = request
        data = request.get('BODY', '')
        self.scope = 'exclusive'
        self.type = 'write'
        self.owner = ''
        timeout = request.get_header('Timeout', 'Infinite')
        self.timeout = string.strip(string.split(timeout,',')[-1])
        self.parse(data)

    def parse(self, data, dav='DAV:'):
        root = XmlParser().parse(data)
        info = root.elements('lockinfo', ns=dav)[0]
        ls = info.elements('lockscope', ns=dav)[0]
        self.scope = ls.elements()[0].name()
        lt = info.elements('locktype', ns=dav)[0]
        self.type = lt.elements()[0].name()

        lockowner = info.elements('owner', ns=dav)
        if lockowner:
            # Since the Owner element may contain children in different
            # namespaces (or none at all), we have to find them for potential
            # remapping.  Note that Cadaver doesn't use namespaces in the
            # XML it sends.
            lockowner = lockowner[0]
            for el in lockowner.elements():
                name, elns = el.name(), el.namespace()
                if not elns:
                    # There's no namespace, so we have to add one
                    lockowner.remap({dav:'ot'})
                    el.__nskey__ = 'ot'
                    for subel in el.elements():
                        if not subel.namespace():
                            el.__nskey__ = 'ot'
                else:
                    el.remap({dav:'o'})
            self.owner = lockowner.strval()

    def apply(self, obj, creator=None, depth='infinity', token=None,
              result=None, url=None, top=1):
        """ Apply, built for recursion (so that we may lock subitems
        of a collection if requested """
        if result is None:
            result = StringIO()
            url = urlfix(self.request['URL'], 'LOCK')
            url = urlbase(url)
        iscol = hasattr(obj, '__dav_collection__')
        if iscol and url[-1] != '/': url = url + '/'
        errmsg = None
        lock = None

        try:
            lock = LockItem(creator, self.owner, depth, self.timeout,
                            self.type, self.scope, token)
            if token is None: token = lock.getLockToken()
        except ValueError, valerrors:
            errmsg = "412 Precondition Failed"
        except:
            errmsg = "403 Forbidden"

        try:
            if not WriteLockInterface.isImplementedBy(obj):
                if top:
                    # This is the top level object in the apply, so we
                    # do want an error
                    errmsg = "405 Method Not Allowed"
                else:
                    # We're in an infinity request and a subobject does
                    # not support locking, so we'll just pass
                    pass
            elif obj.wl_isLocked():
                errmsg = "423 Locked"
            else:
                method = getattr(obj, 'wl_setLock')
                vld = getSecurityManager().validate(None, obj, 'wl_setLock',
                                                    method)
                if vld and token and (lock is not None):
                    obj.wl_setLock(token, lock)
                else:
                    errmsg = "403 Forbidden"
        except:
            errmsg = "403 Forbidden"
            
        if errmsg:
            if top and ((depth in (0, '0')) or (not iscol)):
                # We don't need to raise multistatus errors
                raise errmsg[4:]
            elif not result.getvalue():
                # We haven't had any errors yet, so our result is empty
                # and we need to set up the XML header
                result.write('<?xml version="1.0" encoding="utf-8" ?>\n' \
                             '<d:multistatus xmlns:d="DAV:">\n')
            result.write('<d:response>\n <d:href>%s</d:href>\n' % url)
            result.write(' <d:status>HTTP/1.1 %s</d:status>\n' % errmsg)
            result.write('</d:response>\n')

        if depth == 'infinity' and iscol:
            for ob in obj.objectValues():
                if hasattr(obj, '__dav_resource__'):
                    uri = os.path.join(url, absattr(ob.id))
                    self.apply(ob, creator, depth, token, result,
                               uri, top=0)
        if not top: return token, result
        if result.getvalue():
            # One or more subitems probably failed, so close the multistatus
            # element and clear out all succesful locks
            result.write('</d:multistatus>')
            get_transaction().abort() # This *SHOULD* clear all succesful locks
        return token, result.getvalue()
    

class Unlock:
    """ Model an Unlock request """

    def apply(self, obj, token, url=None, result=None, top=1):
        if result is None:
            result = StringIO()
            url = urlfix(url, 'UNLOCK')
            url = urlbase(url)
        iscol = hasattr(obj, '__dav_collection__')
        if iscol and url[-1] != '/': url = url + '/'
        errmsg = None

        islockable = WriteLockInterface.isImplementedBy(obj)

        if islockable and obj.wl_hasLock(token):
            method = getattr(obj, 'wl_delLock')
            vld = getSecurityManager().validate(None,obj,'wl_delLock',method)
            if vld: obj.wl_delLock(token)
            else: errmsg = "403 Forbidden"
        elif not islockable:
            # Only set an error message if the command is being applied
            # to a top level object.  Otherwise, we're descending a tree
            # which may contain many objects that don't implement locking,
            # so we just want to avoid them
            if top: errmsg = "405 Method Not Allowed"

        if errmsg:
            if top and (not iscol):
                # We don't need to raise multistatus errors
                if errmsg[:3] == '403': raise "Forbidden"
                else: raise "Precondition Failed"
            elif not result.getvalue():
                # We haven't had any errors yet, so our result is empty
                # and we need to set up the XML header
                result.write('<?xml version="1.0" encoding="utf-8" ?>\n' \
                             '<d:multistatus xmlns:d="DAV:">\n')
            result.write('<d:response>\n <d:href>%s</d:href>\n' % url)
            result.write(' <d:status>HTTP/1.1 %s</d:status>\n' % errmsg)
            result.write('</d:response>\n')

        if iscol:
            for ob in obj.objectValues():
                if hasattr(ob, '__dav_resource__') and \
                   WriteLockInterface.isImplementedBy(ob):
                    uri = os.path.join(url, absattr(ob.id))
                    self.apply(ob, token, uri, result, top=0)
        if not top: return result
        if result.getvalue():
            # One or more subitems probably failed, so close the multistatus
            # element and clear out all succesful unlocks
            result.write('</d:multistatus>')
            get_transaction().abort()
        return result.getvalue()
    

class DeleteCollection:
    """ With WriteLocks in the picture, deleting a collection involves
    checking *all* descendents (deletes on collections are always of depth
    infinite) for locks and if the locks match. """

    def apply(self, obj, token, user, url=None, result=None, top=1):
        if result is None:
            result = StringIO()
            url = urlfix(url, 'DELETE')
            url = urlbase(url)
        iscol = hasattr(obj, '__dav_collection__')
        errmsg = None
        parent = aq_parent(obj)

        islockable = WriteLockInterface.isImplementedBy(obj)
        if parent and (not user.has_permission('Delete objects', parent)):
            # User doesn't have permission to delete this object
            errmsg = "403 Forbidden"
        elif islockable and obj.wl_isLocked():
            if token and obj.wl_hasLock(token):
                # Object is locked, and the token matches (no error)
                errmsg = ""
            else:
                errmsg = "423 Locked"

        if errmsg:
            if top and (not iscol):
                err = errmsg[4:]
                raise err
            elif not result.getvalue():
                # We haven't had any errors yet, so our result is empty
                # and we need to set up the XML header
                result.write('<?xml version="1.0" encoding="utf-8" ?>\n' \
                             '<d:multistatus xmlns:d="DAV:">\n')
            result.write('<d:response>\n <d:href>%s</d:href>\n' % url)
            result.write(' <d:status>HTTP/1.1 %s</d:status>\n' % errmsg)
            result.write('</d:response>\n')

        if iscol:
            for ob in obj.objectValues():
                dflag = hasattr(ob,'_p_changed') and (ob._p_changed == None)
                if hasattr(ob, '__dav_resource__'):
                    uri = os.path.join(url, absattr(ob.id))
                    self.apply(ob, token, user, uri, result, top=0)
                    if dflag: ob._p_deactivate()
        if not top: return result
        if result.getvalue():
            # One or more subitems can't be delted, so close the multistatus
            # element
            result.write('</d:multistatus>\n')
        return result.getvalue()
    
