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
import controller.controller_cell as cellcontroller


class WorksheetController(object):

    def __init__(self, worksheet, worksheet_view, main_controller):

        self.worksheet = worksheet
        self.worksheet_view = worksheet_view

        self.main_controller = main_controller

        # observe worksheet
        worksheet.register_observer(self)
        worksheet.register_observer(self.main_controller.backend_controller_sagemath)

    def change_notification(self, change_code, notifying_object, parameter):

        if change_code == 'worksheet_name_changed':
            self.main_controller.update_title(self.worksheet)
            
        if change_code == 'kernel_state_changed':
            self.main_controller.update_subtitle(self.worksheet)
            
        if change_code == 'new_cell':
            cell = parameter
            worksheet_position = cell.get_worksheet_position()
            view_position = worksheet_position * 2

            # create cell view and result view revealer
            if isinstance(cell, model.MarkdownCell):
                cell_view = view.CellViewMarkdown(cell)
                result_view_revealer = view.ResultViewRevealer(cell_view)
                result_view_revealer.get_style_context().add_class('markdown')
            elif isinstance(cell, model.CodeCell):
                cell_view = view.CellViewCode(cell)
                result_view_revealer = view.ResultViewRevealer(cell_view)
            
            self.worksheet_view.add_child_at_position(result_view_revealer, view_position)
            self.worksheet_view.add_child_at_position(cell_view, view_position)

            if isinstance(cell, model.MarkdownCell):
                self.main_controller.cell_controllers[cell] = cellcontroller.MarkdownCellController(cell, cell_view, None, self, self.main_controller)
            elif isinstance(cell, model.CodeCell):
                self.main_controller.cell_controllers[cell] = cellcontroller.CodeCellController(cell, cell_view, self, self.main_controller)
            
            self.main_controller.observe_result_view_revealer(result_view_revealer)
            self.main_controller.update_up_down_buttons()
            self.update_line_numbers()

        if change_code == 'deleted_cell':
            child_position = parameter * 2
            
            # remove cell and result revealer from view
            self.worksheet_view.remove_child_by_position(child_position)
            self.worksheet_view.remove_child_by_position(child_position)
            
            self.main_controller.update_up_down_buttons()
            self.update_line_numbers()
        
        if change_code == 'new_active_cell':
            cell = parameter
            child_position = cell.get_worksheet_position() * 2
            cell_view = self.worksheet_view.get_child_by_position(child_position)
            GLib.idle_add(lambda: cell_view.get_source_view().grab_focus())
            cell_view.set_active()
            cell_view.line_numbers_renderer.set_active()
            self.main_controller.update_up_down_buttons()
            
            # update result view
            result_view_revealer = self.worksheet_view.get_child_by_position(child_position + 1)
            result_view_revealer.get_style_context().add_class('active')
            
        if change_code == 'new_inactive_cell':
            cell = parameter
            child_position = cell.get_worksheet_position() * 2
            cell_view = self.worksheet_view.get_child_by_position(child_position)
            cell_view.set_inactive()
            cell_view.line_numbers_renderer.set_inactive()
            
            # unselect text
            insert_mark = cell.get_iter_at_mark(cell.get_insert())
            selection_bound = cell.get_selection_bound()
            cell.move_mark(selection_bound, insert_mark)
            
            # update result view
            result_view_revealer = self.worksheet_view.get_child_by_position(child_position + 1)
            result_view_revealer.get_style_context().remove_class('active')
            
        if change_code == 'cell_moved':
            cell_view1_position = parameter['position'] * 2
            cell_view2_position = parameter['new_position'] * 2
            
            # move cells
            cell_view1 = self.worksheet_view.get_child_by_position(cell_view1_position)
            cell_view2 = self.worksheet_view.get_child_by_position(cell_view2_position)
            self.worksheet_view.move_child(cell_view1, cell_view2_position)
            self.worksheet_view.move_child(cell_view2, cell_view1_position)
            
            # move result revealers
            result_revealer_view1 = self.worksheet_view.get_child_by_position(cell_view1_position + 1)
            result_revealer_view2 = self.worksheet_view.get_child_by_position(cell_view2_position + 1)
            self.worksheet_view.move_child(result_revealer_view1, cell_view2_position + 1)
            self.worksheet_view.move_child(result_revealer_view2, cell_view1_position + 1)
            
            cell_view1.grab_focus()
            GLib.idle_add(lambda: cell_view1.get_source_view().grab_focus())

            self.main_controller.update_up_down_buttons()
            self.update_line_numbers()

        if change_code == 'busy_cell_count_changed':
            self.main_controller.update_subtitle(self.worksheet)
            if self.worksheet == self.main_controller.notebook.active_worksheet:
                self.main_controller.update_stop_button()

        if change_code == 'save_state_change':
            self.main_controller.update_title(self.worksheet)
            self.main_controller.update_sidebar_save_date(self.worksheet)
            if self.worksheet == self.main_controller.notebook.active_worksheet:
                self.main_controller.update_save_button()

    def update_line_numbers(self):
        offset = 0
        total = 0
        for child in self.worksheet_view.children:
            if isinstance(child, view.CellView):
                total += child.text_entry.get_buffer().get_line_count()

        width = 1
        while total >= 10:
            width += 1
            total //= 10
        width += 3
        width = max(width, 6)
        for child in self.worksheet_view.children:
            if isinstance(child, view.CellView):
                child.line_numbers_renderer.set_width(width)
                child.line_numbers_renderer.set_offset(offset)
                child.line_numbers_renderer.queue_draw()
                offset += child.text_entry.get_buffer().get_line_count()
            elif isinstance(child, view.ResultViewRevealer):
                if child.result_view != None:
                    child.result_view.left_padding.set_size_request(width * 9 + 9, -1)
                    child.queue_draw()


