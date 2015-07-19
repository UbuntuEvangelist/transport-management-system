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


# Agregamos manejar una secuencia por cada tienda para controlar viajes 
class sale_shop(osv.osv):
    _name = "sale.shop"
    _inherit = "sale.shop"
    
    _columns = {
            'tms_travel_seq': fields.many2one('ir.sequence', 'Travel Sequence'),
            'tms_advance_seq': fields.many2one('ir.sequence', 'Advance Sequence'),
            'tms_travel_expenses_seq': fields.many2one('ir.sequence', 'Travel Expenses Sequence'),
            'tms_loan_seq': fields.many2one('ir.sequence', 'Loan Sequence'),
            'tms_fuel_sequence_ids': fields.one2many('tms.sale.shop.fuel.supplier.seq', 'shop_id', 'Fuel Sequence per Supplier'),
        }

# Agregamos el detalle de las secuencias por proveedor de combustible por cada tienda. 
class tms_sale_shop_fuel_supplier_seq(osv.osv):
    _name = "tms.sale.shop.fuel.supplier.seq"
    _description = "TMS Sale Shop Fuel Supplier Sequences"
    
    _columns = {
            'shop_id': fields.many2one('sale.shop', 'Shop', required=True),
            'partner_id': fields.many2one('res.partner', 'Fuel Supplier', required=True),
            'fuel_sequence': fields.many2one('ir.sequence', 'Fuel Sequence', required=True),
            }

    _sql_constraints = [
        ('tms_shop_fuel_supplier', 'unique(shop_id, partner_id)', 'Partner must be unique !'),
        ]
