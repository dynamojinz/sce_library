# -*- coding: utf-8 -*-
{
    'name': "SCE Office Library",

    'summary': """
        SCE office library
        Developed for Administration Department.""",

    'description': """
        Place books in office for borrow. 
        Searching
        Borrowing
        Returning.
        Etc.
    """,

    'author': "Jin Zan",
    'website': "http://www.sce-re.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','website','sce_sso','sce_dingtalk'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/book_views.xml',
        'views/book_templates.xml',
        'views/menus.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
}
