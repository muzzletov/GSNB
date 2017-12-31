#!/usr/bin/env python3
# coding: utf-8

# Copyright (C) 2017 Robert Griesel
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import Pango
import datetime
import time


class DocumentListViewItem(Gtk.ListBoxRow):
    ''' Link in sidebar to activate worksheets or documentation, show some data about it '''

    def __init__(self, document_name, document_id, last_saved=None, last_accessed=None):
        Gtk.ListBoxRow.__init__(self)
        
        self.document_name = document_name
        self.document_id = document_id
        self.last_saved = last_saved
        self.last_accessed = last_accessed
        
        self.name = Gtk.Label()
        self.name.set_justify(Gtk.Justification.LEFT)
        self.name.set_xalign(0)
        self.name.set_hexpand(False)
        self.name.set_single_line_mode(True)
        self.name.set_max_width_chars(-1)
        self.name.set_ellipsize(Pango.EllipsizeMode.END)
        self.name.get_style_context().add_class('wslist_name')


class WorksheetListViewItem(DocumentListViewItem):
    ''' Link in sidebar to activate worksheet, show some data about it '''
    
    def __init__(self, worksheet_name, worksheet_id, last_saved, last_accessed=None):
        DocumentListViewItem.__init__(self, worksheet_name, worksheet_id, last_saved, None)
        
        self.icon = Gtk.Image.new_from_file('./resources/sage_icon_2.png')
        self.icon.get_style_context().add_class('wslist_icon')
        
        self.statebox = Gtk.HBox()
        self.state = Gtk.Label()
        self.state.set_justify(Gtk.Justification.LEFT)
        self.state.set_xalign(0)
        self.state.set_hexpand(False)
        self.state.get_style_context().add_class('wslist_state')
        self.last_save = Gtk.Label()
        self.last_save.set_justify(Gtk.Justification.LEFT)
        self.last_save.set_xalign(1)
        self.last_save.set_yalign(0)
        self.last_save.set_hexpand(False)
        self.last_save.get_style_context().add_class('wslist_last_save')
        self.statebox.pack_start(self.state, True, True, 0)
        self.statebox.pack_start(self.last_save, True, True, 0)
        
        self.textbox = Gtk.VBox()
        self.textbox.pack_start(self.name, False, False, 0)
        self.textbox.pack_start(self.statebox, True, True, 0)
        
        self.box = Gtk.HBox()
        self.box.pack_start(self.icon, False, False, 0)
        self.box.pack_end(self.textbox, True, True, 0)
        self.box.get_style_context().add_class('wslist_wrapper')
        self.add(self.box)
        
        self.set_name(self.document_name)
        self.set_last_save(last_saved)
        self.set_state('idle.')
        
    def get_worksheet_id(self):
        return self.document_id
        
    def set_name(self, new_name):
        self.document_name = new_name
        self.name.set_text(self.document_name)
        
    def set_last_save(self, new_date):
        self.last_saved = new_date
        today = datetime.date.today()
        yesterday = datetime.date.fromtimestamp(time.time() - 86400)
        monday = datetime.date.fromtimestamp(time.time() - today.weekday()*86400)
        if self.last_saved.date() == today:
            datestring = '{:02d}:{:02d}'.format((self.last_saved.hour), (self.last_saved.minute))
        elif self.last_saved.date() == yesterday:
            datestring = 'yesterday'
        elif self.last_saved.date() >= monday:
            datestring = self.last_saved.strftime('%a')
        elif self.last_saved.year == today.year:
            datestring = self.last_saved.strftime('%d %b')
        else:
            datestring = self.last_saved.strftime('%d %b %Y')
        self.last_save.set_text(datestring)
        self.changed()
        
    def set_state(self, new_state):
        self.state.set_text(new_state)
        

class DocumentationListViewItem(DocumentListViewItem):
    ''' Link in sidebar to activate worksheet, show some data about it '''
    
    def __init__(self, worksheet_name, worksheet_id, last_saved, last_accessed=None):
        DocumentListViewItem.__init__(self, worksheet_name, worksheet_id, last_saved, None)
        
        self.icon = Gtk.Image.new_from_file('./resources/sage_icon_2.png')
        self.icon.get_style_context().add_class('wslist_icon')
        
        self.statebox = Gtk.HBox()
        self.state = Gtk.Label()
        self.state.set_justify(Gtk.Justification.LEFT)
        self.state.set_xalign(0)
        self.state.set_hexpand(False)
        self.state.get_style_context().add_class('wslist_state')
        self.last_save = Gtk.Label()
        self.last_save.set_justify(Gtk.Justification.LEFT)
        self.last_save.set_xalign(1)
        self.last_save.set_yalign(0)
        self.last_save.set_hexpand(False)
        self.last_save.get_style_context().add_class('wslist_last_save')
        self.statebox.pack_start(self.state, True, True, 0)
        self.statebox.pack_start(self.last_save, True, True, 0)
        
        self.textbox = Gtk.VBox()
        self.textbox.pack_start(self.name, False, False, 0)
        self.textbox.pack_start(self.statebox, True, True, 0)
        
        self.box = Gtk.HBox()
        self.box.pack_start(self.icon, False, False, 0)
        self.box.pack_end(self.textbox, True, True, 0)
        self.box.get_style_context().add_class('wslist_wrapper')
        self.add(self.box)
        
        self.set_name(document_name)
        self.set_last_save(last_saved)
        self.set_state('idle.')
        
    def get_worksheet_id(self):
        return self.document_id
        
    def set_name(self, new_name):
        self.document_name = new_name
        self.name.set_text(self.document_name)
        
    def set_last_save(self, new_date):
        self.last_saved = new_date
        today = datetime.date.today()
        yesterday = datetime.date.fromtimestamp(time.time() - 86400)
        monday = datetime.date.fromtimestamp(time.time() - today.weekday()*86400)
        if self.last_saved.date() == today:
            datestring = '{:02d}:{:02d}'.format((self.last_saved.hour), (self.last_saved.minute))
        elif self.last_saved.date() == yesterday:
            datestring = 'yesterday'
        elif self.last_saved.date() >= monday:
            datestring = self.last_saved.strftime('%a')
        elif self.last_saved.year == today.year:
            datestring = self.last_saved.strftime('%d %b')
        else:
            datestring = self.last_saved.strftime('%d %b %Y')
        self.last_save.set_text(datestring)
        self.changed()
        
    def set_state(self, new_state):
        self.state.set_text(new_state)
        

class WorksheetListView(Gtk.ListBox):
    ''' List on lefthand side of app displaying all existing worksheets '''
        
    def __init__(self):
        Gtk.ListBox.__init__(self)
        
        #self.set_size_request(170, 550)
        
        self.set_sort_func(self.sort)
        self.items = dict()
        
    def add_item(self, item):
        self.items[item.get_worksheet_id()] = item
        self.prepend(item)
        self.show_all()
        
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.CONSTANT_SIZE
                     
    def do_get_preferred_width(self):
        return 250, 250
    
    def do_get_preferred_height(self):
        return 400, 400
        
    def get_row_index_by_worksheet_id(self, worksheet_id):
        index = 0
        for row in self.get_children():
            if row.get_worksheet_id() == worksheet_id:
                return index
            index += 1
            
    def get_item_by_worksheet_id(self, worksheet_id):
        try: item = self.items[worksheet_id]
        except KeyError: pass
        else: return item
            
    def sort(self, row1, row2):
        if row1.last_saved > row2.last_saved: return -1
        elif row1.last_saved < row2.last_saved: return 1
        else: return 0


class DocumentationListView(Gtk.ListBox):
    ''' This view displays available documentation or "books". '''
    
    def __init__(self):

        Gtk.ListBox.__init__(self)
        
        self.set_sort_func(self.sort)
        self.items = dict()
        
    def add_item(self, item):
        self.items[item.get_worksheet_id()] = item
        self.prepend(item)
        self.show_all()
        
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.CONSTANT_SIZE
                     
    def do_get_preferred_width(self):
        return 250, 250
    
    def do_get_preferred_height(self):
        return 400, 400
        
    def get_row_index_by_document_id(self, document_id):
        index = 0
        for row in self.get_children():
            if row.get_document_id() == document_id:
                return index
            index += 1
            
    def get_item_by_document_id(self, document_id):
        try: item = self.items[document_id]
        except KeyError: pass
        else: return item
           
    #TODO order by last accessed 
    def sort(self, row1, row2):
        if row1.last_accessed > row2.last_accessed: return -1
        elif row1.last_accessed < row2.last_accessed: return 1
        else: return 0


class Sidebar(Gtk.VPaned):
    ''' As name suggests, this is the left hand sidebar. '''

    def __init__(self):
        Gtk.VPaned.__init__(self)
        
        self.worksheet_list_view = WorksheetListView()
        self.toolbox = DocumentationListView()
        
        # TODO beide mit size request
        
        self.pack1(self.worksheet_list_view, False, False)
        self.pack2(self.toolbox, False, False)
        # TODO Center
        self.set_position(250)
        self.paned_position = self.get_position()
        
        
