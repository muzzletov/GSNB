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
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio
import viewgtk.viewgtk as view
import controller.controller_cell as cellcontroller
import controller.controller_worksheet as worksheetcontroller
import controller.controller_settings as settingscontroller
import sys
import model.model as model
import time
import os
import tarfile
import tempfile
import pickle
import backend.backendcontroller as backendcontroller


class MainApplicationController(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self)
        
    def do_activate(self):
        ''' Everything starts here. '''
        
        # load settings
        self.settings = settingscontroller.Settings()
        
        self.construct_application_menu()
        self.construct_worksheet_menu()
        
        # init compute queue
        self.backend_controller_sagemath = backendcontroller.BackendControllerSageMath()
        self.backend_controller_markdown = backendcontroller.BackendControllerMarkdown()
        
        # controllers
        self.worksheet_controllers = dict()
        self.cell_controllers = dict()

        # init model
        self.notebook = model.Notebook()
        self.observe_notebook()
        
        # init view
        self.main_window = view.MainWindow(self)
        self.main_window.set_default_size(self.settings.data['window_state']['width'], 
                                          self.settings.data['window_state']['height'])
                                          
        if self.settings.data['window_state']['is_maximized']: self.main_window.maximize()
        else: self.main_window.unmaximize()
        if self.settings.data['window_state']['is_fullscreen']: self.main_window.fullscreen()
        else: self.main_window.unfullscreen()
        
        self.main_window.show_all()
        self.main_window.paned.set_position(self.settings.data['window_state']['paned_position'])
        self.main_window.sidebar.set_position(self.settings.data['window_state'].get('sidebar_paned_position', int(self.main_window.sidebar.get_allocated_height()/2)))
        self.window_mode = None
        self.activate_blank_state_mode()
        
        # populate app
        self.notebook.populate_from_path(os.path.expanduser('~') + '/.sage/gsnb')
        self.notebook.populate_documentation()
        
        # watch changes in view
        self.observe_main_window()
        
        # select first worksheet in list
        row = self.main_window.sidebar.worksheet_list_view.get_row_at_index(0)
        self.main_window.sidebar.worksheet_list_view.select_row(row)

        # to watch for cursor movements
        self.cursor_position = {'cell': None, 'cell_position': None, 'cell_size': None, 'position': None}
        
    '''
    *** notification handlers, get called by observed objects in model
    '''

    def change_notification(self, change_code, notifying_object, parameter):
    
        if change_code == 'new_worksheet':
            worksheet = parameter
            
            # add_worksheet_view
            worksheet_view = view.WorksheetView()
            self.main_window.add_worksheet_view(worksheet, worksheet_view)

            # observe changes in this worksheet
            self.worksheet_controllers[worksheet] = worksheetcontroller.WorksheetController(worksheet, worksheet_view, self)
            
            # add to sidebar, observe clicks
            if isinstance(worksheet, model.NormalWorksheet):
                wslist_item = view.NormalWorksheetListViewItem(worksheet, worksheet.get_last_saved())
                self.main_window.sidebar.worksheet_list_view.add_item(wslist_item)
                self.activate_worksheet_mode()
            elif isinstance(worksheet, model.DocumentationWorksheet):
                doclist_item = view.DocumentationWorksheetListViewItem(worksheet, worksheet.get_last_saved(), worksheet.get_last_accessed())
                self.main_window.sidebar.documentation_list_view.add_item(doclist_item)
            
        if change_code == 'worksheet_removed':
            worksheet = parameter
            self.remove_from_sidebar(worksheet)
            self.main_window.remove_worksheet_view(worksheet)
        
        if change_code == 'changed_active_worksheet':
            worksheet = parameter
            
            self.activate_worksheet_mode()

            # change title, subtitle in headerbar
            self.update_title(worksheet)
            self.update_subtitle(worksheet)
            self.update_save_button()
            self.update_hamburger_menu()
            
            # change worksheet_view
            self.main_window.activate_worksheet_view(worksheet)
            if worksheet.get_active_cell() != None: worksheet.set_active_cell(worksheet.get_active_cell())
            self.update_stop_button()

    '''
    *** main observer functions
    '''

    def observe_notebook(self):
        self.notebook.register_observer(self)
        self.notebook.register_observer(self.backend_controller_sagemath)
        
    def observe_main_window(self):
        hb_left = self.main_window.headerbar.hb_left
        hb_left.create_ws_button.connect('clicked', self.on_create_ws_button_click)
        hb_left.import_ws_button.connect('clicked', self.on_import_ws_button_click)
        
        hb_right = self.main_window.headerbar.hb_right
        hb_right.add_codecell_button.connect('clicked', self.on_add_codecell_button_click)
        hb_right.add_markdowncell_button.connect('clicked', self.on_add_markdowncell_button_click)
        hb_right.down_button.connect('clicked', self.on_down_button_click)
        hb_right.up_button.connect('clicked', self.on_up_button_click)
        hb_right.delete_button.connect('clicked', self.on_delete_button_click)
        hb_right.eval_button.connect('clicked', self.on_eval_button_click)
        hb_right.eval_nc_button.connect('clicked', self.on_eval_nc_button_click)
        hb_right.stop_button.connect('clicked', self.on_stop_button_click)
        hb_right.save_button.connect('clicked', self.on_save_ws_button_click)
        hb_right.revert_button.connect('clicked', self.on_revert_ws_button_click)

        self.main_window.connect('key-press-event', self.observe_keyboard_keypress_events)
        self.main_window.sidebar.worksheet_list_view.connect('row-selected', self.on_worksheet_list_click)
        self.main_window.sidebar.documentation_list_view.connect('row-selected', self.on_documentation_list_click)
        self.main_window.connect('size-allocate', self.on_window_size_allocate)
        self.main_window.connect('window-state-event', self.on_window_state_event)
        self.main_window.connect('delete-event', self.on_window_close)
        self.main_window.sidebar.connect('size-allocate', self.on_ws_view_size_allocate)
    
    def observe_result_view_revealer(self, result_view_revealer):
        result_view_revealer.connect('button-press-event', self.result_on_mouse_click)
        result_view_revealer.connect('size-allocate', self.result_view_on_size_allocate)
        
    '''
    *** reconstruct window when worksheet is open / no worksheet present
    '''

    def activate_worksheet_mode(self):
        if self.window_mode != 'worksheet':
            self.window_mode = 'worksheet'
            hb_right = self.main_window.headerbar.hb_right
            hb_right.show_buttons()
            self.main_window.worksheet_view_wrapper.remove_view(self.blank_state_view)

    def activate_blank_state_mode(self):
        if self.window_mode != 'blank_state':
            self.window_mode = 'blank_state'
            self.main_window.headerbar.set_title('Welcome to GSNB')
            self.main_window.headerbar.set_subtitle('')
            hb_right = self.main_window.headerbar.hb_right
            hb_right.hide_buttons()
            
            self.blank_state_view = view.BlankStateView()
            self.main_window.worksheet_view_wrapper.set_worksheet_view(self.blank_state_view)
            self.blank_state_view.create_ws_link.connect('clicked', self.on_create_ws_button_click)
            self.blank_state_view.import_ws_link.connect('clicked', self.on_import_ws_button_click)

    '''
    *** evaluation / save state indicators
    '''
    
    def update_stop_button(self):
        worksheet = self.notebook.active_worksheet
        if worksheet.get_busy_cell_count() > 0:
            self.main_window.headerbar.activate_stop_button()
        else:
            self.main_window.headerbar.deactivate_stop_button()
            
    def update_save_button(self):
        worksheet = self.notebook.get_active_worksheet()
        if worksheet.get_save_state() == 'modified':
            self.main_window.headerbar.activate_save_button()
            self.main_window.headerbar.activate_revert_button()
        else:
            self.main_window.headerbar.deactivate_save_button()
            self.main_window.headerbar.deactivate_revert_button()
            
        if isinstance(worksheet, model.NormalWorksheet):
            self.main_window.headerbar.activate_documentation_mode()
        else:
            self.main_window.headerbar.deactivate_documentation_mode()
            
    def update_hamburger_menu(self):
        worksheet = self.notebook.get_active_worksheet()
        if isinstance(worksheet, model.NormalWorksheet):
            self.delete_ws_action.set_enabled(True)
            self.rename_ws_action.set_enabled(True)
        elif isinstance(worksheet, model.DocumentationWorksheet):
            self.delete_ws_action.set_enabled(False)
            self.rename_ws_action.set_enabled(False)
            
    def update_up_down_buttons(self):
        worksheet = self.notebook.get_active_worksheet()
        if worksheet != None:
            active_cell = worksheet.get_active_cell()
            if active_cell != None:
                cell_position = active_cell.get_worksheet_position()
                cell_count = worksheet.get_cell_count()
                if cell_position == cell_count - 1:
                    self.main_window.headerbar.deactivate_down_button()
                else:
                    self.main_window.headerbar.activate_down_button()
                if cell_position == 0:
                    self.main_window.headerbar.deactivate_up_button()
                else:
                    self.main_window.headerbar.activate_up_button()

    def update_subtitle(self, worksheet):
        
        busy_cell_count = worksheet.get_busy_cell_count()
        if busy_cell_count > 0:
            plural = 's' if busy_cell_count > 1 else ''
            subtitle = 'evaluating ' + str(busy_cell_count) + ' cell' + plural + '.'
        elif worksheet.get_kernel_state() == 'starting':
            subtitle = 'starting kernel.'
        else:
            subtitle = 'idle.'

        if isinstance(worksheet, model.NormalWorksheet):
            item = self.main_window.sidebar.worksheet_list_view.get_item_by_worksheet(worksheet)
        else:
            item = self.main_window.sidebar.documentation_list_view.get_item_by_worksheet(worksheet)
        item.set_state(subtitle)
        if worksheet == self.notebook.get_active_worksheet():
            if self.main_window.headerbar.get_subtitle() != subtitle:
                self.main_window.headerbar.set_subtitle(subtitle)

    def update_title(self, worksheet):
        if isinstance(worksheet, model.NormalWorksheet):
            save_state = '*' if worksheet.get_save_state() == 'modified' else ''
            item = self.main_window.sidebar.worksheet_list_view.get_item_by_worksheet(worksheet)
            item.set_name(save_state + worksheet.get_name())
        elif isinstance(worksheet, model.DocumentationWorksheet):
            save_state = ''
            item = self.main_window.sidebar.documentation_list_view.get_item_by_worksheet(worksheet)
            item.set_name(save_state + worksheet.get_name())
        if worksheet == self.notebook.active_worksheet:
            self.main_window.headerbar.set_title(save_state + worksheet.get_name())
        
    def update_sidebar_save_date(self, worksheet):
        if isinstance(worksheet, model.NormalWorksheet):
            item = self.main_window.sidebar.worksheet_list_view.get_item_by_worksheet(worksheet)
            item.set_last_save(worksheet.get_last_saved())
        
    def remove_from_sidebar(self, worksheet):
        if isinstance(worksheet, model.NormalWorksheet):
            item = self.main_window.sidebar.worksheet_list_view.get_item_by_worksheet(worksheet)
            self.main_window.sidebar.worksheet_list_view.remove(item)

    '''
    *** signal handlers: results
    '''
    
    def result_on_mouse_click(self, result_view_revealer, click_event):
    
        if click_event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            cell_view = result_view_revealer.cell_view
            cell = cell_view.get_cell()
            worksheet = cell.get_worksheet()
            cell.remove_result()
            worksheet.set_active_cell(cell)
            
        elif click_event.type == Gdk.EventType.BUTTON_PRESS:
            cell_view = result_view_revealer.cell_view
            cell = cell_view.get_cell()
            worksheet = cell.get_worksheet()
            worksheet.set_active_cell(cell)
            
        return False
        
    '''
    *** signal handlers: main window
    '''
    
    def on_create_ws_button_click(self, button_object=None):
        ''' signal handler, create worksheet '''
        
        def update_create_button():
            if len(self.create_ws_dialog.name_entry.get_text()) > 0:
                self.create_ws_dialog.create_button.set_sensitive(True)
            else:
                self.create_ws_dialog.create_button.set_sensitive(False)
                
        def update_name_error():
            if len(self.create_ws_dialog.name_entry.get_text()) > 0:
                if self.create_ws_dialog.errors['name-missing']['entry'].get_style_context().has_class('error'):
                    self.create_ws_dialog.hide_error('name-missing')
            
        def on_name_entry(buffer, position, chars, n_chars=None):
            update_name_error()
            update_create_button()

        def wscreate_on_cancel_button_clicked(cancel_button):
            del(self.create_ws_dialog)

        def wscreate_on_create_button_clicked(create_button):
            name = self.create_ws_dialog.name_entry.get_text().strip()
            if len(name) > 0:
                worksheet = model.NormalWorksheet(self.notebook)
                worksheet.set_id(self.notebook.find_unused_ws_id())
                worksheet.set_name(self.create_ws_dialog.name_entry.get_text().strip())
                pathname = self.notebook.get_pathname() + '/' + str(worksheet.get_id())
                worksheet.set_pathname(pathname)
                self.notebook.add_worksheet(worksheet)
                worksheet.create_cell(0, '', activate=True)
                worksheet.save_to_disk()

                row = self.main_window.sidebar.worksheet_list_view.get_row_at_index(0)
                self.main_window.sidebar.worksheet_list_view.select_row(row)
                del(self.create_ws_dialog)
            else:
                self.create_ws_dialog.show_error('name-missing')

        self.create_ws_dialog = view.dialogs.CreateWorksheet(self.main_window)
        self.create_ws_dialog.cancel_button.connect('clicked', wscreate_on_cancel_button_clicked)
        self.create_ws_dialog.create_button.connect('clicked', wscreate_on_create_button_clicked)
        self.create_ws_dialog.name_entry_buffer.connect('inserted-text', on_name_entry)
        self.create_ws_dialog.name_entry_buffer.connect('deleted-text', on_name_entry)
        update_create_button()
        self.create_ws_dialog.name_entry.set_text('Untitled' + self.notebook.get_untitled_postfix())
        self.create_ws_dialog.run()
    
    def on_import_ws_button_click(self, button_object=None):
        ''' signal handler, import worksheet '''
        
        dialog = view.dialogs.ImportWorksheet(self.main_window)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            tar = tarfile.open(filename, 'r:bz2')
            more_to_import = True
            count = 0
            while more_to_import:
                try: tar.getmember(str(count))
                except KeyError: more_to_import = False
                else:
                    td_path = tempfile.mkdtemp()
                    tar.extractall(td_path)
                    worksheet = model.NormalWorksheet(self.notebook)
                    worksheet.set_id(self.notebook.find_unused_ws_id())
                    pathname = self.notebook.get_pathname() + '/' + str(worksheet.get_id())
                    os.rename(td_path + '/' + str(count), pathname)
                    worksheet.set_pathname(pathname)
                    try: meta_filehandle = open(worksheet.pathname + '/worksheet_conf.pickle', 'rb')
                    except IOError: pass
                    else: 
                        meta = pickle.load(meta_filehandle)
                        worksheet.set_name(meta['name'])
                    worksheet.save_meta_to_disk()
                    self.notebook.add_worksheet(worksheet)
                    row_index = self.main_window.sidebar.worksheet_list_view.get_row_index_by_worksheet(worksheet)
                    row = self.main_window.sidebar.worksheet_list_view.get_row_at_index(row_index)
                    self.main_window.sidebar.worksheet_list_view.select_row(row)
                    count += 1

        dialog.destroy()
        
    def on_worksheet_list_click(self, wslist_view, wslist_item_view):
        ''' signal handler, activate worksheet '''
        
        if wslist_item_view != None:
            self.main_window.sidebar.documentation_list_view.unselect_all()
            worksheet = wslist_item_view.get_worksheet()
            self.notebook.set_active_worksheet(worksheet)
            worksheet.populate_cells()
            
    def on_documentation_list_click(self, wslist_view, wslist_item_view):
        ''' signal handler, activate documentation worksheet '''

        if wslist_item_view != None:
            self.main_window.sidebar.worksheet_list_view.unselect_all()
            worksheet = wslist_item_view.get_worksheet()
            self.notebook.set_active_worksheet(worksheet)
            worksheet.populate_cells()
        
    def on_add_codecell_button_click(self, button_object=None):
        ''' signal handler, add codecell below active cell '''
        
        worksheet = self.notebook.get_active_worksheet()
        position = worksheet.get_active_cell().get_worksheet_position() + 1
        worksheet.create_cell(position, '', activate=True, set_unmodified=False)
                
    def on_add_markdowncell_button_click(self, button_object=None):
        ''' signal handler, add markdown cell below active cell '''
        
        worksheet = self.notebook.get_active_worksheet()
        position = worksheet.get_active_cell().get_worksheet_position() + 1
        worksheet.create_markdowncell(position, '', activate=True, set_unmodified=False)
                
    def on_down_button_click(self, button_object=None):
        ''' signal handler, move active cell down '''
        
        worksheet = self.notebook.get_active_worksheet()
        position = worksheet.get_active_cell().get_worksheet_position()
        cell_count = worksheet.get_cell_count()
        if position < cell_count:
            worksheet.move_cell(position, position + 1)

    def on_up_button_click(self, button_object=None):
        ''' signal handler, move active cell up '''
        
        worksheet = self.notebook.get_active_worksheet()
        position = worksheet.get_active_cell().get_worksheet_position()
        cell_count = worksheet.get_cell_count()
        if position > 0:
            worksheet.move_cell(position, position - 1)
            
    def on_delete_button_click(self, button_object=None):
        ''' signal handler, delete active cell '''
        
        worksheet = self.notebook.get_active_worksheet()
        cell = worksheet.get_active_cell()
        prev_cell = worksheet.get_prev_cell(cell)
        if prev_cell != None: 
            cell.remove_result()
            worksheet.set_active_cell(prev_cell)
            #prev_cell.place_cursor(prev_cell.get_iter_at_line(prev_cell.get_line_count() - 1))
            prev_cell.place_cursor(prev_cell.get_start_iter())
            worksheet.remove_cell(cell)
        else:
            next_cell = worksheet.get_next_cell(cell)
            if next_cell != None:
                cell.remove_result()
                worksheet.set_active_cell(next_cell)
                next_cell.place_cursor(next_cell.get_start_iter())
                worksheet.remove_cell(cell)
            else:
                cell.remove_result()
                worksheet.remove_cell(cell)
                worksheet.create_cell('last', '', activate=True)
            
    def on_eval_button_click(self, button_object=None):
        ''' signal handler, evaluate active cell '''

        active_cell = self.notebook.active_worksheet.active_cell
        if not (isinstance(active_cell, model.MarkdownCell) and active_cell.get_result() != None):
            active_cell.evaluate()
        
    def on_eval_nc_button_click(self, button_object=None):
        ''' signal handler, evaluate active cell, go to next cell '''

        worksheet = self.notebook.active_worksheet
        active_cell = worksheet.active_cell

        if not (isinstance(active_cell, model.MarkdownCell) and active_cell.get_result() != None):
            active_cell.evaluate()
        new_active_cell = worksheet.get_next_visible_cell(active_cell)
        if not new_active_cell == None:
            worksheet.set_active_cell(new_active_cell)
            new_active_cell.place_cursor(new_active_cell.get_start_iter())
        else:
            worksheet.create_cell()
            new_active_cell = worksheet.get_next_visible_cell(active_cell)
            worksheet.set_active_cell(new_active_cell)
            new_active_cell.place_cursor(new_active_cell.get_start_iter())
            
    def on_stop_button_click(self, button_object=None):
        ''' signal handler, stop evaluation '''

        self.notebook.active_worksheet.stop_evaluation()

    def on_save_ws_button_click(self, button_object=None):
        ''' signal handler, save active worksheet to disk '''
        
        worksheet = self.notebook.get_active_worksheet()
        if isinstance(worksheet, model.NormalWorksheet):
            worksheet.save_to_disk()
        
    def on_revert_ws_button_click(self, button_object=None):
        ''' signal handler, save active worksheet to disk '''
        
        worksheet = self.notebook.get_active_worksheet()
        if isinstance(worksheet, model.DocumentationWorksheet):
            worksheet.remove_all_cells()
            worksheet.populate_cells()
        
    def on_window_size_allocate(self, main_window, window_size):
        ''' signal handler, update window size variables '''
        
        if not(main_window.is_maximized) and not(main_window.is_fullscreen):
            main_window.current_width, main_window.current_height = main_window.get_size()
            main_window.set_default_size(main_window.current_width, main_window.current_height)
            
    def on_ws_view_size_allocate(self, paned, paned_size):
        ''' signal handler, update worksheet/ws_list seperator position.
            called on worksheet list size allocation. '''
        
        self.main_window.paned_position = self.main_window.paned.get_position()
            
    def on_window_state_event(self, main_window, state_event):
        ''' signal handler, update window state variables '''
    
        main_window.is_maximized = not((state_event.new_window_state & Gdk.WindowState.MAXIMIZED) == 0)
        main_window.is_fullscreen = not((state_event.new_window_state & Gdk.WindowState.FULLSCREEN) == 0)
        return False
        
    def save_window_state(self):
        ''' save window state variables '''

        main_window = self.main_window
        self.settings.data['window_state']['width'] = main_window.current_width
        self.settings.data['window_state']['height'] = main_window.current_height
        self.settings.data['window_state']['is_maximized'] = main_window.is_maximized
        self.settings.data['window_state']['is_fullscreen'] = main_window.is_fullscreen
        self.settings.data['window_state']['paned_position'] = main_window.paned_position
        self.settings.data['window_state']['sidebar_paned_position'] = main_window.sidebar.get_position()
        self.settings.pickle()
        
    def on_window_close(self, main_window, event=None):
        ''' signal handler, ask user to save unsaved worksheets or discard changes '''
        
        worksheets = self.notebook.get_unsaved_worksheets()
        if len(worksheets) == 0: 
            self.save_window_state()
            return False

        self.save_changes_dialog = view.dialogs.CloseConfirmation(self.main_window, worksheets)
        response = self.save_changes_dialog.run()
        if response == Gtk.ResponseType.NO:
            self.save_changes_dialog.destroy()
            self.save_window_state()
            return False
        elif response == Gtk.ResponseType.YES:
            selected_worksheets_ids = list()
            if len(worksheets) == 1:
                selected_worksheets_ids.append(worksheets[0].get_id())
            else:
                for child in self.save_changes_dialog.chooser.get_children():
                    if child.get_child().get_active():
                        selected_worksheets_ids.append(int(child.get_child().get_name()[30:]))
            for worksheet in worksheets:
                if worksheet.get_id() in selected_worksheets_ids:
                    worksheet.save_to_disk()
            self.save_changes_dialog.destroy()
            self.save_window_state()
            return False
        else:
            self.save_changes_dialog.destroy()
            return True

    '''
    *** application menu
    '''

    def construct_application_menu(self):

        # show classic gnome app menu
        if self.settings.gtksettings.get_property('gtk-shell-shows-app-menu') == True:
            app_menu = Gio.Menu()

            #preferences_section = Gio.Menu()
            #item = Gio.MenuItem.new('Preferences', 'app.show_preferences_window')
            #preferences_section.append_item(item)

            meta_section = Gio.Menu()
            item = Gio.MenuItem.new('Keyboard Shortcuts', 'app.show_shortcuts_window')
            meta_section.append_item(item)
            item = Gio.MenuItem.new('About', 'app.show_about_dialog')
            meta_section.append_item(item)
            item = Gio.MenuItem.new('Quit', 'app.quit')
            meta_section.append_item(item)

            #app_menu.append_section(None, preferences_section)
            app_menu.append_section(None, meta_section)

            self.set_app_menu(app_menu)

            quit_action = Gio.SimpleAction.new('quit', None)
            quit_action.connect('activate', self.on_appmenu_quit)
            self.add_action(quit_action)

            show_about_dialog_action = Gio.SimpleAction.new('show_about_dialog', None)
            show_about_dialog_action.connect('activate', self.on_appmenu_show_about_dialog)
            self.add_action(show_about_dialog_action)

            show_shortcuts_window_action = Gio.SimpleAction.new('show_shortcuts_window', None)
            show_shortcuts_window_action.connect('activate', self.on_appmenu_show_shortcuts_window)
            self.add_action(show_shortcuts_window_action)

    def on_appmenu_show_shortcuts_window(self, action, parameter=''):
        ''' show popup with a list of keyboard shortcuts. '''
        
        self.builder = Gtk.Builder()
        self.builder.add_from_file('./resources/shortcuts_window.ui')
        self.shortcuts_window = self.builder.get_object('shortcuts-window')
        self.shortcuts_window.set_transient_for(self.main_window)
        self.shortcuts_window.show_all()
        
    def on_appmenu_show_about_dialog(self, action, parameter=''):
        ''' show popup with some information about the app. '''
        
        self.about_dialog = Gtk.AboutDialog()
        self.about_dialog.set_transient_for(self.main_window)
        self.about_dialog.set_modal(True)
        self.about_dialog.set_program_name('GSNB')
        self.about_dialog.set_version('0.0.1')
        self.about_dialog.set_copyright('Copyright © 2017 - the GSNB developers')
        self.about_dialog.set_comments('GSNB is a notebook type interface to Python and SageMath. It is designed to make exploring mathematics easy and fun.')
        self.about_dialog.set_license_type(Gtk.License.GPL_3_0)
        self.about_dialog.set_website('https://github.com/cvfosammmm/GSNB')
        self.about_dialog.set_website_label('github.com/cvfosammmm/GSNB')
        self.about_dialog.set_authors(('Robert Griesel',))
        self.about_dialog.show_all()
        
    def on_appmenu_quit(self, action=None, parameter=''):
        ''' quit application, show save dialog if unsaved worksheets present. '''
        
        if not self.on_window_close(self.main_window):
            self.quit()
        
    '''
    *** worksheet menu
    '''
    
    def construct_worksheet_menu(self):
        self.restart_kernel_action = Gio.SimpleAction.new('restart_kernel', None)
        self.restart_kernel_action.connect('activate', self.on_wsmenu_restart_kernel)
        self.add_action(self.restart_kernel_action)
        self.rename_ws_action = Gio.SimpleAction.new('rename_worksheet', None)
        self.rename_ws_action.connect('activate', self.on_wsmenu_rename)
        self.add_action(self.rename_ws_action)
        self.delete_ws_action = Gio.SimpleAction.new('delete_worksheet', None)
        self.delete_ws_action.connect('activate', self.on_wsmenu_delete)
        self.add_action(self.delete_ws_action)
        self.export_gsnb_ws_action = Gio.SimpleAction.new('export_gsnb_worksheet', None)
        self.export_gsnb_ws_action.connect('activate', self.on_wsmenu_gsnb_export)
        self.add_action(self.export_gsnb_ws_action)

        #preferences_section = Gio.Menu()
        #item = Gio.MenuItem.new('Preferences', 'app.show_preferences_window')
        #preferences_section.append_item(item)
        if self.settings.gtksettings.get_property('gtk-shell-shows-app-menu') == False:
            quit_action = Gio.SimpleAction.new('quit', None)
            quit_action.connect('activate', self.on_appmenu_quit)
            self.add_action(quit_action)
            show_about_dialog_action = Gio.SimpleAction.new('show_about_dialog', None)
            show_about_dialog_action.connect('activate', self.on_appmenu_show_about_dialog)
            self.add_action(show_about_dialog_action)
            show_shortcuts_window_action = Gio.SimpleAction.new('show_shortcuts_window', None)
            show_shortcuts_window_action.connect('activate', self.on_appmenu_show_shortcuts_window)
            self.add_action(show_shortcuts_window_action)
        
    def on_wsmenu_restart_kernel(self, action=None, parameter=None):
        ''' signal handler, restart kernel for active worksheet '''

        self.notebook.active_worksheet.restart_kernel()
        
    def on_wsmenu_gsnb_export(self, action=None, parameter=None):
        ''' signal handler, export worksheet in gsnb format '''
        
        worksheet = self.notebook.get_active_worksheet()
        dialog = view.dialogs.ExportWorksheet(self.main_window)
        dialog.set_current_name(worksheet.get_name().lower() + '.gsnb')
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_current_name()
            folder = dialog.get_current_folder()
            worksheet.save_to_disk()
            worksheet.export_gsnb(folder + '/' + filename)

        dialog.destroy()

    def on_wsmenu_rename(self, action, parameter=None):
        worksheet = self.notebook.get_active_worksheet()

        def update_rename_button():
            if len(self.rename_ws_dialog.name_entry.get_text()) > 0:
                self.rename_ws_dialog.rename_button.set_sensitive(True)
            else:
                self.rename_ws_dialog.rename_button.set_sensitive(False)
                
        def update_name_error():
            if len(self.rename_ws_dialog.name_entry.get_text()) > 0:
                if self.rename_ws_dialog.errors['name-missing']['entry'].get_style_context().has_class('error'):
                    self.rename_ws_dialog.hide_error('name-missing')
            
        def on_name_entry(buffer, position, chars, n_chars=None):
            update_name_error()
            update_rename_button()

        def wsrename_on_cancel_button_clicked(cancel_button):
            del(self.rename_ws_dialog)

        def wsrename_on_rename_button_clicked(rename_button):
            name = self.rename_ws_dialog.name_entry.get_text().strip()
            if len(name) > 0:
                worksheet.set_name(self.rename_ws_dialog.name_entry.get_text().strip())
                worksheet.save_meta_to_disk()
                del(self.rename_ws_dialog)
            else:
                self.rename_ws_dialog.show_error('name-missing')

        self.rename_ws_dialog = view.dialogs.RenameWorksheet(self.main_window)
        self.rename_ws_dialog.cancel_button.connect('clicked', wsrename_on_cancel_button_clicked)
        self.rename_ws_dialog.rename_button.connect('clicked', wsrename_on_rename_button_clicked)
        self.rename_ws_dialog.name_entry_buffer.connect('inserted-text', on_name_entry)
        self.rename_ws_dialog.name_entry_buffer.connect('deleted-text', on_name_entry)
        update_rename_button()
        self.rename_ws_dialog.name_entry.set_text(worksheet.get_name())
        self.rename_ws_dialog.run()

    def on_wsmenu_delete(self, action, parameter=None):
        worksheet = self.notebook.get_active_worksheet()
        
        self.delete_ws_dialog = Gtk.MessageDialog(self.main_window, 0, Gtk.MessageType.QUESTION)
        self.delete_ws_dialog.set_property('text', 'Are you sure you want to delete »' + worksheet.get_name() + '«?')
        self.delete_ws_dialog.format_secondary_text('When a worksheet is deleted it\'s permanently gone and can\'t easily be restored.')
        self.delete_ws_dialog.add_button('Cancel', Gtk.ResponseType.NO)
        delete_button = self.delete_ws_dialog.add_button('Delete', Gtk.ResponseType.YES)
        delete_button.get_style_context().add_class(Gtk.STYLE_CLASS_DESTRUCTIVE_ACTION)
        
        response = self.delete_ws_dialog.run()
        if response == Gtk.ResponseType.YES:
            row_index = self.main_window.sidebar.worksheet_list_view.get_row_index_by_worksheet(worksheet)
            row = self.main_window.sidebar.worksheet_list_view.get_row_at_index(row_index + 1)
            if row != None:
                self.main_window.sidebar.worksheet_list_view.select_row(row)
            else:
                row = self.main_window.sidebar.worksheet_list_view.get_row_at_index(row_index - 1)
                if row != None:
                    self.main_window.sidebar.worksheet_list_view.select_row(row)
                else:
                    self.activate_blank_state_mode()

            self.notebook.remove_worksheet_by_id(worksheet.get_id())
            worksheet.remove_from_disk()
        elif response == Gtk.ResponseType.NO:
            pass
        self.delete_ws_dialog.destroy()

    '''
    *** automatic scrolling
    '''
    
    def result_view_on_size_allocate(self, result_view_revealer, allocation):
        cell = self.notebook.active_worksheet.get_active_cell()
        if cell != None and result_view_revealer.autoscroll_on_reveal == True:
            worksheet_view = self.main_window.active_worksheet_view
            cell_view_position = cell.get_worksheet_position() * 2
            cell_view = worksheet_view.get_child_by_position(cell_view_position)
            x, cell_position = cell_view.translate_coordinates(worksheet_view.box, 0, 0)
            x, result_position = result_view_revealer.translate_coordinates(worksheet_view.box, 0, 0)
            
            last_allocation = result_view_revealer.allocation
            result_view_revealer.allocation = allocation
            if cell_position > result_position:
                worksheet_view.scroll(allocation.height - last_allocation.height)
        
    def scroll_to_cursor(self, cell, check_if_position_changed=True):
        if cell.is_active_cell_of_active_worksheet():
            worksheet = self.notebook.get_active_worksheet()
            current_cell = cell
            current_cell_position = cell.get_worksheet_position()
            current_position = cell.get_property('cursor-position')
            worksheet_view = self.main_window.active_worksheet_view
            cell_view_position = cell.get_worksheet_position() * 2
            cell_view = worksheet_view.get_child_by_position(cell_view_position)
            result_view = worksheet_view.get_child_by_position(cell_view_position + 1)
            current_cell_size = cell_view.get_allocation().height
            current_cell_size = cell_view.get_allocation().height + result_view.get_allocation().height

            # check if cursor has changed
            position_changed = False
            if worksheet.cursor_position['cell'] != current_cell: position_changed = True
            if worksheet.cursor_position['cell_position'] != current_cell_position: position_changed = True
            if worksheet.cursor_position['cell_size'] != current_cell_size and (self.cursor_position['position'] != 0 or cell.get_char_count() == 0): 
                position_changed = True
            if worksheet.cursor_position['position'] != current_position: position_changed = True
            if check_if_position_changed == False:
                position_changed = True
                if cell_view.has_changed_size():
                    cell_view.update_size()
            
            first_run = True
            if position_changed:
                if worksheet.cursor_position['cell'] != None: first_run = False
                worksheet.cursor_position['cell'] = current_cell
                worksheet.cursor_position['cell_position'] = current_cell_position
                worksheet.cursor_position['cell_size'] = current_cell_size
                worksheet.cursor_position['position'] = current_position
                
            if first_run == False and position_changed:
                
                # scroll to markdown cell with result
                if isinstance(current_cell, model.MarkdownCell) and current_cell.get_result() != None:

                    # get line number, calculate offset
                    scroll_position = worksheet_view.get_vadjustment()
                    x, cell_position = cell_view.translate_coordinates(worksheet_view.box, 0, 0)
                    line_position = cell_view.text_entry.get_iter_location(cell.get_iter_at_mark(cell.get_insert())).y
                    last_line_position = cell_view.text_entry.get_iter_location(cell.get_end_iter()).y
                    
                    if cell_position >= 0:
                        new_position = cell_position
                    else:
                        new_position = 0
                    
                    window_height = worksheet_view.get_allocated_height()
                    if current_cell_size < window_height:
                        if new_position >= scroll_position.get_value():
                            if new_position + current_cell_size >= scroll_position.get_value() + window_height:
                                new_position += current_cell_size - window_height
                                scroll_position.set_value(new_position)
                        else:
                            scroll_position.set_value(new_position)
                    else:    
                        scroll_position.set_value(new_position)

                # scroll to codecell or md cell without result
                if not isinstance(current_cell, model.MarkdownCell) or current_cell.get_result() == None:

                    # get line number, calculate offset
                    scroll_position = worksheet_view.get_vadjustment()
                    x, cell_position = cell_view.translate_coordinates(worksheet_view.box, 0, 0)
                    line_position = cell_view.text_entry.get_iter_location(cell.get_iter_at_mark(cell.get_insert())).y
                    last_line_position = cell_view.text_entry.get_iter_location(cell.get_end_iter()).y
                    
                    if cell_position >= 0:
                        offset = -scroll_position.get_value() + cell_position + line_position + 15
                    else:
                        offset = 0

                    if line_position == 0 and scroll_position.get_value() >= cell_position:
                        offset -= 15
                    elif line_position >= last_line_position and scroll_position.get_value() <= (cell_position + 15 + line_position + 0):
                        offset += 15
                    
                    # calculate movement
                    window_height = worksheet_view.get_allocated_height()
                    if offset > window_height - cell_view.line_height:
                        movement = offset - window_height + cell_view.line_height
                    elif offset < 0:
                        movement = offset
                    else:
                        movement = 0
                    if movement > 0 and line_position == 0:
                        if current_cell_size < round(window_height / 3.5):
                            movement += current_cell_size
                            if current_cell.get_line_count() == 1:
                                movement -= 50
                            else:
                                movement -= 35
                        else:
                            movement += min(60, current_cell_size - 35)
                        if isinstance(current_cell, model.MarkdownCell):
                            movement -= 1

                    if movement < 0 and line_position >= last_line_position:
                        if current_cell_size < round(window_height / 3.5):
                            movement -= current_cell_size
                            if current_cell.get_line_count() == 1:
                                movement += 50
                            else:
                                movement += 35
                        else:
                            movement -= min(60, current_cell_size - 35)
                        if isinstance(current_cell, model.MarkdownCell):
                            movement -= 1
                            
                    scroll_position.set_value(scroll_position.get_value() + movement)

    '''
    *** keyboard handler
    '''
    
    def observe_keyboard_keypress_events(self, main_window, event):

        # switch cells with arrow keys: upward
        if event.keyval == Gdk.keyval_from_name('Up') and event.state == 0:
            worksheet = self.notebook.active_worksheet
            cell = worksheet.active_cell
            
            if isinstance(cell, model.MarkdownCell) and cell.get_result() != None:
                prev_cell = worksheet.get_prev_cell(cell)
                if not prev_cell == None:
                    worksheet.set_active_cell(prev_cell)
                    self.cell_controllers[prev_cell].place_cursor_on_last_line()
                    return True

            if cell.get_worksheet_position() > 0:
                if cell.get_iter_at_mark(cell.get_insert()).get_offset() == 0:
                    prev_cell = worksheet.get_prev_cell(cell)
                    if not prev_cell == None:
                        worksheet.set_active_cell(prev_cell)
                        self.cell_controllers[prev_cell].place_cursor_on_last_line()
                        return True
        
        # switch cells with arrow keys: downward
        if event.keyval == Gdk.keyval_from_name('Down') and event.state == 0:
            worksheet = self.notebook.active_worksheet
            cell = worksheet.active_cell
            
            if isinstance(cell, model.MarkdownCell) and cell.get_result() != None:
                next_cell = worksheet.get_next_cell(cell)
                if not next_cell == None:
                    worksheet.set_active_cell(next_cell)
                    next_cell.place_cursor(next_cell.get_start_iter())
                    return True
                
            if cell.get_worksheet_position() < worksheet.get_cell_count() - 1:
                if cell.get_char_count() == (cell.get_iter_at_mark(cell.get_insert()).get_offset()):
                    next_cell = worksheet.get_next_cell(cell)
                    if not next_cell == None:
                        worksheet.set_active_cell(next_cell)
                        next_cell.place_cursor(next_cell.get_start_iter())
                        return True

        # delete cell with backspace
        if event.keyval == Gdk.keyval_from_name('BackSpace') and event.state == 0:
            worksheet = self.notebook.active_worksheet
            cell = worksheet.get_active_cell()
            if isinstance(cell, model.CodeCell) and cell.get_char_count() == 0:
                prev_cell = worksheet.get_prev_cell(cell)
                if not prev_cell == None:
                    worksheet.set_active_cell(prev_cell)
                    self.cell_controllers[prev_cell].place_cursor_on_last_line()
                    cell.remove_result()
                    worksheet.remove_cell(cell)
                    return True
            if isinstance(cell, model.MarkdownCell):
                if cell.get_result() != None or cell.get_char_count() == 0:
                    prev_cell = worksheet.get_prev_cell(cell)
                    next_cell = worksheet.get_next_cell(cell)
                    if not prev_cell == None: 
                        worksheet.set_active_cell(prev_cell)
                        self.cell_controllers[prev_cell].place_cursor_on_last_line()
                    elif not next_cell == None:
                        worksheet.set_active_cell(next_cell)
                        next_cell.place_cursor(next_cell.get_start_iter())
                    else:
                        worksheet.create_cell('last', '', activate=True)
                    cell.remove_result()
                    worksheet.remove_cell(cell)
                    return True
                    
        # edit markdown cell with enter
        if event.keyval == Gdk.keyval_from_name('Return') and event.state == 0:
            worksheet = self.notebook.active_worksheet
            cell = worksheet.get_active_cell()
            if isinstance(cell, model.MarkdownCell) and cell.get_result() != None:
                cell.remove_result()
                worksheet.set_active_cell(cell)
                cell.place_cursor(cell.get_start_iter())
                return True

        # evaluate cell with shift+enter
        if event.keyval == Gdk.keyval_from_name('Return') and event.state == Gdk.ModifierType.SHIFT_MASK:
            self.on_eval_button_click()
            return True
            
        # evaluate cell and go to next cell with ctrl+enter
        if event.keyval == Gdk.keyval_from_name('Return') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_eval_nc_button_click()
            return True
            
        # add code cell below with alt+enter
        if event.keyval == Gdk.keyval_from_name('Return') and event.state == Gdk.ModifierType.MOD1_MASK:
            self.on_add_codecell_button_click()
            return True

        # evaluate cell and add code cell below
        if event.keyval == Gdk.keyval_from_name('Return') and event.state == (Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.SHIFT_MASK):
            self.on_eval_button_click()
            self.on_add_codecell_button_click()
            return True

        # add markdown cell below with ctrl+m
        if event.keyval == Gdk.keyval_from_name('m') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_add_markdowncell_button_click()
            return True
            
        # stop computation with ctrl+h
        if event.keyval == Gdk.keyval_from_name('h') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_stop_button_click()
            return True
            
        # delete cell with ctrl+backspace
        if event.keyval == Gdk.keyval_from_name('BackSpace') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_delete_button_click()
            return True
            
        # move cell up with ctrl+up
        if event.keyval == Gdk.keyval_from_name('Up') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_up_button_click()
            return True

        # move cell down with ctrl+down
        if event.keyval == Gdk.keyval_from_name('Down') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_down_button_click()
            return True
            
        # restart kernel with ctrl+r
        if event.keyval == Gdk.keyval_from_name('r') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_wsmenu_restart_kernel()
            return True
            
        # paging up
        if event.keyval == Gdk.keyval_from_name('Page_Up') and event.state == 0:
            worksheet_view = self.main_window.active_worksheet_view
            scroll_position = worksheet_view.get_vadjustment()
            window_height = worksheet_view.get_allocated_height()
            scroll_position.set_value(scroll_position.get_value() - window_height)
            return True

        # paging down
        if event.keyval == Gdk.keyval_from_name('Page_Down') and event.state == 0:
            worksheet_view = self.main_window.active_worksheet_view
            scroll_position = worksheet_view.get_vadjustment()
            window_height = worksheet_view.get_allocated_height()
            scroll_position.set_value(scroll_position.get_value() + window_height)
            return True

        # create new worksheet with ctrl+n
        if event.keyval == Gdk.keyval_from_name('n') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_create_ws_button_click()
            return True
            
        # import worksheet with ctrl+i
        if event.keyval == Gdk.keyval_from_name('i') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_import_ws_button_click()
            return True
            
        # export worksheet with ctrl+e
        if event.keyval == Gdk.keyval_from_name('e') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_wsmenu_gsnb_export()
            return True
            
        # save worksheet with ctrl+s
        if event.keyval == Gdk.keyval_from_name('s') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_save_ws_button_click()
            return True
            
        # quit app with ctrl+q
        if event.keyval == Gdk.keyval_from_name('q') and event.state == Gdk.ModifierType.CONTROL_MASK:
            self.on_appmenu_quit()
            return True
            
        return False

    def do_startup(self):
        Gtk.Application.do_startup(self)


GLib.threads_init()
Gdk.threads_init()
main_controller = MainApplicationController()
exit_status = main_controller.run(sys.argv)
sys.exit(exit_status)
