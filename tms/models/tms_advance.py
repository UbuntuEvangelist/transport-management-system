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
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
import time


# Travel - Money advance payments for Travel expenses
class tms_advance(osv.osv):
    _name ='tms.advance'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Money advance payments for Travel expenses'

    def _paid(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            val = False
            if record.move_id.id:
                for ml in record.move_id.line_id:
                    if ml.credit > 0 and record.employee_id.address_home_id.id == ml.partner_id.id:
                        val = (ml.reconcile_id.id or ml.reconcile_partial_id.id)
            res[record.id] = val
        return res

    def _amount(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):          
            tax_factor = 0.00
            for line in record.product_id.supplier_taxes_id:
                tax_factor = (tax_factor + line.amount) if line.amount != 0.0 else tax_factor

            subtotal = record.price_unit * record.product_uom_qty
            tax_amount = subtotal * tax_factor
            res[record.id] =   {
                            'subtotal'  :   subtotal,
                            'tax_amount':   tax_amount,
                            #'total'     :   total,
                    }
        return res

    def _get_move_line_from_reconcile(self, cr, uid, ids, context=None):
        move = {}
        for r in self.pool.get('account.move.reconcile').browse(cr, uid, ids, context=context):
            for line in r.line_partial_ids:
                move[line.move_id.id] = True
            for line in r.line_id:
                move[line.move_id.id] = True
        advance_ids = []
        if move:
            advance_ids = self.pool.get('tms.advance').search(cr, uid, [('move_id','in',move.keys())], context=context)
        return advance_ids

    _columns = {
        'operation_id'  : fields.many2one('tms.operation', 'Operation', ondelete='restrict', required=False, readonly=False, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)], 'closed':[('readonly',True)]}),
        'name'          : fields.char('Anticipo', size=64, required=False),
        'state'         : fields.selection([('draft','Draft'), ('approved','Approved'), ('confirmed','Confirmed'), ('closed','Closed'), ('cancel','Cancelled')], 'State', readonly=True),
        'date'          : fields.date('Date', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}, required=True),
        'travel_id'     : fields.many2one('tms.travel', 'Travel', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'unit_id'       : fields.related('travel_id', 'unit_id', type='many2one', relation='fleet.vehicle', string='Unit', store=True, readonly=True),
        'employee1_id'  : fields.related('travel_id', 'employee_id', type='many2one', relation='hr.employee', string='Driver', store=True, readonly=True),
        'employee2_id'  : fields.related('travel_id', 'employee2_id', type='many2one', relation='hr.employee', string='Driver Helper', store=True, readonly=True),
        'employee_id'   : fields.many2one('hr.employee', 'Driver', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}, required=True),
        'shop_id'       : fields.many2one('sale.shop', string='Shop'),
        'product_id'    : fields.many2one('product.product', 'Product', domain=[('purchase_ok', '=', 1),('tms_category','=','real_expense')],  required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}, ondelete='restrict'),
        'product_uom_qty': fields.float('Quantity', digits=(16, 4), required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_uom'   : fields.many2one('product.uom', 'Unit of Measure ', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'price_unit'    : fields.float('Price Unit', required=True, digits_compute= dp.get_precision('Sale Price')),
        'price_unit_control' : fields.float('Price Unit', digits_compute= dp.get_precision('Sale Price'), readonly=True),
        'subtotal'      : fields.function(_amount, method=True, string='Subtotal', type='float', digits_compute= dp.get_precision('Sale Price'), multi=True, store=True),
        'tax_amount'    : fields.function(_amount, method=True, string='Tax Amount', type='float', digits_compute= dp.get_precision('Sale Price'), multi=True, store=True),
        'total'         : fields.float('Total', required=True, digits_compute= dp.get_precision('Sale Price'), states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'notes'         : fields.text('Notes', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'create_uid'    : fields.many2one('res.users', 'Created by', readonly=True),
        'create_date'   : fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by'  : fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': fields.datetime('Date Cancelled', readonly=True),
        'approved_by'   : fields.many2one('res.users', 'Approved by', readonly=True),
        'date_approved' : fields.datetime('Date Approved', readonly=True),
        'confirmed_by'  : fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed': fields.datetime('Date Confirmed', readonly=True),
        'closed_by'     : fields.many2one('res.users', 'Closed by', readonly=True),
        'date_closed'   : fields.datetime('Date Closed', readonly=True),
        'drafted_by'    : fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted'  : fields.datetime('Date Drafted', readonly=True),
        'move_id'       : fields.many2one('account.move', 'Journal Entry', readonly=True, select=1, ondelete='restrict', help="Link to the automatically generated Journal Items.\nThis move is only for Travel Expense Records with balance < 0.0"),
        'paid'          : fields.function(_paid, method=True, string='Paid', type='boolean', multi=False,
                                          store = {'account.move.reconcile': (_get_move_line_from_reconcile, None, 50)}),
        'currency_id'   : fields.many2one('res.currency', 'Currency', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'auto_expense'  : fields.boolean('Auto Expense',
                                            help="Check this if you want this product and amount to be automatically created when Travel Expense Record is created.",
                                            states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'driver_helper' : fields.boolean('For Driver Helper', help="Check this if you want to give this advance to Driver Helper.",states={'cancel':[('readonly',True)], 'approved':[('readonly',True)], 'confirmed':[('readonly',True)], 'closed':[('readonly',True)]}),
        }

    _defaults = {
        'date'              : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state'             : lambda *a: 'draft',
        'currency_id'       : lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'product_uom_qty'   : 1,
        }

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Advance number must be unique !'),
        ]
    _order = "name desc, date desc"

    def on_change_price_total(self, cr, uid, ids, product_id, product_uom_qty, price_total):
        res = {}
        if not (product_uom_qty and product_id and price_total):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].supplier_taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
        price_unit = price_total / (1.0 + tax_factor) / product_uom_qty
        price_subtotal = price_unit * product_uom_qty
        tax_amount = price_subtotal * tax_factor
        res = {'value': {
                'price_unit'         : price_unit,
                'price_unit_control' : price_unit,
                'price_subtotal' : price_subtotal, 
                'tax_amount'     : tax_amount, 
                }
               }
        return res

    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        prod = prod_obj.browse(cr, uid, [product_id], context=None)
        return {'value': {'product_uom' : prod[0].uom_id.id}}

    def on_change_driver_helper(self, cr, uid, ids, driver_helper, employee1_id, employee2_id):
        return {'value': {'employee_id' : employee2_id,}} if driver_helper else {'value': {'employee_id' : employee1_id,}}

    def on_change_driver(self, cr, uid, ids, employee_id, employee1_id, employee2_id):
        return {'value': {'driver_helper' : (employee_id == employee2_id),}}

    def on_change_travel_id(self, cr, uid, ids, travel_id):
        res = {}
        if not travel_id:
            return {'value': {  'employee_id'   : False,
                                'employee1_id'  : False,
                                'employee2_id'  : False,
                                'unit_id'       : False,
                                'operation_id'  : False,
                                'shop_id'       : False,
                            }
                    }
        travel = self.pool.get('tms.travel').browse(cr, uid, [travel_id], context=None)[0]
        return {'value': {'employee_id'   : travel.employee_id.id,
                          'employee1_id'  : travel.employee_id.id,
                          'employee2_id'  : travel.employee2_id.id,
                          'unit_id'       : travel.unit_id.id,  
                          'operation_id'  : travel.operation_id.id,  
                          'shop_id'       : travel.shop_id.id,  
                          }
                }

    def create(self, cr, uid, vals, context=None):
        travel = self.pool.get('tms.travel').browse(cr, uid, vals['travel_id'])
        shop_id = travel.shop_id.id
        shop = self.pool.get('sale.shop').browse(cr, uid, [shop_id])[0]
        seq_id = shop.tms_advance_seq.id
        if shop.tms_advance_seq:
            seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
            vals['name'] = seq_number
        else:
            raise osv.except_osv(_('Travel Sequence Error !'), _('You have not defined Advance Sequence for shop ' + shop.name))
        return super(tms_advance, self).create(cr, uid, vals, context=context)

    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        for advance in self.browse(cr, uid, ids):
            if advance.travel_id.state in ('cancel','closed'):
                raise osv.except_osv(
                        _('Could not set to draft this Advance !'),
                        _('Travel is Closed or Cancelled !!!'))
            else:
                self.write(cr, uid, ids, {'state':'draft','drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):
            if advance.travel_id.state in ('closed'):
                raise osv.except_osv(
                        _('Could not cancel Advance !'),
                        _('This Advance is already linked to Travel Expenses record'))
            elif advance.move_id.id:
                move_obj = self.pool.get('account.move')
                move_id = advance.move_id.id                
                if not advance.paid: #(move_line.reconcile_id.id or move_line.reconcile_partial_id.id):
                    if advance.move_id.state == 'posted':
                        move_obj.button_cancel(cr, uid, [move_id])
                    self.write(cr, uid, ids, {'move_id' : False, 'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                    move_obj.unlink(cr, uid, [move_id])
                else:
                    raise osv.except_osv( _('Could not cancel Advance !'),
                                          _('This Advance is already paid'))
            else:
                self.write(cr, uid, ids, {'move_id' : False, 'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_approve(self, cr, uid, ids, context=None):
        for advance in self.browse(cr, uid, ids, context=context):            
            if advance.state in ('draft'):
                if advance.total <= 0.0:
                     raise osv.except_osv(
                        _('Could not approve Advance !'),
                        _('Total Amount must be greater than zero.'))
                self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        adv_invoice = self.pool.get('tms.advance.invoice')
        adv_invoice.makeInvoices(cr, uid, ids, context=None)
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'cancelled_by' : False,
            'date_cancelled': False,
            'approved_by' : False,
            'date_approved': False,
            'confirmed_by' : False,
            'date_confirmed': False,
            'closed_by' : False,
            'date_closed': False,
            'drafted_by' : False,
            'date_drafted': False,
            'move_id': False,
            'notes': False,
            'expense_id':False,
            'expense2_id':False,
        })
        return super(tms_advance, self).copy(cr, uid, id, default, context)

class tms_advance_payment(osv.osv_memory):

    """ To create payment for Advance"""

    _name = 'tms.advance.payment'
    _description = 'Make Payment for Advances'

    def makePayment(self, cr, uid, ids, context=None):

        if context is None:
            record_ids = ids
        else:
            record_ids =  context.get('active_ids',[])

        if not record_ids: return []
        ids = record_ids
        dummy, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_voucher', 'view_vendor_receipt_dialog_form')
        cr.execute("select count(distinct(employee_id, currency_id)) from tms_advance where state in ('confirmed', 'closed') and not paid and id IN %s",(tuple(ids),))
        xids = filter(None, map(lambda x:x[0], cr.fetchall()))
        if len(xids) > 1:
            raise osv.except_osv('Error !',
                                 'You can not create Payment for several Driver Advances and or distinct currency...')
        amount = 0.0
        move_line_ids = []
        advance_names = ""
        for advance in self.pool.get('tms.advance').browse(cr, uid, ids, context=context):
            if advance.state in ('confirmed', 'closed') and not advance.paid:
                advance_names += ", " + advance.name
                amount += advance.total                
                for move_line in advance.move_id.line_id:
                    if move_line.credit > 0.0:
                        move_line_ids.append(move_line.id)
        if not amount:    
            raise osv.except_osv('Warning !',
                                 'All Driver Advances are already paid or are not in Confirmed State...')
        res = {
            'name':_("Driver Advance Payment"),
            'view_mode': 'form',
            'view_id': view_id,
            'view_type': 'form',
            'res_model': 'account.voucher',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]', 
            'context': {
                'payment_expected_currency': advance.currency_id.id,
                'default_partner_id': self.pool.get('res.partner')._find_accounting_partner(advance.employee_id.address_home_id).id,
                'default_amount': amount,
                'default_name': _('Driver Advance(s) %s') % (advance_names),
                'close_after_process': False,
                'move_line_ids': [x for x in move_line_ids],
                'default_type': 'payment',
                'type': 'payment'
            }}
        return res

# Wizard que permite generar la partida contable a pagar correspondiente al Anticipo del Operador
class tms_advance_invoice(osv.osv_memory):

    """ To create invoice for each Advance"""

    _name = 'tms.advance.invoice'
    _description = 'Make Invoices from Advances'

    def makeInvoices(self, cr, uid, ids, context=None):

        """
             To get Advance and create Invoice
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        if context is None:
            record_ids = ids
        else:
            record_ids =  context.get('active_ids',[])
        if record_ids:
            res = False
            invoices = []
            property_obj=self.pool.get('ir.property')
            user_obj=self.pool.get('res.users')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            account_jrnl_obj=self.pool.get('account.journal')
            period_obj = self.pool.get('account.period')
            move_obj = self.pool.get('account.move')
            advance_obj=self.pool.get('tms.advance')
            adv_line_obj=self.pool.get('tms.advance.line')
            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'general'),('tms_advance_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 'You have not defined Account Journal for Travel Advances...')
            journal_id = journal_id and journal_id[0]
            #partner = partner_obj.browse(cr,uid,user_obj.browse(cr,uid,[uid])[0].company_id.partner_id.id)
            cr.execute("select distinct employee_id, currency_id from tms_advance where move_id is null and state='approved' and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv('Warning !',
                                 'Selected records are not Approved or already sent for payment...')
            #print data_ids
            for data in data_ids:
                cr.execute("select id from tms_advance where move_id is null and state='approved' and employee_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                advance_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                inv_lines = []
                notes = _('Driver Advances.')                
                move_lines = []
                precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
                for line in advance_obj.browse(cr,uid,advance_ids):
                    a = line.employee_id.tms_advance_account_id.id
                    if not a:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no advance account defined for this driver: "%s" (id:%d)') % \
                                        (line.employee_id.name, line.employee_id.id,))
                    a = account_fiscal_obj.map_account(cr, uid, False, a)

                    b = line.employee_id.address_home_id.property_account_payable.id
                    if not b:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no address created for this driver: "%s" (id:%d)') % \
                                        (line.employee_id.name, line.employee_id.id,))
                    b = account_fiscal_obj.map_account(cr, uid, False, b)

                    period_id = period_obj.search(cr, uid, [('date_start', '<=', line.date),('date_stop','>=', line.date), ('state','=','draft')], context=None)
                    if not period_id:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no valid account period for this date %s. Period does not exists or is already closed') % \
                                        (line.date,))
                    move_line = (0,0, {
                            'name'          : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'ref'           : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'account_id'    : a,
                            'debit'         : round(line.total, precision),
                            'credit'        : 0.0,
                            'journal_id'    : journal_id,
                            'period_id'     : period_id[0],
                            'vehicle_id'    : line.unit_id.id,
                            'employee_id'   : line.employee_id.id,
                            'sale_shop_id'  : line.shop_id.id,
                            'partner_id'    : line.employee_id.address_home_id.id,
                            })
                    move_lines.append(move_line)
                    move_line = (0,0, {
                            'name'          : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'ref'           : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'account_id'    : b,
                            'debit'         : 0.0,
                            'credit'        : round(line.total, precision),
                            'journal_id'    : journal_id,
                            'period_id'     : period_id[0],
                            'vehicle_id'    : line.unit_id.id,
                            'employee_id'   : line.employee_id.id,
                            'sale_shop_id'  : line.shop_id.id,
                            'partner_id'    : line.employee_id.address_home_id.id,
                            })
                    move_lines.append(move_line)                    
                    notes += '\n' + line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name
                move = {
                            'ref'               : line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                            'journal_id'        : journal_id,
                            'narration'         : notes,
                            'line_id'           : [x for x in move_lines],
                            'date'              : line.date,
                            'period_id'         : period_id[0],
                        }
                move_id = move_obj.create(cr, uid, move)
                if move_id:
                    move_obj.button_validate(cr, uid, [move_id])                            
                advance_obj.write(cr,uid,advance_ids, {'move_id': move_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               
        return True
