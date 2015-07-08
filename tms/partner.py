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
import decimal_precision as dp
from osv.orm import browse_record, browse_null
import time
from datetime import datetime, date


# TMS - Special Category for TMS module
class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    _columns = {
        'tms_category'  : fields.selection([('none', 'N/A'),('fuel','Fuel'), ('gps','GPS')], 'TMS Category', 
                help='This is used in TMS Module \
                \n* N/A    => Useless \
                \n* Fuel   => It\'s for fuel suppliers. \
                \n* GPS => It\'s for GPS Suppliers.'),
        'tms_warehouse_id'  : fields.many2one('stock.warehouse', 'Fuel Warehouse', 
                                                                help='Internal Fuel Warehouse to use with Fuel Vouchers.', 
                                                                required=False),
        'tms_fuel_internal' : fields.boolean('Internal', help="Check if this company will be used as Self Fuel Consumption"),
    }

    _defaults = {
        'tms_category':'none',
    }

    def _check_fuel_internal(self, cr, uid, ids, context=None):
        partner_obj = self.pool.get('res.partner')
        for record in self.browse(cr, uid, ids, context=context):
            if record.tms_category == 'fuel' and record.tms_fuel_internal:
                res = partner_obj.search(cr, uid, [('tms_fuel_internal', '=', 1)], context=None)                
                if res and res[0] and res[0] != record.id:
                    return False
        return True

    
    _constraints = [
        (_check_fuel_internal, 'Error ! You can not have two or more Partners defined for Internal Warehouse Fuel', ['tms_fuel_internal']),
        ]

    
res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
