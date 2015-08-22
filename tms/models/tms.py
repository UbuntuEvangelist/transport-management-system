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
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
import time
import simplejson as json
import urllib as my_urllib


# Master catalog used for:
# - Unit Types
# - Unit Brands
# - Unit / Motor Models
# - Motor Type
# - Extra Data for Units (Like Insurance Policy, Unit Invoice, etc
# - Unit Status (Still not defined if is keeped or not
# - Documentacion expiraton  for Transportation Units
class tms_unit_category(osv.osv):
    _name = "tms.unit.category"
    _description = "Types, Brands, Models, Motor Type for Transport Units"

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _columns = {
        'name': fields.char('Name', size=30, required=True, translate=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", size=300, string='Complete Name', store=True),
        'parent_id': fields.many2one('tms.unit.category','Parent Category', select=True),
        'child_id': fields.one2many('tms.unit.category', 'parent_id', string='Child Categories'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying this list of categories."),
        'type': fields.selection([
                            ('view','View'), 
                            ('unit_type','Unit Type'), 
                            ('brand','Motor Brand'), 
                            ('motor','Motor Model'), 
                            ('extra_data', 'Extra Data'),
                            ('unit_status','Unit Status'),
                            ('expiry','Expiry'),
                            ('active_cause','Active / Inactive Causes'),
                            ('red_tape','Red Tape Types'),
                        ], 'Category Type',required=True, help="""Category Types:
 - View: Use this to define tree structure
 - Type: Use this to define Unit types, like Tractor, Trailers, dolly, van, etc.
 - Brand: Units brands
 - Motor: Motors
 - Extra Data: Use to define several extra fields for unit catalog.
 - Expiry: Use it to define several extra fields for units related to document expiration (Ex. Insurance Validity, Plates Renewal, etc)
 - Active / Inactive Causes: Use to define causes for a unit to be Active / Inactive (Ex: Highway Accident, Sold, etc)
 - Red Tape Types: Use it to define all kind of Red Tapes like Unit registration, Traffic Violations, etc.
"""
                ),
        'fuel_efficiency_drive_unit': fields.float('Fuel Efficiency Drive Unit', required=False, digits=(14,4)),
        'fuel_efficiency_1trailer': fields.float('Fuel Efficiency One Trailer', required=False, digits=(14,4)),
        'fuel_efficiency_2trailer': fields.float('Fuel Efficiency Two Trailer', required=False, digits=(14,4)),
        'notes': fields.text('Notes'),
        'active': fields.boolean('Active'),
        'mandatory': fields.boolean('Mandatory', help="This field is used only when field <Category Type> = expiry"),
        'company_id': fields.many2one('res.company', 'Company', required=False),
    }

    _defaults = {
#        'type' : lambda *a : 'unit_type',
        'active': True,
    }

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category name number must be unique !'),
        ]

    _order = "sequence"

    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from tms_unit_category where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive categories.', ['parent_id'])
    ]

    def child_get(self, cr, uid, ids):
        return [ids]

    def copy(self, cr, uid, id, default=None, context=None):
        categ = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default['name'] = categ['name'] + ' (copy)'
        return super(tms_unit_category, self).copy(cr, uid, id, default, context=context)

# Units for Transportation
class fleet_vehicle(osv.osv):
    _name = 'fleet.vehicle'
    _inherit = ['fleet.vehicle']
    _description = "All motor/trailer units"

    def _get_current_odometer(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):            
            odom_obj = self.pool.get('fleet.vehicle.odometer.device')
            result = odom_obj.search(cr, uid, [('vehicle_id', '=', record.id),('state', '=', 'active')], limit=1, context=None)
            ##print "result: ", result
            if result and result[0]:
                res[record.id] = result[0]
        return res

    _columns = {
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=False),
#        'company_id': fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'name': fields.char('Unit Name', size=64, required=True),
        'year_model':fields.char('Year Model', size=64), 
        'unit_type_id':fields.many2one('tms.unit.category', 'Unit Type', domain="[('type','=','unit_type')]"),
#        'unit_brand_id':fields.many2one('tms.unit.category', 'Brand', domain="[('type','=','brand')]"),
#        'unit_model_id':fields.many2one('tms.unit.category', 'Model', domain="[('type','=','model')]"),
        'unit_motor_id':fields.many2one('tms.unit.category', 'Motor', domain="[('type','=','motor')]"),
        'serial_number': fields.char('Serial Number', size=64),
        'vin': fields.char('VIN', size=64),
        'day_no_circulation': fields.selection([
                            ('sunday','Sunday'), 
                            ('monday','Monday'), 
                            ('tuesday','Tuesday'), 
                            ('wednesday','Wednesday'), 
                            ('thursday','Thursday'), 
                            ('friday','Friday'), 
                            ('saturday','Saturday'), 
                            ('none','Not Applicable'), 
                           ], string="Day no Circulation", translate=True),
        'registration': fields.char('Registration', size=64), # Tarjeta de Circulacion
        'gps_supplier_id': fields.many2one('res.partner', 'GPS Supplier', required=False, readonly=False, 
                                            domain="[('tms_category','=','gps'),('is_company', '=', True)]"),
        'gps_id': fields.char('GPS Id', size=64),
        'employee_id': fields.many2one('hr.employee', 'Driver', required=False, domain=[('tms_category', '=', 'driver')], help="This is used in TMS Module..."),
        'fleet_type': fields.selection([('tractor','Motorized Unit'), ('trailer','Trailer'), ('dolly','Dolly'), ('other','Other')], 'Unit Fleet Type', required=True),
        'avg_odometer_uom_per_day'  :fields.float('Avg Distance/Time per day', required=False, digits=(16,2), help='Specify average distance traveled (mi./kms) or Time (Days, hours) of use per day for this'),
        
        'notes'                 : fields.text('Notes'),
        'active'                : fields.boolean('Active'),
        'unit_extradata_ids'    : fields.one2many('tms.unit.extradata', 'unit_id', 'Extra Data'),
        'unit_expiry_ids'       : fields.one2many('tms.unit.expiry', 'unit_id', 'Expiry Extra Data'), 
        'unit_photo_ids'        : fields.one2many('tms.unit.photo', 'unit_id', 'Photos'), 
        'unit_active_history_ids' : fields.one2many('tms.unit.active_history', 'unit_id', 'Active/Inactive History'), 
        'unit_red_tape_ids'     : fields.one2many('tms.unit.red_tape', 'unit_id', 'Unit Red Tapes'), 
        'supplier_unit'         : fields.boolean('Supplier Unit'),
        'supplier_id'           : fields.many2one('res.partner', 'Supplier', required=False, readonly=False, 
                                            domain="[('tms_category','=','none'),('is_company', '=', True)]"),
        'latitude'              : fields.float('Lat', required=False, digits=(20,10), help='GPS Latitude'),
        'longitude'             : fields.float('Lng', required=False, digits=(20,10), help='GPS Longitude'),
        'last_position'         : fields.char('Last Position', size=250),
        'last_position_update'  : fields.datetime('Last GPS Update'),
        'active_odometer'       : fields.float('Odometer', required=False, digits=(20,10), help='Odometer'),
        'active_odometer_id'    : fields.function(_get_current_odometer, type='many2one', relation="fleet.vehicle.odometer.device", string="Active Odometer"),
        'current_odometer_read' : fields.related('active_odometer_id', 'odometer_end', type='float', string='Last Odometer Read', readonly=True),
        'odometer_uom'          : fields.selection([('distance','Distance (mi./km)'),
                                                                ('hours','Time (Hours)'),
                                                                ('days','Time (Days)')], 'Odometer UoM', help="Odometer UoM"),

    }

    _defaults = {
        'fleet_type'  : lambda *a : 'tractor',
        'active'      : True,
        'odometer_uom': lambda *a : 'distance',
    	}

    def _check_extra_data_expiry(self, cr, uid, ids, context=None):
        categ_obj = self.pool.get('tms.unit.category')
        expiry_obj = self.pool.get('tms.unit.expiry')
        recs = categ_obj.search(cr, uid, [('mandatory', '=', 1), ('type', '=', 'expiry')])
        if recs:
            unit_id = self.browse(cr, uid, ids)[0].id
            for rec in categ_obj.browse(cr, uid, recs):
                if not expiry_obj.search(cr, uid, [('expiry_id', '=', rec.id), ('unit_id', '=', unit_id)]):
                    return False
        return True

    _constraints = [
        (_check_extra_data_expiry,
            'You have defined certain mandatory Expiration Extra Data fields that you did not include in this Vehicle record. Please add missing fields.',
            ['unit_expiry_ids'])
        ]

    _sql_constraints = [
            ('name_uniq', 'unique(name)', 'Unit name number must be unique !'),
            ('gps_id_uniq', 'unique(gps_id)', 'Unit GPS ID must be unique !'),
        ]

    def copy(self, cr, uid, id, default=None, context=None):
        unit = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default['name'] = unit['name'] + ' (copy)'
        default['gps_id'] = ''
        default['unit_extradata_ids'] = []
        default['unit_expiry_ids'] = []
        default['unit_photo_ids'] = []
        return super(fleet_vehicle, self).copy(cr, uid, id, default, context=context)

    def create(self, cr, uid, vals, context=None):
        values = vals
        res = super(fleet_vehicle, self).create(cr, uid, values, context=context)
        
        odom_obj = self.pool.get('fleet.vehicle.odometer.device')
        rec = { 'name'          : _('Odometer device created when vehicle %s was created') % (vals['name']),
                'state'         : 'draft',
                'date'          : time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
                'date_start'    : time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
                'vehicle_id'    : res,
                'accumulated_start' : 0.0,
                'odometer_start'    : 0.0, 
            }
        odom_id = odom_obj.create(cr, uid, rec)    
        odom_obj.action_activate(cr, uid, [odom_id])
        return res

    def return_action_to_open_tms(self, cr, uid, ids, context=None):
        """ This opens the xml view specified in xml_id for the current vehicle """
        if context is None:
            context = {}
        if context.get('xml_id'):
            res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'tms', context['xml_id'], context=context)
            res['context'] = context
            res['context'].update({'default_unit_id': ids[0]})
            res['domain'] = [('unit_id','=', ids[0])]
            return res
        return False

# Units PHOTOS
class tms_unit_photo(osv.osv):
    _name = "tms.unit.photo"
    _description = "Units Photos"

    _columns = {
        'unit_id' : fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade'),
        'name': fields.char('Description', size=64, required=True),
        'photo': fields.binary('Photo'),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,name)', 'Photo name number must be unique for each unit !'),
        ]

# Units EXTRA DATA
class tms_unit_extradata(osv.osv):
    _name = "tms.unit.extradata"
    _description = "Extra Data for Units"
    _rec_name = "extra_value"

    _columns = {
        'unit_id'       : fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', select=True,),        
        'extra_data_id' :fields.many2one('tms.unit.category', 'Field', domain="[('type','=','extra_data')]", required=True),
        'extra_value'   : fields.char('Valor', size=64, required=True),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,extra_data_id)', 'Extra Data Field must be unique for each unit !'),
        ]

# Units for Transportation EXPIRY EXTRA DATA
class tms_unit_expiry(osv.osv):
    _name = "tms.unit.expiry"
    _description = "Expiry Extra Data for Units"

    _columns = {
        'unit_id'       : fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', select=True,),        
        'expiry_id'     :fields.many2one('tms.unit.category', 'Field', domain="[('type','=','expiry')]", required=True),
        'extra_value'   : fields.date('Value', required=True),
        'name'          : fields.char('Valor', size=10, required=True),
        }

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,expiry_id)', 'Expiry Data Field must be unique for each unit !'),
        ]

    def on_change_extra_value(self, cr, uid, ids, extra_value):
        return {'value': {'name': extra_value[8:] + '/' + extra_value[5:-3] + '/' + extra_value[:-6]}}

# Units Kits
class tms_unit_kit(osv.osv):
    _name = "tms.unit.kit"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Units Kits"

    _columns = {
        'name'          : fields.char('Name', size=64, required=True),
        'unit_id'       : fields.many2one('fleet.vehicle', 'Unit', required=True),
        'unit_type'     : fields.related('unit_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Unit Type', store=True, readonly=True),
        'trailer1_id'   : fields.many2one('fleet.vehicle', 'Trailer 1', required=True),
        'trailer1_type' : fields.related('trailer1_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Trailer 1 Type', store=True, readonly=True),
        'dolly_id'      : fields.many2one('fleet.vehicle', 'Dolly'),
        'dolly_type'    : fields.related('dolly_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Dolly Type', store=True, readonly=True),
        'trailer2_id'   : fields.many2one('fleet.vehicle', 'Trailer 2'),
        'trailer2_type' : fields.related('trailer2_id', 'unit_type_id', type='many2one', relation='tms.unit.category', string='Trailer 2 Type', store=True, readonly=True),
        'employee_id'   : fields.many2one('hr.employee', 'Driver', domain=[('tms_category', '=', 'driver')]),
        'date_start'    : fields.datetime('Date start', required=True),
        'date_end'      : fields.datetime('Date end', required=True),
        'notes'         : fields.text('Notes'),
        'active'            : fields.boolean('Active'),        
        }

    _defaults = {
        'active' : lambda *a : True,
    }

    def _check_expiration(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            date_start = record.date_start
            date_end   = record.date_end
            
            sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and unit_id = ' + str(record.unit_id.id) \
                    + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                        + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 

            cr.execute(sql)
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            if len(data):
                raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for unit %s !\n' \
                                                                'This unit is overlaping Kit << %s >>')%(record.unit_id.name, data[0]))
            if record.dolly_id.id:
                sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and dolly_id = ' + str(record.dolly_id.id) \
                        + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                            + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 

                cr.execute(sql)
                data = filter(None, map(lambda x:x[0], cr.fetchall()))
                if len(data):
                    raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for dolly %s !\n' \
                                                                    'This dolly is overlaping Kit << %s >>')%(record.dolly_id.name, data[0]))
            sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and (trailer1_id = ' + str(record.trailer1_id.id) + 'or trailer2_id = ' + str(record.trailer1_id.id) + ')' \
                    + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                        + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 
            cr.execute(sql)
            data = filter(None, map(lambda x:x[0], cr.fetchall()))
            if len(data):
                raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for trailer %s !\n' \
                                                                'This trailer is overlaping Kit << %s >>')%(record.trailer1_id.name, data[0]))
            if record.trailer2_id.id:
                sql = 'select name from tms_unit_kit where id <> ' + str(record.id) + ' and (trailer1_id = ' + str(record.trailer2_id.id) + 'or trailer2_id = ' + str(record.trailer2_id.id) + ')' \
                        + ' and (date_start between \'' + date_start + '\' and \'' + date_end + '\'' \
                            + ' or date_end between \'' + date_start + '\' and \'' + date_end + '\');' 
                cr.execute(sql)
                data = filter(None, map(lambda x:x[0], cr.fetchall()))  
                if len(data):
                    raise osv.except_osv(_('Validity Error !'), _('You cannot have overlaping expiration dates for trailer %s !\n' \
                                                                    'This trailer is overlaping Kit << %s >>')%(record.trailer2_id.name, data[0]))
            return True

    _constraints = [
        (_check_expiration,
            'The expiration is overlaping an existing Kit for this unit!',
            ['date_start'])
    ]

    _sql_constraints = [
        ('name_uniq', 'unique(unit_id,name)', 'Kit name number must be unique for each unit !'),
        ]
    _order = "name desc, date_start desc"

    def on_change_tms_unit_id(self, cr, uid, ids, tms_unit_id):
        res = {'value': {'date_start': time.strftime('%Y-%m-%d %H:%M')}}
        if not (tms_unit_id):
            return res
        cr.execute("select date_end from tms_unit_kit where id=%s order by  date_end desc limit 1", tms_unit_id)
        date_start = cr.fetchall()
        if not date_start:
            return res
        else:
            return {'value': {'date_start': date_start[0]}} 

    def on_change_active(self, cr, uid, ids, active):
        if active:
            return {}
        return {'value': {'date_end' : time.strftime('%d/%m/%Y %H:%M:%S')}}

#Unit Active / Inactive history
class tms_unit_active_history(osv.osv):
    _name = "tms.unit.active_history"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Units Active / Inactive history"

    _columns = {
        'state'             : fields.selection([('draft','Draft'), ('confirmed','Confirmed'), ('cancel','Cancelled')], 'State', readonly=True),
        'unit_id'           : fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', domain=[('active', 'in', ('true', 'false'))]),
        'unit_type_id'      : fields.related('unit_id', 'unit_type_id', type='many2one', relation='tms.unit.category', store=True, string='Unit Type'),
        'prev_state'        : fields.selection([('active','Active'), ('inactive','Inactive')], 'Previous State', readonly=True),
        'new_state'         : fields.selection([('active','Active'), ('inactive','Inactive')], 'New State', readonly=True),
        'date'              : fields.datetime('Date', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=True),
        'state_cause_id'    : fields.many2one('tms.unit.category', 'Active/Inactive Cause', domain="[('type','=','active_cause')]", states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=True),
        'name'              : fields.char('Description', size=64, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=True),
        'notes'             : fields.text('Notes', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)]}, required=False),
        'create_uid'        : fields.many2one('res.users', 'Created by', readonly=True),
        'create_date'       : fields.datetime('Creation Date', readonly=True, select=True),
        'confirmed_by'      : fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed'    : fields.datetime('Date Confirmed', readonly=True),
        'cancelled_by'      : fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled'    : fields.datetime('Date Cancelled', readonly=True),
        }

    _defaults = {
        'state'     : lambda *a: 'draft',
        'date'      : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        }

    def on_change_state_cause_id(self, cr, uid, ids, state_cause_id):
        return {'value': {'name': self.pool.get('tms.unit.category').browse(cr, uid, [state_cause_id])[0].name }}

    def on_change_unit_id(self, cr, uid, ids, unit_id):
        val = {}
        if not unit_id:
            return  val
        for rec in self.pool.get('fleet.vehicle').browse(cr, uid, [unit_id]):
            val = {'value' : {'prev_state' : 'active' if rec.active else 'inactive','new_state' : 'inactive' if rec.active else 'active' } }
        return val

    def create(self, cr, uid, vals, context=None):
        values = vals
        if 'unit_id' in vals:
            res = self.search(cr, uid, [('unit_id', '=', vals['unit_id']),('state','=','draft')], context=None)
            if res and res[0]:
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not create a new record for this unit because theres is already a record for this unit in Draft State.'))
            unit_obj = self.pool.get('fleet.vehicle')
            for rec in unit_obj.browse(cr, uid, [vals['unit_id']]):
                vals.update({
                                'prev_state' : 'active' if rec.active else 'inactive',
                                'new_state'  : 'inactive' if rec.active else 'active' }
                            )
        ##print vals
        return super(tms_unit_active_history, self).create(cr, uid, values, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not delete a record if is already Confirmed!!! Click Cancel button to continue.'))
        super(tms_unit_active_history, self).unlink(cr, uid, ids, context=context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not cancel a record if is already Confirmed!!!'))
        self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by' : uid, 'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            ##print rec.new_state == 'active'
            self.pool.get('fleet.vehicle').write(cr, uid, [rec.unit_id.id], {'active' : (rec.new_state == 'active')} )
        self.write(cr, uid, ids, {'state':'confirmed', 'confirmed_by' : uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

# Unit Red Tape
class tms_unit_red_tape(osv.osv):
    _name = "tms.unit.red_tape"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Units Red Tape history"

    _columns = {
        'state'             : fields.selection([('draft','Draft'), ('pending','Pending'), ('progress','Progress'), ('done','Done'), ('cancel','Cancelled')], 'State', readonly=True),
        'unit_id'           : fields.many2one('fleet.vehicle', 'Unit Name', required=True, ondelete='cascade', domain=[('active', 'in', ('true', 'false'))],
                                                            readonly=True, states={'draft':[('readonly',False)]} ),
        'unit_type_id'      : fields.related('unit_id', 'unit_type_id', type='many2one', relation='tms.unit.category', store=True, string='Unit Type', readonly=True),
        'date'              : fields.datetime('Date', required=True, readonly=True, states={'draft':[('readonly',False)], 'pending':[('readonly',False)]} ),
        'date_start'        : fields.datetime('Date Start', readonly=True),
        'date_end'          : fields.datetime('Date End', readonly=True),
        'red_tape_id'       : fields.many2one('tms.unit.category', 'Red Tape', domain="[('type','=','red_tape')]",  required=True,
                                readonly=True, states={'draft':[('readonly',False)]} ),
        'partner_id'        : fields.many2one('res.partner', 'Partner', states={'cancel':[('readonly',True)], 'done':[('readonly',True)]}, required=False),
        'name'              : fields.char('Description', size=64, required=True, readonly=True, states={'draft':[('readonly',False)], 'pending':[('readonly',False)]} ),
        'notes'             : fields.text('Notes', states={'cancel':[('readonly',True)], 'done':[('readonly',True)]}, required=False),
        'amount'            : fields.float('Amount', required=True, digits_compute= dp.get_precision('Sale Price'), readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)]} ),
        'amount_paid'       : fields.float('Amount Paid', required=True, digits_compute= dp.get_precision('Sale Price'), readonly=False, states={'cancel':[('readonly',True)], 'done':[('readonly',True)]} ),
        'create_uid'        : fields.many2one('res.users', 'Created by', readonly=True),
        'create_date'       : fields.datetime('Creation Date', readonly=True, select=True),
        'pending_by'        : fields.many2one('res.users', 'Pending by', readonly=True),
        'date_pending'      : fields.datetime('Date Pending', readonly=True),
        'progress_by'       : fields.many2one('res.users', 'Progress by', readonly=True),
        'date_progress'     : fields.datetime('Date Progress', readonly=True),
        'done_by'           : fields.many2one('res.users', 'Done by', readonly=True),
        'date_done'         : fields.datetime('Date Done', readonly=True),
        'cancelled_by'      : fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled'    : fields.datetime('Date Cancelled', readonly=True),
        'drafted_by'        : fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted'      : fields.datetime('Date Drafted', readonly=True),
        }

    _defaults = {
        'state'       : lambda *a: 'draft',
        'date'        : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'amount'      : 0.0,
        'amount_paid' : 0.0,
        }

    def on_change_red_tape_id(self, cr, uid, ids, red_tape_id):
        return {'value': {'name': self.pool.get('tms.unit.category').browse(cr, uid, [red_tape_id])[0].name }}

    def create(self, cr, uid, vals, context=None):
        if 'unit_id' in vals:
            res = self.search(cr, uid, [('unit_id', '=', vals['unit_id']),('state','=','draft')], context=None)
            if res and res[0]:
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not create a new record for this unit because theres is already a record for this unit in Draft State.'))
        return super(tms_unit_red_tape, self).create(cr, uid, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not delete a record if is already Confirmed!!! Click Cancel button to continue.'))

        super(tms_unit_active_history, self).unlink(cr, uid, ids, context=context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.state == 'confirmed':
                raise osv.except_osv(
                        _('Warning!'),
                        _('You can not cancel a record if already Confirmed!!!'))
        self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by' : uid, 'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_pending(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'pending', 'pending_by' : uid, 'date_pending':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_cancel_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft', 'drafted_by' : uid, 'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_progress(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'progress', 'progress_by' : uid, 
                                    'date_progress':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                    'date_start':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                    })
        return True

    def action_done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'done', 'done_by' : uid, 
                                  'date_done':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                  'date_end':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                  })
        return True

# Causes for active / inactive transportation units   
# Pendiente

# Cities / Places
class tms_place(osv.osv):
    _name = 'tms.place'
    _description = 'Cities / Places'

    def _get_place_and_state(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):            
            xname = record.name + ', ' + record.state_id.code
            res[record.id] = xname
        return res

    _columns = {
        'company_id'    : fields.many2one('res.company', 'Company', required=False),
        'name'          : fields.char('Place', size=64, required=True, select=True),
        'complete_name' : fields.function(_get_place_and_state, method=True, type="char", size=100, string='Complete Name', store=True),
        'state_id'      : fields.many2one('res.country.state', 'State Name', required=True),
        'country_id'    : fields.related('state_id', 'country_id', type='many2one', relation='res.country', string='Country'),
        'latitude'      : fields.float('Latitude', required=False, digits=(20,10), help='GPS Latitude'),
        'longitude'     : fields.float('Longitude', required=False, digits=(20,10), help='GPS Longitude'),
        'route_ids'     : fields.many2many('tms.route', 'tms_route_places_rel', 'place_id', 'route_id', 'Routes with this Place'),        
    }

    _rec_name = 'complete_name'

    def  button_get_coords(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            address = rec.name + "," + rec.state_id.name + "," + rec.country_id.name
            google_url = 'http://maps.googleapis.com/maps/api/geocode/json?address=' + address.encode('utf-8') + '&sensor=false'
            result = json.load(my_urllib.urlopen(google_url))
            #print google_url
            #print result
            if result['status'] == 'OK':
                #print 'latitude: ', result['results'][0]['geometry']['location']['lat']
                #print 'longitude: ', result['results'][0]['geometry']['location']['lng']
                self.write(cr, uid, ids, {'latitude': result['results'][0]['geometry']['location']['lat'], 'longitude' : result['results'][0]['geometry']['location']['lng'] })
            #else:
                #print result['status']
        return True

    def button_open_google(self, cr, uid, ids, context=None):
        for place in self.browse(cr, uid, ids):
            url="/tms/static/src/googlemaps/get_place_from_coords.html?" + str(place.latitude) + ','+ str(place.longitude)
        return { 'type': 'ir.actions.act_url', 'url': url, 'nodestroy': True, 'target': 'new' }

# Routes
class tms_route(osv.osv):
    _name ='tms.route'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = 'Routes'

    _columns = {
        'company_id': fields.many2one('res.company', 'Company', required=False),
        'name' : fields.char('Route Name', size=64, required=True, select=True),
        'departure_id': fields.many2one('tms.place', 'Departure', required=True),
        'arrival_id': fields.many2one('tms.place', 'Arrival', required=True),
        'distance':fields.float('Distance (mi./kms)', required=True, digits=(14,4), help='Route distance (mi./kms)'),
        'places_ids' : fields.one2many('tms.route.place', 'route_id', 'Intermediate places in Route'),
        'travel_time':fields.float('Travel Time (hrs)', required=True, digits=(14,4), help='Route travel time (hours)'),
        'route_fuelefficiency_ids' : fields.one2many('tms.route.fuelefficiency', 'tms_route_id', 'Fuel Efficiency by Motor type'),
        'fuel_efficiency_drive_unit': fields.float('Fuel Efficiency Drive Unit', required=False, digits=(14,4)),
        'fuel_efficiency_1trailer': fields.float('Fuel Efficiency One Trailer', required=False, digits=(14,4)),
        'fuel_efficiency_2trailer': fields.float('Fuel Efficiency Two Trailer', required=False, digits=(14,4)),
        'notes': fields.text('Notes'),
        'active':fields.boolean('Active'),
        }

    _defaults = {
        'active': True,
    }

    def _check_distance(self, cr, uid, ids, context=None):
        return (self.browse(cr, uid, ids, context=context)[0].distance > 0)

    _constraints = [
        (_check_distance, 'You can not save New Route without Distance!', ['distance']),
        ]

    def  button_get_route_info(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            if rec.departure_id.latitude and rec.departure_id.longitude and rec.arrival_id.latitude and rec.arrival_id.longitude:
                destinations = ""
                origins = str(rec.departure_id.latitude) + ',' + str(rec.departure_id.longitude)
                places = [str(x.place_id.latitude) + ',' + str(x.place_id.longitude) for x in rec.places_ids if x.place_id.latitude and x.place_id.longitude]                        
                #print "places: ", places
                for place in places:
                    origins += "|" + place
                    destinations += place + "|"
                destinations += str(rec.arrival_id.latitude) +',' + str(rec.arrival_id.longitude)
                #print "origins: ", origins
                #print "destinations: ", destinations
                google_url = 'http://maps.googleapis.com/maps/api/distancematrix/json?origins=' + origins + \
                                                                                '&destinations=' + destinations + \
                                                                                '&mode=driving' + \
                                                                                '&language=' + context['lang'][:2] + \
                                                                                '&sensor=false'
                result = json.load(my_urllib.urlopen(google_url))
                if result['status'] == 'OK':
                    distance = duration = 0.0
                    if len(rec.places_ids):
                        i = 0
                        for row in result['rows']:
                            #print row
                            distance += row['elements'][i]['distance']['value'] / 1000.0
                            duration += row['elements'][i]['duration']['value'] / 3600.0
                            i += 1
                    else:
                        distance = result['rows'][0]['elements'][0]['distance']['value'] / 1000.0
                        duration = result['rows'][0]['elements'][0]['duration']['value'] / 3600.0

                    #print "distance: ", distance
                    #print "duration: ", duration

                    self.write(cr, uid, ids, {'distance': distance, 'travel_time' : duration })
                #else:
                    #print result['status']
            else:
                raise osv.except_osv(_('Error !'), _('You cannot get route info because one of the places has no coordinates.'))

        return True

    def button_open_google(self, cr, uid, ids, context=None):
        for route in self.browse(cr, uid, ids):
            points = str(route.departure_id.latitude) + ','+ str(route.departure_id.longitude) + (',' if len(route.places_ids) else '') +  \
                        ','.join([str(x.place_id.latitude) + ',' + str(x.place_id.longitude) for x in route.places_ids if x.place_id.latitude and x.place_id.longitude]) + \
                        ',' + str(route.arrival_id.latitude) + ','+ str(route.arrival_id.longitude)
            #print points
            url="/tms/static/src/googlemaps/get_route.html?" + points
        return { 'type': 'ir.actions.act_url', 'url': url, 'nodestroy': True, 'target': 'new' }

class tms_route_place(osv.osv):
    _name ='tms.route.place'
    _description = 'Intermediate Places in Routes'

    _columns = {
        'route_id'  : fields.many2one('tms.route', 'Route', required=True),
        'place_id'  : fields.many2one('tms.place', 'Place', required=True),
        'state_id'  : fields.related('place_id', 'state_id', type='many2one', relation='res.country.state', string='State', store=True, readonly=True),
        'country_id': fields.related('place_id', 'country_id', type='many2one', relation='res.country', string='Country', store=True, readonly=True),
        'sequence'  : fields.integer('Sequence', help="Gives the sequence order when displaying this list."),
    }

    _defaults = {
        'sequence': 10,
    }

# Route Fuel Efficiency by Motor
class tms_route_fuelefficiency(osv.osv):
    _name = "tms.route.fuelefficiency"
    _description = "Fuel Efficiency by Motor"

    _columns = {
        'tms_route_id' : fields.many2one('tms.route', 'Route', required=True),        
        'motor_id':fields.many2one('tms.unit.category', 'Motor', domain="[('type','=','motor')]", required=True),
        'type': fields.selection([('tractor','Drive Unit'), ('one_trailer','Single Trailer'), ('two_trailer','Double Trailer')], 'Type', required=True),
        'performance' :fields.float('Performance', required=True, digits=(14,4), help='Fuel Efficiency for this motor type'),
        }
    
    _sql_constraints = [
        ('route_motor_type_uniq', 'unique(tms_route_id, motor_id, type)', 'Motor + Type must be unique !'),
        ]

# Routes toll stations
class tms_route_tollstation(osv.osv):
    _name ='tms.route.tollstation'
    _description = 'Routes toll stations'

    _columns = {
        'company_id': fields.many2one('res.company', 'Company', required=False),
        'name' : fields.char('Name', size=64, required=True),
        'place_id':fields.many2one('tms.place', 'Place', required=True),
        'partner_id':fields.many2one('res.partner', 'Partner', required=True),
        'credit': fields.boolean('Credit'),
        'tms_route_ids':fields.many2many('tms.route', 'tms_route_tollstation_route_rel', 'route_id', 'tollstation_id', 'Routes with this Toll Station'),
        'active': fields.boolean('Active'),
    }

    _defaults = {
        'active': True,
        }

# Routes toll stations cost per axis
class tms_route_tollstation_costperaxis(osv.osv):
    _name ='tms.route.tollstation.costperaxis'
    _description = 'Routes toll stations cost per axis'

    _columns = {
        'tms_route_tollstation_id' : fields.many2one('tms.route.tollstation', 'Toll Station', required=True),
        'unit_type_id':fields.many2one('tms.unit.category', 'Unit Type', domain="[('type','=','unit_type')]", required=True),        
        'axis':fields.integer('Axis', required=True),
        'cost_credit':fields.float('Cost Credit', required=True, digits=(14,4)),
        'cost_cash':fields.float('Cost Cash', required=True, digits=(14,4)),
        }

# Routes toll stations INHERIT for adding cost per axis
class tms_route_tollstation(osv.osv):
    _inherit ='tms.route.tollstation'

    _columns = {
        'tms_route_tollstation_costperaxis_ids' : fields.one2many('tms.route.tollstation.costperaxis', 'tms_route_tollstation_id', 'Toll Cost per Axis', required=True),
        }

# Routes INHERIT for adding Toll Stations
class tms_route(osv.osv):
    _inherit ='tms.route'

    _columns = {
        'tms_route_tollstation_ids' : fields.many2many('tms.route.tollstation', 'tms_route_tollstation_route_rel', 'tollstation_id', 'route_id', 'Toll Station in this Route'),
        }

# Route Fuel Efficiency by Motor
class tms_route_fuelefficiency(osv.osv):
    _name = "tms.route.fuelefficiency"
    _description = "Fuel Efficiency by Motor"

    _columns = {
        'tms_route_id' : fields.many2one('tms.route', 'Route', required=True),        
        'motor_id':fields.many2one('tms.unit.category', 'Motor', domain="[('type','=','motor')]", required=True),
        'type': fields.selection([('tractor','Drive Unit'), ('one_trailer','Single Trailer'), ('two_trailer','Double Trailer')], 'Type', required=True),
        'performance' :fields.float('Performance', required=True, digits=(14,4), help='Fuel Efficiency for this motor type'),
        }

    _sql_constraints = [
        ('route_motor_type_uniq', 'unique(tms_route_id, motor_id, type)', 'Motor + Type must be unique !'),
        ]

# Fleet Vehicle odometer device
class fleet_vehicle_odometer_device(osv.osv):
    _name = "fleet.vehicle.odometer.device"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Fleet Vehicle Odometer Device"

    _columns = {
        'state'             : fields.selection([('draft','Draft'), ('active','Active'), ('inactive','Inactive'), ('cancel','Cancelled')], 'State', readonly=True),
        'date'              : fields.datetime('Date', required=True, states={'cancel':[('readonly',True)], 'active':[('readonly',True)], 'inactive':[('readonly',True)]} ),
        'date_start'        : fields.datetime('Date Start', required=True, states={'cancel':[('readonly',True)], 'active':[('readonly',True)], 'inactive':[('readonly',True)]} ),
        'date_end'          : fields.datetime('Date End', readonly=True),
        'name'              : fields.char('Name', size=128, required=True, states={'cancel':[('readonly',True)], 'active':[('readonly',True)], 'inactive':[('readonly',True)]} ),
        'vehicle_id'        : fields.many2one('fleet.vehicle', 'Vehicle', required=True, ondelete='cascade', states={'cancel':[('readonly',True)], 'active':[('readonly',True)], 'inactive':[('readonly',True)]} ),
        'replacement_of'    : fields.many2one('fleet.vehicle.odometer.device', 'Replacement of', required=False, digits=(16, 2), states={'cancel':[('readonly',True)], 'active':[('readonly',True)], 'inactive':[('readonly',True)]} ),
        'accumulated_start' : fields.float('Original Accumulated', help="Kms /Miles Accumulated from vehicle at the moment of activation of this odometer", readonly=True ),
        'odometer_start'    : fields.float('Start count', required=True, help="Initial counter from device", digits=(16, 2), states={'cancel':[('readonly',True)], 'active':[('readonly',True)], 'inactive':[('readonly',True)]} ),
        'odometer_end'      : fields.float('End count', required=True, help="Ending counter from device", digits=(16, 2), states={'cancel':[('readonly',True)], 'active':[('readonly',True)], 'inactive':[('readonly',True)]} ),
        'odometer_reading_ids': fields.one2many('fleet.vehicle.odometer', 'odometer_id', 'Odometer Readings', readonly=True),
        }

    _defaults ={
            'date'              : lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'date_start'        : lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'odometer_start'    : 0.0,
            'odometer_end'      : 0.0,
            'state'             : 'draft',
        } 

    def _check_state(self, cr, uid, ids, context=None):
        #print "Entrando a _check_state "
        hubod_obj = self.pool.get('fleet.vehicle.odometer.device')
        for record in self.browse(cr, uid, ids, context=context):
            #print "ID: ", record.id
            #print "State: ", record.state
            res = hubod_obj.search(cr, uid, [('vehicle_id', '=', record.vehicle_id.id),('state', 'not in', ('cancel','inactive')),('state','=',record.state)], context=None)
            if res and res[0] and res[0] != record.id:
                return False
            return True

    def _check_odometer(self, cr, uid, ids, context=None):
        #print "Entrando a _check_odometer"
        for rec in self.browse(cr, uid, ids, context=context):
            #print "rec.odometer_end: ", rec.odometer_end
            #print "rec.odometer_start: ", rec.odometer_start
            if rec.odometer_end < rec.odometer_start:
                return False
            return True

    def _check_dates(self, cr, uid, ids, context=None):
        #print "Entrando a _check_dates"
        hubod_obj = self.pool.get('fleet.vehicle.odometer.device')
        for record in self.browse(cr, uid, ids, context=context):
            if record.date_end and record.date_end < record.date_start:            
                raise osv.except_osv(_('Error !'), _('Ending Date (%s) is less than Starting Date (%s)')%(record.date_end, record.date_start))
            res = hubod_obj.search(cr, uid, [('vehicle_id', '=', record.vehicle_id.id),('state', '!=', 'cancel'),('date_end','>',record.date_start)], context=None)
            #print "res: ", res
            if res and res[0] and res[0] != record.id:
                return False
            return True

    _constraints = [
        (_check_state, 'You can not have two records with the same State (Draft / Active) !', ['state']),
        (_check_odometer, 'You can not have Odometer End less than Odometer Start', ['odometer_end']),
        (_check_dates, 'You can not have this Star Date because is overlaping with another record', ['date_end'])
        ]

    def write(self, cr, uid, ids, vals, context=None):
        values = vals
        #print self._name, " vals: ", vals
        return super(fleet_vehicle_odometer_device, self).write(cr, uid, ids, values, context=context)

    def on_change_vehicle_id(self, cr, uid, ids, vehicle_id, date_start):
        odom_obj = self.pool.get('fleet.vehicle.odometer.device')
        res = odom_obj.search(cr, uid, [('vehicle_id', '=', vehicle_id),('state', '!=', 'cancel'),('date_end','<',date_start)], limit=1, order="date_end desc", context=None)
        odometer_id = False
        accumulated = 0.0
        #print "res: ", res
        if res and res[0]:
            for rec in odom_obj.browse(cr, uid, res):
                odometer_id = rec.id
                accumulated = rec.vehicle_id.odometer
        return {'value': {'replacement_of': odometer_id, 'accumulated': accumulated }}

    def action_activate(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            odometer = rec.vehicle_id.odometer
            self.write(cr, uid, ids, {'state':'active', 'accumulated' : odometer})
        return True

    def action_inactivate(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            self.write(cr, uid, ids, {'state':'inactive', 'date_end': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids):
            self.write(cr, uid, ids, {'state':'cancel'})
        return True

# Vehicle Odometer records
class fleet_vehicle_odometer(osv.osv):
    _inherit = ['fleet.vehicle.odometer']
    _name='fleet.vehicle.odometer'
### PENDIENTES
# - CALCULAR LA DISTANCIA RECORRIDA ENTRE EL REGISTRO ACTUAL Y EL ANTERIOR BASADA EN EL ODOMETRO ACTIVO. NO SE PUEDEN GUARDAR
    _columns = {
        'odometer_id'       : fields.many2one('fleet.vehicle.odometer.device', 'Odometer', required=True),
        'last_odometer'     : fields.float('Last Read', digits=(16,2), required=True),        
        'current_odometer'  : fields.float('Current Read', digits=(16,2), required=True),
        'distance'          : fields.float('Distance', digits=(16,2), required=True),
        'tms_expense_id'    : fields.many2one('tms.expense', 'Expense Rec'),
        'tms_travel_id'     : fields.many2one('tms.travel', 'Travel'),
    }

    def _check_values(self, cr, uid, ids, context=None):         
        for record in self.browse(cr, uid, ids, context=context):
            #print "record.current_odometer: ", record.current_odometer
            #print "record.last_odometer: ", record.last_odometer
            if record.current_odometer <= record.last_odometer:
                return False
            return True

    _constraints = [
        (_check_values, 'You can not have Current Reading <= Last Reading !', ['current_odometer']),
        ]

    def on_change_vehicle(self, cr, uid, ids, vehicle_id, context=None):
        res = super(fleet_vehicle_odometer, self).on_change_vehicle(cr, uid, ids, vehicle_id, context=context)
        for vehicle in self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id], context=context):
            odom_obj = self.pool.get('fleet.vehicle.odometer.device')
            odometer_id = odom_obj.search(cr, uid, [('vehicle_id', '=', vehicle_id), ('state', '=','active')], context=context)
            if odometer_id and odometer_id[0]:
                for odometer in odom_obj.browse(cr, uid, odometer_id):                
                    res['value']['odometer_id'] = odometer_id[0]
                    res['value']['last_odometer'] = odometer.odometer_end
                    res['value']['value'] = vehicle.odometer
            else:
                raise osv.except_osv(
                        _('Record Warning !'),
                        _('There is no Active Odometer for vehicle %s') % (vehicle.name))

        return res

    def on_change_current_odometer(self, cr, uid, ids, vehicle_id, last_odometer, current_odometer, context=None):
        distance = current_odometer - last_odometer
        accum = self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id], context=context)[0].odometer + distance
        return {'value': {
                        'distance'  : distance,
                        'value'     : accum,
                        }    
                }

    def on_change_distance(self, cr, uid, ids, vehicle_id, last_odometer, distance, context=None):
        current_odometer = last_odometer + distance
        accum = self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id], context=context)[0].odometer + distance
        return {'value': {
                        'current_odometer'  : current_odometer,
                        'value'             : accum,
                        }    
                }

    def on_change_value(self, cr, uid, ids, vehicle_id, last_odometer, value, context=None):
        distance = value - self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id], context=context)[0].odometer
        current_odometer = last_odometer + distance
        return {'value': {
                        'current_odometer'  : current_odometer,
                        'distance'          : distance,
                        }    
                }

    def create(self, cr, uid, vals, context=None):
        values = vals
        #print "vals: ", vals
        if 'odometer_id' in vals and vals['odometer_id']:
            odom_obj = self.pool.get('fleet.vehicle.odometer.device')
            odometer_end = odom_obj.browse(cr, uid, [vals['odometer_id']])[0].odometer_end + vals['distance']
            odom_obj.write(cr, uid, [vals['odometer_id']], {'odometer_end': odometer_end}, context=context)
        return super(fleet_vehicle_odometer, self).create(cr, uid, values, context=context)

    def create_odometer_log(self, cr, uid, expense_id, travel_id, vehicle_id, distance, context=None):
        vehicle = self.pool.get('fleet.vehicle').browse(cr, uid, [vehicle_id])[0]
        odom_dev_obj = self.pool.get('fleet.vehicle.odometer.device')
        odometer_id = odom_dev_obj.search(cr, uid, [('vehicle_id', '=', vehicle_id), ('state', '=','active')], context=context)
        last_odometer = 0.0
        if odometer_id and odometer_id[0]:
            last_odometer = odom_dev_obj.browse(cr, uid, odometer_id)[0].odometer_end
        else:
            raise osv.except_osv(
                _('Could not create Odometer Record!'),
                _('There is no Active Odometer for Vehicle %s') % (vehicle.name))
           
        values = { 'odometer_id'      : odometer_id[0],
                   'vehicle_id'       : vehicle_id,
                   'value'            : vehicle.odometer + distance,
                   'last_odometer'    : last_odometer,
                   'distance'         : distance,
                   'current_odometer' : last_odometer + distance,
                   'tms_expense_id'   : expense_id,
                   'tms_travel_id'    : travel_id,
                   }
        res = self.create(cr, uid, values)
        # Falta crear un método para actualizar el promedio diario de recorrido de la unidad
        return

    def unlink_odometer_rec(self, cr, uid, ids, travel_ids, unit_id, context=None):
        #print "Entrando a: unlink_odometer_rec "
        unit_obj = self.pool.get('fleet.vehicle')
        odom_dev_obj = self.pool.get('fleet.vehicle.odometer.device')
        res = self.search(cr, uid, [('tms_travel_id', 'in', tuple(travel_ids),), ('vehicle_id', '=', unit_id)])
        #print "Registros de lecturas de odometro especificando unidad: ", res
        res1 = self.search(cr, uid, [('tms_travel_id', 'in', tuple(travel_ids),)])
        #print "Registros de lecturas de odometro sin especificar unidad: ", res1
        #print "Recorriendo las lecturas de odometro..."
        for odom_rec in self.browse(cr, uid, res):
            #print "===================================="
            #print "Vehiculo: ", odom_rec.vehicle_id.name
            unit_odometer = unit_obj.browse(cr, uid, [odom_rec.vehicle_id.id])[0].current_odometer_read
            #print "unit_odometer: ", unit_odometer
            #print "odom_rec.distance: ",odom_rec.distance
            #print "Valor a descontar: ", round(unit_odometer, 2) - round(odom_rec.distance, 2)
            unit_obj.write(cr, uid, [unit_id],  {'current_odometer_read': round(unit_odometer, 2) - round(odom_rec.distance, 2)})
            #print "Después de actualizar el odometro de la unidad..."
            #device_odometer = odom_dev_obj.browse(cr, uid, [odom_rec.odometer_id.id])[0].odometer_end
            ##print "device_odometer: ", device_odometer
            ##print "device_odometer - odom_rec.distance : ", round(device_odometer, 2) - round(odom_rec.distance, 2)
            #odom_dev_obj.write(cr, uid, [odom_rec.odometer_id.id],  {'odometer_end': round(device_odometer, 2) - round(odom_rec.distance, 2)})
            #print "===================================="
        self.unlink(cr, uid, res1)
        return
