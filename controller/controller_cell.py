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
from gi.repository import GLib
import viewgtk.viewgtk as view
import model.model as model


class CellController(object):

    def __init__(self, cell, cell_view, worksheet_controller, main_controller):

        self.cell = cell
        self.cell_view = cell_view

        self.worksheet_controller = worksheet_controller
        self.main_controller = main_controller

        # observe cell
        self.cell.register_observer(self)

        self.cell.connect('mark-set', self.on_cursor_movement)
        self.cell.connect('changed', self.on_change)
        self.cell.connect('paste-done', self.on_paste)

        # observe cell view
        self.cell_view.get_source_view().connect('focus-in-event', self.on_focus_in)
        self.cell_view.get_source_view().connect('size-allocate', self.on_size_allocate)
        self.cell_view.connect('size-allocate', self.cell_view_revealer_on_size_allocate)
        
    '''
    *** signal handlers: cells
    '''
    
    def on_cursor_movement(self, cell=None, mark=None, user_data=None):
        self.main_controller.scroll_to_cursor(self.cell, check_if_position_changed=True)

    def on_change(self, cell=None):
        self.worksheet_controller.update_line_numbers()
        
    def on_paste(self, cell=None, clipboard=None, user_data=None):
        ''' hack to prevent some gtk weirdness. '''
            
        prev_insert = self.cell.create_mark('name', self.cell.get_iter_at_mark(self.cell.get_insert()), True)
        self.cell.insert_at_cursor('\n')
        GLib.idle_add(lambda: self.cell.delete(self.cell.get_iter_at_mark(self.cell.get_insert()), self.cell.get_iter_at_mark(prev_insert)))

    def on_focus_in(self, text_field, event=None):
        ''' activate cell on click '''

        if self.cell.is_active_cell() == False:
            self.cell.get_worksheet().set_active_cell(self.cell)
            return True
        
        self.main_controller.scroll_to_cursor(text_field.get_buffer(), check_if_position_changed=True)
        return False
    
    def on_size_allocate(self, text_field, allocation=None):
        self.main_controller.scroll_to_cursor(text_field.get_buffer(), check_if_position_changed=True)
        
    def cell_view_revealer_on_size_allocate(self, cell_view_revealer, allocation):
        cell = self.main_controller.notebook.active_worksheet.get_active_cell()
        if cell != None:
            worksheet_view = self.main_controller.main_window.active_worksheet_view
            cell_view_position = cell.get_worksheet_position() * 2
            cell_view = worksheet_view.get_child_by_position(cell_view_position)
            x, cell_position = cell_view.translate_coordinates(worksheet_view.box, 0, 0)
            x, result_position = cell_view_revealer.translate_coordinates(worksheet_view.box, 0, 0)
            
            last_allocation = cell_view_revealer.allocation
            cell_view_revealer.allocation = allocation
            if cell_position > result_position:
                worksheet_view.scroll(allocation.height - last_allocation.height)
        
    '''
    *** helpers: cell
    '''
    
    def place_cursor_on_last_line(self):
        target_iter = self.cell_view.text_entry.get_iter_at_position(0, self.cell_view.text_entry.get_allocated_height() - 30)
        self.cell.place_cursor(target_iter[1])


class CodeCellController(CellController):

    def __init__(self, cell, cell_view, worksheet_controller, main_controller):
        CellController.__init__(self, cell, cell_view, worksheet_controller, main_controller)

        self.cell.register_observer(self.main_controller.backend_controller_sagemath)

    def change_notification(self, change_code, notifying_object, parameter):

        if change_code == 'new_result':
            result = parameter['result']
            worksheet_view = self.main_controller.main_window.worksheet_views[self.cell.get_worksheet()]
            cell_view_position = self.cell.get_worksheet_position() * 2
                
            # check if cell view is still present
            if cell_view_position >= 0:

                # remove previous results
                revealer = worksheet_view.get_child_by_position(cell_view_position + 1)
                
                # add result
                if result == None:
                    revealer.unreveal()
                    self.cell_view.set_reveal_child(True)
                    self.cell_view.text_entry.set_editable(True)
                else:
                    if isinstance(result, model.SageMathResultImage):
                        result_view = view.SageMathResultViewImage(self.cell_view)
                        result_view.load_image_from_filename(result.get_absolute_path())
                        revealer.set_result_view(result_view)
                        revealer.show_all()
                        GLib.idle_add(lambda: revealer.reveal(parameter['show_animation']))
                    elif isinstance(result, model.SageMathResultText):
                        result_view = view.SageMathResultViewText(self.cell_view)
                        result_view.set_text(result.get_as_raw_text())
                        revealer.set_result_view(result_view)
                        revealer.show_all()
                        GLib.idle_add(lambda: revealer.reveal(parameter['show_animation']))

                # enable auto-scrolling for this cell (not enabled on startup)
                GLib.idle_add(lambda: revealer.set_autoscroll_on_reveal(True))
                
        if change_code == 'cell_state_change':
            worksheet_view = self.main_controller.main_window.worksheet_views[self.cell.get_worksheet()]
            child_position = self.cell.get_worksheet_position() * 2
            cell_view = worksheet_view.get_child_by_position(child_position)

            if cell_view != None:
                if parameter == 'idle': cell_view.state_display.show_nothing()
                elif parameter == 'edit': cell_view.state_display.show_nothing()
                elif parameter == 'display': cell_view.state_display.show_nothing()
                elif parameter == 'queued_for_evaluation': cell_view.state_display.show_spinner()
                elif parameter == 'ready_for_evaluation': cell_view.state_display.show_spinner()
                elif parameter == 'evaluation_in_progress': cell_view.state_display.show_spinner()
            

class MarkdownCellController(CellController):

    def __init__(self, cell, cell_view, toolbar, worksheet_controller, main_controller):
        CellController.__init__(self, cell, cell_view, worksheet_controller, main_controller)
    
        self.toolbar = toolbar
        
        self.cell.register_observer(self.main_controller.backend_controller_markdown)
        
        #observe toolbar
        #TODO
        
    def change_notification(self, change_code, notifying_object, parameter):

        if change_code == 'new_result':
            result = parameter['result']
            worksheet_view = self.main_controller.main_window.worksheet_views[self.cell.get_worksheet()]
            cell_view_position = self.cell.get_worksheet_position() * 2
                
            # check if cell view is still present
            if cell_view_position >= 0:

                # remove previous results
                revealer = worksheet_view.get_child_by_position(cell_view_position + 1)
                
                # add result
                if result == None:
                    revealer.unreveal()
                    self.cell_view.set_reveal_child(True)
                    self.cell_view.text_entry.set_editable(True)
                elif isinstance(result, model.MarkdownResult):
                    self.cell_view.unreveal(parameter['show_animation'])
                    self.cell_view.text_entry.set_editable(False)
                    result_view = view.MarkdownResultView(self.cell_view)
                    result_view.set_buildable(result.get_buildable())
                    result_view.set_replacements(result.get_replacements())
                    result_view.compile()
                    revealer.set_result_view(result_view)
                    if parameter['show_animation'] == False:
                        revealer.reveal(parameter['show_animation'])
                    else:
                        GLib.idle_add(lambda: revealer.reveal(parameter['show_animation']))

                # enable auto-scrolling for this cell (not enabled on startup)
                GLib.idle_add(lambda: revealer.set_autoscroll_on_reveal(True))
                
        if change_code == 'cell_state_change':
            worksheet_view = self.main_controller.main_window.worksheet_views[self.cell.get_worksheet()]
            child_position = self.cell.get_worksheet_position() * 2
            cell_view = worksheet_view.get_child_by_position(child_position)

            if cell_view != None:
                if parameter == 'idle': self.cell_view.state_display.show_nothing()
                elif parameter == 'edit': self.cell_view.state_display.show_nothing()
                elif parameter == 'display': self.cell_view.state_display.show_nothing()
                elif parameter == 'queued_for_evaluation': self.cell_view.state_display.show_spinner()
                elif parameter == 'ready_for_evaluation': self.cell_view.state_display.show_spinner()
                elif parameter == 'evaluation_in_progress': self.cell_view.state_display.show_spinner()

        

