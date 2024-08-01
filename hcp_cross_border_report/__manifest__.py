{
    'name': "HCP Cross Border Report",
    'description': """Cross Border Report""",
    'category': 'report',
    'version': '0.16',
    'depends': [
        'base',
        'sale',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
