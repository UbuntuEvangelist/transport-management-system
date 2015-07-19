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
import time
from tools.translate import _
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import decimal_precision as dp
import netsvc


# TMS Travel Expenses
class tms_expense(osv.osv):
    _name = 'tms.expense'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'TMS Travel Expenses'

    def _invoiced(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            invoiced = (record.invoice_id.id)
            paid = (record.invoice_id.state == 'paid') if record.invoice_id.id else False
            res[record.id] =  { 'invoiced'     : invoiced,
                                'invoice_paid' : paid,
                                'invoice_name' : record.invoice_id.supplier_invoice_number
                                }
        return res

    def _get_route_distance(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        distance=0.0
        for expense in self.browse(cr, uid, ids, context=context):
            for travel in expense.travel_ids:
                distance += travel.route_id.distance
            res[expense.id] = distance
        return res

    def _get_fuel_efficiency(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for expense in self.browse(cr, uid, ids, context=context):
            res[expense.id] = (expense.distance_routes / expense.fuel_qty) if expense.fuel_qty > 0.0 else 0.0
        return res

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for expense in self.browse(cr, uid, ids, context=context):
            res[expense.id] = {
                'amount_real_expense'       : 0.0,
                'amount_madeup_expense'     : 0.0,
                'fuel_qty'                  : 0.0,
                'amount_fuel'               : 0.0,
                'amount_fuel_voucher'       : 0.0,
                'amount_salary'             : 0.0,
                'amount_net_salary'         : 0.0,
                'amount_salary_retention'   : 0.0,
                'amount_salary_discount'    : 0.0,
                'amount_subtotal_real'      : 0.0,
                'amount_subtotal_total'     : 0.0,
                'amount_tax_real'           : 0.0,
                'amount_tax_total'          : 0.0,
                'amount_total_real'         : 0.0,
                'amount_total_total'        : 0.0,
                'amount_balance'            : 0.0,
                'amount_advance'            : 0.0,
                }            
            cur = expense.currency_id
            advance = fuel_voucher = fuel_qty = 0.0
            for _advance in expense.advance_ids:
                if _advance.currency_id.id != cur.id:
                    raise osv.except_osv(
                         _('Currency Error !'), 
                         _('You can not create a Travel Expense Record with Advances with different Currency. This Expense record was created with %s and Advance is with %s ') % (expense.currency_id.name, _advance.currency_id.name))
                advance += _advance.total
            for _fuelvoucher in expense.fuelvoucher_ids:
                if _fuelvoucher.currency_id.id != cur.id:
                    raise osv.except_osv(
                         _('Currency Error !'), 
                         _('You can not create a Travel Expense Record with Fuel Vouchers with different Currency. This Expense record was created with %s and Fuel Voucher is with %s ') % (expense.currency_id.name, _advance.currency_id.name))
                fuel_voucher += _fuelvoucher.price_subtotal
                fuel_qty += _fuelvoucher.product_uom_qty
            negative_balance = real_expense = madeup_expense = fuel = salary = salary_retention = salary_discount = tax_real = tax_total = subtotal_real = subtotal_total = total_real = total_total = balance = 0.0
            for line in expense.expense_line:
                    madeup_expense  += line.price_subtotal if line.product_id.tms_category == 'madeup_expense' else 0.0
                    negative_balance += line.price_subtotal if line.product_id.tms_category == 'negative_balance' else 0.0
                    real_expense    += line.price_subtotal if line.product_id.tms_category == 'real_expense' else 0.0
                    salary          += line.price_subtotal if line.product_id.tms_category == 'salary' else 0.0
                    salary_retention += line.price_subtotal if line.product_id.tms_category == 'salary_retention' else 0.0
                    salary_discount += line.price_subtotal if line.product_id.tms_category == 'salary_discount' else 0.0
                    fuel            += line.price_subtotal if (line.product_id.tms_category == 'fuel' and not line.fuel_voucher) else 0.0
                    fuel_qty        += line.product_uom_qty if (line.product_id.tms_category == 'fuel' and not line.fuel_voucher) else 0.0 
                    tax_total       += line.tax_amount if line.product_id.tms_category != 'madeup_expense' else 0.0
                    tax_real        += line.tax_amount if (line.product_id.tms_category == 'real_expense' or (line.product_id.tms_category == 'fuel' and not line.fuel_voucher)) else 0.0
            subtotal_real = real_expense + fuel + salary + salary_retention + salary_discount + negative_balance
            total_real = subtotal_real + tax_real
            subtotal_total = subtotal_real + fuel_voucher
            total_total = subtotal_total + tax_total
            balance = total_real - advance
            res[expense.id] = { 
                'amount_real_expense'       : cur_obj.round(cr, uid, cur, real_expense),
                'amount_madeup_expense'     : cur_obj.round(cr, uid, cur, madeup_expense),
                'fuel_qty'                  : cur_obj.round(cr, uid, cur, fuel_qty),
                'amount_fuel'               : cur_obj.round(cr, uid, cur, fuel),
                'amount_fuel_voucher'       : cur_obj.round(cr, uid, cur, fuel_voucher),
                'amount_salary'             : cur_obj.round(cr, uid, cur, salary),
                'amount_net_salary'         : cur_obj.round(cr, uid, cur, salary + salary_retention + salary_discount),
                'amount_salary_retention'   : cur_obj.round(cr, uid, cur, salary_retention),
                'amount_salary_discount'    : cur_obj.round(cr, uid, cur, salary_discount),
                'amount_subtotal_real'      : cur_obj.round(cr, uid, cur, subtotal_real),
                'amount_subtotal_total'     : cur_obj.round(cr, uid, cur, subtotal_total),
                'amount_tax_real'           : cur_obj.round(cr, uid, cur, tax_real),
                'amount_tax_total'          : cur_obj.round(cr, uid, cur, tax_total),
                'amount_total_real'         : cur_obj.round(cr, uid, cur, total_real),
                'amount_total_total'        : cur_obj.round(cr, uid, cur, total_total),
                'amount_advance'            : cur_obj.round(cr, uid, cur, advance),
                'amount_balance'            : cur_obj.round(cr, uid, cur, balance),
                'amount_balance2'           : cur_obj.round(cr, uid, cur, balance),
                              }
        return res

    def _paid(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            val = False
            if record.move_id.id:
                for ml in record.move_id.line_id:
                    if ml.credit > 0 and record.employee_id.address_home_id.id == ml.partner_id.id:
                        res[record.id]  = (ml.reconcile_id.id or ml.reconcile_partial_id.id)
                        return res
        return res

    def _get_move_line_from_reconcile(self, cr, uid, ids, context=None):
        move = {}
        for r in self.pool.get('account.move.reconcile').browse(cr, uid, ids, context=context):
            for line in r.line_partial_ids:
                move[line.move_id.id] = True
            for line in r.line_id:
                move[line.move_id.id] = True
        expense_ids = []
        if move:
            expense_ids = self.pool.get('tms.expense').search(cr, uid, [('move_id','in',move.keys())], context=context)
        return expense_ids

    def _get_fuel_diff(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for expense in self.browse(cr, uid, ids, context=context):
            fuel=0.0
            if expense.fuel_qty_real and expense.fuel_qty:                
                res[expense.id] = {'fuel_diff': float(expense.fuel_qty_real) - float(expense.fuel_qty),
                                   'global_fuel_efficiency_real': (expense.distance_real / expense.fuel_qty_real) if expense.fuel_qty_real else 0.0,
                                  }
        return res    

    _columns = {
        'name': fields.char('Name', size=64, readonly=True, select=True),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'employee_id': fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')], readonly=True, states={'draft': [('readonly', False)]}),
        'employee_id_control': fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')], readonly=True, states={'draft': [('readonly', False)]}),
        'travel_ids': fields.many2many('tms.travel', 'tms_expense_travel_rel', 'expense_id', 'travel_id', 'Travels', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'travel_ids2': fields.many2many('tms.travel', 'tms_expense_travel_rel2', 'expense_id', 'travel_id', 'Travels for Driver Helper', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'unit_id': fields.many2one('fleet.vehicle', 'Unit', required=False, readonly=True),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('confirmed', 'Confirmed'),
            ('cancel', 'Cancelled')
            ], 'Expense State', readonly=True, help="Gives the state of the Travel Expense. ", select=True),
        'expense_policy': fields.selection([           
            ('manual', 'Manual'),
            ('automatic', 'Automatic'),
            ], 'Expense  Policy', readonly=True,
            help=" Manual - This expense record is manual\nAutomatic - This expense record is automatically generated by parametrization", select=True),
        'origin': fields.char('Source Document', size=64, help="Reference of the document that generated this Expense Record",readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'date': fields.date('Date', required=True, select=True,readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'invoice_id': fields.many2one('account.invoice','Invoice Record', readonly=True),
        'invoiced':  fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi='invoiced'),
        'invoice_paid':  fields.function(_invoiced, method=True, string='Paid', type='boolean', multi='invoiced'),
        'invoice_name':  fields.function(_invoiced, method=True, string='Invoice', type='char', size=64, multi='invoiced', store=True),
        'expense_line': fields.one2many('tms.expense.line', 'expense_id', 'Expense Lines', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'amount_real_expense': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Expenses', type='float', multi=True),
        'amount_madeup_expense': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fake Expenses', type='float', multi=True), 
        'fuel_qty'  : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fuel Qty', type='float', multi=True),
        'amount_fuel': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fuel (Cash)', type='float', multi=True),
        'amount_fuel_voucher': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fuel (Voucher)', type='float', multi=True),
        'amount_salary': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary', type='float', multi=True),
        'amount_net_salary': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Net Salary', type='float', multi=True),
        'amount_salary_retention': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary Retentions', type='float', multi=True),
        'amount_salary_discount': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary Discounts', type='float', multi=True),
        'amount_advance': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Advances', type='float', multi=True),
        'amount_balance': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Balance', type='float', multi=True),
        'amount_balance2': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Balance', type='float', multi=True, store=True),
        'amount_tax_total': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes (All)', type='float', multi=True),
        'amount_tax_real': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes (Real)', type='float', multi=True),
        'amount_total_real': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (Real)', type='float', multi=True),
        'amount_total_total': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (All)', type='float', multi=True),
        'amount_subtotal_real': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='SubTotal (Real)', type='float', multi=True),
        'amount_subtotal_total': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='SubTotal (All)', type='float', multi=True),
        'vehicle_id'        : fields.many2one('fleet.vehicle', 'Vehicle'),
        'odometer_id'       : fields.many2one('fleet.vehicle.odometer.device', 'Odometer'),
        'last_odometer'     : fields.float('Last Read', digits=(16,2)),
        'vehicle_odometer'  : fields.float('Vehicle Odometer', digits=(16,2)),
        'current_odometer'  : fields.float('Current Read', digits=(16,2)),
        'distance_routes'   : fields.function(_get_route_distance, string='Distance from routes', method=True, type='float', digits=(16,2), help="Routes Distance"),
        'distance_real'     : fields.float('Distance Real', digits=(16,2), help="Route obtained by electronic reading and/or GPS"),
        'odometer_log_id'   : fields.many2one('fleet.vehicle.odometer', 'Odometer Record'),
        'global_fuel_efficiency_routes': fields.function(_get_fuel_efficiency, string='Global Fuel Efficiency Routes', method=True, type='float', digits=(16,2)),        
        'loaded_fuel_efficiency': fields.float('Loaded Fuel Efficiency', required=False, digits=(14,2)),
        'unloaded_fuel_efficiency': fields.float('Unloaded Fuel Efficiency', required=False, digits=(14,2)),
        'create_uid' : fields.many2one('res.users', 'Created by', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by' : fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': fields.datetime('Date Cancelled', readonly=True),
        'approved_by' : fields.many2one('res.users', 'Approved by', readonly=True),
        'date_approved': fields.datetime('Date Approved', readonly=True),
        'confirmed_by' : fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed': fields.datetime('Date Confirmed', readonly=True),
        'drafted_by' : fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted': fields.datetime('Date Drafted', readonly=True),
        'notes': fields.text('Notes', readonly=False, states={'closed':[('readonly',True)]}),
        'move_id'       : fields.many2one('account.move', 'Journal Entry', readonly=True, select=1, ondelete='restrict', help="Link to the automatically generated Journal Items."),

        'paid'          : fields.function(_paid, method=True, string='Paid', type='boolean', multi=False,
                                          store = {'tms.expense': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                   'account.move.reconcile': (_get_move_line_from_reconcile, None, 50)}),        
        'fuelvoucher_ids':fields.one2many('tms.fuelvoucher', 'expense_id', string='Fuel Vouchers', readonly=True),
        'advance_ids':fields.one2many('tms.advance', 'expense_id', string='Advances', readonly=True),
        'parameter_distance': fields.integer('Distance Parameter', help="1 = Travel, 2 = Travel Expense, 3 = Manual, 4 = Tyre"),
        'driver_helper' : fields.boolean('For Driver Helper', help="Check this if you want to make record for Driver Helper.", states={'cancel':[('readonly',True)], 'approved':[('readonly',True)], 'confirmed':[('readonly',True)]}),
        'fuel_qty_real' : fields.float('Fuel Qty Real', digits=(16,2), 
                                          help="Fuel Qty computed based on Distance Real and Global Fuel Efficiency Real obtained by electronic reading and/or GPS"),
        'fuel_diff'     : fields.function(_get_fuel_diff, string="Fuel Difference", type='float', digits=(16,2), method=True, multi=True,
                                          store = {'tms.expense': (lambda self, cr, uid, ids, c={}: ids, [], 10)},
                                          help="Fuel Qty Difference between Fuel Vouchers + Fuel Paid in Cash versus Fuel qty computed based on Distance Real and Global Fuel Efficiency Real obtained by electronic reading and/or GPS"),
        'global_fuel_efficiency_real': fields.function(_get_fuel_diff, string='Global Fuel Efficiency Real', type='float', digits=(16,2), method=True, multi=True,
                                                       store = {'tms.expense': (lambda self, cr, uid, ids, c={}: ids, [], 10)},
                                                       ),

    }
    _defaults = {
        'date'              : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'expense_policy'    : 'manual',
        'state'             : lambda *a: 'draft',
        'currency_id'       : lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'parameter_distance': lambda s, cr, uid, c: int(s.pool.get('ir.config_parameter').get_param(cr, uid, 'tms_property_update_vehicle_distance', context=c)[0]),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Expense record must be unique !'),
    ]

    def _check_units_in_travels(self, cr, uid, ids, context=None):
        for expense in self.browse(cr, uid, ids, context=context):  
            last_unit = False
            first = True
            for travel in expense.travel_ids:
                if not first:
                    if last_unit != travel.unit_id.id:
                        return False
                else:
                    last_unit = travel.unit_id.id
                    first = False
        return True

    def _check_odometer(self, cr, uid, ids, context=None):         
        for record in self.browse(cr, uid, ids, context=context):
            if record.current_odometer <= record.last_odometer:
                return False
        return True

    def _check_date(self, cr, uid, ids, context=None):         
        for record in self.browse(cr, uid, ids, context=context):
            # print "record.date: ", record.date
            cr.execute("select date from tms_expense where id <> %s and employee_id = %s and state = 'confirmed' and date > '%s' order by date desc, date_confirmed desc limit 1;" % (record.id, record.employee_id.id, record.date))
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            # print "data: ", data
            return not bool(len(data))
        return True

    _constraints = [
        (_check_units_in_travels, 'You can not create a Travel Expense Record with several units.', ['travel_ids']),
        (_check_odometer, 'You can not have Current Reading <= Last Reading !', ['current_odometer']),
        (_check_date, 'You can not have Travel Expense Record with date before last Travel Expense record related to this Driver !', ['date']),
    ]

    _order = 'name desc'

    def on_change_employee_id(self, cr, uid, ids, employee_id, context=None):
        expense_obj = self.pool.get('tms.expense')
        res = expense_obj.search(cr, uid, [('employee_id', '=', employee_id),('state','in', ('draft','approved'))], limit=1)
        if res:
            raise osv.except_osv(
                        _('Warning !'),
                        _('There is already a Travel Expense Record pending to be confirmed. You can not create another Travel Expense record with the same driver !!!'))   
        return {'value': {'employee_id': employee_id}}

    def get_salary_retentions(self, cr, uid, ids, context=None):
        factor_special_obj = self.pool.get('tms.factor.special')
        factor_special_ids = factor_special_obj.search(cr, uid, [('type', '=', 'retention'), ('active', '=', True)])        
        if len(factor_special_ids):
            for expense in self.browse(cr, uid, ids):
                exec factor_special_obj.browse(cr, uid, factor_special_ids)[0].python_code
        return

    def get_salary_advances_and_fuel_vouchers(self, cr, uid, ids, vals, context=None):  
        prod_obj = self.pool.get('product.product')
        salary_id = prod_obj.search(cr, uid, [('tms_category', '=', 'salary'),('tms_default_salary','=', 1),('active','=', 1)], limit=1)
        if not salary_id:
            raise osv.except_osv(
                        _('Missing configuration !'),
                        _('There is no product defined as Default Salary !!!'))
        salary = prod_obj.browse(cr, uid, salary_id, context=None)[0]
        qty = amount_untaxed = 0.0
        factor_obj = self.pool.get('tms.factor')
        factor_special_obj = self.pool.get('tms.factor.special')
        expense_line_obj = self.pool.get('tms.expense.line')
        expense_obj = self.pool.get('tms.expense')
        travel_obj = self.pool.get('tms.travel')
        fuelvoucher_obj = self.pool.get('tms.fuelvoucher')
        advance_obj     = self.pool.get('tms.advance')
        res = expense_line_obj.search(cr, uid, [('expense_id', '=', ids[0]),('control','=', 1),('loan_id','=',False)])
        if len(res):
            res = expense_line_obj.unlink(cr, uid, res)
        fuel = 0.0
        for expense in self.browse(cr, uid, ids):
            currency_id = expense.currency_id.id
            # Quitamos la referencia en caso de que ya existan registros asociados a la Liquidacion
            fuelvoucher_ids = advance_ids = travel_ids = False
            fuelvoucher_ids = fuelvoucher_obj.search(cr, uid, [('expense_id', '=', expense.id)])
            if fuelvoucher_ids:
                fuelvoucher_obj.write(cr, uid, fuelvoucher_ids, {'expense_id': False, 'state':'confirmed', 'closed_by': False,'date_closed': False})
            advance_ids = advance_obj.search(cr, uid, [('expense_id', '=', expense.id)])
            if advance_ids:
                advance_obj.write(cr, uid, advance_ids, {'expense_id': False, 'state':'confirmed', 'closed_by': False, 'date_closed': False})
            if not expense.driver_helper:
                travel_ids = travel_obj.search(cr, uid, [('expense_id', '=', expense.id)])
                if travel_ids:
                    travel_obj.write(cr, uid, travel_ids, {'expense_id': False, 'state':'done', 'closed_by': False, 'date_closed': False})
            else:
                travel_ids = travel_obj.search(cr, uid, [('expense2_id', '=', expense.id)])
                if travel_ids:
                    travel_obj.write(cr, uid, travel_ids, {'expense2_id': False})
            travel_ids = []
            for travel in (expense.travel_ids if not expense.driver_helper else expense.travel_ids2):
                travel_ids.append(travel.id)
                factor_special_ids = factor_special_obj.search(cr, uid, [('type', '=', 'salary'), ('active', '=', True)])
                if len(factor_special_ids):
                    exec factor_special_obj.browse(cr, uid, factor_special_ids, driver_helper=expense.driver_helper)[0].python_code
                else:
                    result = factor_obj.calculate(cr, uid, 'expense', False, 'driver', [travel.id], driver_helper=expense.driver_helper)
                #salary += result
                xline = {
                        'travel_id'         : travel.id,
                        'expense_id'        : expense.id,
                        'line_type'         : salary.tms_category,
                        'name'              : salary.name + ' - ' + _('Travel: ') + travel.name, 
                        'sequence'          : 1,
                        'product_id'        : salary.id,
                        'product_uom'       : salary.uom_id.id,
                        'product_uom_qty'   : 1,
                        'price_unit'        : result,
                        'control'           : True,
                        'operation_id'      : travel.operation_id.id,
                        'tax_id'            : [(6, 0, [x.id for x in salary.supplier_taxes_id])],
                        }
                if result:
                    res = expense_line_obj.create(cr, uid, xline)
                qty = 0.0
                for fuelvoucher in travel.fuelvoucher_ids:
                    if fuelvoucher.state == 'cancel':
                        continue
                    elif fuelvoucher.state in ('draft', 'approved'):
                        raise osv.except_osv(_('Warning !'),
                                     _('Fuel Voucher %s is not Confirmed...') % (fuelvoucher.name)
                                     )
                    elif fuelvoucher.employee_id.id == expense.employee_id.id:
                        xline = {
                                'travel_id'         : travel.id,
                                'expense_id'        : expense.id,
                                'line_type'         : 'fuel',
                                'name'              : fuelvoucher.product_id.name + _(' from Fuel Vouchers - Travel: ') + travel.name,
                                'sequence'          : 5,
                                'product_id'        : fuelvoucher.product_id.id,
                                'product_uom'       : fuelvoucher.product_id.uom_id.id,
                                'product_uom_qty'   : fuelvoucher.product_uom_qty,
                                'price_unit'        : (fuelvoucher.price_subtotal / fuelvoucher.currency_id.rate) / fuelvoucher.product_uom_qty,
                                'control'           : True,
                                'tax_id'            : [(6, 0, [x.id for x in fuelvoucher.product_id.supplier_taxes_id])] if not fuelvoucher.partner_id.tms_fuel_internal else [],
                                'fuel_voucher'      : True,
                                'operation_id'      : fuelvoucher.operation_id.id,
                                'special_tax_amount': fuelvoucher.special_tax_amount,
                                }
                        res = expense_line_obj.create(cr, uid, xline)
                        fuelvoucher_obj.write(cr, uid, [fuelvoucher.id], {'expense_id': expense.id, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                for advance in travel.advance_ids:                    
                    if advance.state == 'cancel':
                        continue
                    elif advance.state in ('draft', 'approved'):
                        raise osv.except_osv(_('Warning !'),
                                     _('Advance %s is not Confirmed...') % (advance.name)
                                     )
                    #elif not advance.paid and advance.state == 'confirmed':
                    #    raise osv.except_osv(_('Warning !'),
                    #                 _('Advance %s is Confirmed but is not Paid yet...') % (advance.name)
                    #                 )
                    elif advance.employee_id.id == expense.employee_id.id:
                        if advance.auto_expense:
                            xline = {
                                'travel_id'         : travel.id,
                                'expense_id'        : expense.id,
                                'line_type'         : advance.product_id.tms_category,
                                'name'              : advance.product_id.name + ' - ' + _('Travel: ') + travel.name, 
                                'sequence'          : 7,
                                'product_id'        : advance.product_id.id,
                                'product_uom'       : advance.product_id.uom_id.id,
                                'product_uom_qty'   : advance.product_uom_qty,
                                'price_unit'        : advance.price_unit,
                                'control'           : True,
                                'tax_id'            : [(6, 0, [x.id for x in advance.product_id.supplier_taxes_id])],
                                'operation_id'      : advance.operation_id.id,
                                }
                            res = expense_line_obj.create(cr, uid, xline)
                        advance_obj.write(cr, uid, [advance.id], {'expense_id': expense.id, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                if not expense.driver_helper:    
                    travel_obj.write(cr, uid, [travel.id], {'expense_id': expense.id, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                else:
                    travel_obj.write(cr, uid, [travel.id], {'expense2_id': expense.id})
                self.pool.get('tms.expense.loan').get_loan_discounts(cr, uid, expense.employee_id.id, expense.id)
            #Revisamos si tiene un Balance en contra
            cr.execute("select id from tms_expense where employee_id = %s and state = 'confirmed' order by date desc, date_confirmed desc limit 1" % (expense.employee_id.id))
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            if len(data):
                rec = self.browse(cr, uid, data)[0]
                ##print "=======\nLiquidación: ", rec.name
                ##print "Saldo: ", rec.amount_balance
                if rec.amount_balance < 0:
                    ##print "Si entra a intentar crear la linea de Saldo en contra arrastrado..."
                    red_balance_id = prod_obj.search(cr, uid, [('tms_category', '=', 'negative_balance'),('active','=', 1)], limit=1)
                    if not red_balance_id:
                        raise osv.except_osv(
                            _('Missing configuration !'),
                            _('There is no product defined as Negative Balance !!!'))
                    red_balance = prod_obj.browse(cr, uid, red_balance_id, context=None)[0]
                    xline = {                                
                        'expense_id'        : expense.id,
                        'line_type'         : red_balance.tms_category,
                        'name'              : red_balance.name + ' - ' + _('Travel Expense: ') + rec.name, 
                        'sequence'          : 200,
                        'product_id'        : red_balance.id,
                        'product_uom'       : red_balance.uom_id.id,
                        'product_uom_qty'   : 1,
                        'price_unit'        : rec.amount_balance,
                        'control'           : True,
                        'tax_id'            : [(6, 0, [x.id for x in red_balance.supplier_taxes_id])],                                
                        }
                    res = expense_line_obj.create(cr, uid, xline)
                    
            # Revisamos si se tiene que hacer Descuento por Rendimiento bajo
            if int(self.pool.get('ir.config_parameter').get_param(cr, uid, 'tms_property_discount_for_low_fuel_efficiency_performance', context=context)[0]) \
                and expense.fuel_qty_real and expense.fuel_qty and expense.fuel_qty_real < expense.fuel_qty:
                fuel_qty_diff = expense.fuel_qty_real - expense.fuel_qty
                fuel_id_closed = fuelvoucher_obj.search(cr, uid, [('state','=','closed')], limit=1, order="date desc")
                fuel_id_confirmed = fuelvoucher_obj.search(cr, uid, [('state','=','confirmed')], limit=1, order="date desc")
                fuel_cost = 0
                if fuel_id_closed and fuel_id_confirmed:
                    fuelvoucher_closed = fuelvoucher_obj.browse(cr, uid, fuel_id_closed)[0]
                    fuelvoucher_confirmed = fuelvoucher_obj.browse(cr, uid, fuel_id_confirmed)[0]
                    fuel_cost = fuelvoucher_closed.price_unit if fuelvoucher_confirmed.date < fuelvoucher_closed.date else fuelvoucher_confirmed.price_unit
                elif fuel_id_closed and not fuel_id_confirmed:
                    fuelvoucher_closed = fuelvoucher_obj.browse(cr, uid, fuel_id_closed)[0]
                    fuel_cost = fuelvoucher_closed.price_unit
                elif fuel_id_confirmed and not fuel_id_closed:
                    fuelvoucher_confirmed = fuelvoucher_obj.browse(cr, uid, fuel_id_confirmed)[0]
                    fuel_cost = fuelvoucher_confirmed.price_unit
                if not fuel_cost:
                    fuel_cost = float(self.pool.get('ir.config_parameter').get_param(cr, uid, 'tms_property_fuel_cost_for_discount', context=context)[0])
                if fuel_qty_diff < 0.0: 
                    fuel_discount_prod_id = prod_obj.search(cr, uid, [('tms_category', '=', 'salary_discount'),('tms_default_fuel_discount','=', 1),('active','=', 1)], limit=1)
                    if not fuel_discount_prod_id:
                        raise osv.except_osv(
                            _('Missing configuration !'),
                            _('There is no product defined as Default Fuel Discount !!!'))
                    fuel_discount_prod = prod_obj.browse(cr, uid, fuel_discount_prod_id, context=None)[0]
                    xline = {                                
                        'expense_id'        : expense.id,
                        'line_type'         : fuel_discount_prod.tms_category,
                        'name'              : fuel_discount_prod.name, 
                        'sequence'          : 200,
                        'product_id'        : fuel_discount_prod.id,
                        'product_uom'       : fuel_discount_prod.uom_id.id,
                        'product_uom_qty'   : fuel_qty_diff,
                        'price_unit'        : fuel_cost,
                        'control'           : True,
                        'tax_id'            : [(6, 0, [x.id for x in fuel_discount_prod.supplier_taxes_id])],                                
                        }
                    res = expense_line_obj.create(cr, uid, xline)        
        return

    def on_change_travel_ids(self, cr, uid, ids, travel_ids, driver_helper, context=None):
        res = {'value' : 
                           {'unit_id'          : False,
                            'vehicle_id'       : False,
                            'vehicle_odometer' : 0.0,
                            'odometer_id'      : False,
                            'last_odometer'    : 0.0,
                            'distance_real'    : 0.0,
                            } 
                           }
        distance_extraction = 0.0
        for expense in self.browse(cr, uid, ids):
            if not expense.driver_helper:
                for travel in expense.travel_ids:
                    distance_extraction += travel.distance_extraction
            else:
                distance_extraction = 1.0
        travels = []
        for rec in travel_ids[0][2]:
            travels.append(rec)
        if len(travels):
            cr.execute("select sum(distance_extraction), unit_id from tms_travel where id in %s group by unit_id limit 1;",(tuple(travels),))
            data = cr.fetchall()
            if not len(data):
                raise osv.except_osv(_('Warning !'),
                                     _('There is no information about the Travel you just selected...'))
            #Falta revisar si se están duplicando los recorridos por primer y segundo operador.
            distance_extraction = data[0][0] if len(data) and not driver_helper else 1.0
            unit_id = data[0][1]
            odom_obj = self.pool.get('fleet.vehicle.odometer.device')
            odometer_id = odom_obj.search(cr, uid, [('vehicle_id', '=', unit_id), ('state', '=','active')], context=context)
            if odometer_id and odometer_id[0]:
                for odometer in odom_obj.browse(cr, uid, odometer_id):     
                    res = {'value' : 
                           {'unit_id'          : unit_id,
                            'vehicle_id'       : unit_id,
                            'vehicle_odometer' : round(self.pool.get('fleet.vehicle').browse(cr, uid, [unit_id])[0].odometer, 2),
                            'odometer_id'      : odometer_id[0],
                            'last_odometer'    : round(odometer.odometer_end, 2),
                            'distance_real'    : round(distance_extraction, 2),
                            } 
                           }
            else:
                raise osv.except_osv(
                        _('Record Warning !'),
                        _('There is no Active Odometer for vehicle %s') % (travel.unit_id.name))     
        return res    

    def on_change_fuel_qty_real(self, cr, uid, ids, distance_real, fuel_qty_real, fuel_qty):
        res = {}
        if fuel_qty_real:
            res = {'value': 
                   {'global_fuel_efficiency_real' : float(distance_real) / float(fuel_qty_real),
                    'fuel_diff'     : (fuel_qty_real - fuel_qty) if fuel_qty_real else 0.0,
                   }
                  }
        return res

    def on_change_current_odometer(self, cr, uid, ids, vehicle_id, last_odometer, current_odometer, distance_real, global_fuel_efficiency_real, fuel_qty_real, context=None):
        distance = round(current_odometer - last_odometer, 2)
        accum = round(self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id], context=context)[0].odometer + distance , 2)
        res =  {'value': {'vehicle_odometer' : accum }} 
        if round(distance, 2) != round(distance_real, 2):
            res = {'value': {'distance_real' : round(distance, 2),
                             'global_fuel_efficiency_real' : (float(distance_real) / float(fuel_qty_real)) if fuel_qty_real else 0.0,
                            }
                  }
        return res
        
    def on_change_distance_real(self, cr, uid, ids, vehicle_id, last_odometer, distance_real, fuel_qty_real, context=None):
        current_odometer = last_odometer + distance_real
        accum = self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id], context=context)[0].odometer + distance_real
        res =  {'value': {
                        'current_odometer' : round(current_odometer, 2),
                        'vehicle_odometer' : round(accum, 2),
                        'global_fuel_efficiency_real'    : (float(distance_real) / float(fuel_qty_real)) if fuel_qty_real else 0.0,
                        }    
                }
        return res

    def on_change_vehicle_odometer(self, cr, uid, ids, vehicle_id, last_odometer, vehicle_odometer, global_fuel_efficiency_real, context=None):
        return {}
        distance = vehicle_odometer - self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id], context=context)[0].odometer
        current_odometer = last_odometer + distance
        return {'value': {
                        'current_odometer' : round(current_odometer, 2),
                        'distance_real'    : round(distance, 2),
                        'fuel_qty_real'    : round(distance / global_fuel_efficiency_real, 2) if global_fuel_efficiency_real and distance else 0.0,
                        }    
                }

    def write(self, cr, uid, ids, vals, context=None):
        values = vals
        if 'vehicle_id' in vals and vals['vehicle_id']:
            values['unit_id'] = vals['vehicle_id']
        super(tms_expense, self).write(cr, uid, ids, values, context=context)
        for rec in self.browse(cr, uid, ids):
            if ('state' in vals and vals['state'] not in ('cancel', 'confirmed')) ^ (rec.state not in  ('cancel', 'confirmed')):
                self.get_salary_advances_and_fuel_vouchers(cr, uid, ids, vals)
                self.get_salary_retentions(cr, uid, ids, vals)
                self.pool.get('tms.expense.loan').get_loan_discounts(cr, uid, rec.employee_id.id, rec.id)
        return True

    def create(self, cr, uid, vals, context=None):
        values = vals
        if 'shop_id' in vals and vals['shop_id']:
            shop = self.pool.get('sale.shop').browse(cr, uid, [vals['shop_id']])[0]
            seq_id = shop.tms_travel_expenses_seq.id
            if shop.tms_travel_expenses_seq:
                seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
                values['name'] = seq_number
            else:
                raise osv.except_osv(_('Expense Sequence Error !'), _('You have not defined Expense Sequence for shop ' + shop.name))
        if 'vehicle_id' in vals and vals['vehicle_id']:
            values['unit_id'] = vals['vehicle_id']
        cr.execute("select id from tms_expense where state in ('draft', 'approved') and employee_id = " + str(vals['employee_id']))
        data = filter(None, map(lambda x:x[0], cr.fetchall()))
        if data:
            raise osv.except_osv(_('Warning !'), _('You can not have more than one Travel Expense Record in  Draft / Approved State'))                    
        res = super(tms_expense, self).create(cr, uid, values, context=context)
        self.get_salary_advances_and_fuel_vouchers(cr, uid, [res], vals)
        self.get_salary_retentions(cr, uid, [res])
        self.pool.get('tms.expense.loan').get_loan_discounts(cr, uid, values['employee_id'], res)
        return res

    def action_approve(self, cr, uid, ids, context=None):
        for expense in self.browse(cr, uid, ids, context=context):            
            if expense.amount_total_total == 0.0:
                 raise osv.except_osv(
                    _('Could not approve Expense !'),
                    _('Total Amount must be greater than zero.'))
            self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Expense '%s' is set to approved.") % name
            self.log(cr, uid, id, message)
        return True

    def action_confirm(self, cr, uid, ids, context=None):                
        for expense in self.browse(cr, uid, ids, context=None):
            current_odometer = self.pool.get('fleet.vehicle').browse(cr, uid, [expense.vehicle_id.id], context=context)[0].odometer
            if expense.vehicle_id.odometer != current_odometer:
                raise osv.except_osv(
                    _('Could not Confirm Expense Record!'),
                    _('Current Vehicle Odometer is grater than this Expense Record. You will have to cancel this Record and create a new one. Current Vehicle Odometer: %s Expense Record Odometer: %s') % (current_odometer, expense.vehicle_id.odometer))

            if not expense.parameter_distance:
                raise osv.except_osv(
                    _('Could not Confirm Expense Record !'),
                    _('Parameter to determine Vehicle distance update from does not exist.'))
            
            elif expense.parameter_distance == 2: # Revisamos el parametro (tms_property_update_vehicle_distance) donde se define donde se actualizan los kms/millas a las unidades 
                odom_obj = self.pool.get('fleet.vehicle.odometer')
                distance_real = distance_routes = 0.0
                for travel in expense.travel_ids:
                    distance_real += travel.distance_extraction
                    distance_routes += travel.distance_route
                for travel in expense.travel_ids:
                    xdistance = (travel.distance_route / distance_routes) * expense.distance_real if distance_real != expense.distance_real else travel.distance_extraction
                    odom_obj.create_odometer_log(cr, uid, expense.id, travel.id, expense.vehicle_id.id, xdistance)
                    if travel.trailer1_id and travel.trailer1_id.id:
                        odom_obj.create_odometer_log(cr, uid, expense.id, travel.id, travel.trailer1_id.id, xdistance)
                    if travel.dolly_id and travel.dolly_id.id:
                        odom_obj.create_odometer_log(cr, uid, expense.id, travel.id, travel.dolly_id.id, xdistance)
                    if travel.trailer2_id and travel.trailer2_id.id:
                        odom_obj.create_odometer_log(cr, uid, expense.id, travel.id, travel.trailer2_id.id, xdistance)


            factor_special_obj = self.pool.get('tms.factor.special')
            factor_special_ids = factor_special_obj.search(cr, uid, [('type', '=', 'salary_distribution'), ('active', '=', True)])        
            if len(factor_special_ids):
                for expense in self.browse(cr, uid, ids):
                    exec factor_special_obj.browse(cr, uid, factor_special_ids, driver_helper=expense.driver_helper)[0].python_code


        exp_invoice = self.pool.get('tms.expense.invoice')
        exp_invoice.makeInvoices(cr, uid, ids, context=None)
        return True

# Adding relation between Advances and Travel Expenses
class tms_advance(osv.osv):
    _inherit = "tms.advance"

    _columns = {
            'expense_id':fields.many2one('tms.expense', 'Expense Record', required=False, readonly=True),
            'expense2_id'   : fields.many2one('tms.expense', 'Expense Record for Drivef Helper', required=False, readonly=True),
        }

# Adding relation between Fuel Vouchers and Travel Expenses
class tms_fuelvoucher(osv.osv):
    _inherit = "tms.fuelvoucher"

    _columns = {
            'expense_id':fields.many2one('tms.expense', 'Expense Record', required=False, readonly=True),
            'expense2_id'   : fields.many2one('tms.expense', 'Expense Record for Drivef Helper', required=False, readonly=True),
        }

# Adding relation between Expense Records and Travels
class tms_travel(osv.osv):
    _inherit="tms.travel"

    _columns = {
        'expense_ids'   : fields.many2many('tms.expense', 'tms_expense_travel_rel', 'travel_id', 'expense_id', 'Expense Record'),
        'expense_ids2'   : fields.many2many('tms.expense', 'tms_expense_travel_rel2', 'travel_id', 'expense_id', 'Expense Record for Driver Helper'),
        'expense_id'    : fields.many2one('tms.expense', 'Expense Record', required=False, readonly=True),
        'expense2_id'   : fields.many2one('tms.expense', 'Expense Record for Driver Helper', required=False, readonly=True),
    }

# Class for Expense Lines
class tms_expense_line(osv.osv):
    _name = 'tms.expense.line'
    _description = 'Expense Line'

    def _amount_line(self, cr, uid, ids, field_name, args, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit
            partner_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id
            addr_id = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['invoice'])['invoice']
            taxes = tax_obj.compute_all(cr, uid, line.product_id.supplier_taxes_id, price, line.product_uom_qty, addr_id, line.product_id, line.company_id.partner_id)
            cur = line.expense_id.currency_id
            amount_with_taxes = cur_obj.round(cr, uid, cur, taxes['total_included'])
            amount_tax = cur_obj.round(cr, uid, cur, taxes['total_included']) - (cur_obj.round(cr, uid, cur, taxes['total']) or 0.0) + \
                        cur_obj.round(cr, uid, cur, line.special_tax_amount)
            price_subtotal = line.price_unit * line.product_uom_qty
            res[line.id] =  {   'price_subtotal': price_subtotal,
                                'price_total'   : amount_with_taxes,
                                'tax_amount'    : amount_tax,
                                }
        return res

    _columns = {
        'operation_id'      : fields.many2one('tms.operation', 'Operation', ondelete='restrict', required=False, readonly=False),        
        'travel_id'         : fields.many2one('tms.travel', 'Travel', required=False),
        'expense_id'        : fields.many2one('tms.expense', 'Expense', required=False, ondelete='cascade', select=True, readonly=True),
        'line_type'         : fields.selection([
                                          ('real_expense','Real Expense'),
                                          ('madeup_expense','Made-up Expense'),
                                          ('salary','Salary'),
                                          ('salary_retention','Salary Retention'),
                                          ('salary_discount','Salary Discount'),
                                          ('fuel','Fuel'),
                                          ('indirect','Indirect'),
                                          ('negative_balance','Negative Balance'),
                                    ], 'Line Type', require=True),

        'name'              : fields.char('Description', size=256, required=True),
        'sequence'          : fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
        'product_id'        : fields.many2one('product.product', 'Product', 
                                    domain=[('tms_category', 'in', ('expense_real', 'madeup_expense', 'salary','salary_retention' ,'salary_discount'))],
                                    ondelete='restrict'),
        'price_unit'        : fields.float('Price Unit', required=True, digits=(16, 4)),
        'price_unit_control': fields.float('Price Unit', digits_compute= dp.get_precision('Sale Price')),
        'price_subtotal'    : fields.function(_amount_line, method=True, string='SubTotal', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_total'       : fields.function(_amount_line, method=True, string='Total', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_amount'        : fields.function(_amount_line, method=True, string='Tax Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'special_tax_amount': fields.float('Special Tax', required=False, digits_compute= dp.get_precision('Sale Price')),
        'tax_id'            : fields.many2many('account.tax', 'expense_tax', 'tms_expense_line_id', 'tax_id', 'Taxes'),
        'product_uom_qty'   : fields.float('Quantity (UoM)', digits=(16, 4)),
        'product_uom'       : fields.many2one('product.uom', 'Unit of Measure '),
        'notes'             : fields.text('Notes'),
        'employee_id'       : fields.related('expense_id', 'employee_id', type='many2one', relation='hr.employee', store=True, string='Driver'),
        'shop_id'           : fields.related('expense_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'company_id'        : fields.related('expense_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'date'              : fields.related('expense_id', 'date', string='Date', type='date', store=True, readonly=True),
        'state'             : fields.related('expense_id', 'state', string='State', type='char', size=64, store=True, readonly=True),
        'fuel_voucher'      : fields.boolean('Fuel Voucher'),

        'control'           : fields.boolean('Control'), # Useful to mark those lines that must not be deleted for Expense Record (like Fuel from Fuel Voucher, Toll Stations payed without cash (credit card, voucher, etc)
        'automatic'         : fields.boolean('Automatic', help="Check this if you want to create Advances and/or Fuel Vouchers for this line automatically"),
        'credit'            : fields.boolean('Credit', help="Check this if you want to create Fuel Vouchers for this line"),
        'fuel_supplier_id'  : fields.many2one('res.partner', 'Fuel Supplier', domain=[('tms_category', '=', 'fuel')],  required=False),
    
        # Estos campos se crearon para generar automaticamente las facturas de los gastos que asi sean.
        'is_invoice'        : fields.boolean('Is Invoice?'),
        'partner_id'        : fields.many2one('res.partner', 'Supplier'),
        'invoice_date'      : fields.date('Date'),
        'invoice_number'    : fields.char('Invoice Number', size=64),
        'invoice_id'        : fields.many2one('account.invoice', 'Supplier Invoice', readonly=True),
    }
    _order = 'sequence'

    _defaults = {
        'line_type'         : 'real_expense',
        'product_uom_qty'   : 1,
        'sequence'          : 10,
        'price_unit'        : 0.0,
        'special_tax_amount': 0.0,
    }

    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        for product in prod_obj.browse(cr, uid, [product_id], context=None):
            res = {'value': {'product_uom' : product.uom_id.id,
                             'name': product.name,
                             'tax_id': [(6, 0, [x.id for x in product.supplier_taxes_id])],
                            }
                }
        return res

    def on_change_price_total(self, cr, uid, ids, product_id, product_uom_qty, price_total, special_tax_amount):
        res = {}
        if not (product_uom_qty and product_id and price_total):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].supplier_taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
        price_unit = price_total / (1.0 + tax_factor) / product_uom_qty
        price_subtotal = price_unit * product_uom_qty
        tax_amount = price_subtotal * tax_factor + special_tax_amount
        res = {'value': {
                'price_unit'         : price_unit,
                'price_unit_control' : price_unit,
                'price_subtotal' : price_subtotal, 
                'tax_amount'     : tax_amount, 
                }
               }
        return res

    def on_change_qty(self, cr, uid, ids, product_id, product_uom_qty, price_unit):
        res = {}
        if not (product_uom_qty and product_id and price_unit):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].supplier_taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
        price_total = price_unit * (1.0 + tax_factor) * product_uom_qty
        price_subtotal = price_unit * product_uom_qty
        tax_amount = price_subtotal * tax_factor
        res = {'value': {
                'price_unit'     : price_unit,
                'price_total'    : price_total,
                'price_subtotal' : price_subtotal, 
                'tax_amount'     : tax_amount, 
                }
               }
        return res

# Wizard que permite validar la cancelacion de una Liquidacion
class tms_expense_cancel(osv.osv_memory):

    """ To validate Expense Record Cancellation"""

    _name = 'tms.expense.cancel'
    _description = 'Validate Expense Record Cancellation'

    def action_cancel(self, cr, uid, ids, context=None):

        """
             To Validate when cancelling Expense Record
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """
        record_id =  context.get('active_ids',[])
        if record_id:
            invoice_obj = self.pool.get('account.invoice')
            expense_obj = self.pool.get('tms.expense')
            expense_line_obj = self.pool.get('tms.expense.line')
            expense_loan_obj = self.pool.get('tms.expense.loan')
            obj_move_reconcile = self.pool.get('account.move.reconcile')
            for expense in expense_obj.browse(cr, uid, record_id):
                cr.execute("select id from tms_expense where state <> 'cancel' and employee_id = " + str(expense.employee_id.id) + " order by date desc limit 1")
                data = filter(None, map(lambda x:x[0], cr.fetchall()))
                if len(data) > 0 and data[0] != expense.id:
                    raise osv.except_osv(
                            _('Could not cancel Expense Record!'),
                            _('This Expense Record is not the last one for this driver'))
                if expense.paid:
                    raise osv.except_osv(
                            _('Could not cancel Expense Record!'),
                            _('This Expense Record\'s is already paid'))
                    return False
                if expense.state == 'confirmed': # Unreconcile & Cancel Invoices linked to this Travel Expense Record
                    reconcile_ids = []
                    invoice_ids = []
                    for expense_line in expense.expense_line:
                        if expense_line.is_invoice:
                            invoice_ids.append(expense_line.invoice_id.id)
                            for move_line in expense_line.invoice_id.move_id.line_id:
                                if move_line.reconcile_id:
                                    reconcile_ids.append(move_line.reconcile_id.id)
                    if reconcile_ids:
                        obj_move_reconcile.unlink(cr, uid, reconcile_ids, context=context)
                    if invoice_ids:
                        wres = invoice_obj.action_cancel(cr, uid, invoice_ids, context)
                        #wres = invoice_obj.unlink(cr, uid, invoice_ids, context)
                move_id = expense.move_id.id
                move_state = expense.move_id.state
                expense_obj.write(cr, uid, record_id, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT), 'move_id': False})
                loan_ids = []
                for x in expense_obj.browse(cr, uid, record_id)[0].expense_line:                    
                    if x.loan_id.id:
                        loan_ids.append(x.loan_id.id)
                expense_line_obj.unlink(cr, uid, [x.id for x in expense_obj.browse(cr, uid, record_id)[0].expense_line])
                if len(loan_ids):
                    expense_loan_obj.write(cr, uid,loan_ids, {'state':'confirmed', 'closed_by' : False, 'date_closed':False} )
                if move_id:
                    move_obj = self.pool.get('account.move')
                    if move_state == 'posted':
                        move_obj.button_cancel(cr, uid, [move_id]) 
                    move_obj.unlink(cr, uid, [move_id])
                travel_ids = []
                for travel in (expense.travel_ids if not expense.driver_helper else expense.travel_ids2):
                    travel_ids.append(travel.id)
                fuelvoucher_obj = self.pool.get('tms.fuelvoucher')
                advance_obj     = self.pool.get('tms.advance')
                travel_obj     = self.pool.get('tms.travel')
                record_ids = fuelvoucher_obj.search(cr, uid, [('travel_id', 'in', tuple(travel_ids),), ('employee_id', '=', expense.employee_id.id), ('state','!=', 'cancel')])
                fuelvoucher_obj.write(cr, uid, record_ids, {'expense_id': False, 'state':'confirmed','closed_by':False,'date_closed':False})
                record_ids = advance_obj.search(cr, uid, [('travel_id', 'in', tuple(travel_ids),), ('employee_id', '=', expense.employee_id.id), ('state','!=', 'cancel')])
                advance_obj.write(cr, uid, record_ids, {'expense_id': False, 'state':'confirmed','closed_by':False,'date_closed':False})
                if not expense.driver_helper:
                    travel_obj.write(cr, uid, travel_ids, {'expense_id': False, 'state':'done','closed_by':False,'date_closed':False})
                else:
                    travel_obj.write(cr, uid, travel_ids, {'expense2_id': False})
                if not expense.parameter_distance:
                    raise osv.except_osv(
                        _('Could not Confirm Expense Record !'),
                        _('Parameter to determine Vehicle distance update from does not exist.'))
                elif expense.parameter_distance == 2 and expense.state=='confirmed': # Revisamos el parametro (tms_property_update_vehicle_distance) donde se define donde se actualizan los kms/millas a las unidades 
                    self.pool.get('fleet.vehicle.odometer').unlink_odometer_rec(cr, uid, ids, travel_ids, expense.unit_id.id)
        return {'type': 'ir.actions.act_window_close'}

# Wizard que permite generar el pago de la liquidación
class tms_expense_payment(osv.osv_memory):

    """ To create payment for expense"""

    _name = 'tms.expense.payment'
    _description = 'Make Payment for Travel Expenses'

    def makePayment(self, cr, uid, ids, context=None):
        if context is None:
            record_ids = ids
        else:
            record_ids =  context.get('active_ids',[])
        if not record_ids: return []
        ids = record_ids
        dummy, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_voucher', 'view_vendor_receipt_dialog_form')
        cr.execute("select count(distinct(employee_id, currency_id)) from tms_expense where state in ('confirmed') and id IN %s",(tuple(ids),))
        xids = filter(None, map(lambda x:x[0], cr.fetchall()))
        if len(xids) > 1:
            raise osv.except_osv('Error !',
                                 'You can not create Payment for several Drivers and or distinct currency...')
        amount = 0.0
        move_line_ids = []
        expense_names = ""
        for expense in self.pool.get('tms.expense').browse(cr, uid, ids, context=context):
            if expense.state=='confirmed' and expense.amount_balance > 0.0 and not expense.paid:
                expense_names += ", " + expense.name
                amount += expense.amount_balance
                for move_line in expense.move_id.line_id:
                    if move_line.credit > 0.0 and expense.employee_id.address_home_id.property_account_payable.id == move_line.account_id.id:
                        move_line_ids.append(move_line.id)
        if not amount:    
            raise osv.except_osv('Warning !',
                                 'All Travel Expenses are already paid or are not in Confirmed State...')
        res = {
            'name':_("Travel Expense Payment"),
            'view_mode': 'form',
            'view_id': view_id,
            'view_type': 'form',
            'res_model': 'account.voucher',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]', 
            'context': {
                'payment_expected_currency': expense.currency_id.id,
                'default_partner_id': self.pool.get('res.partner')._find_accounting_partner(expense.employee_id.address_home_id).id,
                'default_amount': amount,
                'default_name': _('Travel Expense(s) %s') % (expense_names),
                'close_after_process': False,
                'move_line_ids': [x for x in move_line_ids],
                'default_type': 'payment',
                'type': 'payment'
            }}
    
        return res

# Wizard que permite generar la poliza con el monto a pagar correspondiente a la liquidación del Operador
class tms_expense_invoice(osv.osv_memory):

    """ To create invoice for each Expense"""

    _name = 'tms.expense.invoice'
    _description = 'Make Invoices from Expense Records'

    def makeInvoices(self, cr, uid, ids, context=None):

        """
             To get Expense Record and create Invoice
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
            partner_obj=self.pool.get('res.partner')
            user_obj=self.pool.get('res.users')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            expense_obj=self.pool.get('tms.expense')
            expense_line_obj=self.pool.get('tms.expense.line')
            period_obj = self.pool.get('account.period')
            move_obj = self.pool.get('account.move')
            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'general'),('tms_expense_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 'You have not defined Travel Expense Purchase Journal...')
            journal_id = journal_id and journal_id[0]
            cr.execute("select distinct employee_id, currency_id from tms_expense where invoice_id is null and state='approved' and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv('Warning !',
                                 'Selected records are not Approved or already sent for payment...')
            for data in data_ids:
                expenses_ids = expense_obj.search(cr, uid, [('state','=','approved'),('employee_id','=', data[0]), ('currency_id','=', data[1]), ('id','in', tuple(record_ids),)])
                for expense in expense_obj.browse(cr, uid, expenses_ids):
                    period_id = period_obj.search(cr, uid, [('date_start', '<=', expense.date),('date_stop','>=', expense.date), ('state','=','draft')], context=None)
                    if not period_id:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no valid account period for this date %s. Period does not exists or is already closed') % \
                                        (expense.date,))
                    if not (expense.employee_id.tms_advance_account_id.id and expense.employee_id.tms_expense_negative_balance_account_id.id):
                        raise osv.except_osv(_('Warning !'),
                                _('There is no advance account and/or Travel Expense Negative Balance account defined ' \
                                        'for this driver: "%s" (id:%d)') % \
                                        (expense.employee_id.name, expense.employee_id.id,))
                    if not (expense.employee_id.address_home_id and expense.employee_id.address_home_id.id):
                        raise osv.except_osv(_('Warning !'),
                                _('There is no Address defined for this driver: "%s" (id:%d)') % \
                                        (expense.employee_id.name, expense.employee_id.id,))
                    advance_account = expense.employee_id.tms_advance_account_id.id
                    negative_balance_account = expense.employee_id.tms_expense_negative_balance_account_id.id
                    advance_account = account_fiscal_obj.map_account(cr, uid, False, advance_account)
                    negative_balance_account = account_fiscal_obj.map_account(cr, uid, False, negative_balance_account)

                    move_lines = []
                    precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
                    notes = _("Travel Expense Record ")
                    ### Revisamos si tiene Anticipos de Viaje para descontarlo del saldo del Operador
                    if expense.amount_advance:
                        move_line = (0,0, {
                                'name'          : _('Advance Discount'),
                                'account_id'    : advance_account,
                                'debit'         : 0.0,
                                'credit'        : round(expense.amount_advance, precision),
                                'journal_id'    : journal_id,
                                'period_id'     : period_id[0],
                                'vehicle_id'    : expense.unit_id.id,
                                'employee_id'   : expense.employee_id.id,
                                'sale_shop_id'  : expense.shop_id.id,
                                'partner_id'    : expense.employee_id.address_home_id.id,
                                })
                        move_lines.append(move_line)
                        notes += '\n' + _('Advance Discount')

                    ### Recorremos las lineas de gastos, estas deben ser cualquiera excepto: 
                    ### * Vales de Combustible
                    ### * Facilidades administrativas

                    invoice_ids = []
                    for line in expense.expense_line:
                        if line.line_type != ('madeup_expense') and not line.fuel_voucher:                            
                            prod_account = negative_balance_account if line.product_id.tms_category == 'negative_balance' else line.product_id.property_account_expense.id if line.product_id.property_account_expense.id else line.product_id.categ_id.property_account_expense_categ.id if line.product_id.categ_id.property_account_expense_categ.id else False
                            if not prod_account:
                                raise osv.except_osv(_('Warning !'),
                                        _('Expense Account is not defined for product %s (id:%d)') % \
                                            (line.product_id.name, line.product_id.id,))
                            inv_id = False
                            if line.is_invoice:
                                inv_id = self.create_supplier_invoice(cr, uid, line)
                                invoice_ids.append(inv_id)
                                yres = expense_line_obj.write(cr, uid, [line.id], {'invoice_id': inv_id})
                            ### Creamos la partida de cada Gasto "Valido"
                            move_line = (0,0, {
                                'name'              : expense.name + ((' |%s|' % (inv_id)) if inv_id else '') + line.name,
                                'ref'               : expense.name + ' - Inv ID - ' + str(inv_id) if inv_id else '',
                                'product_id'        : line.product_id.id,
                                'product_uom_id'    : line.product_uom.id,
                                'account_id'        : account_fiscal_obj.map_account(cr, uid, False, prod_account) if not line.is_invoice else line.partner_id.property_account_payable.id,
                                'debit'             : (round(line.price_subtotal, precision) if line.price_subtotal > 0.0 else 0.0) if not line.is_invoice else (line.price_total + (line.special_tax_amount or 0.0)),
                                'credit'            : round(abs(line.price_subtotal), precision) if line.price_subtotal <= 0.0 else 0.0,
                                'quantity'          : line.product_uom_qty,
                                'journal_id'        : journal_id,
                                'period_id'         : period_id[0],
                                'vehicle_id'        : expense.unit_id.id,
                                'employee_id'       : expense.employee_id.id,
                                'sale_shop_id'      : expense.shop_id.id,
                                'partner_id'        : expense.employee_id.address_home_id.id if not line.is_invoice else line.partner_id.id,
                                })
                            move_lines.append(move_line)
                            notes += '\n' + line.name
                            ### En caso de que el producto tenga definido impuestos, generamos las partidas correspondientes.
                            for tax in line.product_id.supplier_taxes_id:
                                tax_account = tax.account_collected_voucher_id.id
                                if not tax_account:
                                    raise osv.except_osv(_('Warning !'),
                                            _('Tax Account is not defined for Tax %s (id:%d)') % \
                                                (tax.name, tax.id,))
                                tax_amount = round(line.price_subtotal * tax.amount, precision)

                                move_line = (0,0, {
                                    'name'          : expense.name + ' - ' + tax.name + ' - ' + line.name + ' - ' + line.employee_id.name + ' (' + str(line.employee_id.id) + ')',
                                    'ref'           : expense.name,
                                    'account_id'    : account_fiscal_obj.map_account(cr, uid, False, tax_account),
                                    'debit'         : round(tax_amount, precision) if tax_amount > 0.0 else 0.0,
                                    'credit'        : round(abs(tax_amount), precision) if tax_amount <= 0.0 else 0.0,
                                    'journal_id'    : journal_id,
                                    'period_id'     : period_id[0],
                                    'tax_id_secondary' : tax.id if line.is_invoice else False,
                                    'amount_base'   : round(abs(line.price_subtotal),precision) if line.is_invoice else False,
                                    })
                                move_lines.append(move_line)
                                ### En caso de que sea una factura, se genera automaticamente la cancelación del impuesto
                                if line.is_invoice:
                                    tax_account = tax.account_collected_id.id
                                    if not tax_account:
                                        raise osv.except_osv(_('Warning !'),
                                                _('Tax Account is not defined for Tax %s (id:%d)') % \
                                                    (tax.name, tax.id,))
                                    tax_amount = round(line.price_subtotal * tax.amount, precision)
                                    move_line = (0,0, {
                                        'name'          : expense.name + ' - ' + tax.name + ' - ' + line.name + ' - ' + line.employee_id.name + ' (' + str(line.employee_id.id) + ')',
                                        'ref'           : expense.name,
                                        'account_id'    : account_fiscal_obj.map_account(cr, uid, False, tax_account),
                                        'debit'         : round(tax_amount, precision) if tax_amount <= 0.0 else 0.0,
                                        'credit'        : round(abs(tax_amount), precision) if tax_amount > 0.0 else 0.0,
                                        'journal_id'    : journal_id,
                                        'period_id'     : period_id[0],
                                        #'tax_id_secondary' : tax.id,
                                        #'amount_base'   : round(abs(line.price_subtotal),precision),                                            
                                        })
                                    move_lines.append(move_line)
                    if expense.amount_balance < 0:
                        move_line = (0,0, {
                                    'name'          : _('Negative Balance'),
                                    'ref'           : expense.name,
                                    'account_id'    : negative_balance_account,
                                    'debit'         : round(expense.amount_balance * -1.0, precision),
                                    'credit'        : 0.0,
                                    'journal_id'    : journal_id,
                                    'period_id'     : period_id[0],
                                    'vehicle_id'    : expense.unit_id.id,
                                    'employee_id'   : expense.employee_id.id,
                                    'partner_id'    : expense.employee_id.address_home_id.id,
                                    })
                        notes += '\n' + _('Debit Balance')
                    else:
                        b = line.employee_id.address_home_id.property_account_payable.id
                        if not b:
                            raise osv.except_osv(_('Warning !'),
                                _('There is no address created for this driver or there is no payable account defined for: "%s" (id:%d)') % \
                                    (line.employee_id.name, line.employee_id.id,))
                        b = account_fiscal_obj.map_account(cr, uid, False, b)
                        move_line = (0,0, {
                                    'name'          : _('Positive Balance'),
                                    'ref'           : expense.name,
                                    'account_id'    : b,
                                    'debit'         : 0.0,
                                    'credit'        : round(expense.amount_balance, precision),
                                    'journal_id'    : journal_id,
                                    'period_id'     : period_id[0],
                                    'vehicle_id'    : expense.unit_id.id,
                                    'employee_id'   : expense.employee_id.id,
                                    'partner_id'    : expense.employee_id.address_home_id.id,
                                    })
                        notes += '\n' + _('Credit Balance')
                    move_lines.append(move_line)
                    move = {
                        'ref'               : expense.name,
                        'journal_id'        : journal_id,
                        'narration'         : _('TMS-Travel Expense Record') + ' - ' + expense.name + ' - ' + expense.employee_id.name + ' (' + str(expense.employee_id.id) + ')',
                        'line_id'           : [x for x in move_lines],
                        'date'              : expense.date,
                        'period_id'         : period_id[0],
                        }
                    move_id = move_obj.create(cr, uid, move)
                    if move_id:
                        move_obj.button_validate(cr, uid, [move_id])
                    expense_obj.write(cr,uid,[expense.id], {'move_id': move_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                    res = self.reconcile_supplier_invoices(cr, uid, move_id, invoice_ids, context)
        return True

    def reconcile_supplier_invoices(self, cr, uid, move_id, invoice_ids, context=None):
        if context is None:
            context = {}
        move_line_obj = self.pool.get('account.move.line')
        for invoice in self.pool.get('account.invoice').browse(cr, uid, invoice_ids):
            xid = '%s' % (invoice.id)
            res = move_line_obj.search(cr, uid, [('move_id','=',move_id),('name','ilike',xid)])
            if not res:
                raise osv.except_osv('Error !',
                                    _('Move line was not found, please check your data...'))
            #print "invoice.id: ", invoice.id
            #print "invoice.number: ", invoice.number
            #print "invoice.supplier_invoice_number: ", invoice.supplier_invoice_number
            #print "invoice.amount_untaxed: ",  invoice.amount_untaxed
            #print "invoice.amount_tax: ", invoice.amount_tax
            #print "invoice.amount_total: ", invoice.amount_total
            #print "invoice.residual: ", invoice.residual     
            #print "invoice.partner_id: (%s) %s" % (invoice.partner_id.id, invoice.partner_id.name)
            for move_line in invoice.move_id.line_id:
                if move_line.account_id.type=='payable':
                    #print "move_line.account_id %s - %s" % (move_line.account_id.code, move_line.account_id.name)                    
                    lines = res + [move_line.id]
                    #for xline in move_line_obj.browse(cr, uid, lines):
                        #print "xline.account_id %s - %s" % (xline.account_id.code, xline.account_id.name)
                        #print "xline.debit: ", xline.debit
                        #print "xline.credit: ", xline.credit
                        #print "xline.partner_id: (%s) %s" % (xline.partner_id.id, xline.partner_id.name)
                        #print "xline.invoice.number: ", xline.invoice.number if xline.invoice else ''
                        #print "xline.invoice.supplier_invoice_number: ", xline.invoice.supplier_invoice_number if xline.invoice else ''
                        #print "xline.invoice.id: ", xline.invoice.id if xline.invoice else ''                        
                    res2 = move_line_obj.reconcile(cr, uid, lines, context=context)
        return

    def create_supplier_invoice(self, cr, uid, line, context=None):
        invoice_obj = self.pool.get('account.invoice')
        invoice_tax_obj = self.pool.get('account.invoice.tax')
        expense_line_obj = self.pool.get('tms.expense.line')
        journal_id = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'purchase'),('tms_expense_suppliers_journal','=', 1)], context)
        if not journal_id:
            raise osv.except_osv('Error !',
                             _('You have not defined Travel Expense Supplier Journal...'))
        journal_id = journal_id and journal_id[0]

        if line.product_id:
            a = line.product_id.product_tmpl_id.property_account_expense.id
            if not a:
                a = line.product_id.categ_id.property_account_expense_categ.id
            if not a:
                raise osv.except_osv(_('Error !'),
                        _('There is no expense account defined ' \
                                'for this product: "%s" (id:%d)') % \
                                (line.product_id.name, line.product_id.id,))
        else:
            a = property_obj.get(cr, uid,
                    'property_account_expense_categ', 'product.category',
                    context=context).id
        account_fiscal_obj=self.pool.get('account.fiscal.position')
        a = account_fiscal_obj.map_account(cr, uid, False, a)
        inv_line = (0,0, {
            'name'                  : _('%s (TMS Expense Record %s)') % (line.product_id.name, line.expense_id.name),
            'origin'                : line.expense_id.name,
            'account_id'            : a,
            'quantity'              : line.product_uom_qty,
            'price_unit'            : line.price_unit,
            'invoice_line_tax_id'   : [(6, 0, [x.id for x in line.product_id.supplier_taxes_id])],
            'uos_id'                : line.product_uom.id,
            'product_id'            : line.product_id.id,
            'notes'                  : line.name,
            'account_analytic_id'   : False,
            'vehicle_id'            : line.expense_id.unit_id.id,
            'employee_id'           : line.expense_id.employee_id.id,
            'sale_shop_id'          : line.expense_id.shop_id.id,
            })
        #print "Subtotal Factura: ", round(line.price_subtotal / line.product_uom_qty, 4)
        notes = line.expense_id.name + ' - ' + line.product_id.name
        a = line.partner_id.property_account_payable.id
        inv = {
            'supplier_invoice_number' : line.invoice_number,
            'name'              : line.expense_id.name + ' - ' + line.invoice_number,
            'origin'            : line.expense_id.name,
            'type'              : 'in_invoice',
            'journal_id'        : journal_id,
            'reference'         : line.expense_id.name + ' - ' + line.invoice_number,
            'account_id'        : a,
            'partner_id'        : line.partner_id.id,
            'invoice_line'      : [inv_line],
            'currency_id'       : line.expense_id.currency_id.id,
            'comment'           : line.expense_id.name + ' - ' + line.invoice_number,
            'payment_term'      : line.partner_id.property_payment_term and line.partner_id.property_payment_term.id or False,
            'fiscal_position'   : line.partner_id.property_account_position.id or False,
            'comment'           : notes,
            }

        inv_id = invoice_obj.create(cr, uid, inv)
        if line.special_tax_amount:
            invoice_obj.button_reset_taxes(cr, uid, [inv_id])
            for tax_line in invoice_obj.browse(cr, uid, inv_id).tax_line:
                if tax_line.amount==0.0:
                    invoice_tax_obj.write(cr, uid, [tax_line.id], {'amount':line.special_tax_amount})
        wf_service = netsvc.LocalService('workflow')
        wf_service.trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)
        res = expense_line_obj.write(cr, uid, [line.id], {'invoice_id':inv_id})
        return inv_id
