import sys
from lxml import etree as ET

def parse_yaml(yaml_file):
    """
    This is simple approach to parsing a yaml config that is only
    intended for this SDK as this only supports a very minimal subset
    of yaml options.
    """

    with open(yaml_file) as f:
        data = {None: {}}
        current_key = None

        for line in f.readlines():

            # ignore comments
            if line.startswith('#'):
                continue

            # parse the header
            elif line[0].isalnum():
                key = line.strip().replace(':', '')
                current_key = key
                data[current_key] = {}

            # parse the key: value line
            elif line[0].isspace():
                values = line.strip().split(':')

                if len(values) == 2:
                    cval = values[1].strip()

                    if cval == '0':
                        cval = False
                    elif cval == '1':
                        cval = True

                    data[current_key][values[0].strip()] = cval
        return data


def python_2_unicode_compatible(klass):
    """
    A decorator that defines __unicode__ and __str__ methods under Python 2.
    Under Python 3 it does nothing.

    To support Python 2 and 3 with a single code base, define a __str__ method
    returning text and apply this decorator to the class.
    """
    if sys.version_info[0] < 3:
        if '__str__' not in klass.__dict__:
            raise ValueError("@python_2_unicode_compatible cannot be applied "
                             "to %s because it doesn't define __str__()." %
                             klass.__name__)
        klass.__unicode__ = klass.__str__
        klass.__str__ = lambda self: self.__unicode__().encode('utf-8')
    return klass


def get_dom_tree(xml):
    tree = ET.fromstring(xml.content)
    return tree.getroottree().getroot()

def attribute_check(root):
    attrs = []
    value = None

    if isinstance(root, dict):
        if '#text' in root:
            value = root['#text']
        if '@attrs' in root:
            for ak, av in sorted(root.pop('@attrs').items()):
                attrs.append(str('{0}="{1}"').format(ak, smart_encode(av)))

    return attrs, value

def smart_encode(value):
    try:
        if sys.version_info[0] < 3:
            return str(value).encode('utf-8')
        else:
            return value
            #return str(value)

    except UnicodeDecodeError:
        return value


def to_xml(root):
    return dict2xml(root)

def dict2xml(root):
    xml = str('')
    if root is None:
        return xml

    if isinstance(root, dict):
        for key in sorted(root.keys()):

            if isinstance(root[key], dict):
                attrs, value = attribute_check(root[key])

                if not value:
                    value = dict2xml(root[key])
                elif isinstance(value, dict):
                    value = dict2xml(value)

                attrs_sp = str('')
                if len(attrs) > 0:
                    attrs_sp = str(' ')

                xml = str('{xml}<{tag}{attrs_sp}{attrs}>{value}</{tag}>') \
                    .format(**{'tag': key, 'xml': str(xml), 'attrs': str(' ').join(attrs),
                               'value': smart_encode(value), 'attrs_sp': attrs_sp})

            elif isinstance(root[key], list):

                for item in root[key]:
                    attrs, value = attribute_check(item)

                    if not value:
                        value = dict2xml(item)
                    elif isinstance(value, dict):
                        value = dict2xml(value)

                    attrs_sp = ''
                    if len(attrs) > 0:
                        attrs_sp = ' '

                    xml = str('{xml}<{tag}{attrs_sp}{attrs}>{value}</{tag}>') \
                        .format(**{'xml': str(xml), 'tag': key, 'attrs': ' '.join(attrs), 'value': smart_encode(value),
                                   'attrs_sp': attrs_sp})

            else:
                value = root[key]
                xml = str('{xml}<{tag}>{value}</{tag}>') \
                    .format(**{'xml': str(xml), 'tag': key, 'value': smart_encode(value)})

    elif isinstance(root, str) or isinstance(root, int) \
        or isinstance(root, str) or isinstance(root, int) \
        or isinstance(root, float):
        xml = str('{0}{1}').format(str(xml), root)
    else:
        raise Exception('Unable to serialize node of type %s (%s)' % \
            (type(root), root))

    return xml

def getValue(response_dict, *args, **kwargs):
    args_a = [w for w in args]
    first = args_a[0]
    args_a.remove(first)

    h = kwargs.get('mydict', {})
    if h:
        h = h.get(first, {})
    else:
        h = response_dict.get(first, {})

    if len(args) == 1:
        try:
            return h.get('value', None)
        except:
            return h

    last = args_a.pop()

    for a in args_a:
        h = h.get(a, {})

    h = h.get(last, {})

    try:
        return h.get('value', None)
    except:
        return h

def getNodeText(node):
    "Returns the node's text string."

    rc = []

    if hasattr(node, 'childNodes'):
        for cn in node.childNodes:
            if cn.nodeType == cn.TEXT_NODE:
                rc.append(cn.data)
            elif cn.nodeType == cn.CDATA_SECTION_NODE:
                rc.append(cn.data)

    return ''.join(rc)

def perftest_dict2xml():
    sample_dict = {
        'searchFilter': {'categoryId': {'#text': 222, '@attrs': {'site': 'US'}}},
        'paginationInput': {
            'pageNumber': '1',
            'pageSize': '25'
        },
        'itemFilter': [
            {'name': 'Condition',
             'value': 'Used'},
            {'name': 'LocatedIn',
             'value': 'GB'},
        ],
        'sortOrder': 'StartTimeNewest'
    }
    xml = dict2xml(sample_dict)

if __name__ == '__main__':

    import timeit
    # print(("perftest_dict2xml() %s" % \
    #     timeit.timeit("perftest_dict2xml()", number=50000,
    #                   setup="from __main__ import perftest_dict2xml")))

    import doctest
    failure_count, test_count = doctest.testmod()
    sys.exit(failure_count)