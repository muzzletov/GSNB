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
gi.require_version('GtkSource', '3.0')
from gi.repository import Gtk
from gi.repository import GtkSource
from gi.repository import Gdk
from gi.repository import GLib, GObject
from gi.repository import Gio
import os

import viewgtk.viewgtk_dialogs as dialogs
from viewgtk.viewgtk_headerbars import *
from viewgtk.viewgtk_sidebar import *


class ApplicationMenu(Gio.Menu):
    ''' The top level application menu. '''

    def __init__(self):
        self.meta_section = Gio.Menu()
        
        self.quit_item = Gio.MenuItem.new('Quit', 'app.quit')
        self.quit_item.set_attribute_value('accel', GLib.Variant('s', '<Control>Q'))
        self.meta_section.append_item(self.quit_item)

        self.append_section(None, self.meta_section)


class WorksheetViewWrapper(Gtk.Notebook):

    def __init__(self):
        Gtk.Notebook.__init__(self)

        self.set_show_border(False)
        self.set_show_tabs(False)
        self.show_all()
        
    def set_worksheet_view(self, worksheet_view):
        page_index = self.page_num(worksheet_view)
        if page_index == -1:
            page_index = self.append_page(worksheet_view)
        worksheet_view.show_all()
        self.set_current_page(page_index)
        self.show_all()
        
    def remove_view(self, view):
        page_index = self.page_num(view)
        if page_index >= 0:
            self.remove_page(page_index)
        
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.CONSTANT_SIZE
                     
    def do_get_preferred_width(self):
        return 520, 520


class BlankStateView(Gtk.ScrolledWindow):

    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)

        self.set_hexpand(True)

        self.box = Gtk.VBox()
        self.add_with_viewport(self.box)
        
        self.welcome_message = Gtk.Label()
        self.welcome_message.set_text('GSNB is an Interface to the Sagemath Computer Algebra \nSystem. You create worksheets to type in Sagemath commands \nfor computation, plotting functions and many more things.\n')
        self.welcome_message.set_line_wrap(True)
        self.welcome_message.set_xalign(0)
        self.welcome_message.set_yalign(0)
        self.welcome_message.set_size_request(400, 50)
        
        self.welcome_links = Gtk.HBox()
        #self.welcome_links.set_size_request(400, 50)
        
        self.create_ws_link = Gtk.LinkButton('action://app.placeholder', 'Create New Worksheet')
        self.create_ws_link.set_can_focus(False)
        self.create_ws_link.set_tooltip_text('')
        self.import_ws_link = Gtk.LinkButton('action://app.placeholder', 'Import Worksheet(s)')
        self.import_ws_link.set_can_focus(False)
        self.import_ws_link.set_tooltip_text('')
        self.welcome_links.pack_start(self.create_ws_link, False, False, 0)
        self.welcome_links.pack_start(Gtk.Label(' or '), False, False, 0)
        self.welcome_links.pack_start(self.import_ws_link, False, False, 0)
        
        self.footer = Gtk.Label()
        #self.footer.set_text('Of Note: To get started using Sagemath consider our "Absolute Beginners\' Guide to Sagemath" (also in the sidebar).')
        self.footer.set_margin_bottom(20)
        self.footer.set_margin_left(25)
        self.footer.set_xalign(0)
        self.footer.set_line_wrap(True)

        self.welcome_box = Gtk.VBox()
        self.welcome_box.set_size_request(400, 250)
        self.welcome_box.pack_start(self.welcome_message, False, False, 0)
        self.welcome_box.pack_start(self.welcome_links, False, False, 0)
        self.welcome_box_wrapper = Gtk.HBox()
        self.welcome_box_wrapper.set_center_widget(self.welcome_box)
        self.box.set_center_widget(self.welcome_box_wrapper)
        self.box.pack_end(self.footer, False, False, 0)
        

class WorksheetView(Gtk.ScrolledWindow):

    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)

        self.set_hexpand(True)
        #self.set_min_content_height(600)
        self.set_propagate_natural_height(True)
        self.set_propagate_natural_width(True)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.box = Gtk.VBox()
        self.add_with_viewport(self.box)
        
        # fill worksheet with white background
        self.footer = Gtk.HBox()
        self.footer.pack_start(Gtk.DrawingArea(), True, True, 0)
        self.box.pack_end(self.footer, True, True, 0)

        # contains all types of cell view, result views, ...
        self.children = list()

        # disable auto scrolling
        self.get_child().set_focus_vadjustment(Gtk.Adjustment())
        self.get_child().set_focus_hadjustment(Gtk.Adjustment())

    def add_child_at_position(self, view, position):
        self.children.insert(position, view)
        self.box.pack_start(view, False, False, 0)
        self.box.reorder_child(view, position)
        self.show_all()
        
    def move_child(self, child, position):
        old_position = self.get_child_position(child)
        self.children[old_position], self.children[position] = self.children[position], self.children[old_position]
        self.box.reorder_child(child, position)
        
    def get_child_by_position(self, position):
        if position < len(self.children):
            return self.children[position]
        else:
            return None
    
    def get_child_position(self, child):
        try: index = self.children.index(child)
        except ValueError: index = -1
        return index
    
    def remove_child_by_position(self, position):
        self.box.remove(self.children[position])
        del(self.children[position])
        self.show_all()
        
    def scroll(self, amount):
        scroll_position = self.get_vadjustment()
        
        #print(amount)
        #print(scroll_position.get_upper() - scroll_position.get_value() - self.get_allocation().height)
        scroll_position.set_value(scroll_position.get_value() + amount)
    

class CellViewStateDisplay(Gtk.DrawingArea):

    def __init__(self):
        Gtk.Box.__init__(self)
        self.set_hexpand(False)
        self.state = 'nothing'
        self.set_size_request(9, -1)
        self.spinner_state = 0
        self.connect('draw', self.draw)
        GObject.timeout_add(10, self.draw_spinner)

    def show_spinner(self):
        if self.state != 'spinner':
            self.state = 'spinner'
        
    def draw_spinner(self):
        self.spinner_state += 1
        self.queue_draw()
        return True
    
    def draw(self, widget, cr, data = None):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        context = self.get_style_context()
        Gtk.render_background(context, cr, 0, 0, width, height)
        
        if self.state == 'spinner':
            cr.set_source_rgba(1, 1, 1, 0.5)
            i = -20 + (self.spinner_state % 20)
            while i < height:
                cr.rectangle(0, i, 10, 10)
                cr.fill()
                i += 20
        return True
    
    def show_nothing(self):
        if self.state != 'nothing':
            self.state = 'nothing'


class CellViewCodeLineNumbersRenderer(GtkSource.GutterRendererText):

    def __init__(self):
        GtkSource.GutterRendererText.__init__(self)
        self.offset = 0
        self.width = 6
        self.set_inactive()
        self.set_size(54)
        self.is_active = False

    def do_query_data(self, start, end, flags):
        number = start.get_line() + self.offset + 1
        pot = 10
        ws_count = self.width - 2
        while number >= pot:
            ws_count -= 1
            pot *= 10
        whitespace = ' ' * (ws_count)

        if int(flags) % 2 == 1 and self.is_active:
            colorstring = '#000'
            self.props.markup = '<b><span color="' + colorstring + '">' + whitespace + str(number) + '</span></b>'
        else:
            colorstring = '#666666' if self.is_active else '#888888'
            colorstring = '#999'
            self.props.markup = '<span color="' + colorstring + '">' + whitespace + str(number) + '</span>'
        
    def set_offset(self, offset):
        self.offset = offset
        
    def set_width(self, width):
        self.width = width
        self.set_size(9 * self.width)

    def set_active(self):
        self.is_active = True
        rgba = Gdk.RGBA()
        rgba.parse('#fff')
        self.set_property('background-rgba', rgba)

    def set_inactive(self):
        self.is_active = False
        rgba = Gdk.RGBA()
        rgba.parse('#fff')
        self.set_property('background-rgba', rgba)


class CellView(Gtk.Revealer):

    def __init__(self, cell):
        Gtk.Revealer.__init__(self)
        
        self.wrapper = Gtk.ScrolledWindow()
        self.wrapper.set_hexpand(False)
        self.wrapper.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.box = Gtk.HBox()
        self.box.set_hexpand(False)
        self.set_reveal_child(True)
        self.cell = cell

        self.line_height = 20
        
        self.size = {'width': self.get_allocated_width(), 'height': self.get_allocated_height()}

        self.text_entry = GtkSource.View.new_with_buffer(cell)
        self.text_entry.set_monospace(True)
        self.text_entry.set_can_focus(True)
        self.text_entry.set_pixels_inside_wrap(2)
        self.text_entry.set_pixels_below_lines(2)
        self.text_entry.set_pixels_above_lines(0)
        self.wrapper.add(self.text_entry)
        
        self.state_display = CellViewStateDisplay()
        self.box.pack_start(self.state_display, False, False, 0)
        self.box.pack_start(self.wrapper, True, True, 0)
        self.add(self.box)
        self.text_entry.set_vadjustment(Gtk.Adjustment())
        self.text_entry.set_hadjustment(Gtk.Adjustment())

        self.text_entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_entry.set_show_line_numbers(False)
        self.text_entry.set_hexpand(False)
        self.text_entry.set_indent_width(4)
        self.text_entry.set_indent_on_tab(True)
        self.text_entry.set_auto_indent(True)
        self.text_entry.set_insert_spaces_instead_of_tabs(True)

        self.allocation = self.get_allocation()
        
    def get_source_view(self):
        return self.text_entry

    def get_cell(self):
        return self.cell

    def set_active(self):
        self.get_style_context().add_class('active')

    def set_inactive(self):
        self.get_style_context().remove_class('active')

    def has_changed_size(self):
        if self.size['width'] == self.get_allocated_width() and self.size['height'] == self.get_allocated_height():
            return False
        return True

    def update_size(self):
        self.size['width'] = self.get_allocated_width()
        self.size['height'] = self.get_allocated_height()
        

class CellViewCode(CellView):

    def __init__(self, cell):
        CellView.__init__(self, cell)

        self.text_entry.set_left_margin(9)
        self.text_entry.set_right_margin(15)
        self.text_entry.set_top_margin(15)
        self.text_entry.set_bottom_margin(13)
        
        self.left_gutter = self.text_entry.get_gutter(Gtk.TextWindowType.LEFT)
        self.line_numbers_renderer = CellViewCodeLineNumbersRenderer()
        self.left_gutter.insert(self.line_numbers_renderer, 0)

        self.set_hexpand(False)
        self.set_can_focus(True)

        self.show_all()


class CellViewMarkdown(CellView):

    def __init__(self, cell):
        CellView.__init__(self, cell)

        self.text_entry.set_left_margin(9)
        self.text_entry.set_right_margin(15)
        self.text_entry.set_top_margin(15)
        self.text_entry.set_bottom_margin(13)
        
        self.left_gutter = self.text_entry.get_gutter(Gtk.TextWindowType.LEFT)
        self.line_numbers_renderer = CellViewCodeLineNumbersRenderer()
        self.left_gutter.insert(self.line_numbers_renderer, 0)

        self.set_hexpand(False)
        self.set_can_focus(True)

        self.show_all()

    def reveal(self, show_animation=True):
        if show_animation == False:
            self.set_transition_type(Gtk.RevealerTransitionType.NONE)
        else:
            self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.set_reveal_child(True)
        
    def unreveal(self, show_animation=True):
        if show_animation == False:
            self.set_transition_type(Gtk.RevealerTransitionType.NONE)
        else:
            self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.set_reveal_child(False)
    

class ResultViewSeperator1(Gtk.DrawingArea):
    
    def __init__(self, is_white):
        Gtk.DrawingArea.__init__(self)
        self.set_size_request(-1, 1)
        self.connect('draw', self.draw)
        self.opacity = 0
        self.bgcolor = 'white' if is_white else 'grey'
        
    def draw(self, widget, cr, data = None):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        context = self.get_style_context()
        if self.bgcolor == 'white':
            Gtk.render_background(context, cr, 0, 0, width, height)
        else:
            cr.set_source_rgba(0.97, 0.97, 0.97, 1)
            cr.rectangle(0, 0, width, height)
            cr.fill()
        
        if self.opacity > 0:
            cr.set_source_rgba(0.86, 0.86, 0.86, self.opacity)
            i = 0
            while i < width:
                cr.rectangle(i, 0, 9, 9)
                cr.fill()
                i += 18
        else:
            pass
        return False
    
    def reduce_opacity(self):
        if self.opacity > 0:
            self.opacity -= 0.05
            self.queue_draw()
            return True
        else:
            self.opacity = 0
            self.queue_draw()
            return False
        
    def increase_opacity(self):
        if self.opacity < 1:
            self.opacity += 0.05
            self.queue_draw()
            return True
        else:
            self.opacity = 1
            self.queue_draw()
            return False

    def reveal(self, duration=100):
        GObject.timeout_add(duration / 20, self.increase_opacity)
        self.queue_draw()
        return False
    
    def unreveal(self, duration=100):
        GObject.timeout_add(duration / 20, self.reduce_opacity)
        return False
        

class ResultViewRevealer(Gtk.EventBox):

    def __init__(self, cell_view):
        Gtk.EventBox.__init__(self)

        self.cell_view = cell_view
        self.wrapper = Gtk.HBox()
        self.revealer = Gtk.Revealer()

        self.seperator1 = ResultViewSeperator1(isinstance(self.cell_view, CellViewCode))
        self.superbox = Gtk.VBox()
        self.superbox.pack_start(self.seperator1, False, False, 0)

        self.box = Gtk.VBox()
        self.revealer.add(self.box)
        self.state_display = CellViewStateDisplay()
        self.superbox.pack_start(self.revealer, True, True, 0)

        self.wrapper.pack_start(self.state_display, False, False, 0)
        self.wrapper.pack_start(self.superbox, True, True, 0)
        self.add(self.wrapper)
        self.revealer.set_reveal_child(False)
        
        self.result_view = None
        self.allocation = self.get_allocation()
        self.autoscroll_on_reveal = False
        
    def set_result_view(self, result_view):
        if self.result_view != None:
            self.box.remove(self.result_view)
        
        self.result_view = result_view
        self.box.pack_start(self.result_view, True, True, 0)
    
    def reveal(self, show_animation=True, duration=250):
        self.revealer.set_transition_duration(duration)
        if show_animation == False:
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.NONE)
        else:
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        if not isinstance(self.result_view, MarkdownResultView):
            self.seperator1.reveal()
        self.revealer.set_reveal_child(True)
        
    def unreveal(self, show_animation=True, duration=250):
        self.seperator1.unreveal(100)
        self.revealer.set_transition_duration(duration)
        if show_animation == False:
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.NONE)
        else:
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.revealer.set_reveal_child(False)
        
    def set_autoscroll_on_reveal(self, value):
        self.autoscroll_on_reveal = value
    

class ResultView(Gtk.HBox):

    def __init__(self, cell_view):
        Gtk.HBox.__init__(self)
        
        self.cell_view = cell_view


class MarkdownResultView(ResultView):

    def __init__(self, cell_view):
        ResultView.__init__(self, cell_view)
        
        self.width = cell_view.line_numbers_renderer.width * 9 + 9
        
        self.left_padding = Gtk.DrawingArea()
        self.left_padding.set_size_request(self.width, -1)
        self.right_padding = Gtk.DrawingArea()
        self.right_padding.set_size_request(self.width, -1)
        self.top_padding = Gtk.DrawingArea()
        self.top_padding.set_size_request(-1, 16)
        self.bottom_padding = Gtk.DrawingArea()
        self.bottom_padding.set_size_request(-1, 17)
        self.bottom_padding.set_size_request(-1, 22)

        self.pack_start(self.left_padding, False, False, 0)
        self.pack_end(self.right_padding, False, False, 0)

        self.set_hexpand(True)
        
        self.buildable = ''
        self.replacements = list()

    def set_buildable(self, buildable):
        self.buildable = buildable
        
    def set_replacements(self, replacements):
        self.replacements = replacements
        
    def allocation_hack(self, content, allocation):
        self.contentwrap.set_size_request(-1, allocation.height)

    def compile(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_string(self.buildable)
        self.content = self.builder.get_object('buildablewrap')
        self.content.connect('size-allocate', self.allocation_hack)
        
        self.centerbox = Gtk.VBox()
        self.centerbox.pack_start(self.top_padding, False, False, 0)
        self.labels = list()

        for key, value in enumerate(self.replacements):
            label = self.builder.get_object('label-' + str(key))
            label.set_markup('<span rise="0">' + (value) + '</span>')
            label.set_single_line_mode(False)
            self.labels.append(label)
            
        self.centerbox.pack_end(self.bottom_padding, False, False, 0)
        self.contentwrap = Gtk.VBox()
        self.contentwrap.pack_start(self.content, False, False, 0)
        self.centerbox.set_center_widget(self.contentwrap)
        self.pack_start(self.centerbox, True, True, 0)
        self.show_all()


class SageMathResultView(ResultView):

    def __init__(self, cell_view):
        ResultView.__init__(self, cell_view)
        
        self.width = cell_view.line_numbers_renderer.width * 9 + 9
        
        self.left_padding = Gtk.DrawingArea()
        self.left_padding.set_size_request(self.width, -1)
        self.right_padding = Gtk.DrawingArea()
        self.right_padding.set_size_request(self.width, -1)

        self.pack_start(self.left_padding, True, True, 0)
        self.pack_end(self.right_padding, True, True, 0)

        self.centerbox = Gtk.VBox()
        self.top_padding = Gtk.DrawingArea()
        self.top_padding.set_size_request(-1, 16)
        self.bottom_padding = Gtk.DrawingArea()
        self.bottom_padding.set_size_request(-1, 14)
        self.centerbox.pack_start(self.top_padding, False, False, 0)
        self.centerbox.pack_end(self.bottom_padding, False, False, 0)
        self.set_center_widget(self.centerbox)
        self.set_hexpand(True)
        

class SageMathResultViewText(SageMathResultView):

    def __init__(self, cell_view):
        SageMathResultView.__init__(self, cell_view)
        
        self.label = Gtk.Label()
        self.label.set_single_line_mode(False)
        self.label.set_line_wrap_mode(2) # Pango.WrapMode.CHAR
        self.label.set_line_wrap(True)
        #self.label.set_selectable(True) # sollte aber nicht focussable sein, typing weiter in active cell

        self.size_box = Gtk.VBox()
        self.size_box.pack_start(self.label, False, False, 0)
        self.centerbox.pack_start(self.size_box, False, False, 0)
        self.show_all()
        self.label.connect('size-allocate', self.allocation_hack)
    
    def allocation_hack(self, label, allocation):
        self.size_box.set_size_request(-1, allocation.height)
        number_of_lines = label.get_text().count('\n') + 1
        if (number_of_lines * 20) < allocation.height:
            self.label.set_justify(Gtk.Justification.LEFT)
            self.label.set_xalign(0)
        else:
            self.label.set_justify(Gtk.Justification.CENTER)
            self.label.set_xalign(0.5)

    def set_text(self, text):
        if not len(text) > 0: text = ''
        #resolution = self.get_style_context().get_screen().get_resolution()
        #rise_units = int(4*1024.0 * (max(resolution, 96)/72))
        rise_units = 6144
        self.label.set_markup('<span rise="' + str(rise_units) + '"><span font_desc="">' + GLib.markup_escape_text(text) + '</span></span>')
        

class SageMathResultViewImage(SageMathResultView):

    def __init__(self, cell_view):
        SageMathResultView.__init__(self, cell_view)
        
        self.filename = None
        self.image = None
        self.wrapper = Gtk.HBox()
        self.wrapper.set_hexpand(True)
        self.centerbox.set_center_widget(self.wrapper)
        self.show_all()
    
    def load_image_from_filename(self, filename):
        self.filename = filename
        self.image = Gtk.Image.new_from_file(self.filename)
        self.centerbox.set_center_widget(self.image)
        self.show_all()
        

class MainWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        Gtk.Window.__init__(self, application=app)
        self.set_size_request(1000, 550)
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.set_property('show-menubar', False)
        
        # window state variables
        self.current_width, self.current_height = self.get_size()
        self.is_maximized = False
        self.is_fullscreen = False

        # headerbar
        self.headerbar = HeaderBar(app.settings.button_layout, app.settings.gtksettings.get_property('gtk-shell-shows-app-menu'))
        self.set_titlebar(self.headerbar)

        # window content
        self.worksheet_list_view = WorksheetListView()
        self.worksheet_views = dict()
        self.worksheet_view_wrapper = WorksheetViewWrapper()

        self.paned = Gtk.Paned()
        self.paned.pack1(self.worksheet_list_view, False, False)
        self.paned.pack2(self.worksheet_view_wrapper, True, False)
        self.paned.set_position(250)
        self.paned_position = self.paned.get_position()
        self.add(self.paned)

        # sync paneds
        self.paned.bind_property('position', self.headerbar, 'position', 1)

        # css
        BlankStateView.set_css_name('blankstateview')
        WorksheetView.set_css_name('worksheetview')
        CellView.set_css_name('cellview')
        CellViewCode.set_css_name('cellviewcode')
        CellViewMarkdown.set_css_name('cellviewmarkdown')
        SageMathResultViewText.set_css_name('smresultviewtext')
        SageMathResultViewImage.set_css_name('smresultviewimage')
        MarkdownResultView.set_css_name('mdresultview')
        SageMathResultView.set_css_name('smresultview')
        CellViewStateDisplay.set_css_name('cellviewstatedisplay')
        ResultViewRevealer.set_css_name('resultviewrevealer')
        ResultViewSeperator1.set_css_name('resultviewseperator1')

        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_path(os.getcwd() + '/resources/style_gtk.css')
        self.style_context = Gtk.StyleContext()
        self.style_context.add_provider_for_screen(self.get_screen(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def add_worksheet_view(self, worksheet_id, worksheet_view):
        self.worksheet_views[worksheet_id] = worksheet_view
        
    def remove_worksheet_view(self, worksheet_id):
        worksheet_view = self.worksheet_views[worksheet_id]
        self.worksheet_view_wrapper.remove_view(worksheet_view)
        del(self.worksheet_views[worksheet_id])

    def activate_worksheet_view(self, worksheet_id):
        self.active_worksheet_view = self.worksheet_views[worksheet_id]
        self.worksheet_view_wrapper.set_worksheet_view(self.active_worksheet_view)
        self.show_all()
    
        
