import sys
import lxml
import copy
import datetime
import logging
from collections import defaultdict
from odoo.addons.purolator_shipping_integration.models.utils import get_dom_tree, python_2_unicode_compatible
import json
_logger = logging.getLogger(__name__)

@python_2_unicode_compatible
class ResponseDataObject():

    def __init__(self, mydict, datetime_nodes=[]):
        self._load_dict(mydict, list(datetime_nodes))

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "%s" % self.__dict__

    def has_key(self, name):
        try:
            getattr(self, name)
            return True
        except AttributeError:
            return False

    def get(self, name, default=None):
        try:
            return getattr(self, name)
        except AttributeError:
            return default

    def _setattr(self, name, value, datetime_nodes):
        if name.lower() in datetime_nodes:
            try:
                ts = "%s %s" % (value.partition('T')[0], value.partition('T')[2].partition('.')[0])
                value = datetime.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass

        setattr(self, name, value)

    def _load_dict(self, mydict, datetime_nodes):
        
        for a in list(mydict.items()):

            if isinstance(a[1], dict):
                o = ResponseDataObject(a[1], datetime_nodes)
                setattr(self, a[0], o)

            elif isinstance(a[1], list):
                objs = []
                for i in a[1]:
                    if i is None or isinstance(i, str) or isinstance(i, str):
                        objs.append(i)
                    else:
                        objs.append(ResponseDataObject(i, datetime_nodes))
                
                setattr(self, a[0], objs)
            else:
                self._setattr(a[0], a[1], datetime_nodes)

class Response():

    def __init__(self, obj, verb=None, parse_response=True):
        self._obj = obj
        if parse_response:
            try:
                self._dom = self._parse_xml(obj)
                self._dict = self._etree_to_dict(self._dom)

                # print(self._dict)
                if verb and 'Envelope' in list(self._dict.keys()):
                    elem = self._dom.find('Body').find('%sResponse' % verb)
                    if elem is not None:
                        self._dom = elem

                    self._dict = self._dict['Envelope']['Body'].get('%sResponse' % verb, self._dict)
                elif verb:
                    elem = self._dom.find('%sResponse' % verb)
                    if elem is not None:
                        self._dom = elem

                    self._dict = self._dict.get('%sResponse' % verb, self._dict)
                
                self.reply = ResponseDataObject(self._dict,[])

            except lxml.etree.XMLSyntaxError as e:
                _logger.debug('Response parse failed: %s' % e)
                self.reply = ResponseDataObject({}, [])
        else:
            self.reply = ResponseDataObject({}, [])

    def _get_node_path(self, t):
        i = t
        path = []
        path.insert(0, i.tag)
        while 1:
            try:
                path.insert(0, i.getparent().tag)
                i = i.getparent()
            except AttributeError:
                break

        return '.'.join(path)

    @staticmethod
    def _pullval(v):
        if len(v) == 1:
            return v[0]
        else:
            return v

    def _etree_to_dict(self, t):
        if type(t) == lxml.etree._Comment:
            return {}

        # remove xmlns from nodes, I find them meaningless
        t.tag = self._get_node_tag(t)

        d = {t.tag: {} if t.attrib else None}
        children = list(t)
        if children:
            dd = defaultdict(list)
            for dc in map(self._etree_to_dict, children):
                for k, v in list(dc.items()):
                    dd[k].append(v)

            d = {t.tag: dict((k, self._pullval(v)) for k, v in list(dd.items()))}
            #d = {t.tag: {k:v[0] if len(v) == 1 else v for k, v in dd.items()}}    

            # TODO: Optimizations? Forces a node to type list
            parent_path = self._get_node_path(t)
            for k in list(d[t.tag].keys()):
                path = "%s.%s" % (parent_path, k)

        if t.attrib:
            d[t.tag].update(('_' + k, v) for k, v in list(t.attrib.items()))
        if t.text:
            text = t.text.strip()
            if children or t.attrib:
                if text:
                    d[t.tag]['value'] = text
            else:
                d[t.tag] = text
        return d

    def __getattr__(self, name):
        return getattr(self._obj, name)

    def _parse_xml(self, xml):
        return get_dom_tree(xml)
        
    def _get_node_tag(self, node):
        return node.tag.replace('{' + node.nsmap.get(node.prefix, '') + '}', '')

    def dom(self, lxml=True):
        if not lxml:
            # create and return a cElementTree DOM
            pass
        return self._dom

    def dict(self):
        return self._dict

    def json(self):
        return json.dumps(self.dict())