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
import netsvc
import pooler
from tools.translate import _
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import decimal_precision as dp
from osv.orm import browse_record, browse_null
import time
from datetime import datetime, date

import openerp


# Trip Fuel Vouchers

class tms_fuelvoucher(osv.osv):
    _name ='tms.fuelvoucher'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Fuel Vouchers'

    def _invoiced(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        invoiced = paid = name = False
        for record in self.browse(cr, uid, ids, context=context):
            if (record.invoice_id.id):                
                invoiced = True
                paid = (record.invoice_id.state == 'paid')
                name = record.invoice_id.supplier_invoice_number
            res[record.id] =  { 'invoiced': invoiced,
                                'invoice_paid': paid,
                                'invoice_name': name 
                                }
        return res

    def _amount_calculation(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):        
            tax_factor = 0.00
            for line in record.product_id.supplier_taxes_id:
                tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
            if (record.tax_amount) and tax_factor == 0.00:
                raise osv.except_osv(_('No taxes defined in product !'), _('You have to add taxes for this product. Para Mexico: Tiene que agregar el IVA que corresponda y el IEPS con factor 0.0.'))
            
            if record.partner_id.tms_fuel_internal:
                price_total = subtotal = record.product_uom_qty * record.product_id.standard_price
                special_tax_amount = 0
                price_unit = record.product_id.standard_price
                
            else:
                subtotal = (record.tax_amount / tax_factor) if tax_factor <> 0.0 else record.price_total
                special_tax_amount = (record.price_total - subtotal - record.tax_amount) if tax_factor else 0.0
                price_unit = subtotal / (record.product_uom_qty or 1.0)
                price_total = record.price_total
            ##print "subtotal: ", subtotal
            ##print "IEPS: ", special_tax_amount
            ##print "Impuestos: ", record.tax_amount
            ##print "price_unit: ", price_unit 
            res[record.id] =   {'price_subtotal': subtotal,
                                'special_tax_amount': special_tax_amount,
                                'price_unit': price_unit,
                                'price_total': price_total,
                                }
        return res

    
    _columns = {
        'operation_id'  : fields.many2one('tms.operation', 'Operation', ondelete='restrict', required=False, readonly=False, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)], 'closed':[('readonly',True)]}),
        'name'          : fields.char('Fuel Voucher', size=64, required=False),
        'state'         : fields.selection([('draft','Draft'), ('approved','Approved'), ('confirmed','Confirmed'), ('closed','Closed'), ('cancel','Cancelled')], 'State', readonly=True),
        'date'          : fields.date('Date', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}, required=True),
        
        'employee1_id'  : fields.related('travel_id', 'employee_id', type='many2one', relation='hr.employee', string='Driver', store=True, readonly=True),
        'employee2_id'  : fields.related('travel_id', 'employee2_id', type='many2one', relation='hr.employee', string='Driver Helper', store=True, readonly=True),
        'employee_id'   : fields.many2one('hr.employee', 'Driver', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]},required=False),
        #'shop_id'       : fields.related('travel_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'shop_id'       : fields.many2one('sale.shop', 'Shop', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'travel_id'     : fields.many2one('tms.travel', 'Travel', required=False, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'unit_id'       : fields.many2one('fleet.vehicle', 'Vehicle', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'partner_id'    : fields.many2one('res.partner', 'Fuel Supplier', domain=[('tms_category', '=', 'fuel')],  required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_id'    : fields.many2one('product.product', 'Product', domain=[('purchase_ok', '=', True),('tms_category','=','fuel')],  required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}, ondelete='restrict'),
        'product_uom_qty': fields.float('Quantity', digits=(16, 4), required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_uom'   : fields.many2one('product.uom', 'UoM ', required=True),
        'price_unit'    : fields.function(_amount_calculation, method=True, string='Unit Price', type='float', digits=(16, 4), multi='price_unit', store=True),
        'price_subtotal': fields.function(_amount_calculation, method=True, string='SubTotal', type='float', digits_compute= dp.get_precision('Sale Price'), multi='price_unit', store=True),
        'tax_amount'    : fields.float('Taxes', required=True, digits_compute= dp.get_precision('Sale Price'), states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'special_tax_amount' : fields.function(_amount_calculation, method=True, string='IEPS', type='float', digits_compute= dp.get_precision('Sale Price'), multi='price_unit', store=True),
        'price_total'   : fields.float('Total', required=True, digits_compute= dp.get_precision('Sale Price'), states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
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
        'invoice_id'    : fields.many2one('account.invoice','Invoice Record', readonly=True, domain=[('state', '!=', 'cancel')],),
        'invoiced'      : fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi='invoiced'),               
        'invoice_paid'  : fields.function(_invoiced, method=True, string='Paid', type='boolean', multi='invoiced'),
        'invoice_name'  : fields.function(_invoiced, method=True, string='Invoice', type='char', size=64, multi='invoiced', store=True),
        'currency_id'   : fields.many2one('res.currency', 'Currency', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'move_id'       : fields.many2one('account.move', 'Account Move', required=False, readonly=True, ondelete='restrict'),
        'picking_id'    : fields.many2one('stock.picking.out', 'Stock Picking', required=False, readonly=True, ondelete='restrict'),
        'picking_id_cancel' : fields.many2one('stock.picking.in', 'Stock Picking', required=False, readonly=True, ondelete='restrict'),
        'driver_helper' : fields.boolean('For Driver Helper', help="Check this if you want to give this Fuel Voucher to Driver Helper.", states={'cancel':[('readonly',True)], 'approved':[('readonly',True)], 'confirmed':[('readonly',True)], 'closed':[('readonly',True)]}),
        'no_travel'     : fields.boolean('No Travel', help="Check this if you want to create Fuel Voucher with no Travel.", states={'cancel':[('readonly',True)], 'approved':[('readonly',True)], 'confirmed':[('readonly',True)], 'closed':[('readonly',True)]}),

        }
    
    _defaults = {
        'date': lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': 'draft',
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        }
    
    _sql_constraints = [
        ('name_uniq', 'unique(partner_id,name)', 'Fuel Voucher number must be unique !'),
        ]
    _order = "name desc, date desc"

    
    def _check_driver(self, cr, uid, ids, context=None):         
        for record in self.browse(cr, uid, ids, context=context):            
            if not record.no_travel and record.driver_helper and not record.travel_id.employee2_id.id==record.employee_id.id:
                return False
            elif not record.no_travel and not record.travel_id.employee_id.id==record.employee_id.id:
                return False
            return True

    _constraints = [
        (_check_driver, 'You can not create Fuel Voucher with Driver not in Travel Record.', ['employee_id']),
    ]
    

    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        return {'value': {'product_uom' : prod_obj.browse(cr, uid, [product_id], context=None)[0].uom_id.id }}

    def on_change_no_travel(self, cr, uid, ids, no_travel):
        return no_travel and {'value': {'travel_id' : False, 'unit_id':False, 'employee_id':False}} or {}

    
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

    

    def on_change_amount(self, cr, uid, ids, product_uom_qty, price_total, tax_amount, product_id):
        res = {'value': {'price_unit': 0.0, 'price_subtotal': 0.0, 'special_tax_amount': 0.0}}
        if not (product_uom_qty and price_total and product_id):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].supplier_taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
        if (tax_amount) and tax_factor == 0.00:
            raise osv.except_osv(_('No taxes defined in product !'), _('You have to add taxes for this product. Para Mexico: Tiene que agregar el IVA que corresponda y el IEPS con factor 0.0.'))        
        subtotal = (tax_amount / tax_factor) if tax_factor <> 0.0 else price_total
        special_tax = (price_total - subtotal - tax_amount) if tax_factor else 0.0
        return {'value': {'price_unit': (subtotal / product_uom_qty), 'price_subtotal': subtotal, 'special_tax_amount': special_tax}}
                
    def create(self, cr, uid, vals, context=None):
        'travel_id' in vals and vals['travel_id'] and \
        'no_travel' in vals and vals['no_travel'] and vals.pop('travel_id')
        shop_id = 'shop_id' in vals and vals['shop_id'] or False
        #print "vals: ", vals
        if 'travel_id' in vals and vals['travel_id']:
            travel = self.pool.get('tms.travel').browse(cr, uid, vals['travel_id'])
            shop_id = travel.shop_id.id
            vals.update({'shop_id': travel.shop_id.id, 'unit_id': travel.unit_id.id})
        #print "shop_id: ", shop_id
        supplier_seq_id = self.pool.get('tms.sale.shop.fuel.supplier.seq').search(cr, uid, [('shop_id', '=', shop_id),('partner_id', '=', vals['partner_id'])])
        if supplier_seq_id:
            seq_id = self.pool.get('tms.sale.shop.fuel.supplier.seq').browse(cr, uid, supplier_seq_id)[0].fuel_sequence.id
        else:
            raise osv.except_osv(
                                 _('Fuel Voucher Sequence Error !'), 
                                 _('You have not defined Fuel Voucher Sequence for this shop and Supplier ') + str(vals['partner_id']))
        if seq_id:
            seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
            vals['name'] = seq_number
        else:
            raise osv.except_osv(_('Fuel Voucher Sequence Error !'), _('You have not defined Fuel Voucher Sequence for shop ' + shop.name))
        return super(tms_fuelvoucher, self).create(cr, uid, vals, context=context)


    def write(self, cr, uid, ids, vals, context=None):
        if 'no_travel' in vals:
            raise osv.except_osv(
                                 _('Warning !'), 
                                 _('You can not change field < No Travel > once Fuel Voucher has been saved for the first time'))

        for rec in self.browse(cr, uid, ids):
            'shop_id' in vals and not rec.no_travel and vals.pop('shop_id')
            'unit_id' in vals and not rec.no_travel and vals.pop('unit_id')
            if 'travel_id' in vals:
                travel = self.pool.get('tms.travel').browse(cr, uid, ids, vals['travel_id'])
                vals.update({'shop_id': travel.shop_id.id, 'unit_id': travel.unit_id.id}) 
        return super(tms_fuelvoucher, self).write(cr, uid, ids, vals, context=context)
    
    
    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        for fuelvoucher in self.browse(cr, uid, ids):
            if fuelvoucher.travel_id.state in ('cancel', 'closed'):
                raise osv.except_osv(
                        _('Warning !!! '),
                        _('Could not set to draft this Fuel Voucher, Travel is Closed or Cancelled !!!'))
            elif fuelvoucher.picking_id.id and fuelvoucher.picking_id_cancel.id:
                raise osv.except_osv(
                        _('Warning !!! '),
                        _('Could not set to draft this Fuel Voucher because it was from Fuel Self Consumption.'))                
            else:
                self.write(cr, uid, ids, {'state':'draft','drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        for fuelvoucher in self.browse(cr, uid, ids, context=context):
            move_id = fuelvoucher.move_id.id
            if fuelvoucher.invoiced:
                raise osv.except_osv(
                        _('Could not cancel Fuel Voucher !'),
                        _('This Fuel Voucher is already Invoiced'))
            elif fuelvoucher.travel_id and fuelvoucher.travel_id.state in ('closed'):
                raise osv.except_osv(
                        _('Could not cancel Fuel Voucher !'),
                        _('This Fuel Voucher is already linked to Travel Expenses record'))
                
            elif move_id:
                move_obj = self.pool.get('account.move')
                if fuelvoucher.move_id.state != 'draft':
                    move_obj.button_cancel(cr, uid, [fuelvoucher.move_id.id]) 
                self.write(cr, uid, ids, {'state':'cancel', 'invoice_id':False, 'move_id': False, 'picking_id': False, 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                #move_obj.unlink(cr, uid, [move_id])

            elif fuelvoucher.picking_id and fuelvoucher.picking_id.id:                
                picking_id = self.create_picking(cr, uid, fuelvoucher, 'return', fuelvoucher.picking_id.id)
                self.write(cr,uid,ids,{'picking_id_cancel': picking_id})                
            self.write(cr, uid, ids, {'state':'cancel', 'invoice_id':False, 'move_id': False, 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            if move_id:
                move_obj.unlink(cr, uid, [move_id])
            
        return True

    
    def create_picking(self, cr, uid, fuelvoucher, picking_type, source_picking_id, context=None):
        picking_obj = self.pool.get('stock.picking')
    
        move = (0, 0, {
                'date'              : fuelvoucher.date if picking_type=='out' else time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'date_expected'     : fuelvoucher.date if picking_type=='out' else time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'product_id'        : fuelvoucher.product_id.id,
                'product_qty'       : fuelvoucher.product_uom_qty,
                'product_uos_qty'   : fuelvoucher.product_uom_qty,
                'product_uom'       : fuelvoucher.product_id.uom_id.id,
                'price_unit'        : fuelvoucher.product_id.standard_price,
                'name'              : fuelvoucher.product_id.name + ' - ' + fuelvoucher.name,
                'auto_validate'     : False,
                'price_currency_id' : self.pool.get('res.users').browse(cr, uid, uid, context).company_id.currency_id.id,
                'location_id'       : fuelvoucher.partner_id.tms_warehouse_id.lot_stock_id.id if picking_type=='out' else fuelvoucher.product_id.property_stock_production.id,
                'location_dest_id'  : fuelvoucher.product_id.property_stock_production.id if picking_type=='out' else fuelvoucher.partner_id.tms_warehouse_id.lot_stock_id.id,
                'company_id'        : self.pool.get('res.users').browse(cr, uid, uid, context).company_id.id,
                'vehicle_id'        : fuelvoucher.unit_id.id,
                'employee_id'       : fuelvoucher.employee_id.id,
                'fuelvoucher_id'    : fuelvoucher.id,
                })

        last_pick_name = picking_obj.read(cr, uid, [source_picking_id], ['name'])[0]['name'] if picking_type !='out' else ''
        new_pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking')
        name = new_pick_name if picking_type=='out' else _('%s-%s-Ret') % (new_pick_name,last_pick_name )
        picking = {
                'name'              : name, 
                'date'              : fuelvoucher.date if picking_type=='out' else time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'min_date'          : fuelvoucher.date if picking_type=='out' else time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'origin'            : fuelvoucher.name,
                'move_lines'        : [move],
                'move_type'         : 'direct',
                'type'              : 'internal',
                'invoice_state'     : 'none',
                }

        
        picking_id = picking_obj.create(cr, uid, picking)
        if picking_id:
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)                    
            stock_move_obj = self.pool.get('stock.move')
            for picking in picking_obj.browse(cr, uid, [picking_id]):
                for move in picking.move_lines:
                    stock_move_obj.force_assign(cr, uid, [move.id])
                    stock_move_obj.action_done(cr, uid, [move.id])
        else:
            raise osv.except_osv(_('Error !'),
                    _('Could not create Picking for Fuel Voucher %s') % (fuelvoucher.name,))
        return picking_id
    
    def action_approve(self, cr, uid, ids, context=None):
        for fuelvoucher in self.browse(cr, uid, ids, context=context):
            if fuelvoucher.state in ('draft'):
                self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        for fuelvoucher in self.browse(cr, uid, ids, context=context):
            if fuelvoucher.product_uom_qty <= 0.0:
                 raise osv.except_osv(
                        _('Could not confirm Fuel Voucher !'),
                        _('Product quantity must be greater than zero.'))
            
            elif fuelvoucher.partner_id.tms_category == 'fuel' and fuelvoucher.partner_id.tms_fuel_internal:
                if fuelvoucher.product_id.qty_available < fuelvoucher.product_uom_qty:
                    raise osv.except_osv(_('Warning !'),
                            _('There is no enough Product Inventory to Confirm Fuel Voucher %s') % (fuelvoucher.name,))
                picking_id = self.create_picking(cr, uid, fuelvoucher, 'out', 'False')
                self.write(cr,uid,ids,{'picking_id': picking_id, 'price_total': fuelvoucher.product_id.standard_price * fuelvoucher.product_uom_qty, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            else:
            
                move_obj = self.pool.get('account.move')
                period_obj = self.pool.get('account.period')
                account_jrnl_obj=self.pool.get('account.journal')
                
                period_id = period_obj.search(cr, uid, [('date_start', '<=', fuelvoucher.date),('date_stop','>=', fuelvoucher.date), ('state','=','draft')], context=None)
                
                if not period_id:
                    raise osv.except_osv(_('Warning !'),
                            _('There is no valid account period for this date %s. Period does not exists or is already closed') % \
                                    (fuelvoucher.date,))
                
                journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'general'),('tms_fuelvoucher_journal','=', 1)], context=None)
                if not journal_id:
                    raise osv.except_osv('Error !',
                                     'You have not defined Fuel Voucher Journal...')
                journal_id = journal_id and journal_id[0]
                
                
                move_lines = []
                precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
                notes = _("Fuel Voucher: %s\nTravel: %s\nDriver: (ID %s) %s\nVehicle: %s") % \
                        (fuelvoucher.name, fuelvoucher.travel_id and fuelvoucher.travel_id.name or 'N/A', 
                         fuelvoucher.travel_id and fuelvoucher.travel_id.employee_id.id or 0, 
                         fuelvoucher.travel_id.employee_id and fuelvoucher.travel_id.employee_id.name or 'N/A', 
                         fuelvoucher.travel_id and fuelvoucher.travel_id.unit_id and fuelvoucher.travel_id.unit_id.name or fuelvoucher.unit_id.name)
                ##print "notes: ", notes
                
                
                if not (fuelvoucher.product_id.property_account_expense.id if fuelvoucher.product_id.property_account_expense.id else fuelvoucher.product_id.categ_id.property_account_expense_categ.id if fuelvoucher.product_id.categ_id.property_account_expense_categ.id else False):
                    raise osv.except_osv(_('Missing configuration !!!'),
                                     _('You have not defined expense Account for Product %s...') % (fuelvoucher.product_id.name))
    
                move_line = (0,0, {
                                    'name'          : _('Fuel Voucher: %s') % (fuelvoucher.name),
                                    'account_id'    : fuelvoucher.product_id.property_account_expense.id if fuelvoucher.product_id.property_account_expense.id else fuelvoucher.product_id.categ_id.property_account_expense_categ.id,
                                    'debit'         : 0.0,
                                    'credit'        : round(fuelvoucher.price_subtotal, precision),
                                    'journal_id'    : journal_id,
                                    'period_id'     : period_id[0],
                                    'vehicle_id'    : fuelvoucher.unit_id.id,
                                    'employee_id'   : fuelvoucher.employee_id and fuelvoucher.employee_id.id or False,
                                    'sale_shop_id'  : fuelvoucher.shop_id.id,
                                    'product_id'    : fuelvoucher.product_id.id,
                                    'product_uom_id': fuelvoucher.product_id.uom_id.id,
                                    'quantity'      : fuelvoucher.product_uom_qty
                                    })
                move_lines.append(move_line)
                
                if not (fuelvoucher.product_id.tms_property_account_expense.id if fuelvoucher.product_id.tms_property_account_expense.id else fuelvoucher.product_id.categ_id.tms_property_account_expense_categ.id if fuelvoucher.product_id.categ_id.tms_property_account_expense_categ.id else False):
                    raise osv.except_osv(_('Missing configuration !!!'),
                                     _('You have not defined breakdown Account for Product %s...') % (fuelvoucher.product_id.name))
                    
                move_line = (0,0, {
                                    'name'          : _('Fuel Voucher: %s') % (fuelvoucher.name),
                                    'account_id'    : fuelvoucher.product_id.tms_property_account_expense.id if fuelvoucher.product_id.tms_property_account_expense.id else fuelvoucher.product_id.categ_id.tms_property_account_expense_categ.id,
                                    'debit'         : round(fuelvoucher.price_subtotal, precision),
                                    'credit'        : 0.0,
                                    'journal_id'    : journal_id,
                                    'period_id'     : period_id[0],
                                    'vehicle_id'    : fuelvoucher.unit_id.id,
                                    'employee_id'   : fuelvoucher.employee_id and fuelvoucher.employee_id.id or False,
                                    'sale_shop_id'  : fuelvoucher.shop_id.id,
                                    'product_id'    : fuelvoucher.product_id.id,
                                    'product_uom_id': fuelvoucher.product_id.uom_id.id,
                                    'quantity'      : fuelvoucher.product_uom_qty                                    
                                    })
                move_lines.append(move_line)
    
                move = {
                        'ref'        : _('Fuel Voucher: %s') % (fuelvoucher.name),
                        'journal_id' : journal_id,
                        'narration'  : notes,
                        'line_id'    : [x for x in move_lines],
                        'date'       : fuelvoucher.date,
                        'period_id'  : period_id[0],
                        }
                        
                move_id = move_obj.create(cr, uid, move)
                if move_id:
                    move_obj.button_validate(cr, uid, [move_id])                            
    
                self.write(cr,uid,ids,{'move_id': move_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        
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
            'invoice_id': False,
            'notes': False,
        })
        return super(tms_fuelvoucher, self).copy(cr, uid, id, default, context)


tms_fuelvoucher()

# Wizard que permite conciliar los Vales de combustible en una factura

class tms_fuelvoucher_invoice(osv.osv_memory):

    """ To create invoice for each Fuel Voucher"""

    _name = 'tms.fuelvoucher.invoice'
    _description = 'Make Invoices from Fuel Vouchers'

    def makeInvoices(self, cr, uid, ids, context=None):

        """
             To get Fuel Voucher and create Invoice
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        if context is None:
            context={}

        record_ids =  context.get('active_ids',[])
        if record_ids:
            res = False
            invoices = []
            property_obj=self.pool.get('ir.property')
            partner_obj=self.pool.get('res.partner')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            invoice_line_obj=self.pool.get('account.invoice.line')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            fuelvoucher_obj=self.pool.get('tms.fuelvoucher')

            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'purchase'),('tms_expense_suppliers_journal', '=', 1)], context=None)
            journal_id = journal_id and journal_id[0] or False

            cr.execute("select distinct partner_id, currency_id from tms_fuelvoucher where invoice_id is null and state in ('confirmed', 'closed') and id IN %s",(tuple(record_ids),))

            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv(_('Warning !'),
                                 _('Selected records are not Confirmed or already invoiced...'))
            #print data_ids

            for data in data_ids:
                partner = partner_obj.browse(cr,uid,data[0])

                cr.execute("select id from tms_fuelvoucher where invoice_id is null and state in ('confirmed', 'closed') and partner_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                fuelvoucher_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                
                inv_lines = []
                notes = "Conciliacion de Vales de Combustible. "
                for line in fuelvoucher_obj.browse(cr,uid,fuelvoucher_ids):
                    if (not line.invoiced) and (line.state not in ('draft','approved','cancel')):                      
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

                    a = account_fiscal_obj.map_account(cr, uid, False, a)
                    #print "line.price_unit: ", line.price_unit
                    inv_line = (0,0, {
                        'name': line.product_id.name + ' - ' + (line.travel_id and line.travel_id.name or ' ') + ' - ' + line.name,
                        'origin': line.name,
                        'account_id': a,
                        'price_unit': line.price_unit,
                        'quantity': line.product_uom_qty,
                        'uos_id': line.product_uom.id,
                        'product_id': line.product_id.id,
                        'invoice_line_tax_id': [(6, 0, [x.id for x in line.product_id.supplier_taxes_id])],
                        'note': line.notes,
                        'account_analytic_id': False,
                        'vehicle_id'    : line.unit_id.id,
                        'employee_id'   : line.employee_id and line.employee_id.id or False,
                        'sale_shop_id'  : line.shop_id.id,
                        })
                    #print "inv_line: ", inv_line
                    inv_lines.append(inv_line)
                
                    notes += '\n' + line.name

                a = partner.property_account_payable.id
                if partner and partner.property_payment_term.id:
                    pay_term = partner.property_payment_term.id
                else:
                    pay_term = False

                inv = {
                    'name'              : _('Fuel Vouchers Invoice'),
                    'origin'            : _('Invoice from Fuel Vouchers'),
                    'type'              : 'in_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : _('Fuel Vouchers Invoice'),
                    'account_id'        : a,
                    'partner_id'        : partner.id,
                    #'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    #'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'currency_id'       : data[1],
                    'comment'           : 'TMS-Conciliacion de Vales de Combustible',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : partner.property_account_position.id,
                    'comment'           : notes,
                }



                inv_id = invoice_obj.create(cr, uid, inv)
                invoices.append(inv_id)

                fuelvoucher_obj.write(cr,uid,fuelvoucher_ids, {'invoice_id': inv_id})               

        return {
            'domain': "[('id','in', ["+','.join(map(str,invoices))+"])]",
            'name': _('Supplier Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'in_invoice', 'journal_type': 'purchase'}",
            'type': 'ir.actions.act_window'
        }
tms_fuelvoucher_invoice()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

