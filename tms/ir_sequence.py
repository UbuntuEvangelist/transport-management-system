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
import openerp

# Agregamos un método en la clase ir_sequence para controlar secuencias de Viajes / Cartas Porte / Anticipos / Vales de Combustible 
class ir_sequence(osv.osv):
    _name = 'ir.sequence'
    _inherit = 'ir.sequence'

    _columns = {
        'tms_waybill_sequence': openerp.osv.fields.boolean('TMS Waybill Sequence'),
        'tms_waybill_automatic': openerp.osv.fields.boolean('TMS Waybill Automatic', help="Indicates if this Waybill Sequence will be automatically invoiced"),
        'shop_id': openerp.osv.fields.many2one('sale.shop', 'Shop', domain="[('company_id','=',company_id)]"),        
        }
    
#    def tms_get_id(self, cr, uid, sequence_id, context=None):
        #print sequence_id
#        sql =  "SELECT id, number_next, prefix, suffix, padding FROM ir_sequence WHERE active=true AND id=" + str(sequence_id)
        #print sql
#        cr.execute(sql)
#        res = cr.dictfetchone()
#        if res:
#            cr.execute('UPDATE ir_sequence SET number_next=number_next+number_increment WHERE id=%s AND active=true', (res['id'],))
#            if res['number_next']:
#                return self._process(res['prefix']) + '%%0%sd' % res['padding'] % res['number_next'] + self._process(res['suffix'])
#            else:
#                return self._process(res['prefix']) + self._process(res['suffix'])
#        return False
    
ir_sequence()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
