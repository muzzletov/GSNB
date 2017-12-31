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
from gi.repository import Gio
from gi.repository import GLib


class HeaderBar(Gtk.Paned):
    ''' Title bar of the app, contains always visible controls, 
        worksheet title and state (computing, idle, ...) '''
        
    def __init__(self, button_layout, shows_app_menu):
        Gtk.Paned.__init__(self)
        
        show_close_button = True if (button_layout.find('close') < button_layout.find(':') and button_layout.find('close') >= 0) else False
        self.hb_left = HeaderBarLeft(show_close_button)
        
        show_close_button = True if (button_layout.find('close') > button_layout.find(':') and button_layout.find('close') >= 0) else False
        self.hb_right = HeaderBarRight(show_close_button, not shows_app_menu)
        
        self.pack1(self.hb_left, False, False)
        self.pack2(self.hb_right, True, False)
        
    def set_title(self, text):
        self.hb_right.set_title(text)

    def set_subtitle(self, text):
        self.hb_right.set_subtitle(text)

    def get_subtitle(self):
        return self.hb_right.get_subtitle()
        
    def activate_stop_button(self):
        self.hb_right.stop_button.set_sensitive(True)

    def deactivate_stop_button(self):
        self.hb_right.stop_button.set_sensitive(False)

    def activate_up_button(self):
        self.hb_right.up_button.set_sensitive(True)

    def deactivate_up_button(self):
        self.hb_right.up_button.set_sensitive(False)

    def activate_down_button(self):
        self.hb_right.down_button.set_sensitive(True)

    def deactivate_down_button(self):
        self.hb_right.down_button.set_sensitive(False)

    def activate_save_button(self):
        self.hb_right.save_button.set_sensitive(True)

    def deactivate_save_button(self):
        self.hb_right.save_button.set_sensitive(False)


class HeaderBarLeft(Gtk.HeaderBar):

    def __init__(self, show_close_button):
        Gtk.HeaderBar.__init__(self)

        self.set_show_close_button(show_close_button)

        self.create_buttons()

    def create_buttons(self):
        self.ws_add_wrapper = Gtk.HBox()
        self.create_ws_button = Gtk.Button.new_from_icon_name('document-new-symbolic', Gtk.IconSize.BUTTON)
        self.create_ws_button.set_tooltip_text('Create new worksheet')
        self.create_ws_button.set_focus_on_click(False)
        self.pack_start(self.create_ws_button)
        self.import_ws_button = Gtk.Button.new_from_icon_name('document-open-symbolic', Gtk.IconSize.BUTTON)
        self.import_ws_button.set_tooltip_text('Import worksheet')
        self.import_ws_button.set_focus_on_click(False)
        self.pack_start(self.import_ws_button)

        self.search_button = Gtk.Button.new_from_icon_name('system-search-symbolic', Gtk.IconSize.BUTTON)
        self.search_button.set_tooltip_text('Search')
        self.search_button.set_focus_on_click(False)
        #self.search_button.set_sensitive(False)
        #self.pack_end(self.search_button)

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.CONSTANT_SIZE
                     
    def do_get_preferred_width(self):
        return 250, 250
    

class HeaderBarRight(Gtk.HeaderBar):

    def __init__(self, show_close_button, show_appmenu):
        Gtk.HeaderBar.__init__(self)

        self.set_show_close_button(show_close_button)
        self.props.title = ''
        
        Gtk.IconTheme.append_search_path(Gtk.IconTheme.get_default(), './resources');
        self.create_buttons(show_appmenu)

    def create_buttons(self, show_appmenu=False):
        self.add_cell_box = Gtk.HBox()
        self.add_cell_box.get_style_context().add_class('linked')

        self.add_codecell_button = Gtk.Button.new_from_icon_name('add-codecell-symbolic', Gtk.IconSize.BUTTON)
        self.add_codecell_button.set_tooltip_text('Add code cell below (Alt+Return)')
        self.add_codecell_button.set_focus_on_click(False)
        self.add_cell_box.add(self.add_codecell_button)
        self.add_markdowncell_button = Gtk.Button.new_from_icon_name('add-markdowncell-symbolic', Gtk.IconSize.BUTTON)
        self.add_markdowncell_button.set_tooltip_text('Add markdown cell below (Ctrl+M)')
        self.add_markdowncell_button.set_focus_on_click(False)
        self.add_cell_box.add(self.add_markdowncell_button)
        
        self.move_cell_box = Gtk.HBox()
        self.move_cell_box.get_style_context().add_class('linked')
        self.up_button = Gtk.Button.new_from_icon_name('up-button-symbolic', Gtk.IconSize.BUTTON)
        self.up_button.set_tooltip_text('Move cell up (Ctrl+Up)')
        self.up_button.set_focus_on_click(False)
        self.up_button.set_sensitive(False)
        self.move_cell_box.add(self.up_button)
        self.down_button = Gtk.Button.new_from_icon_name('down-button-symbolic', Gtk.IconSize.BUTTON)
        self.down_button.set_tooltip_text('Move cell down (Ctrl+Down)')
        self.down_button.set_focus_on_click(False)
        self.down_button.set_sensitive(False)
        self.move_cell_box.add(self.down_button)
        self.delete_button = Gtk.Button.new_from_icon_name('edit-delete-symbolic', Gtk.IconSize.BUTTON)
        self.delete_button.set_tooltip_text('Delete cell (Ctrl+Backspace)')
        self.delete_button.set_focus_on_click(False)
        self.move_cell_box.add(self.delete_button)

        self.eval_box = Gtk.HBox()
        self.eval_box.get_style_context().add_class('linked')
        self.eval_button = Gtk.Button.new_from_icon_name('eval-button-symbolic', Gtk.IconSize.BUTTON)
        self.eval_button.set_tooltip_text('Evaluate Cell (Shift+Return)')
        self.eval_button.set_focus_on_click(False)
        self.eval_box.add(self.eval_button)
        self.eval_nc_button = Gtk.Button.new_from_icon_name('eval-nc-button-symbolic', Gtk.IconSize.BUTTON)
        self.eval_nc_button.set_tooltip_text('Evaluate Cell, then Go to next Cell (Ctrl+Return)')
        self.eval_nc_button.set_focus_on_click(False)
        self.eval_box.add(self.eval_nc_button)
        self.stop_button = Gtk.Button.new_from_icon_name('media-playback-stop-symbolic', Gtk.IconSize.BUTTON)
        self.stop_button.set_tooltip_text('Stop Evaluation (Ctrl+H)')
        self.stop_button.set_focus_on_click(False)
        self.stop_button.set_sensitive(False)
        self.eval_box.add(self.stop_button)

        self.menu_button = Gtk.MenuButton()
        image = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.BUTTON)
        self.menu_button.set_image(image)
        self.menu_button.set_focus_on_click(False)
        self.builder = Gtk.Builder()
        self.builder.add_from_file('./resources/worksheet_menu.ui')
        self.options_menu = self.builder.get_object('options-menu')
        
        if show_appmenu == True:
            meta_section = Gio.Menu()
            item = Gio.MenuItem.new('Keyboard Shortcuts', 'app.show_shortcuts_window')
            meta_section.append_item(item)
            item = Gio.MenuItem.new('About', 'app.show_about_dialog')
            meta_section.append_item(item)
            item = Gio.MenuItem.new('Quit', 'app.quit')
            meta_section.append_item(item)
            self.options_menu.append_section(None, meta_section)
        
        self.menu_button.set_menu_model(self.options_menu)
        
        self.save_button = Gtk.Button()
        self.save_button.set_label('Save')
        self.save_button.set_tooltip_text('Save the currently opened file')
        self.save_button.set_focus_on_click(False)

    def show_buttons(self):
        self.pack_start(self.add_cell_box)
        self.pack_start(self.move_cell_box)
        self.pack_start(self.eval_box)
        self.pack_end(self.menu_button)
        self.pack_end(self.save_button)

    def hide_buttons(self):
        self.remove(self.add_cell_box)
        self.remove(self.move_cell_box)
        self.remove(self.eval_box)
        self.remove(self.menu_button)
        self.remove(self.save_button)
        self.show_all()
        
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.CONSTANT_SIZE
                     
    def do_get_preferred_width(self):
        return 520, 520
        
        
