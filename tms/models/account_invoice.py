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
import openerp.addons.decimal_precision as dp

class account_invoice(osv.osv):
    _inherit ='account.invoice'

    def _get_waybill_info(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}
        res = {}            
        for invoice in self.browse(cr, uid, ids, context=context):
            waybill_rate = invoice_positive_taxes = invoice_negative_taxes = 0
            product = ''
            arrival_id = departure_id = unit_id = False
            for waybill in invoice.waybill_ids:
                product = waybill.waybill_shipped_product[0].product_id.name.split(' ')[0]
                arrival_id = waybill.travel_id.route_id.arrival_id.id
                departure_id = waybill.travel_id.route_id.departure_id.id
                unit_id = waybill.unit_id.id
                for factor in waybill.waybill_customer_factor:
                    waybill_rate = factor.factor if factor.factor_type=='weight' else factor.fixed_amount
                    continue
                continue
            for taxes in invoice.tax_line:
                invoice_positive_taxes += taxes.amount if taxes.amount > 0.0 else 0.0 
                invoice_negative_taxes += taxes.amount if taxes.amount < 0.0 else 0.0 
            res[invoice.id] =  {'product'       : product,
                                'waybill_rate'  : waybill_rate,
                                'departure_id'    : departure_id,
                                'arrival_id'    : arrival_id,
                                'unit_id'       : unit_id,
                                'invoice_positive_taxes_sum'  : invoice_positive_taxes,
                                'invoice_negative_taxes_sum'  : invoice_negative_taxes,
                                }
        return res


    _columns = {
        'tms_type'      : fields.selection([
                        ('none', 'N/A'),
                        ('waybill', 'Waybill'),
                        ('invoice', 'Invoice'),
                        ], 'TMS Type', help="Waybill -> This invoice results from one Waybill (Mexico - Carta Porte/Guia con valor fiscal)\nInvoice -> This Invoice results from several Waybills (México - Carta Porte/Guia sin valor Fiscal)", require=False),
        'waybill_ids': fields.one2many('tms.waybill', 'invoice_id', 'Waybills', readonly=True, required=False),
        'departure_address_id': fields.many2one('res.partner', 'Departure Address', readonly=True, required=False),
        'arrival_address_id': fields.many2one('res.partner', 'Arrival Address', readonly=True, required=False),
        'expense_ids'       : fields.one2many('tms.expense', 'invoice_id', 'Travel Expenses', readonly=True, required=False),
        'fuelvoucher_ids'   : fields.one2many('tms.fuelvoucher', 'invoice_id', 'Fuel Vouchers', readonly=True, required=False),
        'travel_id': fields.many2one('tms.travel', 'Travel', readonly=True, required=False),
        'vehicle_id': fields.many2one('fleet.vehicle', 'Vehicle', readonly=True, required=False),
        'employee_id': fields.many2one('hr.employee', 'Driver', readonly=True, required=False),
        'waybill_shipped_ids': fields.one2many('tms.waybill.shipped_grouped', 'invoice_id', 'Group Shipped Qty by Product', readonly=True, required=False),
#        'product'       : fields.function(_get_waybill_info, string='Product',  type='char',  size='128', multi=True, method=True),
        'waybill_rate'  : fields.function(_get_waybill_info, string='Waybill Rate', type='float', digits_compute= dp.get_precision('Sale Price'),  multi=True, method=True),
        'departure_id'  : fields.function(_get_waybill_info, string='Departure', type='many2one', relation='tms.place',  multi=True, method=True),
        'arrival_id'    : fields.function(_get_waybill_info, string='Arrival', type='many2one', relation='tms.place',  multi=True, method=True),
        'unit_id'       : fields.function(_get_waybill_info, string='Unit', type='many2one', relation='fleet.vehicle',  multi=True, method=True),
        'invoice_positive_taxes_sum'  : fields.function(_get_waybill_info, string='Positive Taxes', type='float', digits_compute= dp.get_precision('Sale Price'),  multi=True, method=True),
        'invoice_negative_taxes_sum'  : fields.function(_get_waybill_info, string='Negative Taxes', type='float', digits_compute= dp.get_precision('Sale Price'),  multi=True, method=True),
        
    }
    
    _defaults = {
        'tms_type' : 'none',        
    }

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        invoices = self.read(cr, uid, ids, ['state','internal_number', 'origin'], context=context)
        for invoice in invoices:
            if invoice['state'] in ('draft', 'cancel') and invoice['internal_number'] != False and invoice['origin'] == 'TMS-Fuel Voucher':
                self.write(cr, uid, ids, {'internal_number':False})
                
        return super(account_invoice, self).unlink(cr, uid, ids, context=context)

    def action_cancel_draft(self, cr, uid, ids, *args):
        for invoice in self.browse(cr, uid, ids):
            if invoice.waybill_ids:
                raise osv.except_osv(_('Warning!'),_("You can not Set to Draft an Invoice created from Waybills!"))
        return super(account_invoice, self).action_cancel_draft(cr, uid, ids, *args)
    
#    def action_move_create(self, cr, uid, ids, context=None):
#        res = super(account_invoice, self).action_move_create(cr, uid, ids, context=context)
#        move_line_obj = self.pool.get('account.move.line')
#        for invoice in self.browse(cr, uid, ids):
#            lines = move_line_obj.search(cr, uid, [('move_id','=', invoice.move_id.id)])
#            if invoice.vehicle_id.id:
#                move_line_obj.write(cr, uid, lines, {'vehicle_id': invoice.vehicle_id.id})
#            if invoice.employee_id.id:
#                move_line_obj.write(cr, uid, lines, {'employee_id': invoice.employee_id.id})                    
#        return res


    def line_get_convert(self, cr, uid, x, part, date, context=None):
        res = super(account_invoice, self).line_get_convert(cr, uid, x, part, date, context=context)
        res.update({
            'vehicle_id'    : x.get('vehicle_id', False),
            'employee_id'   : x.get('employee_id', False),
            'sale_shop_id'  : x.get('sale_shop_id', False),
            })
        return res
    
    
    def _get_analytic_lines(self, cr, uid, id, context=None):
        if context is None:
            context = {}
        inv = self.browse(cr, uid, id)
        cur_obj = self.pool.get('res.currency')

        company_currency = self.pool['res.company'].browse(cr, uid, inv.company_id.id).currency_id.id
        if inv.type in ('out_invoice', 'in_refund'):
            sign = 1
        else:
            sign = -1

        iml = self.pool.get('account.invoice.line').move_line_get(cr, uid, inv.id, context=context)
        for il in iml:
            if not il['account_id'] or il['account_id']==None:
                il['account_id']=il['account_id2']
            if il['account_analytic_id']:
                if inv.type in ('in_invoice', 'in_refund'):
                    ref = inv.reference
                else:
                    ref = self._convert_ref(cr, uid, inv.number)
                if not inv.journal_id.analytic_journal_id:
                    raise osv.except_osv(_('No Analytic Journal!'),_("You have to define an analytic journal on the '%s' journal!") % (inv.journal_id.name,))
                il['analytic_lines'] = [(0,0, {
                    'name': il['name'],
                    'date': inv['date_invoice'],
                    'account_id': il['account_analytic_id'],
                    'unit_amount': il['quantity'],
                    'amount': cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, il['price'], context={'date': inv.date_invoice}) * sign,
                    'product_id': il['product_id'],
                    'product_uom_id': il['uos_id'],
                    'general_account_id': il['account_id'],
                    'journal_id': inv.journal_id.analytic_journal_id.id,
                    'ref': ref,
                })]
        return iml

# Grouped Shipped Quantity by Product
class tms_waybill_shipped_grouped(osv.osv):
    _name = "tms.waybill.shipped_grouped"
    _description = "Waybill Grouped Shipped Qty by Product"

    _columns = {        
        'invoice_id': fields.many2one('account.invoice', 'Invoice', required=True, ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product', required=True), 
        'quantity': fields.float('Quantity', digits=(16, 2),required=True),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ',required=True),
        }

    _defaults = {
        'quantity': 0,
    }

    
class account_invoice_line(osv.osv):
    _inherit ='account.invoice.line'
    
    _columns = {
            'vehicle_id'    : fields.many2one('fleet.vehicle', 'Vehicle', readonly=True, required=False),
            'employee_id'   : fields.many2one('hr.employee', 'Driver', readonly=True, required=False),
            'sale_shop_id'  : fields.many2one('sale.shop', 'Shop', readonly=True, required=False),
    }

    def move_line_get_item(self, cr, uid, line, context=None):
        res = super(account_invoice_line, self).move_line_get_item(cr, uid, line, context=context)
        res.update({
            'vehicle_id'    : line.vehicle_id.id if line.vehicle_id else False,
            'employee_id'   : line.employee_id.id if line.employee_id else False,
            'sale_shop_id'  : line.sale_shop_id.id if line.sale_shop_id else False,
            'line_id'       : line.id,
            'account_id2'   : line.account_id.id,
            })
        return res
