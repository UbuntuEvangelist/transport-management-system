# -*- encoding: utf-8 -*-
from openerp.osv import fields, osv

class sale_shop(osv.osv):
    _name = "sale.shop"
    _description = "Sales Shop"
    _columns = {
        'name': fields.char('Shop Name', size=64, required=True),
        'tms_travel_seq': fields.many2one('ir.sequence', 'Travel Sequence'),
        'tms_advance_seq': fields.many2one('ir.sequence', 'Advance Sequence'),
        'tms_travel_expenses_seq': fields.many2one('ir.sequence', 'Travel Expenses Sequence'),
        'tms_loan_seq': fields.many2one('ir.sequence', 'Loan Sequence'),
        'tms_fuel_sequence_ids': fields.one2many('tms.sale.shop.fuel.supplier.seq', 'shop_id', 'Fuel Sequence per Supplier'),
    }
    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'sale.shop', context=c),
    }
