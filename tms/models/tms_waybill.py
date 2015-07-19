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
from datetime import datetime, date
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
from openerp import netsvc
from pytz import timezone


# Waybill Category
class tms_waybill_category(osv.osv):
    _name = 'tms.waybill.category'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Waybill Categories'

    _columns = {
        'shop_id'     : fields.many2one('sale.shop', 'Shop'),
        'company_id'  : fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'name'        : fields.char('Name', size=64, required=True),
        'description' : fields.text('Description'),
        'active'      : fields.boolean('Active'),
        }

    _defaults = {
        'active' : True,
        }

# Impuestos para desglose en Cartas Porte
class tms_waybill_taxes(osv.osv):
    _name = "tms.waybill.taxes"
    _description = "Waybill Taxes"

    _columns = {
        'waybill_id': fields.many2one('tms.waybill', 'Waybill', readonly=True),
        'name'      : fields.char('Impuesto', size=64, required=True),
        'tax_id'    : fields.many2one('account.tax', 'Impuesto', readonly=True),
        'account_id': fields.many2one('account.account', 'Tax Account', required=False, domain=[('type','<>','view'),('type','<>','income'), ('type', '<>', 'closed')]),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic account'),
        'base'      : fields.float('Base', digits_compute=dp.get_precision('Account'), readonly=True),
        'tax_amount': fields.float('Monto Impuesto', digits_compute=dp.get_precision('Account'), readonly=True),
    }
    
    _order = "tax_amount desc"
    
    def compute(self, cr, uid, waybill_ids, context=None):
        for id in waybill_ids:
            cr.execute("DELETE FROM tms_waybill_taxes WHERE waybill_id=%s", (id,))
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        wb_taxes_obj = self.pool.get('tms.waybill.taxes')
        for waybill in self.pool.get('tms.waybill').browse(cr, uid, waybill_ids, context=context):
            tax_grouped = {}
            cur = waybill.currency_id
            company_currency = self.pool['res.company'].browse(cr, uid, waybill.company_id.id).currency_id.id
            for line in waybill.waybill_line: 
                for tax in tax_obj.compute_all(cr, uid, line.tax_id, line.price_unit, line.product_uom_qty, line.product_id, waybill.partner_id)['taxes']:
                    val={}
                    val['waybill_id'] = waybill.id
                    val['name'] = tax['name']
                    val['tax_id'] = tax['id']
                    val['amount'] = tax['amount']
                    val['base'] = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['product_uom_qty'])
                    val['base_amount'] = cur_obj.compute(cr, uid, waybill.currency_id.id, company_currency, val['base'] * tax['base_sign'], context={'date': waybill.date_order or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, waybill.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], context={'date': waybill.date_order or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_collected_id'] or False
                    val['account_analytic_id'] = tax['account_analytic_collected_id']
                    key = (val['tax_id'], val['name'], val['account_id'], val['account_analytic_id'])
                    if not key in tax_grouped:
                        tax_grouped[key] = val
                    else:
                        tax_grouped[key]['amount'] += val['amount']
                        tax_grouped[key]['base'] += val['base']
                        tax_grouped[key]['base_amount'] += val['base_amount']
                        tax_grouped[key]['tax_amount'] += val['tax_amount']
            
            for t in tax_grouped.values():
                vals = {'waybill_id' : waybill.id,
                        'name'     : t['name'],
                        'tax_id'   : t['tax_id'],
                        'account_id': t['account_id'],
                        'account_analytic_id': t['account_analytic_id'],
                        'tax_amount': t['amount'],
                        'base'      : t['base'],
                        }
                res = wb_taxes_obj.create(cr, uid, vals)
                t['base'] = cur_obj.round(cr, uid, cur, t['base'])
                t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
                t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
                t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
        return 

    
 # TMS Waybills
class tms_waybill(osv.osv):
    _name = 'tms.waybill'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Waybills'


    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        #print "_amount_all"
        cur_obj = self.pool.get('res.currency')
        res = {}
        for waybill in self.browse(cr, uid, ids, context=context):
            res[waybill.id] = {
                'amount_freight': 0.0,
                'amount_freight': 0.0,
                'amount_move': 0.0,
                'amount_highway_tolls': 0.0,
                'amount_insurance': 0.0,
                'amount_other': 0.0,
                'amount_subtotal': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            cur = waybill.currency_id
            x_freight = x_move = x_highway = x_insurance = x_other = x_subtotal = x_tax  = x_total = 0.0
            for line in waybill.waybill_line:
                    x_freight += line.price_subtotal if line.product_id.tms_category == 'freight' else 0.0
                    x_move += line.price_subtotal if line.product_id.tms_category == 'move' else 0.0
                    x_highway += line.price_subtotal if line.product_id.tms_category == 'highway_tolls' else 0.0
                    x_insurance += line.price_subtotal if line.product_id.tms_category == 'insurance' else 0.0
                    x_other += line.price_subtotal if line.product_id.tms_category == 'other' else 0.0
                    x_subtotal += line.price_subtotal
                    x_tax += line.tax_amount
                    x_total += line.price_total
        
            res[waybill.id] = { 'amount_freight'        : cur_obj.round(cr, uid, cur, x_freight),
                                'amount_move'           : cur_obj.round(cr, uid, cur, x_move),
                                'amount_highway_tolls'  : cur_obj.round(cr, uid, cur, x_highway),
                                'amount_insurance'      : cur_obj.round(cr, uid, cur, x_insurance),
                                'amount_other'          : cur_obj.round(cr, uid, cur, x_other),
                                'amount_untaxed'        : cur_obj.round(cr, uid, cur, x_subtotal),
                                'amount_tax'            : cur_obj.round(cr, uid, cur, x_tax),
                                'amount_total'          : cur_obj.round(cr, uid, cur, x_total),

                              }
            
                        
        return res

    def _invoiced(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for rec in self.browse(cr, uid, ids, context=context):
            #print "rec.invoice_id.id: ", rec.invoice_id.id
            #print "rec.invoice_id.state: ", rec.invoice_id.state
            invoiced = bool(rec.invoice_id and rec.invoice_id.id and rec.invoice_id.state != 'cancel' or False)
            paid = bool(rec.invoice_id and rec.invoice_id.state == 'paid' or False)
            res[rec.id] =  { 'invoiced': invoiced,
                                'invoice_paid': paid,
                                'invoice_name': rec.invoice_id and rec.invoice_id.state != 'cancel' and rec.invoice_id.reference or '',
                                }
        return res


    def _supplier_invoiced(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            xinvoiced = bool(record.supplier_invoice_id and record.supplier_invoice_id.id and record.supplier_invoice_id.state != 'cancel' or False)
            xpaid = bool(record.invoice_id and record.invoice_id.state == 'paid')
            res[record.id] =  { 'supplier_invoiced': xinvoiced,
                                'supplier_invoice_paid': xpaid,
                                'supplier_invoice_name': record.supplier_invoice_id and record.supplier_invoice_id.state != 'cancel' and\
                                                         (record.supplier_invoice_id.supplier_invoice_number or\
                                                         record.supplier_invoice_id.reference) or False
                                }
        return res

    def _shipped_product(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        context_wo_lang = context.copy()
        context_wo_lang.pop('lang', None)
        for waybill in self.browse(cr, uid, ids, context=context_wo_lang):
            volume = weight = qty = 0.0
            for record in waybill.waybill_shipped_product:
                qty += record.product_uom_qty
                #print "Waybill - record.product_uom.category_id.name", record.product_uom.category_id.name
                volume += record.product_uom_qty if record.product_uom.category_id.name == 'Volume' else 0.0
                weight += record.product_uom_qty if record.product_uom.category_id.name == 'Weight' else 0.0
                res[waybill.id] =  {'product_qty': qty,
                                    'product_volume': volume,
                                    'product_weight': weight,
                                    'product_uom_type': (record.product_uom.category_id.name),
                                    }
        return res

    def _get_route_distance(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        distance=1.0
        for waybill in self.browse(cr, uid, ids, context=context):
            distance = waybill.route_id.distance
            res[waybill.id] = distance
        return res


    def _get_supplier_amount(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for waybill in self.browse(cr, uid, ids, context=context):
            result = 0.0
            if waybill.waybill_type == 'outsourced':
                factor_special_obj = self.pool.get('tms.factor.special')
                factor_special_ids = factor_special_obj.search(cr, uid, [('type', '=', 'supplier'), ('active', '=', True)])
                if len(factor_special_ids):
                    exec factor_special_obj.browse(cr, uid, factor_special_ids)[0].python_code
                    #print result
                else:
                    factor_obj = self.pool.get('tms.factor')
                    result = factor_obj.calculate(cr, uid, 'waybill', [waybill.id], 'supplier', False)                
            res[waybill.id] = result
        return res


    def _get_newer_travel_id(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        travel_id = False
        for waybill in self.browse(cr, uid, ids, context=context):
            for travel in waybill.travel_ids:
                travel_id = travel.id
            res[waybill.id] = travel_id
        return res

    def _get_waybill_type(self, cr, uid, ids, field_name, arg, context=None):
        #print "Entrando aqui..."
        res = {}
        for waybill in self.browse(cr, uid, ids, context=context):
            waybill_type = 'self'
            for travel in waybill.travel_ids:
                waybill_type = 'outsourced' if travel.unit_id.supplier_unit else 'self'
            res[waybill.id] = waybill_type
        return res

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('tms.waybill.line').browse(cr, uid, ids, context=context):
            result[line.waybill_id.id] = True
        return result.keys()

    def _get_invoice(self, cr, uid, ids, context=None):
        result = {}
        for invoice in self.pool.get('account.invoice').browse(cr, uid, ids, context=context):            
            for waybill in invoice.waybill_ids:
                result[waybill.id] = True
        return result.keys()

    def _get_supplier_invoice(self, cr, uid, ids, context=None):
        result = {}
        for invoice in self.pool.get('account.invoice').browse(cr, uid, ids, context=context):
            for waybill in invoice.waybill_ids:
                result[waybill.id] = True        
        return result.keys()
    

    _columns = {
        'tax_line'          : fields.one2many('tms.waybill.taxes', 'waybill_id', 'Tax Lines', readonly=True, states={'draft':[('readonly',False)]}),
        'name'              : fields.char('Name', size=64, readonly=False, select=True),
        'shop_id'           : fields.many2one('sale.shop', 'Shop', required=True, readonly=False, states={'confirmed': [('readonly', True)]}),
        'operation_id'      : fields.many2one('tms.operation', 'Operation', ondelete='restrict', required=False, readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)], 'closed':[('readonly',True)]}),
        'waybill_category'  : fields.many2one('tms.waybill.category', 'Category', ondelete='restrict', required=False, readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)], 'closed':[('readonly',True)]}),        
        'sequence_id'       : fields.many2one('ir.sequence', 'Sequence', required=True, ondelete='restrict', readonly=False, states={'confirmed': [('readonly', True)]}),
        'travel_ids'        : fields.many2many('tms.travel', 'tms_waybill_travel_rel', 'waybill_id', 'travel_id', 'Travels', readonly=False, states={'confirmed': [('readonly', True)]}),

        'travel_id'         : fields.function(_get_newer_travel_id, method=True, relation='tms.travel', type="many2one", string='Actual Travel', readonly=True, store=True, ondelete='cascade'),
        'supplier_id'       : fields.related('unit_id', 'supplier_id', type='many2one', relation='res.partner', string='Freight Supplier', store=True, readonly=True),                
        'supplier_amount'   : fields.function(_get_supplier_amount, string='Supplier Freight Amount', method=True, type='float', digits_compute= dp.get_precision('Sale Price'), help="Freight Amount from Supplier.", multi=False, store=True),

        'unit_id'           : fields.related('travel_id', 'unit_id', type='many2one', relation='fleet.vehicle', string='Unit', store=True, readonly=True),                
        'trailer1_id'       : fields.related('travel_id', 'trailer1_id', type='many2one', relation='fleet.vehicle', string='Trailer 1', store=True, readonly=True),                
        'dolly_id'          : fields.related('travel_id', 'dolly_id', type='many2one', relation='fleet.vehicle', string='Dolly', store=True, readonly=True),                
        'trailer2_id'       : fields.related('travel_id', 'trailer2_id', type='many2one', relation='fleet.vehicle', string='Trailer 2', store=True, readonly=True),                
        'employee_id'       : fields.related('travel_id', 'employee_id', type='many2one', relation='hr.employee', string='Driver', store=True, readonly=True),
        'employee2_id'      : fields.related('travel_id', 'employee2_id', type='many2one', relation='hr.employee', string='Driver Helper', store=True, readonly=True),                
        'route_id'          : fields.related('travel_id', 'route_id', type='many2one', relation='tms.route', string='Route', store=True, readonly=True),                
        'departure_id'      : fields.related('route_id', 'departure_id', type='many2one', relation='tms.place', string='Departure', store=True, readonly=True),                
        'arrival_id'        : fields.related('route_id', 'arrival_id', type='many2one', relation='tms.place', string='Arrival', store=True, readonly=True),                

        'origin'            : fields.char('Source Document', size=64, help="Reference of the document that generated this Waybill request.",readonly=False, states={'confirmed': [('readonly', True)]}),
        'client_order_ref'  : fields.char('Customer Reference', size=64, readonly=False, states={'confirmed': [('readonly', True)]}),
        'state'             : fields.selection([
                                ('draft', 'Pending'),
                                ('approved', 'Approved'),
                                ('confirmed', 'Confirmed'),
                                ('cancel', 'Cancelled')
                                ], 'State', readonly=True, help="Gives the state of the Waybill. \n ", select=True),
        'billing_policy'    : fields.selection([
                                ('manual', 'Manual'),
                                ('automatic', 'Automatic'),
                                ], 'Billing Policy', readonly=False, states={'confirmed': [('readonly', True)]},
                                help="Gives the state of the Waybill. \n -The exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception). \nThe 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to run on the date 'Ordered Date'.", select=True),

        'waybill_type'      : fields.function(_get_waybill_type, method=True, type='selection', selection=[('self', 'Self'), ('outsourced', 'Outsourced')], 
                                        string='Waybill Type', store=True, help=" - Self: Travel with our own units. \n - Outsourced: Travel without our own units."),

        'date_order'        : fields.date('Date', required=True, select=True,readonly=False, states={'confirmed': [('readonly', True)]}),
        'user_id'           : fields.many2one('res.users', 'Salesman', select=True, readonly=False, states={'confirmed': [('readonly', True)]}),

        'partner_id'        : fields.many2one('res.partner', 'Customer', required=True, change_default=True, select=True, readonly=False, states={'confirmed': [('readonly', True)]}),
        'currency_id'       : fields.many2one('res.currency', 'Currency', required=True, states={'confirmed': [('readonly', True)]}),
        'partner_invoice_id': fields.many2one('res.partner', 'Invoice Address', required=True, help="Invoice address for current Waybill.", readonly=False, states={'confirmed': [('readonly', True)]}),
        'partner_order_id'  : fields.many2one('res.partner', 'Ordering Contact', required=True,  help="The name and address of the contact who requested the order or quotation.", readonly=False, states={'confirmed': [('readonly', True)]}),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic Account',  help="The analytic account related to a Waybill.", readonly=False, states={'confirmed': [('readonly', True)]}),
        'departure_address_id': fields.many2one('res.partner', 'Departure Address', required=True, help="Departure address for current Waybill.", readonly=False, states={'confirmed': [('readonly', True)]}),



        'arrival_address_id': fields.many2one('res.partner', 'Arrival Address', required=True, help="Arrival address for current Waybill.", readonly=False, states={'confirmed': [('readonly', True)]}),


        'upload_point'     : fields.char('Upload Point', size=128, readonly=False, states={'confirmed': [('readonly', True)]}),
        'download_point'   : fields.char('Download Point', size=128, required=False, readonly=False, states={'confirmed': [('readonly', True)]}),
        'shipped'          : fields.boolean('Delivered', readonly=True, help="It indicates that the Waybill has been delivered. This field is updated only after the scheduler(s) have been launched."),

        'invoice_id'       : fields.many2one('account.invoice','Invoice Record', readonly=True),
        'invoiced'         : fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi=True,
                                             store={'tms.waybill': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                    'account.invoice': (_get_invoice, ['state'], 20)
                                                   },
                                             ),
        'invoice_paid'     : fields.function(_invoiced, method=True, string='Paid', type='boolean', multi=True,
                                              store={'tms.waybill': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                    'account.invoice': (_get_invoice, ['state'], 20)
                                                    }
                                             ),
        'invoice_name'     : fields.function(_invoiced, method=True, string='Invoice', type='char', size=64, multi=True,
                                             store={'tms.waybill': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                    'account.invoice': (_get_invoice, ['state'], 20)
                                                   }
                                            ),

        'supplier_invoice_id': fields.many2one('account.invoice','Supplier Invoice Rec', readonly=True),
        'supplier_invoiced':     fields.function(_supplier_invoiced, method=True, string='Supplier Invoiced', type='boolean', multi=True,
                                                store={'tms.waybill': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                       'account.invoice': (_get_supplier_invoice, ['state'], 20)
                                                    }
                                                ),
        'supplier_invoice_paid': fields.function(_supplier_invoiced, method=True, string='Supplier Invoice Paid', type='boolean', multi='invoiced', 
                                                 store={'tms.waybill': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                        'account.invoice': (_get_supplier_invoice, ['state'], 20)
                                                       }
                                                ),
        'supplier_invoice_name': fields.function(_supplier_invoiced, method=True, string='Supplier Invoice', type='char', size=64, multi='invoiced', 
                                                 store={'tms.waybill': (lambda self, cr, uid, ids, c={}: ids, None, 10),
                                                        'account.invoice': (_get_supplier_invoice, ['state'], 20)
                                                       }
                                                ),
        'supplier_invoiced_by' : fields.many2one('res.users', 'Suppl. Invoiced by', readonly=True),
        'supplier_invoiced_date' : fields.datetime('Suppl. Inv. Date', readonly=True, select=True),

        'waybill_line'     : fields.one2many('tms.waybill.line', 'waybill_id', 'Waybill Lines', readonly=False, states={'confirmed': [('readonly', True)]}),
        'waybill_shipped_product': fields.one2many('tms.waybill.shipped_product', 'waybill_id', 'Shipped Products', readonly=False, states={'confirmed': [('readonly', True)]}),
        'product_qty'      : fields.function(_shipped_product, method=True, string='Sum Qty', type='float', digits=(20, 6),  store=True, multi='product_qty'),
        'product_volume'   : fields.function(_shipped_product, method=True, string='Sum Volume', type='float', digits=(20, 6),  store=True, multi='product_qty'),
        'product_weight'   : fields.function(_shipped_product, method=True, string='Sum Weight', type='float', digits=(20, 6),  store=True, multi='product_qty'),
        'product_uom_type' : fields.function(_shipped_product, method=True, string='Product UoM Type', type='char', size=64, store=True, multi='product_qty'),

        'waybill_extradata': fields.one2many('tms.waybill.extradata', 'waybill_id', 'Extra Data Fields', readonly=False, states={'confirmed': [('readonly', True)]}),


        'amount_freight'   : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Freight', type='float', store=False, multi=True),
        'amount_move'      : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Moves', type='float', store=False, multi=True),
        'amount_highway_tolls': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Highway Tolls', type='float', store=False, multi=True),
        'amount_insurance' : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Insurance', type='float', store=False, multi=True),
        'amount_other'     : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Other', type='float', store=False, multi=True),
        'amount_untaxed'   : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='SubTotal', type='float', store=False, multi=True),
        'amount_tax'       : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes', type='float', store=False, multi=True),
        'amount_total'     : fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total', type='float', store=False, multi=True),

        'distance_route'   : fields.function(_get_route_distance, string='Distance from route', method=True, type='float', digits=(18,6), help="Route Distance.", multi=False),
        'distance_real'    : fields.float('Distance Real', digits=(18,6), help="Route obtained by electronic reading"),
       
        'create_uid'       : fields.many2one('res.users', 'Created by', readonly=True),
        'create_date'      : fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by'     : fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled'   : fields.datetime('Date Cancelled', readonly=True),
        'approved_by'      : fields.many2one('res.users', 'Approved by', readonly=True),
        'date_approved'    : fields.datetime('Date Approved', readonly=True),
        'confirmed_by'     : fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed'   : fields.datetime('Date Confirmed', readonly=True),
        'drafted_by'       : fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted'     : fields.datetime('Date Drafted', readonly=True),

        'notes'            : fields.text('Notes', readonly=False),
        
        'payment_term'     : fields.many2one('account.payment.term', 'Payment Term', readonly=False, states={'confirmed': [('readonly', True)]}),
        'fiscal_position'  : fields.many2one('account.fiscal.position', 'Fiscal Position', readonly=False, states={'confirmed': [('readonly', True)]}),
        'company_id'       : fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),


        'date_start'       : fields.datetime('Load Date Sched', required=False, help="Date Start time for Load"),
        'date_up_start_sched': fields.datetime('UpLd Start Sched', required=False),
        'date_up_end_sched': fields.datetime('UpLd End Sched', required=False),
        'date_up_docs_sched': fields.datetime('UpLd Docs Sched', required=False),
        'date_appoint_down_sched': fields.datetime('Download Date Sched', required=False),
        'date_down_start_sched': fields.datetime('Download Start Sched', required=False),
        'date_down_end_sched': fields.datetime('Download End Sched', required=False),
        'date_down_docs_sched': fields.datetime('Download Docs Sched', required=False),
        'date_end'         : fields.datetime('Travel End Sched', required=False, help="Date End time for Load"),        

        'date_start_real'  : fields.datetime('Load Date Real', required=False),
        'date_up_start_real': fields.datetime('UpLoad Start Real', required=False),
        'date_up_end_real' : fields.datetime('UpLoad End Real', required=False),
        'date_up_docs_real': fields.datetime('Load Docs Real', required=False),
        'date_appoint_down_real': fields.datetime('Download Date Real', required=False),
        'date_down_start_real': fields.datetime('Download Start Real', required=False),
        'date_down_end_real': fields.datetime('Download End Real', required=False),
        'date_down_docs_real': fields.datetime('Download Docs Real', required=False),
        'date_end_real'    : fields.datetime('Travel End Real', required=False),



        
#        'time_from_appointment_to_uploading_std': fields.float('Std Time from Appointment to Loading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_for_uploading_std': fields.float('Std Time for loading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_from_uploading_to_docs_sched': fields.float('Std Time from Load to Document Release (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_travel_sched': fields.float('Std Time for Travel (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_from_appointment_to_downloading_std': fields.float('Std Time from Download Appointment to Downloading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_for_downloading_sched': fields.float('Std Time for downloading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_from_downloading_to_docs_sched': fields.float('Std Time for Download Document Release (Hrs)', digits=(10, 2), required=True, readonly=False),                                                                                                        

        
#        'payment_type': fields.selection([
#                                          ('quantity','Charge by Quantity'), 
#                                          ('tons','Charge by Tons'), 
#                                          ('distance','Charge by Distance (mi./kms)'), 
#                                          ('travel','Charge by Travel'), 
#                                          ('volume', 'Charge by Volume'),
#                                          ], 'Charge Type',required=True,),
#        'payment_factor': fields.float('Factor', digits=(16, 4), required=True),
#      
        'amount_declared' : fields.float('Amount Declared', digits_compute= dp.get_precision('Sale Price'), help=" Load value amount declared for insurance purposes..."),
        'replaced_waybill_id' : fields.many2one('tms.waybill', 'Replaced Waybill', readonly=True),
        'move_id'       : fields.many2one('account.move', 'Account Move', required=False, readonly=True),

    }
    _defaults = {
        'date_order'            : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'date_start'            : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_up_start_sched'   : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_up_end_sched'     : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_up_docs_sched'    : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_appoint_down_sched': lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_down_start_sched' : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_down_end_sched'   : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_down_docs_sched'  : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_end'              : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'currency_id'           : lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'billing_policy'        : 'manual',
        'state'                 : lambda *a: 'draft',
        'waybill_type'          : 'self',
        'user_id'               : lambda obj, cr, uid, context: uid,
        'partner_invoice_id'    : lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['invoice'])['invoice'],
        'partner_order_id'      : lambda self, cr, uid, context: context.get('partner_id', False) and  self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['contact'])['contact'],
        'departure_address_id'  : lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['delivery'])['delivery'],
        'arrival_address_id'    : lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['delivery'])['delivery'],
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Waybill must be unique !'),
    ]

    _order = 'name desc'


    def get_freight_from_factors(self, cr, uid, ids, context=None):
        prod_obj = self.pool.get('product.product')
        

        factor = self.pool.get('tms.factor')
        line_obj = self.pool.get('tms.waybill.line')
        fpos_obj = self.pool.get('account.fiscal.position')
        for waybill in self.browse(cr, uid, ids):
            prod_id = prod_obj.search(cr, uid, [('tms_category', '=', 'freight'),('tms_default_freight' if waybill.waybill_type =='self' else 'tms_default_supplier_freight','=', 1),('active','=', 1)], limit=1)
            if not prod_id:
                raise osv.except_osv(_('Missing configuration !'), _('There is no product defined as Default Freight !!!'))
            product = prod_obj.browse(cr, uid, prod_id,	 context=None)

            for line in waybill.waybill_line:
                if line.control:
                    line_obj.unlink(cr, uid, [line.id])
            result = factor.calculate(cr, uid, 'waybill', ids, 'client', False)

            #print result

            fpos = waybill.partner_id.property_account_position.id or False
            #print "fpos: ", fpos
            fpos = fpos and fpos_obj.browse(cr, uid, fpos, context=context) or False
            #print "fpos: ", fpos
            #print "product[0].taxes_id: ", product[0].taxes_id
            #print "fpos_obj.map_tax: ", (6, 0, [_x for _x in fpos_obj.map_tax(cr, uid, fpos, product[0].taxes_id)]),
            
            xline = {
                    'waybill_id'        : waybill.id,
                    'line_type'         : 'product',
                    'name'              : product[0].name,
                    'sequence'          : 1,
                    'product_id'        : product[0].id,
                    'product_uom'       : product[0].uom_id.id,
                    'product_uom_qty'   : 1,
                    'price_unit'        : result,
                    'discount'          : 0.0,
                    'control'           : True,
                    'tax_id'            : [(6, 0, [_w for _w in fpos_obj.map_tax(cr, uid, fpos, product[0].taxes_id)])],
                }
            #print xline
            line_obj.create(cr, uid, xline)
        return True
        

    def write(self, cr, uid, ids, vals, context=None):
        super(tms_waybill, self).write(cr, uid, ids, vals, context=context)        
        if 'state' in vals and vals['state'] not in ('confirmed', 'cancel') or self.browse(cr, uid, ids)[0].state in ('draft', 'approved')  :
            self.get_freight_from_factors(cr, uid, ids, context=context)
        self.pool.get('tms.waybill.taxes').compute(cr, uid, waybill_ids=ids)
        return True

    def create(self, cr, uid, vals, context=None):
        res = super(tms_waybill, self).create(cr, uid, vals, context=context)
        self.get_freight_from_factors(cr, uid, [res], context=context)
        self.pool.get('tms.waybill.taxes').compute(cr, uid, waybill_ids=[res])
        return res


    def onchange_sequence_id(self, cr, uid, ids, sequence_id):
        if not sequence_id:
            return {'value': {'billing_policy': 'manual', 
                        }}
        result = self.pool.get('ir.sequence').browse(cr, uid, [sequence_id])[0].tms_waybill_automatic
        return {'value': {'billing_policy': 'automatic' if result else 'manual', 
                        }}


    def onchange_travel_ids(self, cr, uid, ids, travel_ids):
        if not travel_ids or not len(travel_ids[0][2]):
            return {'value': {  'waybill_type'  : 'own',
                                'unit_id'       : False,
                                'trailer1_id'   : False,
                                'dolly_id'      : False,
                                'trailer2_id'   : False,
                                'employee_id'   : False,
                                'route_id'      : False,
                                'departure_id'  : False,
                                'arrival_id'    : False,
                                'travel_id'     : False,
                             }
                    }
        travel_id = False
        for rec in travel_ids:
            travel_id = rec[2][len(rec[2])-1] or False

        for travel in self.pool.get('tms.travel').browse(cr, uid, [travel_id]):
            return {'value': {  'waybill_type'  : 'outsourced' if (travel.unit_id.supplier_unit) else 'own',
                                'unit_id'       : travel.unit_id.id,
                                'trailer1_id'   : travel.trailer1_id.id,
                                'dolly_id'      : travel.dolly_id.id,
                                'trailer2_id'   : travel.trailer2_id.id,
                                'employee_id'   : travel.employee_id.id,
                                'route_id'      : travel.route_id.id,
                                'departure_id'  : travel.route_id.departure_id.id,
                                'arrival_id'    : travel.route_id.arrival_id.id,
                                'travel_id'     : travel_id,
                                'operation_id'  : travel.operation_id.id,                                
                             }
                    }
        return {'value': {'travel_id': travel_id}}


    def onchange_partner_id(self, cr, uid, ids, partner_id):
        if not partner_id:
            return {'value': {'partner_invoice_id': False, 
                              'partner_order_id': False, 
                              'payment_term': False, 
                              'user_id': False}
                    }
                    
        addr = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['invoice', 'contact', 'default', 'delivery'])
        part = self.pool.get('res.partner').browse(cr, uid, partner_id)
        payment_term = part.property_payment_term and part.property_payment_term.id or False
        dedicated_salesman = part.user_id and part.user_id.id or uid
        val = {
            'partner_invoice_id': addr['invoice'] if addr['invoice'] else addr['default'],
            'partner_order_id': addr['contact'] if addr['contact'] else addr['default'],
            'payment_term': payment_term,
            'user_id': dedicated_salesman,
        }
        return {'value': val}


    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
                        'name'			: False, 
                        'state'			: 'draft',
                        'invoice_id'	: False, 
                        'cancelled_by'  : False,
                        'date_cancelled': False,
                        'approved_by'   : False,
                        'date_approved' : False,
                        'confirmed_by'  : False,
                        'date_confirmed': False,
                        'drafted_by'    : False,
                        'date_drafted'  : False,
                        'replaced_waybill_id': False,
                        'move_id': False,
                        'user_id': uid,
						})

        return super(tms_waybill, self).copy(cr, uid, id, default, context)


    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False

        for waybill in self.browse(cr, uid, ids):
            if (waybill.travel_id.id) and waybill.travel_id.state in ('cancel'):
                raise osv.except_osv(
                        _('Could not set to draft this Waybill !'),
                        _('Travel is Cancelled !!!'))
            else:
                self.write(cr, uid, ids, {'state':'draft', 'drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True
    
    def action_approve(self, cr, uid, ids, context=None):
        #print "action_approve"
        for waybill in self.browse(cr, uid, ids, context=context):            
            if waybill.state in ('draft'):                
                if not waybill.sequence_id.id:
                    raise osv.except_osv('Could not Approve Waybill !', 'You have not selected a valid Waybill Sequence')
                elif not waybill.name:
                    seq_id = waybill.sequence_id.id
                    seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
                else:
                    seq_number = waybill.name

                self.write(cr, uid, ids, {'name':seq_number, 'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        #print "action_confirm"
        # *******************
        move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')
        account_jrnl_obj=self.pool.get('account.journal')
        cur_obj = self.pool.get('res.currency')        
        for waybill in self.browse(cr, uid, ids, context=None):
            company_currency = self.pool['res.company'].browse(cr, uid, waybill.company_id.id).currency_id.id
            if waybill.amount_untaxed <= 0.0:
                raise osv.except_osv(_('Could not confirm Waybill !'),_('Total Amount must be greater than zero.'))
            elif not waybill.travel_id.id:
                raise osv.except_osv(_('Could not confirm Waybill !'),_('Waybill must be assigned to a Travel before confirming.'))
            elif waybill.billing_policy == 'automatic':
                #print "Entrando para generar la factura en automatico..."
                wb_invoice = self.pool.get('tms.waybill.invoice')
                wb_invoice.makeWaybillInvoices(cr, uid, ids, context=None)
            
            
            period_id = period_obj.search(cr, uid, [('date_start', '<=', waybill.date_order),('date_stop','>=', waybill.date_order), ('state','=','draft')], context=None)
            
            if not period_id:
                raise osv.except_osv(_('Warning !'),
                        _('There is no valid account period for this date %s. Period does not exists or is already closed') % \
                                (waybill.date_order,))
            
            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'general'),('tms_waybill_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 'You have not defined Waybill Journal...')
            journal_id = journal_id and journal_id[0]
            
            
            move_lines = []
            
            precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
            notes = _("Waybill: %s\nTravel: %s\nDriver: (ID %s) %s\nVehicle: %s") % (waybill.name, waybill.travel_id.name, waybill.travel_id.employee_id.id, waybill.travel_id.employee_id.name, waybill.travel_id.unit_id.name)
            # #print "notes: ", notes
            
            for waybill_line in waybill.waybill_line:
                if not waybill_line.line_type == "product":
                    continue
                tms_prod_income_account = waybill_line.product_id.tms_property_account_income.id if waybill_line.product_id.tms_property_account_income.id else waybill_line.product_id.categ_id.tms_property_account_income_categ.id if waybill_line.product_id.categ_id.tms_property_account_income_categ.id else False
                prod_income_account     = waybill_line.product_id.property_account_income.id if waybill_line.product_id.property_account_income.id else waybill_line.product_id.categ_id.property_account_income_categ.id if waybill_line.product_id.categ_id.property_account_income_categ.id else False

                
                if not (tms_prod_income_account & prod_income_account):
                    raise osv.except_osv('Error !',
                                 _('You have not defined Income Account for product %s') % (waybill_line.product_id.name))
                xsubtotal = cur_obj.compute(cr, uid, waybill.currency_id.id, company_currency, waybill_line.price_subtotal, context={'date': waybill.date_order})
                move_line = (0,0, {
                                'name'          : _('Waybill: %s - Product: %s') % (waybill.name, waybill_line.name),
                                'account_id'    : tms_prod_income_account,
                                'debit'         : 0.0,
                                'credit'        : round(xsubtotal, precision),
                                'journal_id'    : journal_id,
                                'period_id'     : period_id[0],
                                'product_id'    : waybill_line.product_id.id,
                                'sale_shop_id'  : waybill.travel_id.shop_id.id,
                                'vehicle_id'    : waybill.travel_id.unit_id.id,
                                'employee_id'   : waybill.travel_id.employee_id.id,
                                'currency_id'   : waybill.currency_id.id != company_currency and waybill.currency_id.id or False,
                                'amount_currency': waybill.currency_id.id != company_currency and (waybill_line.price_subtotal * -1.0) or False,
                                })
                move_lines.append(move_line)
            
                move_line = (0,0, {
                                'name'          : _('Waybill: %s - Product: %s') % (waybill.name, waybill_line.name),
                                'account_id'    : prod_income_account,
                                'debit'         : round(xsubtotal, precision),
                                'credit'        : 0.0,
                                'journal_id'    : journal_id,
                                'period_id'     : period_id[0],
                                'sale_shop_id'  : waybill.travel_id.shop_id.id,
                                'vehicle_id'    : waybill.travel_id.unit_id.id,
                                'employee_id'   : waybill.travel_id.employee_id.id,
                                'currency_id'   : waybill.currency_id.id != company_currency and waybill.currency_id.id or False,
                                'amount_currency': waybill.currency_id.id != company_currency and waybill_line.price_subtotal or False,                        
                                })
                move_lines.append(move_line)

            move = {
                    'ref'        : _('Waybill: %s') % (waybill.name),
                    'journal_id' : journal_id,
                    'narration'  : notes,
                    'line_id'    : [x for x in move_lines],
                    'date'       : waybill.date_order,
                    'period_id'  : period_id[0],
                    }
                    
            move_id = move_obj.create(cr, uid, move)
            if move_id:
                move_obj.button_validate(cr, uid, [move_id])                            

            
            self.write(cr, uid, ids, {'move_id': move_id, 'state':'confirmed', 'confirmed_by' : uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def button_dummy(self, cr, uid, ids, context=None):
        return True


#    def copy(self, cr, uid, id, default=None, context=None):
#        if not default:
#            default = {}
#        default.update({
#                        'name'			: False, 
#                        'state'			: 'draft',
#                        'invoice_id'	: False, 
#                        'cancelled_by'  : False,
#                        'date_cancelled': False,
#                        'approved_by'   : False,
#                        'date_approved' : False,
#                        'confirmed_by'  : False,
#                        'date_confirmed': False,
#                        'drafted_by'    : False,
#                        'date_drafted'  : False,
#						})
#        #print default
#        #print id
#        return super(tms_waybill, self).copy(cr, uid, id, default, context=context)



tms_waybill()


# Adding relation between Waybills and Travels
class tms_travel(osv.osv):
    _inherit="tms.travel"

    _columns = {
        'waybill_ids': fields.many2many('tms.waybill', 'tms_waybill_travel_rel', 'travel_id', 'waybill_id', 'Waybills'),
        'default_waybill_id': fields.one2many('tms.waybill', 'travel_id', 'Waybill', readonly=True),
        'partner_id' : fields.related('default_waybill_id', 'partner_id', type='many2one', relation='res.partner', string='Customer', store=True),
        'arrival_address_id' : fields.related('default_waybill_id', 'arrival_address_id', type='many2one', relation='res.partner', string='Arrival Address', store=True),
    }

tms_travel()


# Class for Waybill Lines
class tms_waybill_line(osv.osv):
    _name = 'tms.waybill.line'
    _description = 'Waybill Line'


    def _amount_line(self, cr, uid, ids, field_name, args, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax_obj.compute_all(cr, uid, line.tax_id, price, line.product_uom_qty, line.product_id, line.waybill_id.partner_id)
            cur = line.waybill_id.currency_id

            amount_with_taxes = cur_obj.round(cr, uid, cur, taxes['total_included'])
            amount_tax = cur_obj.round(cr, uid, cur, taxes['total_included']) - cur_obj.round(cr, uid, cur, taxes['total'])
            
            price_subtotal = line.price_unit * line.product_uom_qty
            price_discount = price_subtotal * (line.discount or 0.0) / 100.0
            res[line.id] =  {   'price_total'   : amount_with_taxes,
                                'price_amount': price_subtotal,
                                'price_discount': price_discount,
                                'price_subtotal': (price_subtotal - price_discount),
                                'tax_amount'    : amount_tax,
                                }
        return res



    _columns = {
#        'agreement_id': fields.many2one('tms.agreement', 'Agreement', required=False, ondelete='cascade', select=True, readonly=True),
        'waybill_id': fields.many2one('tms.waybill', 'Waybill', required=False, ondelete='cascade', select=True, readonly=True),
        'line_type': fields.selection([
            ('product', 'Product'),
            ('note', 'Note'),
            ], 'Line Type', require=True),

        'name': fields.char('Description', size=256, required=True),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
        'product_id': fields.many2one('product.product', 'Product', 
                            domain=[('sale_ok', '=', True),
                                    ('tms_category', 'in',('freight','move','insurance','highway_tolls','other')),
                                    ], change_default=True, ondelete='restrict'),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Sale Price')),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_amount': fields.function(_amount_line, method=True, string='Price Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_discount': fields.function(_amount_line, method=True, string='Discount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_total'   : fields.function(_amount_line, method=True, string='Total Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_amount'   : fields.function(_amount_line, method=True, string='Tax Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_id'            : fields.many2many('account.tax', 'waybill_tax', 'waybill_line_id', 'tax_id', 'Taxes'),
        'product_uom_qty': fields.float('Quantity (UoM)', digits=(16, 4)),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure '),
        'discount': fields.float('Discount (%)', digits=(16, 2), help="Please use 99.99 format..."),
        'notes': fields.text('Notes'),
        'waybill_partner_id': fields.related('waybill_id', 'partner_id', type='many2one', relation='res.partner', store=True, string='Customer'),
        'salesman_id':fields.related('waybill_id', 'user_id', type='many2one', relation='res.users', store=True, string='Salesman'),
        'company_id': fields.related('waybill_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'control': fields.boolean('Control'),
    }
    _order = 'sequence, id desc'

    _defaults = {
        'line_type': 'product',
        'discount': 0.0,
        'product_uom_qty': 1,
        'sequence': 10,
        'price_unit': 0.0,
    }




    def on_change_product_id(self, cr, uid, ids, product_id, partner_id, context=None):
        res = {}
        if not product_id:
            return {}
        context = context or {}
        lang = context.get('lang',False)
        if not  partner_id:
            raise osv.except_osv(_('No Customer Defined !'), _('Before choosing a product,\n select a customer in the form.'))
        partner_obj = self.pool.get('res.partner')
        if partner_id:
            lang = partner_obj.browse(cr, uid, partner_id).lang
        context_partner = {'lang': lang, 'partner_id': partner_id}

        fpos = partner_obj.browse(cr, uid, partner_id).property_account_position.id or False

        prod_obj = self.pool.get('product.product')
        fpos_obj = self.pool.get('account.fiscal.position')
        fpos = fpos and fpos_obj.browse(cr, uid, fpos, context=context) or False
        product_obj = prod_obj.browse(cr, uid, product_id, context=context_partner)
        taxes = product_obj.taxes_id
        res = {'value': {'product_uom' : product_obj.uom_id.id,
                         'name': product_obj.name,
                         'tax_id': fpos_obj.map_tax(cr, uid, fpos, taxes),
                        }
            }
        return res

    def on_change_amount(self, cr, uid, ids, product_uom_qty, price_unit, discount, product_id, partner_id, context=None):
        res = {'value': {
                    'price_amount': 0.0, 
                    'price_subtotal': 0.0, 
                    'price_discount': 0.0, 
                    'price_total': 0.0,
                    'tax_amount': 0.0, 
                        }
                }
        if not (product_uom_qty and price_unit and product_id ):
            return res
        fpos = self.pool.get('res.partner').browse(cr, uid, [partner_id])[0].property_account_position.id or False
        fpos_obj = self.pool.get('account.fiscal.position')
        tax_obj = self.pool.get('account.tax')
        fpos = fpos and fpos_obj.browse(cr, uid, fpos, context=context) or False
        prod_obj = self.pool.get('product.product')
        tax_factor = 0.00
        for line in tax_obj.browse(cr, uid, fpos_obj.map_tax(cr, uid, fpos, prod_obj.browse(cr, uid, [product_id], context=None)[0].taxes_id)):
            #print line
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
#        if tax_factor == 0.00:
#            raise osv.except_osv(_('No taxes defined in product !'), _('You have to add taxes for this product. Para Mexico: Tiene que agregar el IVA que corresponda y el IEPS con factor 0.0.'))        

        price_amount = price_unit * product_uom_qty
        price_discount = (price_unit * product_uom_qty) * (discount/100.0)
        res = {'value': {
                    'price_amount': price_amount, 
                    'price_discount': price_discount, 
                    'price_subtotal': (price_amount - price_discount), 
                    'tax_amount': (price_amount - price_discount) * tax_factor, 
                    'price_total': (price_amount - price_discount) * (1.0 + tax_factor),
                        }
                }
        return res

tms_waybill_line()

# Class for Waybill Shipped Products
class tms_waybill_shipped_product(osv.osv):
    _name = 'tms.waybill.shipped_product'
    _description = 'Waybill Shipped Product'


    _columns = {
#        'agreement_id': fields.many2one('tms.agreement', 'Agreement', required=False, ondelete='cascade', select=True, readonly=True),
        'waybill_id': fields.many2one('tms.waybill', 'waybill', required=False, ondelete='cascade', select=True, readonly=True),
        'name': fields.char('Description', size=256, required=True, select=True),
        'product_id': fields.many2one('product.product', 'Product', 
                            domain=[
                                    ('tms_category', '=','transportable'), 
                                    ('tms_category', '=','move'), 
                                    ('tms_category', '=','insurance'), 
                                    ('tms_category', '=','highway_tolls'), 
                                    ('tms_category', '=','other'),
                                    ], change_default=True, required=True),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ', required=True),
        'product_uom_qty': fields.float('Quantity (UoM)', digits=(16, 4), required=True),
        'notes': fields.text('Notes'),
        'waybill_partner_id': fields.related('waybill_id', 'partner_id', type='many2one', relation='res.partner', store=True, string='Customer'),
        'salesman_id':fields.related('waybill_id', 'user_id', type='many2one', relation='res.users', store=True, string='Salesman'),
        'shop_id': fields.related('waybill_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'company_id': fields.related('waybill_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
    }
    _order = 'sequence, id desc'
    _defaults = {
        'product_uom_qty': 1,
        'sequence': 10,
    }

    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        for product in prod_obj.browse(cr, uid, [product_id], context=None):            
            res = {'value': {'product_uom' : product.uom_id.id,
                             'name': product.name}
                }
        return res



tms_waybill_shipped_product()


# Extra data fields for Waybills & Negotiations
class tms_waybill_extradata(osv.osv):
    _name = "tms.waybill.extradata"
    _description = "Tms Waybill Extra Data"

    _columns = {        
        'name': fields.char('Name', size=30, required=True),
        'notes': fields.text('Notes'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying this list of categories."),
        'mandatory': fields.boolean('Mandatory'),
        'type_extra': fields.selection([
            ('char', 'String (250)'),
            ('text', 'Text'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('date', 'Date'),
            ('datetime', 'Datetime')
            ], 'Data Type', help="Useful to set wich field is used for extra data field", select=True),

        'value_char'    : fields.char('Value', size=250),
        'value_text'    : fields.text('Value'),
        'value_integer' : fields.integer('Value'),
        'value_float'   : fields.float('Value',digits=(16, 4)),
        'value_date'    : fields.date('Value'),
        'value_datetime': fields.datetime('Value'),
        'value_extra'   : fields.text('Value'),

        'waybill_id': fields.many2one('tms.waybill', 'Waybill', required=False, ondelete='cascade'), #, select=True, readonly=True),
#        'agreement_id': fields.many2one('tms.agreement', 'Agreement', required=False, ondelete='cascade', select=True, readonly=True),
        
    }

    _defaults = {
#        'mandatory': True, 
        'sequence':10,
    }


    _order = "sequence"


    def on_change_value(self, cr, uid, ids, type_extra, value):
        if not type_extra and not value:
            return {}
        if type_extra == 'char' or type_extra == 'text':
            return {'value': {'value_extra' : value}}
        elif type_extra == 'integer' or type_extra=='float':
            return {'value': {'value_extra' : str(value)}}
        elif type_extra == 'date':
            xdate = filter(None, map(lambda x:int(x), value.split('-'))) 
            return {'value': {'value_extra' : date(xdate[0], xdate[1], xdate[2]).strftime(DEFAULT_SERVER_DATE_FORMAT)}}                
        elif type_extra == 'datetime':
            #print "value: ", value            
            xvalue = value.split(' ')
            xdate = filter(None, map(lambda x:int(x), xvalue[0].split('-'))) 
            xtime = map(lambda x:int(x), xvalue[1].split(':')) 

            tzone = timezone(self.pool.get('res.users').browse(cr, uid, uid).tz)
            value = tzone.localize(datetime(xdate[0], xdate[1], xdate[2], xtime[0], xtime[1], xtime[2]))

            #print value
            xvalue = value.split(' ')
            xdate = filter(None, map(lambda x:int(x), xvalue[0].split('-'))) 
            xtime = map(lambda x:int(x), xvalue[1].split(':')) 
            return {'value': {'value_extra' : datetime(xdate[0], xdate[1], xdate[2], xtime[0], xtime[1], xtime[2]).strftime( DEFAULT_SERVER_DATETIME_FORMAT)}}                
        return False


    
tms_waybill_extradata()


# Wizard que permite hacer una copia de la carta porte al momento de cancelarla
class tms_waybill_cancel(osv.osv_memory):

    """ To create a copy of Waybill when cancelled"""

    _name = 'tms.waybill.cancel'
    _description = 'Make a copy of Cancelled Waybill'

    _columns = {
            'company_id'    : fields.many2one('res.company', 'Company'),
            'copy_waybill'  : fields.boolean('Create copy of this waybill?', required=False),
            'sequence_id'   : fields.many2one('ir.sequence', 'Sequence', required=False),
            'date_order'    : fields.date('Date', required=False),
        }

    _defaults = {'date_order'   : fields.date.context_today,
                 'company_id'   :  lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid).company_id.id
                 }

    def make_copy(self, cr, uid, ids, context=None):

        """
             To copy Waybills when cancelling them
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        record_id =  context.get('active_ids',[])

        #print record_id

        if record_id:
            #print "Si entra..."
            for record in self.browse(cr,uid, ids):
                #print record.company_id.name
                #print record.date_order
                waybill_obj = self.pool.get('tms.waybill')
                for waybill in waybill_obj.browse(cr, uid, record_id):
                    #print waybill.name
                    if waybill.invoiced and waybill.invoice_paid:
                        raise osv.except_osv(
                                _('Could not cancel Waybill !'),
                                _('This Waybill\'s Invoice is already paid'))
                        return False
                    elif waybill.invoiced and waybill.invoice_id and waybill.invoice_id.id and waybill.invoice_id.state != 'cancel' and waybill.billing_policy=='manual':
                        raise osv.except_osv(
                                _('Could not cancel Waybill !'),
                                _('This Waybill is already Invoiced'))
                        return False
                    elif waybill.waybill_type=='outsourced' and waybill.supplier_invoiced and waybill.supplier_invoice_paid:
                        raise osv.except_osv(
                                _('Could not cancel Waybill !'),
                                _('This Waybill\'s Supplier Invoice is already paid'))
                        return False

                    elif waybill.billing_policy=='automatic' and waybill.invoiced and not waybill.invoice_paid:
                        wf_service = netsvc.LocalService("workflow")
                        wf_service.trg_validate(uid, 'account.invoice', waybill.invoice_id.id, 'invoice_cancel', cr)
                        invoice_obj=self.pool.get('account.invoice')
                        invoice_obj.unlink(cr, uid, [waybill.invoice_id.id], context=None)
        #            elif waybill.state in ('draft','approved','confirmed') and waybill.travel_id.state in ('closed'):
        #                raise osv.except_osv(
        #                        _('Could not cancel Advance !'),
        #                        _('This Waybill is already linked to Travel Expenses record'))
                    #print "record_id:", record_id
                    elif waybill.waybill_type=='outsourced' and waybill.supplier_invoiced:
                        raise osv.except_osv(
                            _('Could not cancel Waybill !'),
                            _('This Waybill\'s Supplier Invoice is already created. First, cancel Supplier Invoice and then try again'))
                        
                    if waybill.move_id.id:                
                        move_obj = self.pool.get('account.move')
                        if waybill.move_id.state != 'draft':
                            move_obj.button_cancel(cr, uid, [waybill.move_id.id]) 
                        move_obj.unlink(cr, uid, [waybill.move_id.id])
                    
                    waybill_obj.write(cr, uid, record_id, {'move_id' : False, 'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
          
                    if record.copy_waybill:                        
                        default ={} 
                        default.update({'replaced_waybill_id': waybill.id,'move_id':False })
                        if record.sequence_id.id:
                            default.update({'sequence_id': record.sequence_id.id })
                        if record.date_order:
                            default.update({'date_order': record.date_order })
                        waybill=waybill_obj.copy(cr, uid, record_id[0], default=default)
        return {'type': 'ir.actions.act_window_close'}

tms_waybill_cancel()


# Wizard que permite crear la factura de cliente de la(s) cartas porte(s) seleccionadas
class tms_waybill_invoice(osv.osv_memory):

    """ To create invoice for each Waybill"""

    _name = 'tms.waybill.invoice'
    _description = 'Make Invoices from Waybill'
    
    _columns = {'group_line_product'    : fields.boolean('Group Waybill Lines', help='Group Waybill Lines Quantity & Subtotal by Product'),
                }
    
    _defaults ={'group_line_product'    : True,
                }

    def makeWaybillInvoices(self, cr, uid, ids, context=None):

        """
             To get Waybills and create Invoices
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
        
        
        group_lines = self.browse(cr,uid, ids)[0].group_line_product
            
        if record_ids:
            res = False
            invoices = []
            shipped_grouped_obj = self.pool.get('tms.waybill.shipped_grouped')
            property_obj=self.pool.get('ir.property')
            partner_obj=self.pool.get('res.partner')
            user_obj=self.pool.get('res.users')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            invoice_line_obj=self.pool.get('account.invoice.line')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            waybill_obj=self.pool.get('tms.waybill')

            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'sale')], context=None)
            journal_id = journal_id and journal_id[0] or False

            cr.execute("select distinct partner_id, currency_id from tms_waybill where (invoice_id is null or (select account_invoice.state from account_invoice where account_invoice.id = tms_waybill.invoice_id)='cancel') and (state='confirmed' or (state='approved' and billing_policy='automatic')) and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv(_('Warning !'),
                                     _('Not all selected records are Confirmed yet or already invoiced...'))            
            #print data_ids

            for data in data_ids:
                if not data[0]:
                    raise osv.except_osv(_('Warning !'),
                                     _('You have not defined Client account...'))            
                    
                partner = partner_obj.browse(cr,uid,data[0])
                cr.execute("select id from tms_waybill where (invoice_id is null or (select account_invoice.state from account_invoice where account_invoice.id = tms_waybill.invoice_id)='cancel') and (state='confirmed' or (state='approved' and billing_policy='automatic')) and partner_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                waybill_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                #print "waybill_ids : ", waybill_ids
                inv_lines = []
                notes = _("Waybills")
                inv_amount = 0.0
                empl_name = ''
                product_shipped_grouped = {}
                for waybill in waybill_obj.browse(cr,uid,waybill_ids):
                    fpos = waybill.partner_id.property_account_position.id or False
                    fpos = fpos and account_fiscal_obj.browse(cr, uid, fpos, context=context) or False

                    for shipped_prod in waybill.waybill_shipped_product:
                        # *****                            
                        val={'product_name' : shipped_prod.product_id.name,
                            'product_id'    : shipped_prod.product_id.id,
                            'product_uom'   : shipped_prod.product_uom.id,
                            'quantity'      : shipped_prod.product_uom_qty,
                            }
                        key = (val['product_id'], val['product_uom'], val['product_name'])
                        if not key in product_shipped_grouped:
                            product_shipped_grouped[key] = val
                        else:
                            product_shipped_grouped[key]['quantity'] += val['quantity']
                        # *****

                    currency_id = waybill.currency_id.id
                    for line in waybill.waybill_line:
                        if line.line_type=='product':
                            if line.product_id:
                                a = line.product_id.product_tmpl_id.property_account_income.id
                                if not a:
                                    a = line.product_id.categ_id.property_account_income_categ.id
                                if not a:
                                    a = property_obj.get(cr, uid,
                                        'property_account_income_categ', 'product.category',
                                        context=context).id
                                if not a:
                                    raise osv.except_osv(_('Error !'),
                                            _('There is no income account defined ' \
                                                    'for this product: "%s" (id:%d)') % \
                                                    (line.product_id.name, line.product_id.id,))

                                a = account_fiscal_obj.map_account(cr, uid, False, a)
                                
            
                                
                                inv_line = (0,0, {
                                    'name': line.name,
                                    'origin': line.waybill_id.name,
                                    'account_id': a,
                                    'price_unit': line.price_unit,
                                    'quantity': line.product_uom_qty,
                                    'uos_id': line.product_uom.id,
                                    'product_id': line.product_id.id,
                                    'invoice_line_tax_id': [(6, 0, [_w for _w in account_fiscal_obj.map_tax(cr, uid, fpos, line.product_id.taxes_id)])],
                                    'vehicle_id'    : line.waybill_id.travel_id.unit_id.id if line.waybill_id.travel_id else False,
                                    'employee_id'   : line.waybill_id.travel_id.employee_id.id if line.waybill_id.travel_id else False,
                                    'sale_shop_id'  : line.waybill_id.shop_id.id,
                                    'note': line.notes,
                                    #'account_analytic_id': False,
                                    })
                                inv_lines.append(inv_line)
                                
                        
                        notes += ', ' + line.waybill_id.name
                    # ***** 
                    #print "inv_lines: ", inv_lines
                    if group_lines:
                        #print "Si entra a agrupar lineas de Cartas Porte"
                        line_grouped = {}
                        for xline in inv_lines:
                            val={
                                    'name': xline[2]['name'],
                                    'origin': xline[2]['origin'],
                                    'account_id': xline[2]['account_id'],
                                    'price_unit': xline[2]['price_unit'],
                                    'quantity': xline[2]['quantity'],
                                    'uos_id': xline[2]['uos_id'],
                                    'product_id': xline[2]['product_id'],
                                    'invoice_line_tax_id': xline[2]['invoice_line_tax_id'],
                                    'note': xline[2]['note'],
                                    #'vehicle_id': xline[2]['vehicle_id'],
                                    #'employee_id': xline[2]['employee_id'],
                                    #'sale_shop_id': xline[2]['sale_shop_id'],
                                }
                            #print "val: ", val
                            key = (val['product_id'], val['uos_id'])#, val['vehicle_id'], val['employee_id'], val['sale_shop_id'])
                            #print "key: ", key
                            if not key in line_grouped:
                                line_grouped[key] = val
                            else:
                                line_grouped[key]['price_unit'] += val['price_unit']
                                        
                        #print "line_grouped: ", line_grouped
                        inv_lines = []
                        for t in line_grouped.values():
                            #print "t: ", t
                            vals = (0,0, {
                                    'name'          : t['name'],
                                    'origin'        : t['origin'],
                                    'account_id'    : t['account_id'],
                                    'price_unit'    : t['price_unit'],
                                    'quantity'      : t['quantity'],
                                    'uos_id'        : t['uos_id'],
                                    'product_id'    : t['product_id'],
                                    'invoice_line_tax_id': t['invoice_line_tax_id'],
                                    'note'          : t['note'],
                                    #'vehicle_id'    : t['vehicle_id'],
                                    #'employee_id'   : t['employee_id'],
                                    #'sale_shop_id'  : t['sale_shop_id'],
                                        }
                                    )
                            inv_lines.append(vals)
                        #print "inv_lines: ", inv_lines
                            
                # ******


                    # ****

                    departure_address_id = waybill.departure_address_id.id
                    arrival_address_id = waybill.arrival_address_id.id
                a = partner.property_account_receivable.id
                if partner and partner.property_payment_term.id:
                    pay_term = partner.property_payment_term.id
                else:
                    pay_term = False

                inv = {
                    'name'              : 'Factura',
                    'origin'            : 'Fact. de Cartas Porte',
                    'type'              : 'out_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : 'Fact. de Cartas Porte',
                    'account_id'        : a,
                    'partner_id'        : waybill.partner_id.id,
                    'departure_address_id' : departure_address_id,
                    'arrival_address_id'   : arrival_address_id,
                    'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'comment'           : 'Fact. de Cartas Porte',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : partner.property_account_position.id,
                    'pay_method_id'     : partner.pay_method_id.id,
                    'acc_payment'       : partner.bank_ids[0].id if partner.bank_ids and partner.bank_ids[0] else False,
                    'comment'           : notes,
                    'tms_type'          : 'invoice' if waybill.billing_policy == 'manual' else 'waybill'
                }

                inv_id = invoice_obj.create(cr, uid, inv)
                invoices.append(inv_id)
                # ******
                #print "product_shipped_grouped: ", product_shipped_grouped
                for t in product_shipped_grouped.values():
                    #print "t: ", t
                    vals = {
                            'invoice_id'  : inv_id,
                            'product_id'  : t['product_id'],
                            'product_uom' : t['product_uom'],
                            'quantity'    : t['quantity'],
                            }
                    res = shipped_grouped_obj.create(cr, uid, vals)
                # ******
                waybill_obj.write(cr,uid,waybill_ids, {'invoice_id': inv_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               

            ir_model_data = self.pool.get('ir.model.data')
            act_obj = self.pool.get('ir.actions.act_window')
            result = ir_model_data.get_object_reference(cr, uid, 'account', 'action_invoice_tree1')
            id = result and result[1] or False
            result = act_obj.read(cr, uid, [id], context=context)[0]
            result['domain'] = "[('id','in', [" + ','.join(map(str, invoices)) + "])]"
            return result
    
tms_waybill_invoice()


# Wizard que permite crear la factura de proveedor de la(s) cartas porte(s) seleccionadas
class tms_waybill_supplier_invoice(osv.osv_memory):

    """ To create Supplier invoice for each Waybill"""

    _name = 'tms.waybill.supplier_invoice'
    _description = 'Make Supplier Invoices from Waybill'

    def makeWaybillSupplierInvoices(self, cr, uid, ids, context=None):

        """
             To get Waybills and create Invoices
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
            factor = self.pool.get('tms.factor')
            property_obj=self.pool.get('ir.property')
            partner_obj=self.pool.get('res.partner')
            fpos_obj = self.pool.get('account.fiscal.position')
            prod_obj = self.pool.get('product.product')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            waybill_obj=self.pool.get('tms.waybill')
            travel_obj=self.pool.get('tms.travel')

            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'purchase'),('tms_supplier_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 _('You have not defined TMS Supplier Purchase Journal...'))
            journal_id = journal_id and journal_id[0]


            prod_id = prod_obj.search(cr, uid, [('tms_category', '=', 'freight'),('tms_default_supplier_freight','=', 1),('active','=', 1)], limit=1)
            if not prod_id:
                raise osv.except_osv(
                    _('Missing configuration !'),
                    _('There is no product defined as Freight !!!'))
            
            product = prod_obj.browse(cr, uid, prod_id,	 context=None)[0]
            
            #print "product.name : ", product.name
            prod_account = product.product_tmpl_id.property_account_expense.id
            if not prod_account:
                prod_account = product.categ_id.property_account_expense_categ.id
                if not prod_account:
                    raise osv.except_osv(_('Error !'),
                                         _('There is no expense account defined ' \
                                               'for this product: "%s" (id:%d)') % \
                                             (product.name, product.id,))
                    
            prod_account = fpos_obj.map_account(cr, uid, False, prod_account)
                
            cr.execute("select distinct supplier_id, currency_id from tms_waybill where waybill_type='outsourced' and supplier_invoice_id is null and (state='confirmed' or (state='approved' and billing_policy='automatic')) and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv(_('Warning !'),
                                     _('Not all selected records are Confirmed yet or already invoiced or selected records are not from Outsourced Freights...'))
            #print data_ids


            for data in data_ids:
                partner = partner_obj.browse(cr,uid,data[0])
 
                cr.execute("select id from tms_waybill where waybill_type='outsourced' and supplier_invoice_id is null and (state='confirmed' or (state='approved' and billing_policy='automatic')) and supplier_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                waybill_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                
                notes = "Cartas Porte"
                inv_amount = 0.0
                empl_name = ''

                inv_lines = []
                for waybill in waybill_obj.browse(cr,uid,waybill_ids):
                    currency_id = waybill.currency_id.id

                    inv_line = (0,0, {
                            'name': product.name  + ' - Viaje: ' + (waybill.travel_id.name or _('Sin Viaje')) + ' - ' + _('Waybill: ') + waybill.name,
                            'origin': waybill.name,
                            'account_id': prod_account,
                            'price_unit': waybill.supplier_amount,
                            'quantity': 1.0,
                            'uos_id': product.uom_id.id,
                            'product_id': product.id,
                            'invoice_line_tax_id': [(6, 0, [x.id for x in product.supplier_taxes_id])],
                            'note': 'Carta Porte de Permisionario ' + (waybill.travel_id.name or _('Sin Viaje') ),
                            'account_analytic_id': False,
                            })
                    inv_lines.append(inv_line)
                    
                    notes += '\n' + waybill.name
                    departure_address_id = waybill.departure_address_id.id
                    arrival_address_id = waybill.arrival_address_id.id

                    a = waybill.supplier_id.property_account_payable.id
                    if not a:
                        raise osv.except_osv(_('Warning !'),
                                             _('Supplier << %s >> has not Payable Account defined.') % (waybill.supplier_id.name))


                    if waybill.supplier_id.id and waybill.supplier_id.property_supplier_payment_term.id:
                        pay_term = waybill.supplier_id.property_supplier_payment_term.id
                    else:
                        pay_term = False

                inv = {
                    'name'              : 'Fletes de Permisionario',
                    'origin'            : waybill.name,
                    'type'              : 'in_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : 'Factura de Cartas Porte de Permisionario',
                    'account_id'        : a,
                    'partner_id'        : waybill.supplier_id.id,
                    'departure_address_id' : departure_address_id,
                    'arrival_address_id'   : arrival_address_id,
                    'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [waybill.supplier_id.id], ['default'])['default'],
                    'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [waybill.supplier_id.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'comment'           : 'Factura de Cartas Porte de Permisionario',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : waybill.supplier_id.property_account_position.id,
                    'comment'           : notes,
                    'tms_type'          : 'invoice' if waybill.billing_policy == 'manual' else 'waybill'
                }
                #print "inv: " , inv

                travel_obj.write(cr, uid, [waybill.travel_id.id], {'closed_by': uid, 'date_closed' : time.strftime(DEFAULT_SERVER_DATETIME_FORMAT), 'state':'closed'})

                inv_id = invoice_obj.create(cr, uid, inv)
                invoices.append(inv_id)
 
                waybill_obj.write(cr,uid,waybill_ids, {'supplier_invoice_id': inv_id, 'supplier_invoiced_by':uid, '  supplier_invoiced_date':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               

            ir_model_data = self.pool.get('ir.model.data')
            act_obj = self.pool.get('ir.actions.act_window')
            result = ir_model_data.get_object_reference(cr, uid, 'account', 'action_invoice_tree2')
            id = result and result[1] or False
            result = act_obj.read(cr, uid, [id], context=context)[0]
            result['domain'] = "[('id','in', [" + ','.join(map(str, invoices)) + "])]"
            return result
