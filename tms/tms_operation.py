# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


from openerp.osv import osv, fields
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import time


# Travel - Money operation payments for Travel expenses

class tms_operation(osv.osv):
    _name = 'tms.operation'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Travel Operations'
    _columns = {
        'name': fields.char('Operation', size=128, required=True),
        'state': fields.selection([('draft', 'Draft'), ('process', 'Process'), ('done', 'Done'), ('cancel', 'Cancelled')], 'State', readonly=True, required=True),
        'date': fields.date('Date', states={'cancel': [('readonly', True)], 'process': [('readonly', True)], 'done': [('readonly', True)]}, required=True),
        'partner_id': fields.many2one('res.partner', 'Customer', required=True, readonly=False, states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}),
        'date_start': fields.datetime('Starting Date', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, required=True),
        'date_end': fields.datetime('Ending Date', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, required=True),
        'notes': fields.text('Notes', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}),
        'create_uid': fields.many2one('res.users', 'Created by', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by': fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': fields.datetime('Date Cancelled', readonly=True),
        'process_by': fields.many2one('res.users', 'Approved by', readonly=True),
        'date_process': fields.datetime('Date Approved', readonly=True),
        'done_by': fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_done': fields.datetime('Date Confirmed', readonly=True),
        'drafted_by': fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted': fields.datetime('Date Drafted', readonly=True),
        'fuelvoucher_ids': fields.one2many('tms.fuelvoucher', 'operation_id', string='Fuel Vouchers', readonly=True),
        'advance_ids': fields.one2many('tms.advance', 'operation_id', string='Expense Advance', readonly=True),
        'waybill_ids': fields.one2many('tms.waybill', 'operation_id', string='Waybills', readonly=True),
        'expense_line_ids': fields.one2many('tms.expense.line', 'operation_id', string='Travel Expense Lines', readonly=True),
                }
    _defaults = {
        'date': lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'date_start': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_end': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'state': lambda *a: 'draft',
                }
    _sql_constraints = [('name_uniq', 'unique(name)', 'Operation must be unique !')]
    _order = "date desc, name desc"

    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        for operation in self.browse(cr, uid, ids):
            self.write(cr, uid, ids, {'state': 'draft', 'drafted_by': uid, 'date_drafted': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for operation in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, ids, {'state': 'cancel', 'cancelled_by': uid, 'date_cancelled': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_process(self, cr, uid, ids, context=None):
        for operation in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, ids, {'state': 'process', 'process_by': uid, 'date_process': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_done(self, cr, uid, ids, context=None):
        for operation in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, ids, {'state': 'done', 'done_by': uid, 'date_process': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'name': default['name'] + ' copy',
            'cancelled_by': False,
            'date_cancelled': False,
            'process_by': False,
            'date_process': False,
            'done_by': False,
            'date_done': False,
            'drafted_by': False,
            'date_drafted': False,
            'notes': False,
        })
        return super(tms_operation, self).copy(cr, uid, id, default, context)
