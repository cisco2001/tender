from odoo import models, fields, api
from odoo.exceptions import UserError


class TenderToLeadWizard(models.TransientModel):
    _name = 'tender.to.lead.wizard'
    _description = 'Convert Tender to CRM Lead'

    # Reference to the tender being converted
    tender_id = fields.Many2one('tender.tender', string='Tender', required=True)
    
    # Auto-filled fields from tender (editable in case user wants to modify)
    name = fields.Char(string='Lead Name', required=True)
    partner_name = fields.Char(string='Customer Name')
    description = fields.Html(string='Description')
    expected_revenue = fields.Monetary(
        string='Expected Revenue',
        currency_field='currency_id',
        help='Leave empty to use tender estimated value'
    )
    currency_id = fields.Many2one('res.currency', string='Currency')
    date_deadline = fields.Date(string='Expected Closing Date')
    email_from = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    
    # Required fields that need user input
    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        required=True,
        default=lambda self: self.env.user,
        help='Person responsible for this lead'
    )
    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        help='Sales team responsible for this lead'
    )
    source_id = fields.Many2one(
        'utm.source',
        string='Lead Source',
        help='How did you get this lead?'
    )
    
    # Account Manager field
    account_manager = fields.Many2one(
        'res.users',
        string='Account Manager',
        help='User responsible for managing this account/customer relationship',
        domain=[('active', '=', True)]
    )
    
    # NEW FIELDS - These mirror the fields in crm.lead
    business_unit = fields.Many2one(
        string='Business Unit',
        help='Business unit responsible for this lead'
    )
    pre_sale_id = fields.Many2one(
        'res.users',
        string='Pre-sales Person',
        help='Pre-sales person assigned to this lead',
        domain=[('active', '=', True)]
    )

    @api.model
    def _setup_complete(self):
        """Setup the business_unit field dynamically based on crm.lead model"""
        super()._setup_complete()
        
        # Get the business_unit field definition from crm.lead if it exists
        try:
            crm_lead_model = self.env['crm.lead']
            if 'business_unit' in crm_lead_model._fields:
                business_unit_field = crm_lead_model._fields['business_unit']
                if hasattr(business_unit_field, 'comodel_name') and business_unit_field.comodel_name:
                    # Update our business_unit field to use the same comodel
                    self._fields['business_unit'].comodel_name = business_unit_field.comodel_name
                    self._fields['business_unit'].relation = business_unit_field.comodel_name
        except (KeyError, AttributeError):
            pass
    
    # Additional options
    create_activity = fields.Boolean(
        string='Create Follow-up Activity',
        default=True,
        help='Create a follow-up activity for the new lead'
    )
    activity_type_id = fields.Many2one(
        'mail.activity.type',
        string='Activity Type',
        default=lambda self: self.env.ref('mail.mail_activity_data_call', raise_if_not_found=False)
    )
    activity_date_deadline = fields.Date(
        string='Activity Due Date',
        default=lambda self: fields.Date.today()
    )
    activity_summary = fields.Char(
        string='Activity Summary',
        default='Follow up on tender conversion'
    )
    
    # Action after creation
    action_after_create = fields.Selection([
        ('stay', 'Stay on Tender'),
        ('open_lead', 'Open New Lead'),
        ('open_lead_new_tab', 'Open New Lead in New Tab')
    ], string='After Creation', default='open_lead', required=True)

    @api.model
    def default_get(self, fields_list):
        """Auto-fill wizard fields from tender data"""
        res = super().default_get(fields_list)
        
        if self.env.context.get('active_model') == 'tender.tender' and self.env.context.get('active_id'):
            tender = self.env['tender.tender'].browse(self.env.context['active_id'])
            
            # Auto-fill from tender data - use direct field names
            res.update({
                'tender_id': tender.id,
                'name': f"Lead: {tender.name}",
                'partner_name': tender.institution,
                'description': tender.description,
                'expected_revenue': tender.estimated_value,
                'currency_id': tender.currency_id.id if tender.currency_id else self.env.company.currency_id.id,
                'date_deadline': tender.deadline_date,
                'user_id': tender.assigned_to.id if tender.assigned_to else self.env.user.id,
                'email_from': tender.contact_email or '',  # Direct field access
                'phone': tender.contact_phone or ''        # Direct field access
            })
            
            # Set default sales team based on user
            if 'team_id' in fields_list:
                user = tender.assigned_to if tender.assigned_to else self.env.user
                if user.sale_team_id:
                    res['team_id'] = user.sale_team_id.id
            
            # Set default account manager
            if 'account_manager' in fields_list:
                res['account_manager'] = tender.assigned_to.id if tender.assigned_to else self.env.user.id
            
            # Set default pre-sales person
            if 'pre_sale_id' in fields_list:
                res['pre_sale_id'] = tender.assigned_to.id if tender.assigned_to else self.env.user.id
            
            # Set default business unit
            if 'business_unit' in fields_list:
                try:
                    crm_lead_model = self.env['crm.lead']
                    if 'business_unit' in crm_lead_model._fields:
                        business_unit_field = crm_lead_model._fields['business_unit']
                        if hasattr(business_unit_field, 'comodel_name') and business_unit_field.comodel_name:
                            business_unit_model = self.env[business_unit_field.comodel_name]
                            business_unit = None
                            
                            # Try to get business unit from user first
                            user = tender.assigned_to if tender.assigned_to else self.env.user
                            if hasattr(user, 'business_unit_id') and user.business_unit_id:
                                business_unit = user.business_unit_id
                            
                            # If not found, try from tender category
                            if not business_unit and tender.category_id:
                                business_unit = business_unit_model.search([
                                    ('name', 'ilike', tender.category_id.name)
                                ], limit=1)
                            
                            if business_unit:
                                res['business_unit'] = business_unit.id
                except (KeyError, AttributeError):
                    pass
            
            # Auto-set activity due date if tender deadline is soon
            if tender.deadline_date and tender.days_remaining <= 7:
                res['activity_date_deadline'] = min(
                    tender.deadline_date,
                    fields.Date.today() + fields.Timedelta(days=2)
                )
        
        return res

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """When salesperson changes, update team and potentially account manager"""
        if self.user_id:
            # Update team based on salesperson's default team
            if self.user_id.sale_team_id:
                self.team_id = self.user_id.sale_team_id
            
            # Optionally set account manager to same as salesperson if not already set
            if not self.account_manager:
                self.account_manager = self.user_id
            
            # Set business unit from user if available
            if hasattr(self.user_id, 'business_unit_id') and self.user_id.business_unit_id and not self.business_unit:
                self.business_unit = self.user_id.business_unit_id

    @api.onchange('team_id')
    def _onchange_team_id(self):
        """When team changes, filter account manager and pre-sales person by team members"""
        if self.team_id:
            # Filter account manager and pre-sales person to team members
            team_member_ids = self.team_id.member_ids.ids
            if team_member_ids:
                return {
                    'domain': {
                        'account_manager': [('id', 'in', team_member_ids), ('active', '=', True)],
                        'pre_sale_id': [('id', 'in', team_member_ids), ('active', '=', True)]
                    }
                }
        return {
            'domain': {
                'account_manager': [('active', '=', True)],
                'pre_sale_id': [('active', '=', True)]
            }
        }

    def action_convert_to_lead(self):
        """Convert tender to CRM lead with validation"""
        self.ensure_one()
        
        # Validate required fields
        if not self.user_id:
            raise UserError("Please select a salesperson for this lead.")
        
        if self.tender_id.lead_id:
            raise UserError("This tender has already been converted to a lead.")
        
        # Check if new fields exist in crm.lead model
        crm_lead_fields = self.env['crm.lead']._fields
        has_account_manager = 'account_manager' in crm_lead_fields
        has_business_unit = 'business_unit' in crm_lead_fields
        has_pre_sale_id = 'pre_sale_id' in crm_lead_fields
        has_tender_status = 'tender_status' in crm_lead_fields
        
        # Prepare lead values
        lead_vals = {
            'name': self.name,
            'partner_name': self.partner_name,
            'description': self.description,
            'expected_revenue': self.expected_revenue or 0.0,
            'date_deadline': self.date_deadline,
            'email_from': self.email_from,
            'phone': self.phone,
            'user_id': self.user_id.id,
            'team_id': self.team_id.id if self.team_id else False,
            'source_id': self.source_id.id if self.source_id else False,
        }
        
        # Add conditional fields if they exist in crm.lead model
        if has_account_manager and self.account_manager:
            lead_vals['account_manager'] = self.account_manager.id
            
        if has_business_unit and self.business_unit:
            lead_vals['business_unit'] = self.business_unit.id
            
        if has_pre_sale_id and self.pre_sale_id:
            lead_vals['pre_sale_id'] = self.pre_sale_id.id
            
        # SET TENDER STATUS TO YES
        if has_tender_status:
            lead_vals['tender_status'] = 'Yes'
        
        # Handle stage assignment - get the first stage of the team or default
        if self.team_id:
            first_stage = self.env['crm.stage'].search([
                ('team_id', '=', self.team_id.id)
            ], order='sequence', limit=1)
        else:
            first_stage = self.env['crm.stage'].search([], order='sequence', limit=1)
        
        if first_stage:
            lead_vals['stage_id'] = first_stage.id
        else:
            lead_vals['stage_id'] = False
        
        # Add category as tag if available
        if self.tender_id.category_id:
            tag = self.env['crm.tag'].search([('name', '=', self.tender_id.category_id.name)], limit=1)
            if not tag:
                tag = self.env['crm.tag'].create({
                    'name': self.tender_id.category_id.name,
                    'color': self.tender_id.category_id.color if hasattr(self.tender_id.category_id, 'color') else 1,
                })
            lead_vals['tag_ids'] = [(6, 0, [tag.id])]
        
        # Create the lead
        lead = self.env['crm.lead'].create(lead_vals)
        
        # Link the lead to the tender
        self.tender_id.lead_id = lead.id
        
        # Create follow-up activity if requested
        if self.create_activity and self.activity_type_id:
            # Get the res_model_id for crm.lead
            lead_model = self.env['ir.model'].search([('model', '=', 'crm.lead')], limit=1)
            if lead_model:
                self.env['mail.activity'].create({
                    'activity_type_id': self.activity_type_id.id,
                    'date_deadline': self.activity_date_deadline,
                    'summary': self.activity_summary,
                    'user_id': self.user_id.id,
                    'res_model': 'crm.lead',
                    'res_model_id': lead_model.id,
                    'res_id': lead.id,
                })
        
        # Add a comprehensive note to the tender
        tender_note = f"✅ Successfully converted to CRM Lead: <a href='/web#id={lead.id}&model=crm.lead'>{lead.name}</a>"
        tender_note += "<br/><strong>Assignment Details:</strong>"
        if has_account_manager and self.account_manager:
            tender_note += f"<br/>👤 Account Manager: {self.account_manager.name}"
        if has_pre_sale_id and self.pre_sale_id:
            tender_note += f"<br/>🔧 Pre-sales Person: {self.pre_sale_id.name}"
        if has_business_unit and self.business_unit:
            tender_note += f"<br/>🏢 Business Unit: {self.business_unit.name}"
        if has_tender_status:
            tender_note += "<br/>📋 Tender Status: Set to Yes"
            
        self.tender_id.message_post(
            body=tender_note,
            message_type='notification'
        )
        
        # Add a comprehensive note to the lead
        lead_note = f"🎯 Created from Tender: <a href='/web#id={self.tender_id.id}&model=tender.tender'>{self.tender_id.name}</a>"
        lead_note += "<br/><strong>Team Assignment:</strong>"
        if has_account_manager and self.account_manager:
            lead_note += f"<br/>👤 Account Manager: {self.account_manager.name}"
        if has_pre_sale_id and self.pre_sale_id:
            lead_note += f"<br/>🔧 Pre-sales Person: {self.pre_sale_id.name}"
        if has_business_unit and self.business_unit:
            lead_note += f"<br/>🏢 Business Unit: {self.business_unit.name}"
        if has_tender_status:
            lead_note += "<br/>📋 Tender Status: Yes (from tender conversion)"
            
        lead.message_post(
            body=lead_note,
            message_type='notification'
        )
        
        # Show comprehensive success message
        message = f"Lead '{lead.name}' has been successfully created with tender status set to Yes!"
        message_parts = []
        if has_account_manager and self.account_manager:
            message_parts.append(f"Account Manager: {self.account_manager.name}")
        if has_pre_sale_id and self.pre_sale_id:
            message_parts.append(f"Pre-sales: {self.pre_sale_id.name}")
        if has_business_unit and self.business_unit:
            message_parts.append(f"Business Unit: {self.business_unit.name}")
        if self.create_activity:
            message_parts.append(f"Follow-up scheduled for {self.activity_date_deadline}")
            
        if message_parts:
            message += " " + " | ".join(message_parts) + "."
        
        # Return action based on user preference with notification
        if self.action_after_create == 'open_lead':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success!',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': 'CRM Lead',
                    'res_model': 'crm.lead',
                    'res_id': lead.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            }
        elif self.action_after_create == 'open_lead_new_tab':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success!',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': 'CRM Lead',
                    'res_model': 'crm.lead',
                    'res_id': lead.id,
                    'view_mode': 'form',
                    'target': 'new',
                }
            }
        else:  # stay on tender
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success!',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }

    def action_cancel(self):
        """Cancel the conversion"""
        return {'type': 'ir.actions.act_window_close'}


# Update for the main Tender model - replace the existing action_convert_to_lead method
class TenderUpdate(models.Model):
    _inherit = 'tender.tender'
    
    def action_convert_to_lead(self):
        """Open wizard to convert tender to CRM lead/opportunity"""
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
        
        # Open the conversion wizard
        return {
            'name': 'Convert Tender to Lead',
            'type': 'ir.actions.act_window',
            'res_model': 'tender.to.lead.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'tender.tender',
                'default_tender_id': self.id,
            }
        }