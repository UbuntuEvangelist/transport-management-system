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


class hr_job(osv.osv):
    _name = "hr.job"
    _inherit = "hr.job"

    _columns = {
        'tms_global_salary' : fields.float('Global Salary', digits=(18,6)),
      }

    _defaults = {
        'tms_global_salary': lambda *a: 0.0,
    }   

class hr_employee(osv.osv):
    _description ='Employees'
    _name='hr.employee'
    _inherit='hr.employee'

    def name_get(self, cr, uid, ids, context=None):
        reads = self.read(cr, uid, ids, ['name'], context=context)
        res = []
        for record in reads:
            name = ('(%s) ' % record['id']) + record['name']
            res.append((record['id'], name))
        return res

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            ids = self.search(cr, user, [('name','=',name)]+ args, limit=limit, context=context)
            if not ids:
                try:
                    int_name = int(name)
                    ids = self.search(cr, user, [('id','=', int_name)]+ args, limit=limit, context=context)
                except:
                    ids = []
            if not ids:
                ids = set()
                ids.update(self.search(cr, user, args + [('name',operator,name)], limit=limit, context=context))
                ids = list(ids)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result

    _columns = {
        'tms_category': fields.selection([('none','N/A'),('driver','Driver'), ('mechanic','Mechanic'),], 'TMS Category', help='Used to define if this person will be used as a Driver (Frieghts related) or Mechanic (Maintenance related)',required=False),
        'tms_advance_account_id': fields.many2one('account.account', 'Advance Account', domain=[('type', '=', 'other')]), 
        'tms_expense_negative_balance_account_id': fields.many2one('account.account', 'Negative Balance Account', domain=[('type', '=', 'other')]), 
        'tms_supplier_driver': fields.boolean('Supplier Driver'), 
        'tms_supplier_id':fields.many2one('res.partner', 'Supplier', domain=[('supplier', '=', 1)]),
#        'tms_global_salary' : fields.related('job_id', 'tms_global_salary', type='float', digits=(18,6), string='Salary', readonly=True),
        'tms_alimony' : fields.float('Alimony', digits=(18,6)),
        'tms_alimony_prod_id':fields.many2one('product.product', 'Alimony Product', domain=[('tms_category', '=', 'salary_discount')]),
        'tms_house_rent_discount_perc' : fields.float('Monthly House Rental Discount (%)', digits=(18,6)),
        'tms_house_rent_prod_id':fields.many2one('product.product', 'House Rental Product', domain=[('tms_category', '=', 'salary_discount')]),
        'tms_house_rent_discount' : fields.float('Monthly House Rental Discount', digits=(18,6)),
        'tms_credit_charge_discount' : fields.float('Monthly Credit Amount Discount', digits=(18,6)),
        'tms_credit_charge_prod_id':fields.many2one('product.product', 'Credit Charge Product', domain=[('tms_category', '=', 'salary_discount')]),
        'tms_social_security_discount' : fields.float('Social Security Discount', digits=(18,6)),
        'tms_social_security_prod_id':fields.many2one('product.product', 'Social Security Product', domain=[('tms_category', '=', 'salary_discount')]),
        'tms_salary_tax_discount' : fields.float('Salary Tax Discount', digits=(18,6)),
        'tms_salary_tax_prod_id':fields.many2one('product.product', 'Salary Tax Product', domain=[('tms_category', '=', 'salary_retention')]),
        'tms_global_salary' : fields.float('Global Salary', digits=(18,6)),
        'shop_id' : fields.many2one('sale.shop', 'Shop'), #, domain=[('company_id', '=', user.company_id.id)]),
        }

    _defaults = {
        'tms_category': 'none',
    }
