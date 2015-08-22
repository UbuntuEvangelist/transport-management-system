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


# Add special tax calculation for Mexico
class account_tax(osv.osv):
    _name = 'account.tax'
    _inherit ='account.tax'
    
    def compute_all_tax_and_retention(self, cr, uid, taxes, price_unit, quantity, tax_type=None):
        res = 0.0
        precision = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
        total = round(price_unit * quantity, precision)
        for tax in taxes:
            if not (tax_type == 'negative' and tax.amount >= 0.00 ):
                res += round((total * tax.amount), precision)
        return {
            'res': res
        }

# Additionat field to set Account Journal for Advances and Travel Expenses
class account_journal(osv.osv):
    _inherit ='account.journal'

    _columns = {
        'tms_advance_journal': fields.boolean('TMS Advance Journal', help= 'If set to True then it will be used for TMS Advance Invoices. It must be a General Type Journal'),
        'tms_fuelvoucher_journal': fields.boolean('TMS Fuel Voucher Journal', help= 'If set to True then it will be used to create Moves when confirming TMS Fuel Voucher. It must be a General Type Journal'),
        'tms_expense_journal': fields.boolean('TMS Expense Journal', help= 'If set to True then it will be used for TMS Expense Invoices. It must be a General Type Journal'),
        'tms_supplier_journal': fields.boolean('TMS Freight Supplier Journal', help= 'If set to True then it will be used for TMS Waybill Supplier Invoices. It must be a Purchase Type Journal'),
        'tms_waybill_journal': fields.boolean('TMS Waybill Journal', help= 'If set to True then it will be used to create Moves when confirming TMS Waybill . It must be a General Type Journal'),
        'tms_expense_suppliers_journal' : fields.boolean('TMS Default Suppliers Expense Journal', help= 'If set to True then it will be used to create Supplier Invoices when confirming TMS Travel Expense Record and when Creating Invoices from Fuel Vouchers. It must be a Purchase Type Journal'),
        }

    _defaults = {
        'tms_advance_journal'           : lambda *a :False,
        'tms_fuelvoucher_journal'       : lambda *a :False,
        'tms_expense_journal'           : lambda *a :False,
        'tms_supplier_journal'          : lambda *a :False,
        'tms_expense_suppliers_journal' : lambda *a :False,
        }

# Additionat field to set Account Journal for Advances and Travel Expenses
class account_account(osv.osv):
    _inherit ='account.account'

    _columns = {
        'tms_vehicle_mandatory' : fields.boolean('TMS Vehicle Mandatory', help= 'If set to True then it will require to add Vehicle to Move Line'),
        'tms_employee_mandatory': fields.boolean('TMS Employee Mandatory', help= 'If set to True then it will require to add Employee to Move Line'),
        'tms_sale_shop_mandatory'    : fields.boolean('TMS Sale Shop Mandatory', help= 'If set to True then it will require to add Sale Shop to Move Line'),
        }

    _defaults = {
        'tms_vehicle_mandatory' : lambda *a :False,
        'tms_employee_mandatory' : lambda *a :False,
        'tms_sale_shop_mandatory' : lambda *a :False,
        }

# Fields <vechicle_id>, <employee_id> added to acount_move_line for reporting and analysis and constraint added
class account_move_line(osv.osv):
    _inherit ='account.move.line'

    _columns = {
        'vehicle_id'  : fields.many2one('fleet.vehicle', 'Vehicle', required=False),
        'employee_id' : fields.many2one('hr.employee', 'Driver', required=False),
        'sale_shop_id': fields.many2one('sale.shop', 'Shop', required=False),
        }
    
    def _check_mandatory_vehicle(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            return (record.account_id.tms_vehicle_mandatory and record.vehicle_id.id) if record.account_id.tms_vehicle_mandatory else True
        return True
    
    def _check_mandatory_employee(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            return (record.account_id.tms_employee_mandatory and record.employee_id.id) if record.account_id.tms_employee_mandatory else True
        return True

    def _check_mandatory_sale_shop(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            return (record.account_id.tms_sale_shop_mandatory and record.sale_shop_id.id) if record.account_id.tms_sale_shop_mandatory else True
        return True

    
    _constraints = [
        (_check_mandatory_vehicle, 'Error ! You have not added Vehicle to Move Line', ['vehicle_id']),
        (_check_mandatory_employee, 'Error ! You have not added Employee to Move Line', ['employee_id']),
        (_check_mandatory_sale_shop, 'Error ! You have not added Sale Shop to Move Line', ['sale_shop_id']),
        ]
