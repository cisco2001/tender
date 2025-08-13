from odoo import models, fields, api
from datetime import datetime, timedelta


class Tender(models.Model):
    _name = 'tender.tender'
    _description = 'Tender Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline_date desc, create_date desc'

    # Basic Information
    name = fields.Char(string='Tender Title', required=True, tracking=True)
    reference = fields.Char(string='Reference Number', tracking=True)
    description = fields.Html(string='Description')
    institution = fields.Char(string='Institution/Organization', tracking=True)
    
    # Category and Classification
    category_id = fields.Many2one(
        'tender.category',
        string='Category',
        tracking=True
    )
    
    # CRM Integration
    lead_id = fields.Many2one(
        'crm.lead',
        string='Related Lead/Opportunity',
        tracking=True,
        help='Link to CRM lead or opportunity'
    )
    lead_status = fields.Char(
        string='Lead Status',
        compute='_compute_lead_status',
        store=False,
        help='Status of the related CRM lead'
    )
    
    is_it_related = fields.Boolean(
        string='IT Related',
        compute='_compute_is_it_related',
        store=True,
        help='Automatically determined based on category or keywords'
    )
    keywords = fields.Char(
        string='Keywords',
        help='Keywords found in tender description for categorization'
    )
    
    # Dates
    publication_date = fields.Date(string='Publication Date', tracking=True)
    deadline_date = fields.Date(string='Deadline Date', required=True, tracking=True)
    days_remaining = fields.Integer(
        string='Days remaining',
        compute='_compute_days_remaining',
        store=True
    )
    
    # Financial
    estimated_value = fields.Monetary(
        string='Estimated Value',
        currency_field='currency_id',
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Assignment and Collaboration
    assigned_to = fields.Many2one(
        'res.users',
        string='Assigned To',
        tracking=True,
        default=lambda self: self.env.user
    )
    team_members = fields.Many2many(
        'res.users',
        string='Team Members',
        tracking=True
    )
    
    # Status and Progress
    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('preparation', 'Preparation'),
        ('submitted', 'Submitted'),
        ('awarded', 'Awarded'),
        ('lost', 'Lost'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    stage_id = fields.Many2one(
        'tender.stage',
        string='Stage',
        group_expand='_read_group_stage_ids',
        tracking=True
    )
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High')
    ], string='Priority', default='1', tracking=True)
    
    # Documents and Attachments
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count'
    )
    
    # Additional Information
    contact_person = fields.Char(string='Contact Person')
    contact_email = fields.Char(string='Contact Email')
    contact_phone = fields.Char(string='Contact Phone')
    tender_url = fields.Char(string='Tender URL')
    
    # Computed Fields
    effective_contact_email = fields.Char(
        string='Effective Contact Email',
        compute='_compute_effective_contact_info',
        store=False,
        help='Contact email from tender or import batch'
    )
    effective_contact_phone = fields.Char(
        string='Effective Contact Phone', 
        compute='_compute_effective_contact_info',
        store=False,
        help='Contact phone from tender or import batch'
    )
    effective_contact_person = fields.Char(
        string='Effective Contact Person',
        compute='_compute_effective_contact_info', 
        store=False,
        help='Contact person from tender or import batch'
    )

    # Add this new computed method
    @api.depends('contact_email', 'contact_phone', 'contact_person', 'import_id', 
                 'import_id.contact_email', 'import_id.contact_phone', 'import_id.contact_person')
    def _compute_effective_contact_info(self):
        """Get effective contact info from tender or fallback to import batch"""
        for tender in self:
            # Use tender-specific contact info if available, otherwise fallback to import batch
            tender.effective_contact_email = (
                tender.contact_email or 
                (tender.import_id.contact_email if tender.import_id else '')
            )
            tender.effective_contact_phone = (
                tender.contact_phone or 
                (tender.import_id.contact_phone if tender.import_id else '')
            )
            tender.effective_contact_person = (
                tender.contact_person or 
                (tender.import_id.contact_person if tender.import_id else '')
            )

    # Internal Notes
    internal_notes = fields.Text(string='Internal Notes')
    
    # Import Information
    import_id = fields.Many2one(
        'tender.import',
        string='Import Batch',
        help='Link to the import batch this tender came from'
    )
    
    @api.constrains('contact_email')
    def _check_email(self):
        for tender in self:
            if tender.contact_email and '@' not in tender.contact_email:
                raise ValidationError("Please enter a valid email address")

    @api.depends('lead_id')
    def _compute_lead_status(self):
        """Compute the status of the related CRM lead"""
        for tender in self:
            if tender.lead_id and tender.lead_id.stage_id:
                tender.lead_status = tender.lead_id.stage_id.name
            else:
                tender.lead_status = 'No Lead'
    
    @api.depends('category_id', 'keywords')
    def _compute_is_it_related(self):
        """Determine if tender is IT-related based on category or keywords"""
        it_keywords = [
            'software', 'hardware', 'network', 'computer', 'system',
            'application', 'database', 'server', 'cloud', 'cybersecurity',
            'programming', 'development', 'it services', 'technology'
        ]
        
        for tender in self:
            # Check category first
            if tender.category_id and hasattr(tender.category_id, 'is_it_related') and tender.category_id.is_it_related:
                tender.is_it_related = True
                continue
            
            # Check keywords in title and description
            is_it = False
            search_text = f"{tender.name} {tender.description or ''} {tender.keywords or ''}".lower()
            
            for keyword in it_keywords:
                if keyword in search_text:
                    is_it = True
                    break
            
            tender.is_it_related = is_it
    
    @api.depends('deadline_date')
    def _compute_days_remaining(self):
        """Calculate days remaining until deadline"""
        today = fields.Date.today()
        for tender in self:
            if tender.deadline_date:
                delta = tender.deadline_date - today
                tender.days_remaining = delta.days
            else:
                tender.days_remaining = 0
    
    def _compute_document_count(self):
        """Count related documents/attachments"""
        for tender in self:
            tender.document_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', 'tender.tender'),
                ('res_id', '=', tender.id)
            ])
    
    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Return all stages for kanban view"""
        return self.env['tender.stage'].search([])
    
    def action_view_documents(self):
        """Open documents related to this tender"""
        return {
            'name': 'Documents',
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'tree,form',
            'domain': [('res_model', '=', 'tender.tender'), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': 'tender.tender',
                'default_res_id': self.id,
            }
        }
    
    def action_convert_to_lead(self):
        """Convert tender to CRM lead/opportunity"""
        if self.lead_id:
            # If lead already exists, open it
            return {
                'name': 'Lead/Opportunity',
                'type': 'ir.actions.act_window',
                'res_model': 'crm.lead',
                'res_id': self.lead_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        # Create new lead
        lead_vals = {
            'name': f"Lead: {self.name}",
            'description': self.description,
            'partner_name': self.institution,
            'email_from': self.contact_email,
            'phone': self.contact_phone,
            'expected_revenue': self.estimated_value or 0.0,
            'date_deadline': self.deadline_date,
            'user_id': self.assigned_to.id if self.assigned_to else self.env.user.id,
        }
        
        # Add category as tag if available
        if self.category_id:
            # Try to find or create a CRM tag based on category
            tag = self.env['crm.tag'].search([('name', '=', self.category_id.name)], limit=1)
            if not tag:
                tag = self.env['crm.tag'].create({
                    'name': self.category_id.name,
                    'color': 1,  # Default color
                })
            lead_vals['tag_ids'] = [(6, 0, [tag.id])]
        
        lead = self.env['crm.lead'].create(lead_vals)
        
        # Link the lead to this tender
        self.lead_id = lead.id
        
        # Add a note to the tender
        self.message_post(
            body=f"Converted to CRM Lead: <a href='/web#id={lead.id}&model=crm.lead'>{lead.name}</a>",
            message_type='notification'
        )
        
        # Open the created lead
        return {
            'name': 'Lead/Opportunity',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_set_draft(self):
        self.state = 'draft'
    
    def action_set_review(self):
        self.state = 'review'
    
    def action_set_preparation(self):
        self.state = 'preparation'
    
    def action_set_submitted(self):
        self.state = 'submitted'
    
    def action_set_awarded(self):
        self.state = 'awarded'
    
    def action_set_lost(self):
        self.state = 'lost'
    
    def action_set_cancelled(self):
        self.state = 'cancelled'
        
    @api.model
    def auto_categorize_tender(self, title, description):
        """Auto-categorize tender based on title and description"""
        search_text = f"{title} {description or ''}".lower()
        categories = self.env['tender.category'].search([])
        
        for category in categories:
            if hasattr(category, 'get_keywords_list'):
                keywords = category.get_keywords_list()
                for keyword in keywords:
                    if keyword in search_text:
                        return category.id
        
        return False


class TenderStage(models.Model):
    _name = 'tender.stage'
    _description = 'Tender Stage'
    _order = 'sequence, name'

    name = fields.Char(string='Stage Name', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    fold = fields.Boolean(string='Folded in Kanban')
    active = fields.Boolean(string='Active', default=True)
    
    @api.model
    def create_default_stages(self):
        """Create default stages for tender workflow"""
        default_stages = [
            {'name': 'New', 'sequence': 1, 'description': 'Newly imported tenders'},
            {'name': 'Analysis', 'sequence': 2, 'description': 'Under analysis'},
            {'name': 'Preparation', 'sequence': 3, 'description': 'Preparing proposal'},
            {'name': 'Review', 'sequence': 4, 'description': 'Internal review'},
            {'name': 'Submitted', 'sequence': 5, 'description': 'Proposal submitted'},
            {'name': 'Won', 'sequence': 6, 'description': 'Tender won', 'fold': True},
            {'name': 'Lost', 'sequence': 7, 'description': 'Tender lost', 'fold': True},
        ]
        
        for stage_data in default_stages:
            existing = self.search([('name', '=', stage_data['name'])])
            if not existing:
                self.create(stage_data)