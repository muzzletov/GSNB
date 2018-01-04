#!/usr/bin/env python3
# coding: utf-8

# Copyright (C) 2017, 2018 Robert Griesel
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


class ImportWorksheet(Gtk.FileChooserDialog):
    ''' File chooser for worksheets to import '''
    
    def __init__(self, main_window):
        self.action = Gtk.FileChooserAction.OPEN
        self.buttons = ('_Cancel', Gtk.ResponseType.CANCEL, '_Open', Gtk.ResponseType.OK)
        Gtk.FileChooserDialog.__init__(self, 'Import worksheet', main_window, self.action, self.buttons)
    
        for widget in self.get_header_bar().get_children():
            if isinstance(widget, Gtk.Button) and widget.get_label() == '_Open':
                widget.get_style_context().add_class(Gtk.STYLE_CLASS_SUGGESTED_ACTION)
                widget.set_can_default(True)
                widget.grab_default()

        # file filtering
        file_filter1 = Gtk.FileFilter()
        file_filter1.add_pattern('*.gsnb')
        file_filter1.set_name('GSNB Worksheets')
        self.add_filter(file_filter1)
        
        self.set_select_multiple(False)


class ExportWorksheet(Gtk.FileChooserDialog):
    ''' File chooser for worksheets export '''

    def __init__(self, main_window):
        self.action = Gtk.FileChooserAction.SAVE
        self.buttons = ('_Cancel', Gtk.ResponseType.CANCEL, '_Save', Gtk.ResponseType.OK)
        Gtk.FileChooserDialog.__init__(self, 'Export worksheet', main_window, self.action, self.buttons)
        
        self.set_do_overwrite_confirmation(True)

        for widget in self.get_header_bar().get_children():
            if isinstance(widget, Gtk.Button) and widget.get_label() == '_Save':
                widget.get_style_context().add_class(Gtk.STYLE_CLASS_SUGGESTED_ACTION)
                widget.set_can_default(True)
                widget.grab_default()


class CreateWorksheet(object):
    ''' This dialog is asking for the worksheet name. '''

    def __init__(self, main_window):
        self.builder = Gtk.Builder()
        self.builder.add_from_file('./resources/create_worksheet_dialog.ui')

        self.create_dialog = self.builder.get_object('dialog')
        self.create_dialog.set_transient_for(main_window)

        self.name_entry = self.builder.get_object('name-entry')
        self.name_entry_buffer = self.name_entry.get_buffer()
        self.cancel_button = self.builder.get_object('cancel')
        self.create_button = self.builder.get_object('apply')
        #self.create_button.set_sensitive(False)
    
        self.errors = dict()
        self.errors['name-missing'] = {'message': self.builder.get_object('error1'), 'entry': self.name_entry}
    
    def run(self):
        return self.create_dialog.run()
        
    def response(self, args):
        self.create_dialog.response(args)
        
    def show_error(self, code):
        self.errors[code]['message'].set_visible(True)
        self.errors[code]['entry'].get_style_context().add_class('error')
        
    def hide_error(self, code):
        self.errors[code]['message'].set_visible(False)
        self.errors[code]['entry'].get_style_context().remove_class('error')
        
    def __del__(self):
        self.create_dialog.destroy()
        

class RenameWorksheet(object):
    ''' This dialog is asking for the worksheet name. '''

    def __init__(self, main_window):
        self.builder = Gtk.Builder()
        self.builder.add_from_file('./resources/rename_worksheet_dialog.ui')

        self.rename_dialog = self.builder.get_object('dialog')
        self.rename_dialog.set_transient_for(main_window)

        self.name_entry = self.builder.get_object('name-entry')
        self.name_entry_buffer = self.name_entry.get_buffer()
        self.cancel_button = self.builder.get_object('cancel')
        self.rename_button = self.builder.get_object('apply')
        #self.create_button.set_sensitive(False)

        self.errors = dict()
        self.errors['name-missing'] = {'message': self.builder.get_object('error1'), 'entry': self.name_entry}
    
    def run(self):
        return self.rename_dialog.run()
        
    def response(self, args):
        self.rename_dialog.response(args)
        
    def show_error(self, code):
        self.errors[code]['message'].set_visible(True)
        self.errors[code]['entry'].get_style_context().add_class('error')
        
    def hide_error(self, code):
        self.errors[code]['message'].set_visible(False)
        self.errors[code]['entry'].get_style_context().remove_class('error')
        
    def __del__(self):
        self.rename_dialog.destroy()
        

class CloseConfirmation(Gtk.MessageDialog):
    ''' This dialog is asking users to save unsaved worksheets or discard their changes. '''

    def __init__(self, main_window, worksheets):
        Gtk.MessageDialog.__init__(self, main_window, 0, Gtk.MessageType.QUESTION)
        
        if len(worksheets) == 1:
            self.set_property('text', 'Worksheet »' + worksheets[0].get_name() + '« has unsaved changes.')
            self.format_secondary_markup('If you close GSNB without saving, these changes will be lost.')

        if len(worksheets) >= 2:
            self.set_property('text', 'There are ' + str(len(worksheets)) + ' worksheets with unsaved changes.\nSave changes before closing GSNB?')
            self.format_secondary_markup('Select the worksheets you want to save:')
            label = self.get_message_area().get_children()[1]
            label.set_xalign(0)
            label.set_halign(Gtk.Align.START)
            
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_shadow_type(Gtk.ShadowType.IN)
            scrolled_window.set_size_request(446, 112)
            self.chooser = Gtk.ListBox()
            self.chooser.set_selection_mode(Gtk.SelectionMode.NONE)
            for worksheet in worksheets:
                button = Gtk.CheckButton(worksheet.get_name())
                button.set_name('worksheet_to_save_checkbutton_' + str(worksheet.get_id()))
                button.set_active(True)
                button.set_can_focus(False)
                self.chooser.add(button)
            for listboxrow in self.chooser.get_children():
                listboxrow.set_can_focus(False)
            scrolled_window.add(self.chooser)
                
            secondary_text_label = Gtk.Label('If you close GSNB without saving, all changes will be lost.')
            self.message_area = self.get_message_area()
            self.message_area.pack_start(scrolled_window, False, False, 0)
            self.message_area.pack_start(secondary_text_label, False, False, 0)
            self.message_area.show_all()

        self.add_buttons('Close _without Saving', Gtk.ResponseType.NO, '_Cancel', Gtk.ResponseType.CANCEL, '_Save', Gtk.ResponseType.YES)
        self.set_default_response(Gtk.ResponseType.YES)
        

