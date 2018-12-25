# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BookUser(models.Model):
    _inherit='res.users'

    library_manage_loc_ids = fields.Many2many('sce_library.location', string="Manage Library Locations")
    

