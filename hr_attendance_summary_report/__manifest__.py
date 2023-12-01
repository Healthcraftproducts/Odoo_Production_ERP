# -*- coding: utf-8 -*-
{
    'name': 'Employee Attendance Report',
    'summary': "Print employee attendance Report with status & hours on date range",
    'description': "Print employee attendance Report with status & hours on date range",

    'author': 'iPredict IT Solutions Pvt. Ltd.',
    'website': 'http://ipredictitsolutions.com',
    'support': 'ipredictitsolutions@gmail.com',

    'category': 'Human Resources',
    'version': '13.0.0.1.1',
    'depends': ['hr_attendance'],

    'data': [
        'report/hr_attendance_report_view.xml',
        'wizard/hr_attendance_report_wizard.xml',
    ],

    'license': "OPL-1",
    'price': 30,
    'currency': "EUR",

    'auto_install': False,
    'installable': True,

    'images': ['static/description/banner.png'],
}
