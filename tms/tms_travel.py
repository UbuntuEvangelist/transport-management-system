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
from tools.translate import _
from tools import DEFAULT_SERVER_DATETIME_FORMAT
import time
from datetime import datetime


# Trips / travels
class tms_travel(osv.osv):
    _name = 'tms.travel'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Travels'

    def _route_data(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = {
                'distance_route': 0.0,
                'fuel_efficiency_expected': 0.0,
                             }
            distance  = record.route_id.distance
            fuel_efficiency_expected = record.route_id.fuel_efficiency_drive_unit if not record.trailer1_id else record.route_id.fuel_efficiency_1trailer if not record.trailer2_id else record.route_id.fuel_efficiency_2trailer
            res[record.id] = {
                'distance_route': distance,
                'fuel_efficiency_expected': fuel_efficiency_expected,
            }
        return res

    def _validate_for_expense_rec(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = {
                'waybill_income': 0.0,
            }

            advance_ok = False
            fuelvoucher_ok = False
            waybill_ok = False
            waybill_income = 0.0

            cr.execute("select id from tms_advance where travel_id in %s and state not in ('cancel','confirmed')", (tuple(ids),))
            data_ids = cr.fetchall()
            advance_ok = not len(data_ids)

            cr.execute("select id from tms_fuelvoucher where travel_id in %s and state not in ('cancel','confirmed')", (tuple(ids),))
            data_ids = cr.fetchall()
            fuelvoucher_ok = not len(data_ids)

            cr.execute("select id from tms_waybill where travel_id in %s and state not in ('cancel','confirmed')", (tuple(ids),))
            data_ids = cr.fetchall()
            waybill_ok = not len(data_ids)

            waybill_income = 0.0            
            for waybill in record.waybill_ids:
                waybill_income += waybill.amount_untaxed
                        
            res[record.id] = {
                    'advance_ok_for_expense_rec': advance_ok,
                    'fuelvoucher_ok_for_expense_rec': fuelvoucher_ok,
                    'waybill_ok_for_expense_rec': waybill_ok,
                    'waybill_income': waybill_income,
            }
        return res
    
    def _travel_duration(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = {
                'travel_duration': 0.0,
                'travel_duration_real': 0.0,
            }
            dur1 = datetime.strptime(record.date_end, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.date_start, '%Y-%m-%d %H:%M:%S')
            dur2 = datetime.strptime(record.date_end_real, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.date_start_real, '%Y-%m-%d %H:%M:%S')
            x1 = ((dur1.days * 24.0*60.0*60.0) + dur1.seconds) / 3600.0 if dur1 else 0.0
            x2 = ((dur2.days * 24.0*60.0*60.0) + dur2.seconds) / 3600.0 if dur2 else 0.0
            res[record.id]['travel_duration'] = x1
            res[record.id]['travel_duration_real'] = x2
        return res

    def _get_framework(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            if record.trailer2_id.id and record.trailer1_id.id:
                res[record.id] = {
                    'framework': 'Double',
                    'framework_count': 2,
                    }
            elif record.trailer1_id.id:
                res[record.id] = {
                    'framework': 'Single',
                    'framework_count': 1,
                    }
            else:
                res[record.id] = {
                    'framework': 'Unit',
                    'framework_count': 0,
                    }
        return res
    
    _columns = {
        'operation_id'  : fields.many2one('tms.operation', 'Operation', ondelete='restrict', required=False, readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)], 'closed':[('readonly',True)]}),
        'shop_id'       : fields.many2one('sale.shop', 'Shop', ondelete='restrict', required=True, readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)], 'closed':[('readonly',True)]}),
        'company_id'    : fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'name'          : fields.char('Travel Number', size=64, required=False),
        'state'         : fields.selection([('draft','Pending'), ('progress','In Progress'), ('done','Done'), ('closed','Closed'), ('cancel','Cancelled')], 'State', readonly=True),
        'route_id'      : fields.many2one('tms.route', 'Route', required=True, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'kit_id'        : fields.many2one('tms.unit.kit', 'Kit', required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'unit_id'       : fields.many2one('fleet.vehicle', 'Unit', required=True, domain=[('fleet_type', '=', 'tractor')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'supplier_unit' : fields.related('unit_id', 'supplier_unit', type='boolean', string='Supplier Unit', store=True, readonly=True),
        'supplier_id'   : fields.related('unit_id', 'supplier_id',type='many2one',relation='res.partner',string='Supplier', store=True, readonly=True),                
        'trailer1_id'   : fields.many2one('fleet.vehicle', 'Trailer1', required=False,  domain=[('fleet_type', '=', 'trailer')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'dolly_id'      : fields.many2one('fleet.vehicle', 'Dolly', required=False,        domain=[('fleet_type', '=', 'dolly')],   states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'trailer2_id'   : fields.many2one('fleet.vehicle', 'Trailer2', required=False,  domain=[('fleet_type', '=', 'trailer')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'employee_id'   : fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'employee2_id'  : fields.many2one('hr.employee', 'Driver Helper', required=False, domain=[('tms_category', '=', 'driver')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date'          : fields.datetime('Date registered',required=True, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_start'    : fields.datetime('Start Sched',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_end'      : fields.datetime('End Sched',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_start_real': fields.datetime('Start Real',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_end_real' : fields.datetime('End Real',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'travel_duration': fields.function(_travel_duration, string='Duration Sched', method=True, store=True, type='float', digits=(18,6), multi='travel_duration', 
                                                            help="Travel Scheduled duration in hours"),
        'travel_duration_real': fields.function(_travel_duration, string='Duration Real', method=True, store=True, type='float', digits=(18,6), multi='travel_duration',
                                                                help="Travel Real duration in hours"),
        'distance_route': fields.function(_route_data, string='Route Distance (mi./km)', method=True, 
                                          store = {'tms.travel': (lambda self, cr, uid, ids, c={}: ids, None, 10)},
                                          type='float', multi=True), 
        'fuel_efficiency_expected': fields.function(_route_data, string='Fuel Efficiency Expected', method=True, 
                                                    store = {'tms.travel': (lambda self, cr, uid, ids, c={}: ids, None, 10)},
                                                    type='float', multi=True, digits=(14,4)), 
        
        'advance_ok_for_expense_rec': fields.function(_validate_for_expense_rec, string='Advance OK', method=True, type='boolean',  multi=True),
                                            #store={
                                            #     'tms.travel': (lambda self, cr, uid, ids, c={}: ids, ['state', 'fuelvoucher_ids','waybill_ids', 'advance_ids'], 10),
                                            #     'tms.expense.line': (_get_loan_discounts_from_expense_lines, ['product_uom_qty', 'price_unit'], 10),
                                            #     }),
        'fuelvoucher_ok_for_expense_rec': fields.function(_validate_for_expense_rec, string='Fuel Voucher OK', method=True,  type='boolean',  multi=True),
        'waybill_ok_for_expense_rec': fields.function(_validate_for_expense_rec, string='Waybill OK', method=True,  type='boolean',  multi=True),
        'waybill_income': fields.function(_validate_for_expense_rec, string='Income', method=True, type='float', digits=(18,6), store=True, multi=True),

        'distance_driver': fields.float('Distance traveled by driver (mi./km)', required=False, digits=(16,2), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'distance_loaded': fields.float('Distance Loaded (mi./km)', required=False, digits=(16,2), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'distance_empty': fields.float('Distance Empty (mi./km)', required=False, digits=(16,2), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'distance_extraction': fields.float('Distance Extraction (mi./km)', required=False, digits=(16,2), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        
        'fuel_efficiency_travel': fields.float('Fuel Efficiency Travel', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'fuel_efficiency_extraction': fields.float('Fuel Efficiency Extraction', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'departure_id': fields.related('route_id', 'departure_id', type='many2one', relation='tms.place', string='Departure', store=True, readonly=True),                
        'arrival_id': fields.related('route_id', 'arrival_id', type='many2one', relation='tms.place', string='Arrival', store=True, readonly=True),                

        'notes': fields.text('Descripción', required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),

        'fuelvoucher_ids':fields.one2many('tms.fuelvoucher', 'travel_id', string='Fuel Vouchers', states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'advance_ids':fields.one2many('tms.advance', 'travel_id', string='Advances', states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'framework': fields.function(_get_framework, string='Framework', method=True, store=True, type='char', size=15, multi='framework'),
        'framework_count': fields.function(_get_framework, string='Framework Count', method=True, store=True, type='integer', multi='framework'),
        'framework_supplier' : fields.selection([('Unit','Unit'), ('Single','Single'), ('Double','Double')], 'Framework', states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'create_uid' : fields.many2one('res.users', 'Created by', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by' : fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': fields.datetime('Date Cancelled', readonly=True),
        'dispatched_by' : fields.many2one('res.users', 'Dispatched by', readonly=True),
        'date_dispatched': fields.datetime('Date Dispatched', readonly=True),
        'done_by'       : fields.many2one('res.users', 'Ended by', readonly=True),
        'date_done'     : fields.datetime('Date Ended', readonly=True),
        'closed_by'     : fields.many2one('res.users', 'Closed by', readonly=True),
        'date_closed'   : fields.datetime('Date Closed', readonly=True),
        'drafted_by'    : fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted'  : fields.datetime('Date Drafted', readonly=True),
        'user_id'       : fields.many2one('res.users', 'Salesman', select=True, readonly=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'parameter_distance': fields.integer('Distance Parameter', help="1 = Travel, 2 = Travel Expense, 3 = Manual, 4 = Tyre"),
        }


    _defaults = {
        'date'              : lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_start'        : lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_end'          : lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_start_real'   : lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_end_real'     : lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'state'             : 'draft',
        'user_id'           : lambda obj, cr, uid, context: uid,
        'parameter_distance': lambda s, cr, uid, c: int(s.pool.get('ir.config_parameter').get_param(cr, uid, 'tms_property_update_vehicle_distance', context=c)[0]),
        }
    
    _sql_constraints = [
        ('name_uniq', 'unique(shop_id,name)', 'Travel number must be unique !'),
        ]
    _order = "date desc"
        

        
    def _check_drivers_change(self, cr, uid, ids, context=None):         
        for record in self.browse(cr, uid, ids, context=context):
            travel_id = record.id
            employee1_id = record.employee_id.id if record.employee_id.id else 0
            employee2_id = record.employee2_id.id if record.employee2_id.id else 0
            cr.execute("""select id from tms_advance where travel_id = %s and state not in ('cancel') and employee_id <> %s and not driver_helper
                            union 
                            select id from tms_advance where travel_id = %s and state not in ('cancel') and employee_id <> %s and driver_helper
                            union
                            select id from tms_fuelvoucher where travel_id = %s and state not in ('cancel') and employee_id <> %s and not driver_helper
                            union 
                            select id from tms_fuelvoucher where travel_id = %s and state not in ('cancel') and employee_id <> %s and driver_helper
                            """, 
                       (travel_id, employee1_id, travel_id, employee2_id,travel_id, employee1_id, travel_id, employee2_id)
                       )
            data_ids = cr.fetchall()
            #print data_ids
            return (not len(data_ids))

    _constraints = [
        (_check_drivers_change, 'You can not modify Driver and/or Driver Helper if there are linked records (Fuel vouchers, Advances, etc).', ['employee_id', 'employee2_id']),
    ]

        
    def onchange_unit_id(self, cr, uid, ids, unit_id):
        if not unit_id:
            return {}        
        vehicle = self.pool.get('fleet.vehicle').browse(cr, uid, unit_id)
        return {'value' : {'supplier_id': vehicle.supplier_id.id }}
        
        
    def onchange_kit_id(self, cr, uid, ids, kit_id):
        if not kit_id:
            return {}        
        kit = self.pool.get('tms.unit.kit').browse(cr, uid, kit_id)
        return {'value' : {'unit_id': kit.unit_id.id, 'trailer1_id': kit.trailer1_id.id, 'dolly_id': kit.dolly_id.id, 'trailer2_id': kit.trailer2_id.id, 'employee_id': kit.employee_id.id}}


    def get_factors_from_route(self, cr, uid, ids, context=None):        
        if len(ids):
            factor_obj = self.pool.get('tms.factor')       
            factor_ids = factor_obj.search(cr, uid, [('travel_id', '=', ids[0]), ('control', '=', 1)], context=None)
            if factor_ids:
                res = factor_obj.unlink(cr, uid, factor_ids)
                factors = []
            for factor in self.browse(cr, uid, ids)[0].route_id.expense_driver_factor:
                x = {
                            'name'          : factor.name,
                            'category'      : 'driver',
                            'factor_type'   : factor.factor_type,
                            'range_start'   : factor.range_start,
                            'range_end'     : factor.range_end,
                            'factor'        : factor.factor,
                            'fixed_amount'  : factor.fixed_amount,
                            'mixed'         : factor.mixed,
                            'factor_special_id': factor.factor_special_id.id,
                            'travel_id'     : ids[0],
                            'control'       : True,
                            'driver_helper' : factor.driver_helper,
                            }
                print "x: ", x
                factor_obj.create(cr, uid, x)
        return True


    def write(self, cr, uid, ids, vals, context=None):
        super(tms_travel, self).write(cr, uid, ids, vals, context=context)
        if 'state' in vals and vals['state'] not in ('cancel', 'done', 'closed'):
            self.get_factors_from_route(cr, uid, ids, context=context)
        return True


    def onchange_route_id(self, cr, uid, ids, route_id, unit_id, trailer1_id, dolly_id, trailer2_id):
        if not route_id:
            return {'value': {'distance_route': 0.00, 'distance_extraction': 0.0, 'fuel_efficiency_expected': 0.00}}
        val = {}        
        route = self.pool.get('tms.route').browse(cr, uid, route_id)
        distance  = route.distance
        fuel_efficiency_expected = route.fuel_efficiency_drive_unit if not trailer1_id else route.fuel_efficiency_1trailer if not trailer2_id else route.fuel_efficiency_2trailer
        
        factors = []
        for factor in route.expense_driver_factor:
            x = (0,0, {
                        'name'          : factor.name,
                        'category'      : 'driver',
                        'factor_type'   : factor.factor_type,
                        'range_start'   : factor.range_start,
                        'range_end'     : factor.range_end,
                        'factor'        : factor.factor,
                        'fixed_amount'  : factor.fixed_amount,
                        'mixed'         : factor.mixed,
                        'factor_special_id': factor.factor_special_id.id,
                        'control'       : True,
                        'driver_helper' : factor.driver_helper,
#                        'travel_id'     : ids[0],
                        })
            factors.append(x)


        val = {
            'distance_route'            : distance,
            'distance_extraction'       : distance,
            'fuel_efficiency_expected'  : fuel_efficiency_expected,
            'expense_driver_factor'     : factors,
            }
        return {'value': val}

    def onchange_dates(self, cr, uid, ids, date_start, date_end, date_start_real, date_end_real):
        if not date_start or not date_end or not date_start_real or not date_end_real:
            return {'value': {'travel_duration': 0.0, 'travel_duration_real': 0.0}}
        
        dur1 = datetime.strptime(date_end, '%Y-%m-%d %H:%M:%S') - datetime.strptime(date_start, '%Y-%m-%d %H:%M:%S')
        dur2 = datetime.strptime(date_end_real, '%Y-%m-%d %H:%M:%S') - datetime.strptime(date_start_real, '%Y-%m-%d %H:%M:%S')
        x1 = ((dur1.days * 24.0*60.0*60.0) + dur1.seconds) / 3600.0
        x2 = ((dur2.days * 24.0*60.0*60.0) + dur2.seconds) / 3600.0
        val = {
            'travel_duration': x1,
            'travel_duration_real': x2,
        }        
        return {'value': val}


    def create(self, cr, uid, vals, context=None):
        shop = self.pool.get('sale.shop').browse(cr, uid, vals['shop_id'])
        seq_id = shop.tms_travel_seq.id
        if shop.tms_travel_seq:
            seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
            vals['name'] = seq_number
        else:
            raise osv.except_osv(_('Travel Sequence Error !'), _('You have not defined Travel Sequence for shop ' + shop.name))
        return super(tms_travel, self).create(cr, uid, vals, context=context)

    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        self.write(cr, uid, ids, {'state':'draft','drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        for travel in self.browse(cr, uid, ids, context=context):
            for fuelvouchers in travel.fuelvoucher_ids:
                if fuelvouchers.state not in ('cancel'):
                    raise osv.except_osv(
                        _('Could not cancel Travel !'),
                        _('You must first cancel all Fuel Vouchers attached to this Travel.'))
            for waybills in travel.waybill_ids:
                if waybills.state not in ('cancel'):
                    raise osv.except_osv(
                        _('Could not cancel Travel !'),
                        _('You must first cancel all Waybills attached to this Travel.'))
            
            for advances in travel.advance_ids:
                if advances.state not in ('cancel'):
                    raise osv.except_osv(
                        _('Could not cancel Travel !'),
                        _('You must first cancel all Advances for Drivers attached to this Travel.'))

            if not travel.parameter_distance:
                    raise osv.except_osv(
                        _('Could not Confirm Expense Record !'),
                        _('Parameter to determine Vehicle distance update from does not exist.'))
            elif travel.parameter_distance == 2: # Revisamos el parametro (tms_property_update_vehicle_distance) donde se define donde se actualizan los kms/millas a las unidades 
                self.pool.get('fleet.vehicle.odometer').unlink_odometer_rec(cr, uid, ids, ids, False)

        self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

        return True

    def action_dispatch(self, cr, uid, ids, context=None):
        for travel in self.browse(cr, uid, ids, context=context):
            unit = travel.unit_id.id
            travels = self.pool.get('tms.travel')
            travel_id = travels.search(cr, uid, [('unit_id', '=', unit),('state', '=', 'progress')])
            if travel_id:
                raise osv.except_osv(
                        _('Could not dispatch Travel !'),
                        _('There is already a Travel in progress with Unit ' + travel.unit_id.name))
        self.write(cr, uid, ids, {  'state':'progress',
                                    'dispatched_by':uid,
                                    'date_dispatched':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                    'date_start_real':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_end(self, cr, uid, ids, context=None):
        for travel in self.browse(cr, uid, ids):
            if not travel.parameter_distance:
                raise osv.except_osv(
                    _('Could not End Travel !'),
                    _('Parameter to determine Vehicle distance origin does not exist.'))
            elif travel.parameter_distance == 1: #  parametro (tms_property_update_vehicle_distance) donde se define donde se actualizan los kms/millas a las unidades 
                odom_obj = self.pool.get('fleet.vehicle.odometer')
                xdistance = travel.distance_extraction
                odom_obj.create_odometer_log(cr, uid, False, travel.id, travel.unit_id.id, xdistance)
                if travel.trailer1_id and travel.trailer1_id.id:
                    odom_obj.create_odometer_log(cr, uid, False, travel.id, travel.trailer1_id.id, xdistance)
                if travel.dolly_id and travel.dolly_id.id:
                    odom_obj.create_odometer_log(cr, uid, False, travel.id, travel.dolly_id.id, xdistance)
                if travel.trailer2_id and travel.trailer2_id.id:
                    odom_obj.create_odometer_log(cr, uid, False, travel.id, travel.trailer2_id.id, xdistance)
        self.write(cr,uid,ids,{ 'state':'done',
                                'ended_by':uid,
                                'date_ended':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'date_end_real':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True
