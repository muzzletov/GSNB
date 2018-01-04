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
gi.require_version('GtkSource', '3.0')
from gi.repository import Gtk, GLib
from gi.repository import GtkSource
import pickle
import time
import datetime
import os, os.path
import shutil
import tarfile


class Observable(object):
    ''' Documents changes for observers to fetch, thereby making objects observable.
        Observable entities inherit from this class.
        Observers can then register with these entities and
        get change notifications pushed to them. '''

    def __init__(self):
        self.observers = set()
    
    def add_change_code(self, change_code, parameter):
        ''' Observables call this method to notify observers of
            changes in their states. '''
        
        for observer in self.observers:
            observer.change_notification(change_code, self, parameter)
    
    def register_observer(self, observer):
        ''' Observer call this method to register themselves with observable
            objects. They have themselves to implement a method
            'change_notification(change_code, parameter)' which they observable
            will call when it's state changes. '''
        
        self.observers.add(observer)


class Notebook(Observable):
    ''' A notebook contains a user's worksheets. '''

    def __init__(self):
        Observable.__init__(self)

        self.worksheets = dict()
        self.documentation_worksheets = dict()
        self.pathname = None
        self.history = None
        self.active_worksheet = None
        
    def populate_documentation(self):
        ''' Load documentation from gsnb program folder. '''
        
        for filename in os.listdir('./resources/documentation'):
            if os.path.isdir('./resources/documentation/' + filename): # not sure if this is safe
                worksheet = DocumentationWorksheet(self)
                worksheet.set_pathname('./resources/documentation/' + filename)
                worksheet.populate_meta()
                self.add_documentation_worksheet(worksheet)
        
    def populate_from_path(self, pathname):
        ''' Load worksheets from gsnb path. '''
        
        # create folder if it does not exist
        self.pathname = pathname
        if not os.path.isdir(self.pathname):
            os.makedirs(self.pathname)
        
        for filename in os.listdir(self.pathname):
            if os.path.isdir(self.pathname + '/' + filename): # not sure if this is safe
                worksheet = NormalWorksheet(self)
                worksheet.set_pathname(self.pathname + '/' + filename)
                worksheet.populate_meta()
                self.add_worksheet(worksheet)
        
    def add_worksheet(self, worksheet):
        self.worksheets[worksheet.get_id()] = worksheet
        self.add_change_code('new_worksheet', worksheet)
    
    def add_documentation_worksheet(self, worksheet):
        self.documentation_worksheets[worksheet.get_id()] = worksheet
        self.add_change_code('new_worksheet', worksheet)
    
    def set_active_worksheet(self, worksheet):
        self.active_worksheet = worksheet
        self.add_change_code('changed_active_worksheet', worksheet)
        
    def get_active_worksheet(self):
        return self.active_worksheet
        
    def get_worksheet_by_name(self, name):
        ''' return all worksheets matching "name" '''
        
        matching_worksheets = list()
        for worksheet in self.worksheets.values():
            if worksheet.get_name() == name:
                matching_worksheets.append(worksheet)
        return matching_worksheets
        
    def get_unsaved_worksheets(self):
        ''' return worksheets with unsaved changes '''
        
        matching_worksheets = list()
        for worksheet in self.worksheets.values():
            if worksheet.get_save_state() == 'modified':
                matching_worksheets.append(worksheet)
        return matching_worksheets
    
    def get_pathname(self):
        return self.pathname
        
    def find_unused_ws_id(self):
        ''' look for first natural number not currently used as a worksheet id '''

        count = 0
        while count in self.worksheets.keys():
            count += 1
        return count
    
    def get_untitled_postfix(self):
        ''' look for first natural number # not currently used as a "untitled#" worksheet name '''
        
        if len(self.get_worksheet_by_name('Untitled')) == 0:
            return ''
            
        count = 1
        while len(self.get_worksheet_by_name('Untitled' + str(count))) > 0:
            count += 1
        return str(count)
        
    def remove_worksheet_by_id(self, worksheet_id):
        worksheet = self.worksheets[worksheet_id]
        del(self.worksheets[worksheet_id])
        self.add_change_code('worksheet_removed', worksheet)
        

class Worksheet(Observable):

    def __init__(self, notebook):
        Observable.__init__(self)

        self.notebook = notebook
        self.pathname = ''
        self.save_state = 'saved'
        self.meta = {'name': 'Untitled', 'tags': {}, 'id_number': 0, 'backend': 'sage', 'last_change': ('admin', time.time()), 'last_accessed': datetime.datetime.fromtimestamp(0)}
        self.last_saved = datetime.datetime.fromtimestamp(0)
        self.cells = []
        self.active_cell = None
        self.busy_cells = set()
        self.modified_cells = set()
        self.kernel_state = None
        
        # set source language for syntax highlighting
        self.source_language_manager = GtkSource.LanguageManager()
        self.source_language_manager.set_search_path(('./resources/gtksourceview/language-specs',))
        self.source_language_code = self.source_language_manager.get_language('sage')
        self.source_language_markdown = self.source_language_manager.get_language('markdown')
        
        self.source_style_scheme_manager = GtkSource.StyleSchemeManager()
        self.source_style_scheme_manager.set_search_path(('./resources/gtksourceview/styles',))
        self.source_style_scheme = self.source_style_scheme_manager.get_scheme('sage')

        self.cursor_position = {'cell': None, 'cell_position': None, 'cell_size': None, 'position': None}

    def populate_meta(self):
        ''' load metadata from worksheet path. '''
        
        try: meta_filehandle = open(self.pathname + '/worksheet_conf.pickle', 'rb')
        except IOError: pass
        else:
            try: self.meta = pickle.load(meta_filehandle)
            except EOFError: pass
        try:
            timestamp = os.path.getmtime(self.pathname + '/worksheet_conf.pickle')
        except OSError:
            timestamp = 0
        else:
            self.last_saved = datetime.datetime.fromtimestamp(timestamp)
        
    def populate_cells(self):
        ''' Loads data from a sagenb worksheet path. For this has only been
            tested on Debian. This does not implement to whole sagenb file
            API, in fact it ignores most data and only reads code cells. '''
            
        self.populate_cells_from_pathname(self.pathname)
        self.set_last_accessed()
            
    def populate_cells_from_pathname(self, pathname):
        ''' Loads data from a sagenb worksheet path. For this has only been
            tested on Debian. This does not implement to whole sagenb file
            API, in fact it ignores most data and only reads code cells. '''
            
        if self.get_cell_count() == 0:
            try:
                html_filehandle = open(pathname + '/worksheet.html')
            except IOError:
                pass
            else:
                mode = 'html'
                blockbuffer = ''
                activate = True
                for line in html_filehandle:
                    if mode == 'html':
                        if line.startswith('{{{'):
                            blockbuffer = ''
                            mode = 'codecell'
                        elif line.startswith('MD{{{'):
                            blockbuffer = ''
                            mode = 'markdowncell'
                    elif mode == 'codecell':
                        if line.startswith('}}}'):
                            data = blockbuffer.split('\n///')
                            result_string = data[1].strip()

                            if activate == False: set_active = False
                            else:
                                set_active = True
                                activate = False
                            
                            cell = self.create_cell(position='last', text=data[0], activate=set_active)
                            if result_string != '':
                                if result_string.startswith('<image>'):
                                    filename = result_string[7:].split('<')[0]
                                    result = SageMathResultImage(self.pathname, filename, self)
                                    cell.set_result(result, show_animation=False)
                                else:
                                    result = SageMathResultText(result_string)
                                    cell.set_result(result, show_animation=False)
                            blockbuffer = ''
                            mode = 'html'
                        else:
                            blockbuffer += line
                    elif mode == 'markdowncell':
                        if line.startswith('}}}'):
                            data = blockbuffer.split('\n///')
                            result_string = data[1].strip()

                            if activate == False: set_active = False
                            #elif result_string != '': set_active = False
                            else:
                                set_active = True
                                activate = False

                            cell = self.create_markdowncell(position='last', text=data[0], activate=set_active)
                            if result_string != '':
                                result = MarkdownResult(result_string)
                                cell.set_result(result, show_animation=False)
                            blockbuffer = ''
                            mode = 'html'
                        else:
                            blockbuffer += line
                            
                if activate: self.create_cell(position='last', text='', activate=True)
                self.set_save_state('saved')
                
    def remove_all_cells(self):
        while len(self.cells) > 0:
            self.remove_cell(self.cells[0])
        
    def create_cell(self, position='last', text='', activate=False, set_unmodified=True):
        ''' Creates a code cell, then adds it to worksheet. '''
        
        if position == 'last': position = len(self.cells)
        new_cell = CodeCell(self)
        if text == '': new_cell.set_text(' ')
        self.add_cell(new_cell, position)
        GLib.idle_add(lambda: new_cell.first_set_text(text, activate, set_unmodified))
        return new_cell
        
    def create_markdowncell(self, position='last', text='', activate=False, set_unmodified=True):
        ''' Creates a text cell, then adds it to worksheet. '''
        
        if position == 'last': position = len(self.cells)
        new_cell = MarkdownCell(self)
        if text == '': new_cell.set_text(' ')
        self.add_cell(new_cell, position)
        GLib.idle_add(lambda: new_cell.first_set_text(text, activate, set_unmodified))
        return new_cell
        
    def add_cell(self, cell, position='last'):
        ''' Adds cell object to worksheet. '''
        
        if position == 'last': position = len(self.cells)
        self.cells.insert(position, cell)
        self.add_change_code('new_cell', cell)
        self.set_save_state('modified')
        cell.connect('modified-changed', self.on_modified_changed)
    
    def move_cell(self, position, new_position):
        ''' Move cell '''
        
        if len(self.cells) > max(position, new_position):
            self.cells[position], self.cells[new_position] = self.cells[new_position], self.cells[position]
            #self.cells[position].get_worksheet_position()
            #self.cells[new_position].get_worksheet_position()
            self.add_change_code('cell_moved', {'position': position, 'new_position': new_position})
            self.set_save_state('modified')
        
    def on_modified_changed(self, cell):
        if cell.get_modified() == True:
            self.add_modified_cell(cell)
        else:
            self.remove_modified_cell(cell)
        if self.get_modified_cell_count() > 0:
            self.set_save_state('modified')
        else:
            self.set_save_state('saved')
    
    def remove_cell(self, cell):
        try: index = self.cells.index(cell)
        except ValueError: pass
        else:
            self.cells[index].stop_evaluation()
            del(self.cells[index])
            self.add_change_code('deleted_cell', cell.get_worksheet_position())
            self.set_save_state('modified')
            if len(self.cells) == 0:
                self.active_cell = None
    
    def set_active_cell(self, cell):
        if not self.active_cell == None: self.add_change_code('new_inactive_cell', self.active_cell)
        self.active_cell = cell
        self.add_change_code('new_active_cell', cell)
    
    def get_active_cell(self):
        return self.active_cell
    
    def get_next_cell(self, cell):
        try: lindex = self.cells.index(cell)
        except ValueError: return None
        else:
            try: return self.cells[lindex+1]
            except IndexError: return None
    
    def get_next_visible_cell(self, cell):
        try: lindex = self.cells.index(cell)
        except ValueError: return None
        else:
            while lindex < (len(self.cells)-1) and not isinstance(self.cells[lindex+1], CodeCell) \
                and not (isinstance(self.cells[lindex+1], MarkdownCell) and self.cells[lindex+1].get_result() == None):
                lindex += 1 
            try: return self.cells[lindex+1]
            except IndexError: return None
    
    def get_prev_cell(self, cell):
        try: lindex = self.cells.index(cell)
        except ValueError: return None
        else: return self.cells[lindex-1] if lindex > 0 else None
    
    def get_prev_visible_cell(self, cell):
        try: lindex = self.cells.index(cell)
        except ValueError: return None
        else:
            while lindex > 0 and not isinstance(self.cells[lindex-1], CodeCell) and not (isinstance(self.cells[lindex-1], MarkdownCell) and self.cells[lindex-1].get_result() == None):
                lindex -= 1 
            return self.cells[lindex-1] if lindex > 0 else None
    
    def get_cell_count(self):
        return len(self.cells)
        
    def save_meta_to_disk(self):
        try: meta_filehandle = open(self.pathname + '/worksheet_conf.pickle', 'wb')
        except IOError: pass
        else:
            pickle.dump(self.meta, meta_filehandle)
            self.last_saved = datetime.datetime.now()
    
    def save_to_disk(self):
        self.save_meta_to_disk()
        try: content_filehandle = open(self.pathname + '/worksheet.html', 'w+')
        except IOError: pass
        else:
            for key, cell in enumerate(self.cells):
                cell_content = cell.get_text(cell.get_start_iter(), cell.get_end_iter(), False)
                result_string = cell.get_result_string()
                markdown_prefix = 'MD' if isinstance(cell, MarkdownCell) else ''
                content_filehandle.write(markdown_prefix + '{{{id=' + str(key) + '|\n' + cell_content + '\n///' + result_string + '\n}}}\n')
            self.reset_modified_cells()                
            self.set_save_state('saved')
            
    def remove_from_disk(self):
        shutil.rmtree(self.pathname)
        
    def set_save_state(self, state):
        if self.save_state != state:
            self.save_state = state
            self.add_change_code('save_state_change', self.save_state)
            
        if self.save_state == 'saved':
            for cell in self.cells:
                cell.set_modified(False)
        
    def get_save_state(self):
        return self.save_state
        
    def export_gsnb(self, pathname):
        if not pathname.endswith('.gsnb'): pathname += '.gsnb'
        tar = tarfile.open(pathname, 'w:bz2')
        tar.add(self.get_pathname(), arcname='0')
        tar.close()
    
    def get_pathname(self):
        return self.pathname
    
    def set_pathname(self, pathname):
        self.pathname = pathname
        if not os.path.isdir(self.pathname):
            os.makedirs(self.pathname)
    
    def get_cells_in_order(self):
        pass
        
    def get_source_language_code(self):
        return self.source_language_code
        
    def get_source_language_markdown(self):
        return self.source_language_markdown
        
    def get_source_style_scheme(self):
        return self.source_style_scheme
        
    def get_name(self):
        return self.meta['name']
        
    def set_id(self, id):
        self.meta['id_number'] = id
        
    def get_id(self):
        return self.meta['id_number']
        
    def get_last_saved(self):
        return self.last_saved
        
    def set_last_accessed(self):
        self.meta['last_accessed'] = datetime.datetime.now()

    def get_last_accessed(self):
        return self.meta.get('last_accessed', datetime.datetime.fromtimestamp(0))
        
    def set_kernel_state(self, state):
        self.kernel_state = state
        self.add_change_code('kernel_state_changed', self.kernel_state)
    
    def get_kernel_state(self):
        return self.kernel_state
        
    def restart_kernel(self):
        self.add_change_code('kernel_to_restart', None)

    def stop_evaluation(self):
        self.add_change_code('ws_evaluation_to_stop', None)
        
    def add_busy_cell(self, cell):
        self.busy_cells.add(cell)
        self.add_change_code('busy_cell_count_changed', self.get_busy_cell_count())
        
    def remove_busy_cell(self, cell):
        self.busy_cells.discard(cell)
        self.add_change_code('busy_cell_count_changed', self.get_busy_cell_count())

    def get_busy_cell_count(self):
        return len(self.busy_cells)

    def add_modified_cell(self, cell):
        self.modified_cells.add(cell)
        
    def remove_modified_cell(self, cell):
        self.modified_cells.discard(cell)

    def reset_modified_cells(self):
        self.modified_cells = set()

    def get_modified_cell_count(self):
        return len(self.modified_cells)

    def is_active_worksheet(self):
        return True if self.notebook.get_active_worksheet() == self else False
        

class NormalWorksheet(Worksheet):

    def __init__(self, notebook):
        Worksheet.__init__(self, notebook)

    def set_name(self, name):
        self.meta['name'] = name
        self.add_change_code('worksheet_name_changed', name)
        

class DocumentationWorksheet(Worksheet):

    def __init__(self, notebook):
        Worksheet.__init__(self, notebook)


class Cell(GtkSource.Buffer, Observable):

    def __init__(self, worksheet):
        GtkSource.Buffer.__init__(self)
        Observable.__init__(self)

        self.worksheet = worksheet
        self.worksheet_position = None

        self.set_modified(False)
        self.set_highlight_matching_brackets(False)

        self.result_blob = None
        self.result = None

    def first_set_text(self, text, activate=False, set_unmodified=True):
        self.set_text(text)
        self.place_cursor(self.get_start_iter())
        if activate == True:
            self.worksheet.set_active_cell(self)
        if set_unmodified == True:
            self.set_modified(False)
        
    def stop_evaluation(self):
        self.change_state('evaluation_to_stop')

    def set_result_blob(self, result_blob):
        self.result_blob = result_blob
        
    def set_result(self, result, show_animation=True):
        ''' set new result object. '''
        
        self.result = result
        self.add_change_code('new_result', {'result': self.result, 'show_animation': show_animation})
        self.set_modified(True)
        
    def get_result(self):
        return self.result
        
    def remove_result(self, show_animation=True):
        ''' remove result including all of it's assets. '''
        
        if isinstance(self.result, SageMathResultImage): self.result.delete_assets()
        self.result = None
        self.add_change_code('new_result', {'result': self.result, 'show_animation': show_animation})
        self.set_modified(True)
    
    def get_result_string(self):
        result = self.get_result()
        if result != None:
            if isinstance(result, SageMathResultText):
                result_string = result.get_as_raw_text()
                return '\n' + result_string if result_string != '' else ''
            elif isinstance(result, SageMathResultImage):
                result_string = result.get_as_raw_text()
                return '\n' + result_string if result_string != '' else ''
            elif isinstance(result, MarkdownResult):
                result_string = result.get_as_raw_text()
                return '\n' + result_string if result_string != '' else ''
        else:
            return ''
        
    def get_worksheet(self):
        return self.worksheet

    def get_worksheet_position(self):
        cells = self.get_worksheet().cells
        try: position = cells.index(self)
        except ValueError: return self.worksheet_position
        else: 
            self.worksheet_position = position
            return position
        
    def is_active_cell(self):
        return True if self.get_worksheet().get_active_cell() == self else False
        
    def is_active_cell_of_active_worksheet(self):
        worksheet = self.get_worksheet()
        return True if worksheet.is_active_worksheet() and worksheet.get_active_cell() == self else False
        

class CodeCell(Cell):

    def __init__(self, worksheet):
        Cell.__init__(self, worksheet)
        
        # possible states: idle, ready_for_evaluation, queued_for_evaluation
        # evaluation_in_progress, evaluation_to_stop
        self.state = 'idle'
        
        # syntax highlighting
        self.set_language(self.get_worksheet().get_source_language_code())
        self.set_style_scheme(self.get_worksheet().get_source_style_scheme())
    
    def evaluate(self):
        self.remove_result()
        self.stop_evaluation()
        self.change_state('ready_for_evaluation')

    def parse_result_blob(self):
    
        # look for image files (plots), create image result object if there are any
        files = self.result_blob['files']
        if 'sage0.png' in files:
            count = 0
            tmp_filename = 'sage0.png'
            while (tmp_filename in files):
                count += 1
                tmp_filename = 'sage' + str(count) + '.png'
            tmp_filename = 'sage' + str(count-1) + '.png'
            result = SageMathResultImage(self.result_blob['path'], tmp_filename, self.get_worksheet())
            self.set_result(result)
        
        # make text result object if no plot image was found
        elif self.result_blob['text'] != '':
            result = SageMathResultText(self.result_blob['text'])
            self.set_result(result)

    def change_state(self, state):
        self.state = state
        self.add_change_code('cell_state_change', self.state)
        
        # promote info to associated worksheet
        if self.state != 'idle':
            self.worksheet.add_busy_cell(self)
        else:
            self.worksheet.remove_busy_cell(self)
            

class MarkdownCell(Cell):

    def __init__(self, worksheet):
        Cell.__init__(self, worksheet)

        # possible states: edit, display, ready_for_evaluation, queued_for_evaluation
        # evaluation_in_progress, evaluation_to_stop
        self.state = 'edit'
        
        # syntax highlighting
        self.set_language(self.get_worksheet().get_source_language_markdown())
        self.set_style_scheme(self.get_worksheet().get_source_style_scheme())

    def evaluate(self):
        self.remove_result()
        self.stop_evaluation()
        self.change_state('ready_for_evaluation')

    def parse_result_blob(self):
        result = MarkdownResult(self.result_blob)
        self.set_result(result)

    def change_state(self, state):
        self.state = state
        self.add_change_code('cell_state_change', self.state)
        
        # promote info to associated worksheet
        if self.state != 'edit' and self.state != 'display':
            self.worksheet.add_busy_cell(self)
        else:
            self.worksheet.remove_busy_cell(self)
            

class Result():

    def __init__(self):
        pass


class MarkdownResult(Result):

    def __init__(self, result_blob):
        Result.__init__(self)
        self.buildable = ''
        self.replacements = list()
        result_blob = result_blob.split('SPLITMARKER')

        for part in result_blob:
            if part.startswith('<interface>'):
                self.buildable += part
            elif part.startswith('<child>'):
                self.buildable += part + 'PLACEHOLDER'
            elif part.endswith('</child>'):
                self.buildable += part
            elif part.endswith('</interface>'):
                self.buildable += part
            elif len(part.strip()) > 0:
                self.replacements.append(part)
                
    def get_buildable(self):
        return self.buildable
    
    def get_replacements(self):
        return self.replacements
        
    def get_as_raw_text(self):
        buildable = self.buildable
        replacements = self.replacements
        buildable = buildable.replace('<child>', 'SPLITMARKER<child>', 1)
        buildable = buildable.replace('</child>', '</child>SPLITMARKER')
        
        for value in replacements:
            buildable = buildable.replace('PLACEHOLDER', 'SPLITMARKER' + value + 'SPLITMARKER', 1)
        return buildable


class SageMathResultText(Result):

    def __init__(self, result_text):
        Result.__init__(self)
        self.result_text = result_text.rstrip()
        
    def get_as_raw_text(self):
        return self.result_text
        

class SageMathResultImage(Result):

    def __init__(self, tmp_pathname, tmp_filename, worksheet):
        Result.__init__(self)
        self.worksheet = worksheet
        self.worksheet_pathname = self.worksheet.get_pathname()

        if tmp_pathname != self.worksheet_pathname:
            self.filename = self.find_unused_filename()
            self.pathname = self.worksheet_pathname + '/' + self.filename
            shutil.copyfile(tmp_pathname + tmp_filename, self.pathname)
            shutil.rmtree(tmp_pathname)
        else:
            self.filename = tmp_filename
            self.pathname = self.worksheet_pathname + '/' + self.filename
        
    def find_unused_filename(self):
        count = 0
        tmp_filename = self.worksheet.get_pathname() + '/result' + str(count) + '.png'
        while os.path.isfile(tmp_filename):
            count += 1
            tmp_filename = self.worksheet.get_pathname() + '/result' + str(count) + '.png'
        return 'result' + str(count) + '.png'
        
    def get_absolute_path(self):
        return self.pathname
        
    def get_as_raw_text(self):
        return '<image>' + self.filename + '</image>'

    def delete_assets(self):
        try: os.remove(self.pathname)
        except FileNotFoundError: pass


#class SageMathResult3DPlot():
