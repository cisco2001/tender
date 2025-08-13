from odoo import models, fields, api


class TenderCategory(models.Model):
    _name = 'tender.category'
    _description = 'Tender Category'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Category Code', required=True)
    description = fields.Text(string='Description')
    keywords = fields.Text(
        string='Keywords',
        help='Comma-separated keywords for auto-categorization'
    )
    color = fields.Integer(string='Color Index', default=0)
    active = fields.Boolean(string='Active', default=True)
    
    # IT-focused categories
    is_it_related = fields.Boolean(
        string='IT Related',
        default=False,
        help='Mark this category as IT-related for filtering'
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Category code must be unique!'),
        ('name_unique', 'unique(name)', 'Category name must be unique!')
    ]
    
    @api.model
    def create_default_categories(self):
        """Create default IT-related categories"""
        default_categories = [
            {
                'name': 'Software Development',
                'code': 'SW_DEV',
                'description': 'Software development and programming services',
                'keywords': 'software,development,programming,coding,application,system',
                'is_it_related': True,
                'color': 1
            },
            {
                'name': 'Network Infrastructure',
                'code': 'NETWORK',
                'description': 'Network equipment and infrastructure',
                'keywords': 'network,router,switch,firewall,wifi,lan,wan',
                'is_it_related': True,
                'color': 2
            },
            {
                'name': 'Hardware & Equipment',
                'code': 'HARDWARE',
                'description': 'Computer hardware and IT equipment',
                'keywords': 'computer,laptop,server,hardware,equipment,desktop',
                'is_it_related': True,
                'color': 3
            },
            {
                'name': 'Cloud Services',
                'code': 'CLOUD',
                'description': 'Cloud computing and hosting services',
                'keywords': 'cloud,hosting,saas,paas,iaas,aws,azure',
                'is_it_related': True,
                'color': 4
            },
            {
                'name': 'Cybersecurity',
                'code': 'SECURITY',
                'description': 'Security software and services',
                'keywords': 'security,cybersecurity,antivirus,encryption,firewall',
                'is_it_related': True,
                'color': 5
            },
            {
                'name': 'General Services',
                'code': 'GENERAL',
                'description': 'Non-IT related services',
                'keywords': 'consulting,training,maintenance,support',
                'is_it_related': False,
                'color': 6
            }
        ]
        
        for category_data in default_categories:
            existing = self.search([('code', '=', category_data['code'])])
            if not existing:
                self.create(category_data)
    
    def get_keywords_list(self):
        """Return keywords as a list"""
        if self.keywords:
            return [kw.strip().lower() for kw in self.keywords.split(',')]
        return []