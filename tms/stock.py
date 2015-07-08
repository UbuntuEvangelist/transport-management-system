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

# Add special tax calculation for Mexico
class stock_move(osv.osv):
    _inherit ='stock.move'
    
    _columns = {
        'vehicle_id'    : fields.many2one('fleet.vehicle', 'Vehicle', readonly=True, required=False),
        'employee_id'   : fields.many2one('hr.employee', 'Driver', readonly=True, required=False),
        'fuelvoucher_id': fields.many2one('tms.fuelvoucher', 'Fuel Voucher', readonly=True, required=False),
    }
    

    def _create_account_move_line(self, cr, uid, move, src_account_id, dest_account_id, reference_amount, reference_currency_id, context=None):
        #print "Si entra en _create_account_move_line"
        res_prev = super(stock_move, self)._create_account_move_line(cr, uid, move, src_account_id, dest_account_id, reference_amount, reference_currency_id, context=None)
        res = res_prev
        #print "res: ", res
        #print "move: ", move
        if move.fuelvoucher_id and move.fuelvoucher_id.id:
            if not (move.product_id.tms_property_account_expense.id if move.product_id.tms_property_account_expense.id else move.product_id.categ_id.tms_property_account_expense_categ.id if move.product_id.categ_id.tms_property_account_expense_categ.id else False):
                    raise osv.except_osv(_('Missing configuration !!!'),
                                     _('You have not defined breakdown Account for Product %s...') % (move.product_id.name))
            if move.picking_id.name[-3:] == 'Ret':
                res[0][2].update({'vehicle_id': move.vehicle_id.id, 'employee_id' : move.employee_id.id})
                res[1][2].update({'vehicle_id': move.vehicle_id.id, 'employee_id' : move.employee_id.id, 'account_id' : move.product_id.tms_property_account_expense.id if move.product_id.tms_property_account_expense.id else move.product_id.categ_id.tms_property_account_expense_categ.id})
            else:
                res[0][2].update({'vehicle_id': move.vehicle_id.id, 'employee_id' : move.employee_id.id, 'account_id' : move.product_id.tms_property_account_expense.id if move.product_id.tms_property_account_expense.id else move.product_id.categ_id.tms_property_account_expense_categ.id})
                res[1][2].update({'vehicle_id': move.vehicle_id.id, 'employee_id' : move.employee_id.id})

        #print "_create_account_move_line: ", res
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
