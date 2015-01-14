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

from osv import osv, fields
import time
from datetime import datetime, date
from tools.translate import _
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import decimal_precision as dp
import netsvc
import openerp


class tms_expense_line(osv.osv):
    _inherit = 'tms.expense.line'
    
    _columns = {
              'loan_id' : fields.many2one('tms.expense.loan', 'Loan', required=False),
              }

# TMS Travel Expenses
class tms_expense_loan(osv.osv):
    _name = 'tms.expense.loan'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'TMS Driver Loan Mgmnt'


    def _balance(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            cr.execute('select sum(coalesce(price_total, 0.0))::float from tms_expense_line where loan_id = %s' % (record.id))
            data = filter(None, map(lambda x:x[0], cr.fetchall())) or [0.0]
            res[record.id] =   {
                            'balance' : record.amount + data[0],
                            'paid'    : not (record.amount + data[0]) > 0,
                    }            
        return res
        
    def _get_loan_discounts_from_expense_lines(self, cr, uid, ids, context=None):
        expense_line = {}
        for line in self.pool.get('tms.expense.line').browse(cr, uid, ids, context=context):           
            expense_line[line.loan_id.id] = True            

        expense_line_ids = []
        if expense_line:
            expense_line_ids = self.pool.get('tms.expense.loan').search(cr, uid, [('id','in',expense_line.keys())], context=context)
        return expense_line_ids

    
    _columns = {
        'name'        : fields.char('Name', size=64, select=True, readonly=True),
        'description' : fields.char('Description', size=128, select=True, required=True, readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}),
        'date'        : fields.date('Date', required=True, select=True, readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}),
        'employee_id' : fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')]
                                        , readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}),
        'expense_line_ids'  : fields.one2many('tms.expense.line', 'loan_id', 'Expense Line', readonly=True),
        'state'       : fields.selection([
                                ('draft', 'Draft'),
                                ('approved', 'Approved'),
                                ('confirmed', 'Confirmed'),
                                ('closed', 'Closed'),
                                ('cancel', 'Cancelled')
                                ], 'State', readonly=True, help="State of the Driver Loan. ", select=True),
        'discount_method' : fields.selection([
                                ('each', 'Each Travel Expense Record'),
                                ('weekly', 'Weekly'),
                                ('fortnightly', 'Fortnightly'),
                                ('monthly', 'Monthly'),
                                ], 'Discount Method', readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]},
                                help="""Select Loan Recovery Method:
- Weekly: Discount will be applied every week, considering only 4 weeks in each month
- Fortnightly: Discount will be applied forthnightly, considering only 2 discounts in each month, applied the 14th and 28th day of the month.
- Monthy: Discount will be applied only once a month, applied the 28th day of the month.                                . 
                                """, select=True, required=True),

        'discount_type' : fields.selection([
                                ('fixed', 'Fixed'),
                                ('percent', 'Loan Percentage'),
                                ], 'Discount Type', readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]},
                                required=True,
                                help="""Select Loan Recovery Type:
- Fixed: Discount will a fixed amount
- Percent: Discount will be a percentage of total Loan Amount
                                """, select=True),

    
        'notes'         : fields.text('Notes'),
        'origin'        : fields.char('Source Document', size=64, help="Reference of the document that generated this Expense Record",
                                    readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}),
        
        'amount'        : fields.float('Amount', digits_compute=dp.get_precision('Sale Price'), required=True,
                                     readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}),
        'percent_discount' : fields.float('Percent (%)', digits_compute=dp.get_precision('Sale Price'), required=False,
                                          help="Please set percent as 10.00%",
                                          readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}),
        'fixed_discount' : fields.float('Fixed Discount', digits_compute=dp.get_precision('Sale Price'), required=False,
                                        readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]}),

        'balance'       : fields.function(_balance, method=True, digits_compute=dp.get_precision('Sale Price'), string='Balance', type='float', multi=True,
                                          store={
                                                 'tms.expense.loan': (lambda self, cr, uid, ids, c={}: ids, ['notes', 'amount','state','expense_line_ids'], 10),
                                                 'tms.expense.line': (_get_loan_discounts_from_expense_lines, ['product_uom_qty', 'price_unit'], 10),
                                                 }),
                                        #store = {'tms.expense.line': (_get_loan_discounts_from_expense_lines, None, 50)}),
        'paid'          : fields.function(_balance, method=True, string='Paid', type='boolean', multi=True, 
                                          store={
                                                 'tms.expense.loan': (lambda self, cr, uid, ids, c={}: ids, ['notes','amount','state','expense_line_ids'], 10),
                                                 'tms.expense.line': (_get_loan_discounts_from_expense_lines, ['product_uom_qty', 'price_unit'], 10),
                                                 }),
                                        #store = {'tms.expense.line': (_get_loan_discounts_from_expense_lines, None, 50)}),

        'product_id'    : fields.many2one('product.product', 'Discount Product', readonly=True, states={'draft':[('readonly',False)], 'approved':[('readonly',False)]},
                                          required=True, domain=[('tms_category', '=', ('salary_discount'))], ondelete='restrict'),
        'shop_id'       : fields.related('employee_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'company_id'    : fields.related('shop_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        
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
    
    }
    _defaults = {
        'date'              : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state'             : lambda *a: 'draft',
    }
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Loan record must be unique !'),
    ]

    def create(self, cr, uid, vals, context=None):
        values = vals
        if 'employee_id' in vals and vals['employee_id']:
            employee = self.pool.get('hr.employee').browse(cr, uid, [vals['employee_id']])[0]
            seq_id = employee.shop_id.tms_loan_seq.id
            if seq_id:
                seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
                values['name'] = seq_number
            else:
                raise osv.except_osv(_('Loan Sequence Error !'), _('You have not defined Loan Sequence for shop ' + employee.shop_id.name))
            
        return super(tms_expense_loan, self).create(cr, uid, values, context=context)


    def action_approve(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):            
            if rec.amount <= 0.0:
                 raise osv.except_osv(
                    _('Could not approve Loan !'),
                    _('Amount must be greater than zero.'))
            self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Loan '%s' is set to Approved.") % name
            self.log(cr, uid, id, message)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):            
            self.write(cr, uid, ids, {'state':'confirmed', 'confirmed_by' : uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Loan '%s' is set to Confirmed.") % name
            self.log(cr, uid, id, message)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by' : uid, 'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Loan '%s' is set to Cancel.") % name
            self.log(cr, uid, id, message)
        return True

    
    def action_close(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, ids, {'state':'closed', 'closed_by' : uid, 'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):                
                message = _("Loan '%s' is set to Closed even when it is not paid.") % name if rec.balance > 0.0 else _("Loan '%s' is set to Closed.") % name 
            self.log(cr, uid, id, message)
        return True
    

    def get_loan_discounts(self, cr, uid, employee_id, expense_id, context=None):
        expense_line_obj = self.pool.get('tms.expense.line')
        expense_obj = self.pool.get('tms.expense')
        res = expense_line_obj.search(cr, uid, [('expense_id', '=', expense_id),('control','=', 1),('loan_id','!=',False)])
        #print "res: ", res
        if len(res):
            loan_ids = []
            expense_line_ids = []
            for x in expense_obj.browse(cr, uid, [expense_id])[0].expense_line:
                if x.loan_id.id:
                    loan_ids.append(x.loan_id.id)
                    expense_line_ids.append(x.id)
            if len(loan_ids):
                expense_line_obj.unlink(cr, uid, expense_line_ids)
                self.write(cr, uid,loan_ids, {'state':'confirmed', 'closed_by' : False, 'date_closed':False} )

        prod_obj = self.pool.get('product.product')
        loan_ids = self.search(cr, uid, [('employee_id', '=', employee_id),('state','=','confirmed'),('balance', '>', 0.0)])
        flag_each = True
        for rec in self.browse(cr, uid, loan_ids, context=context):
            cr.execute('select date from tms_expense_line where loan_id = %s order by date desc limit 1' % (rec.id))
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            date = data[0] if data else rec.date
            fecha_liq = expense_obj.read(cr, uid, [expense_id], ['date'])[0]['date']
            #print "fecha_liq: ", fecha_liq
            dur = datetime.strptime(fecha_liq, '%Y-%m-%d') - datetime.strptime(date, '%Y-%m-%d')
            product = prod_obj.browse(cr, uid, [rec.product_id.id])[0]
            if rec.discount_method == 'each' and dur.days <= 0:
                continue
            elif rec.discount_method == 'each' and flag_each:
                flag_each = False
                balance = rec.balance
                discount = rec.fixed_discount if rec.discount_type == 'fixed' else rec.amount * rec.percent_discount / 100.0
                discount = balance if discount > balance else discount
                balance -= discount
                xline = {
                    'expense_id'        : expense_id,
                    'line_type'         : product.tms_category,
                    'name'              : product.name + ' - ' + rec.name, 
                    'sequence'          : 100,
                    'product_id'        : product.id,
                    'product_uom'       : product.uom_id.id,
                    'product_uom_qty'   : 1,
                    'price_unit'        : discount * -1.0,
                    'control'           : True,
                    'loan_id'           : rec.id,
                    #'operation_id'      : travel.operation_id.id,
                    #'tax_id'            : [(6, 0, [x.id for x in product.supplier_taxes_id])],
                    }                
                res = expense_line_obj.create(cr, uid, xline)
                if discount >= rec.balance:
                    self.write(cr, uid, [rec.id], {'state':'closed', 'closed_by' : uid, 'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                    for (id,name) in self.name_get(cr, uid, [rec.id]):                
                        message =  _("Loan '%s' has been Closed.") % rec.name 
                    self.log(cr, uid, id, message)
            else:                
                xfactor = 7 if rec.discount_method == 'weekly' else 14.0 if rec.discount_method == 'fortnightly' else 28.0
                rango = 1 if not int(dur.days / xfactor) else int(dur.days / xfactor) + 1
                balance = rec.balance
                while rango and balance:
                    rango -= 1
                    discount = rec.fixed_discount if rec.discount_type == 'fixed' else rec.amount * rec.percent_discount / 100.0
                    discount = balance if discount > balance else discount
                    balance -= discount
                    xline = {
                        'expense_id'        : expense_id,
                        'line_type'         : product.tms_category,
                        'name'              : product.name + ' - ' + rec.name, 
                        'sequence'          : 100,
                        'product_id'        : product.id,
                        'product_uom'       : product.uom_id.id,
                        'product_uom_qty'   : 1,
                        'price_unit'        : discount * -1.0,
                        'control'           : True,
                        'loan_id'           : rec.id,
                        #'operation_id'      : travel.operation_id.id,
                        #'tax_id'            : [(6, 0, [x.id for x in product.supplier_taxes_id])],
                        }                
                    res = expense_line_obj.create(cr, uid, xline)
                    if discount >= rec.balance:
                        self.write(cr, uid, [rec.id], {'state':'closed', 'closed_by' : uid, 'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                        for (id,name) in self.name_get(cr, uid, [rec.id]):                
                            message =  _("Loan '%s' has been Closed.") % rec.name 
                        self.log(cr, uid, id, message)
        return


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
