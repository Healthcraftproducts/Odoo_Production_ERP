# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name" : "Popup Message",
    "author" : "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Extra Tools",
    "summary": """
create Success, warnings, alert message box wizard,success popup message app, alert popup module, email popup module odoo
        
                    """,    
	"description": """
        This module is useful to create a custom popup message Wasting your important time to make popup message wizard-like Alert, Success, Warnings? We will help you to make this procedure quick, just add a few lines of code in your project to open the popup message wizard.

        
                    """,
    "version":"13.0.1",
    "depends" : ["base", "web"],
    "application" : True,
    "data" : ['wizard/sh_message_wizard.xml',
            ],
    "images": ["static/description/background.jpg", ],
    "auto_install":False,
    "installable" : True,
}
