# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 HESATEC (<http://www.hesatecnica.com>).
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

{   
    "name"        : "Freight Management",
    "version"     : "1.0",
    "category"    : "Vertical",
    'complexity'  : "normal",
    "author"      : "HESATEC",
    "website"     : "http://www.hesatecnica.com",
    "depends"     : ["hr", "account_voucher", "purchase","sale", "fleet"],
    "summary"     : "Management System for Carriers, Trucking companies and other freight companies",
    "description" : """
Freight Management System
==========================

This application allows you to manage Truckload Freights and Less-than-truckload freight. It also can help Companies such as owner-operators, carriers, brokers and shippers.

It handles full Travel workflow:

Transport Requirement => Waybill => Freight => Delivery

Managing:
- Driver Cash advance (Payment & Conciliation)
- Fuel Voucher Management
- Checking Travel Expenses
- Freight Invoicing (Trucks of the company or third parties)

It also can manage:
- Trucks Red Tapes
- Truck Odometers
- Events during travel (Example: Arrival delay, Missing Cargo, etc)
- Kits
- Places (Linked with Google Maps)
- Routes (Visible in Google Maps)
- Easy integration with GPS System


""",

    "data" : [
        'security/tms_security.xml',
        'security/ir.model.access.csv',
        'product_view.xml',
        'ir_config_parameter.xml',
        'ir_sequence_view.xml',
        'account_view.xml',
        'hr_view.xml',
        'partner_view.xml',
        'sale_view.xml',
        'tms_view.xml',
        'tms_travel_view.xml',
        'tms_advance_view.xml',
        'tms_fuelvoucher_view.xml',
        'tms_waybill_view.xml',
        'tms_expense_view.xml',
        'tms_factor_view.xml',
        'tms_history_view.xml',
        'tms_operation_view.xml',
        'tms_expense_loan_view.xml',
        ],
    "application": True,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
