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
import decimal_precision as dp
from tools.translate import _
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import openerp

# Extra data fields for Waybills & Agreement
# Factors
class tms_factor(osv.osv):
    _name = "tms.factor"
    _description = "Factors to calculate Payment (Driver/Supplier) & Client charge"

    def _get_total(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        total = 0.0
        for factor in self.browse(cr, uid, ids, context=context):
            if factor.factor_type != 'special':
                res[factor.id] = factor.factor * factor.variable_amount + (factor.fixed_amount if factor.mixed else 0.0)
            else: 
                res[factor.id] = 0.0 # Pendiente generar cálculo especial
        return res


    _columns = {        
        'name'          : fields.char('Name', size=64, required=True),
        'category'      : fields.selection([
                                        ('driver', 'Driver'),
                                        ('customer', 'Customer'),
                                        ('supplier', 'Supplier'),
                                        ], 'Type', required=True),

        'factor_type'   : fields.selection([
                                        ('distance', 'Distance Route (Km/Mi)'),
                                        ('distance_real', 'Distance Real (Km/Mi)'),
                                        ('weight', 'Weight'),
                                        ('travel', 'Travel'),
                                        ('qty', 'Quantity'),
                                        ('volume', 'Volume'),
                                        ('percent', 'Income Percent'),
                                        ('special', 'Special'),
                                        ], 'Factor Type', required=True, help="""
For next options you have to type Ranges or Fixed Amount
 - Distance Route (Km/mi)
 - Distance Real (Km/Mi)
 - Weight
 - Quantity
 - Volume
For next option you only have to type Fixed Amount:
 - Travel
For next option you only have to type Factor like 10.5 for 10.50%:
 - Income Percent
For next option you only have to type Special Python Code:
 - Special
                        """),
        
        'framework'     : fields.selection([
                                ('Any', 'Any'),
                                ('Unit', 'Unit'),
                                ('Single', 'Single'),
                                ('Double', 'Double'),
                                ], 'Framework', required=True),

        'range_start'   : fields.float('Range Start',   digits=(16, 4)),
        'range_end'     : fields.float('Range End',     digits=(16, 4)),
        'factor'        : fields.float('Factor',        digits=(16, 4)),
        'fixed_amount'  : fields.float('Fixed Amount',  digits=(16, 4)),
        'mixed'         : fields.boolean('Mixed'),
        'factor_special_id': fields.many2one('tms.factor.special', 'Special'),

        'variable_amount' : fields.float('Variable',  digits=(16, 4)),
        'total_amount'  : fields.function(_get_total, method=True, digits_compute=dp.get_precision('Sale Price'), string='Total', type='float',
                                            store=True),

#        'waybill_ids'   : fields.many2many('tms.waybill', 'tms_factor_waybill_rel', 'factor_id', 'waybill_id', 'Waybills with this factor'), 
#        'expense_ids'   : fields.many2many('tms.expense', 'tms_factor_expense_rel', 'factor_id', 'expense_id', 'Expenses with this factor'), 
#        'route_ids'     : fields.many2many('tms.route',   'tms_factor_route_rel',   'factor_id', 'route_id',   'Routes with this factor'), 
#        'travel_ids'    : fields.many2many('tms.travel',  'tms_factor_travel_rel',  'factor_id', 'travel_id',  'Travels with this factor'), 

        'waybill_id'    : fields.many2one('tms.waybill', 'Waybill', required=False, ondelete='cascade'), #, select=True, readonly=True),
        'expense_id'    : fields.many2one('tms.expense', 'Expense', required=False, ondelete='cascade'), #, select=True, readonly=True),
        'route_id'      : fields.many2one('tms.route',   'Route', required=False, ondelete='cascade'), #, select=True, readonly=True),
        'travel_id'     : fields.many2one('tms.travel', 'Travel', required=False, ondelete='cascade'), #, select=True, readonly=True),
#        'agreement_id': fields.many2one('tms.negotiation', 'Negotiation', required=False, ondelete='cascade'),# select=True, readonly=True),
        'sequence'      : fields.integer('Sequence', help="Gives the sequence calculation for these factors."),
        'notes'         : fields.text('Notes'),
        'control'       : fields.boolean('Control'),
        'driver_helper' : fields.boolean('For Driver Helper'),
    }

    _defaults = {
        'mixed'             : False,
        'sequence'          : 10,
        'variable_amount'   : 0.0,
        'framework'         : 'Any',
    }

    _order = "sequence"

    def on_change_factor_type(self, cr, uid, ids, factor_type):
        if not factor_type:
            return {'value': {'name': False}}
        values = {
                    'distance'  : _('Distance Route (Km/Mi)'),
                    'distance_real'  : _('Distance Real (Km/Mi)'),
                    'weight'    : _('Weight'),
                    'travel'    : _('Travel'),
                    'qty'       : _('Quantity'),
                    'volume'    : _('Volume'),
                    'percent'   : _('Income Percent'),
                    'special'   : _('Special'),
            }
        return {'value': {'name': values[factor_type]}}

    def calculate(self, cr, uid, record_type, record_ids, calc_type=None, travel_ids=False, driver_helper=False, context=None):
        result = 0.0

        if record_type == 'waybill':
            waybill_obj = self.pool.get('tms.waybill')
            for waybill in waybill_obj.browse(cr, uid, record_ids, context=context):  # No soporta segundo operador
                for factor in (waybill.waybill_customer_factor if calc_type=='client' else waybill.expense_driver_factor if calc_type=='driver' else waybill.waybill_supplier_factor):
                    if factor.factor_type in ('distance', 'distance_real'): 
                        if not waybill.travel_id.id:
                            raise osv.except_osv(
                                _('Could calculate Amount for Waybill !'),
                                _('Waybill %s is not assigned to a Travel') % (waybill.name))
                        x = (float(waybill.travel_id.route_id.distance) if factor.factor_type=='distance' else float(waybill.travel_id.distance_extraction)) if factor.framework == 'Any' or factor.framework == waybill.travel_id.framework else 0.0

                    elif factor.factor_type == 'weight':
                        if not waybill.product_weight:
                            raise osv.except_osv(
                                _('Could calculate Freight Amount !'),
                                _('Waybill %s has no Products with UoM Category = Weight or Product Qty = 0.0' % waybill.name))

                        x = float(waybill.product_weight)

                    elif factor.factor_type == 'qty':
                        if not waybill.product_qty:
                            raise osv.except_osv(
                                _('Could calculate Freight Amount !'),
                                _('Waybill %s has no Products with Quantity > 0.0') % (waybill.name))

                        x = float(waybill.product_qty)

                    elif factor.factor_type == 'volume':
                        if not waybill.product_volume:
                            raise osv.except_osv(
                                _('Could calculate Freight Amount !'),
                                _('Waybill %s has no Products with UoM Category = Volume or Product Qty = 0.0') % (waybill.name))

                        x = float(waybill.product_volume)

                    elif factor.factor_type == 'percent':
                        x = float(waybill.amount_freight) / 100.0

                    elif factor.factor_type == 'travel':
                        x = 0.0

                    elif factor.factor_type == 'special':
                        exec factor.factor_special_id.python_code

                    
                    result += ((factor.fixed_amount if (factor.mixed or factor.factor_type=='travel') else 0.0)+ (factor.factor * x if factor.factor_type != 'special' else x)) if (((x >= factor.range_start and x <= factor.range_end) or (factor.range_start == factor.range_end == 0.0)) and factor.driver_helper==driver_helper) else 0.0

        elif record_type == 'expense' and travel_ids:
            travel_obj = self.pool.get('tms.travel')
            for travel in travel_obj.browse(cr, uid, travel_ids, context=context):
                res1 = res2 = weight = qty = volume = x = 0.0
                if travel.waybill_ids:
                    for waybill in travel.waybill_ids:
                        res1 += self.calculate(cr, uid, 'waybill', [waybill.id], 'driver', travel_ids=False, driver_helper=driver_helper)
                        weight  += waybill.product_weight
                        qty     += waybill.product_qty
                        volume  += waybill.product_volume
                if not res1:
                    for factor in travel.expense_driver_factor:
                        if factor.factor_type == 'distance':
                            x = (float(travel.route_id.distance) if factor.factor_type=='distance' else float(travel.route_id.distance_extraction)) if factor.framework == 'Any' or factor.framework == travel.framework else 0.0

                        elif factor.factor_type == 'weight':                            
                            if not weight:
                                raise osv.except_osv(
                                    _('Could calculate Freight Amount !'),
                                    _('Waybills related to Travel %s has no Products with UoM Category = Weight or Product Qty = 0.0') % (travel.name))
                            x = float(weight)

                        elif factor.factor_type == 'qty':
                            if not qty:
                                raise osv.except_osv(
                                    _('Could calculate Freight Amount !'),
                                    _('Waybills related to Travel %s has no Products with Quantity > 0.0') % (travel.name))
                            x = float(qty)

                        elif factor.factor_type == 'volume':
                            if not volume:
                                raise osv.except_osv(
                                    _('Could calculate Freight Amount !'),
                                    _('Waybills related to Travel %s has no Products with UoM Category = Volume or Product Qty = 0.0') % (travel.name))
                            x = float(volume)

                        elif factor.factor_type == 'travel':
                            x = 0.0

                        elif factor.factor_type == 'special':
                            exec factor.factor_special_id.python_code
                            
                        res2 += ((factor.fixed_amount if (factor.mixed or factor.factor_type=='travel') else 0.0) + (factor.factor * x if factor.factor_type != 'special' else x)) if (((x >= factor.range_start and x <= factor.range_end) or (factor.range_start == factor.range_end == 0.0)) and factor.driver_helper==driver_helper) else 0.0
                        
                result += res1 + res2

        return result
    
tms_factor()


class tms_factor_special(osv.osv):
    _name = "tms.factor.special"
    _description = "Python Code calculate Payment (Driver/Supplier) & Client charge"


    _columns = {
        'name'            : fields.char('Special Name', size=200, required=True),
        'active'          : fields.boolean('Active'),
        'date'            : fields.date('Date', required=True),
        'description'     : fields.text('Description'),
        'python_code'     : fields.text('Python Code', required=True),
        'factor_ids'      : fields.one2many('tms.factor', 'factor_special_id', 'Factor'),
        'type'            : fields.selection([
                ('salary', 'Driver Salary'),
                ('salary_distribution', 'Salary Distribution'),
                ('retention', 'Salary Retentions & Discounts'),
                ('supplier', 'Supplier Payment'),
                ], 'Type', required=True, help="""
Driver Salary => Use this for special Driver Salary calculation
Salary Distribution => Useful in some countries, you can make a Wage distribution on several expenses, so Salary is masked for Tax purposes
Salary Retentions & Discounts => Use this for Driver Tax retentions
Supplier => Use this to calculate Supplier Travel Payment
                """),

        'company_id'      : fields.many2one('res.company', 'Company', required=False),
        }
    
    _defaults = {
        'active' : True,
        'date'   : time.strftime( DEFAULT_SERVER_DATE_FORMAT),
        }

    def _check_only_one(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            cr.execute("select count(id) from tms_factor_special where type='%s' and active;" % (rec.type))
        count = filter(None, map(lambda x:x[0], cr.fetchall()))
        if  count and count[0] > 1:
            return False
        return True


    _constraints = [
        (_check_only_one, _('Error ! You can not have two active Factor with the same Type'), ['type']),
    ]



class tms_waybill(osv.osv):
    _inherit = 'tms.waybill'

    _columns = {

        'waybill_customer_factor': fields.one2many('tms.factor', 'waybill_id', 'Waybill Customer Charge Factors', domain=[('category', '=', 'customer')],
                                readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}), 
        'waybill_supplier_factor': fields.one2many('tms.factor', 'waybill_id', 'Waybill Supplier Payment Factors', domain=[('category', '=', 'supplier')],
                                readonly=False, states={'cancel': [('readonly', True)],'closed':[('readonly',True)]}),
        'expense_driver_factor': fields.one2many('tms.factor', 'waybill_id', 'Travel Driver Payment Factors', domain=[('category', '=', 'driver')],
                                readonly=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),

    }

tms_waybill()

class tms_travel(osv.osv):
    _inherit = 'tms.travel'

    _columns = {
        'expense_driver_factor': fields.one2many('tms.factor', 'travel_id', 'Travel Driver Payment Factors', domain=[('category', '=', 'driver')],
                                readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)]}),

    }

tms_travel()

class tms_route(osv.osv):
    _inherit = 'tms.route'

    _columns = {
        'expense_driver_factor': fields.one2many('tms.factor', 'route_id', 'Travel Driver Payment Factors', domain=[('category', '=', 'driver')],
                                readonly=False),

    }

tms_travel()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
