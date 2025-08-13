{
    'name': 'Tender Management',
    'version': '1.0',
    'summary': 'Manage and filter tenders, with a focus on IT-related tenders.',
    'description': 'Upload tender lists from Excel, filter IT tenders, assign, and track progress in Odoo.',
    'category': 'Operations/Project',
    'author': 'Mtwa Mgimwa',
    'website': 'www.cctz.co.tz',
    'depends': ['base', 'mail', 'crm'],
    'data': [
        'security/ir.model.access.csv',  # Security rules first
        'data/data.xml',                 # Master data (categories, stages, etc.)
        'views/tender_views.xml',        # Main views and actions FIRST
        'views/tender_import_views.xml', # Import views and actions
        'views/tender_wizard_views.xml', # Wizard views and actions
        'views/menu_views.xml',          # Menu items LAST (they reference the actions above)
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}