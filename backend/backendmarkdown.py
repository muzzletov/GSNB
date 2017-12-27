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
from gi.repository import GLib, GObject
import markdown
import time
import _thread as thread, queue
import bleach


class ComputeQueue(object):

    def __init__(self):
        self.observers = set()
        self.state = 'idle'
        self.query_queue = queue.Queue() # put computation tasks on here
        self.query_ignore_counter = dict()
        self.active_query = None
        self.result_blobs_queue = queue.Queue() # computation results are put on here
        self.change_code_queue = queue.Queue() # change code for observers are put on here
        thread.start_new_thread(self.compute_loop, ())
        GObject.timeout_add(50, self.results_loop)
        GObject.timeout_add(50, self.change_code_loop)
        
    def compute_loop(self):
        ''' wait for queries, run them and put results on the queue.
            this method runs in thread. '''

        while True:
            time.sleep(0.05)
            
            # if query complete set state idle
            if self.state == 'busy':
                self.state = self.active_query.get_state()
            
            # check for tasks, start computation
            if self.state == 'idle':
                try:
                    self.active_query = self.query_queue.get(block=False)
                except queue.Empty:
                    pass
                else:
                    cell = self.active_query.get_cell()
                    if self.active_query.ignore_counter >= self.query_ignore_counter.get(cell, 0):
                        self.state = 'busy'
                        self.add_change_code('evaluation_started', self.active_query)
                        result_blob = self.active_query.evaluate()
                        self.add_result_blob(result_blob)
                    else: pass
                        
    def change_code_loop(self):
        ''' notify observers '''

        try:
            change_code = self.change_code_queue.get(block=False)
        except queue.Empty:
            pass
        else:
            for observer in self.observers:
                observer.change_notification(change_code['change_code'], self, change_code['parameter'])
        return True
    
    def register_observer(self, observer):
        ''' Observer call this method to register themselves with observable
            objects. They have themselves to implement a method
            'change_notification(change_code, parameter)' which they observable
            will call when it's state changes. '''
        
        self.observers.add(observer)

    def add_change_code(self, change_code, parameter):
        self.change_code_queue.put({'change_code': change_code, 'parameter': parameter})
                
    def results_loop(self):
        ''' wait for results and add them to their cells '''

        try:
            result_blob = self.result_blobs_queue.get(block=False)
        except queue.Empty:
            pass
        else:
            self.add_change_code('evaluation_finished', result_blob)
        return True
    
    def add_query(self, query):
        query.ignore_counter = self.query_ignore_counter.get(query.get_cell(), 0) + 1
        self.query_queue.put(query)
        self.add_change_code('query_queued', query)
        
    def stop_evaluation_by_cell(self, cell):
        self.query_ignore_counter[cell] = 1 + self.query_ignore_counter.get(cell, 0)
        if self.state == 'busy' and self.active_query.get_cell() == cell:
            self.active_query.stop_evaluation()
            self.state = 'idle'
        self.add_change_code('cell_evaluation_stopped', cell)
        
    def add_result_blob(self, result):
        self.result_blobs_queue.put(result)
        
    def stop_computation(self):
        while not self.query_queue.empty():
            self.query_queue.get(block=False)
        if self.state == 'busy':
            self.active_query.stop_evaluation()
            self.state = 'idle'
    

class MarkdownQuery():

    def __init__(self, worksheet_id, cell, query_string = ''):
        self.set_query_string(query_string)
        self.worksheet_id = worksheet_id
        self.cell = cell
        self.state = 'idle'
        self.ignore_counter = 0
        
        # wrapper
        self.wrapper_start = '''<interface>
    <object class="GtkBox" id="buildablewrap">
        <property name="orientation">vertical</property>
        <property name="can_focus">False</property>
'''
        self.wrapper_end= '''
    </object>
</interface>'''

        # paragraphs
        self.p_start = '''        SPLITMARKER<child>
            <object class="GtkLabel" id="label-POSITION">
                <property name="can_focus">False</property>
                <property name="use_markup">True</property>
                <property name="track_visited_links">False</property>
                <property name="wrap">True</property>
                <property name="wrap_mode">2</property>
                <property name="xalign">0</property>
                <property name="single_line_mode">False</property>
                <property name="label" translatable="no">SPLITMARKER'''
        self.p_end = '''SPLITMARKER</property>
                <style>
                    <class name="p"/>
                </style>
            </object>
            <packing>
                <property name="expand">True</property>
                <property name="fill">True</property>
                <property name="position">POSITION</property>
            </packing>
        </child>SPLITMARKER'''
        self.header_start = '''        SPLITMARKER<child>
            <object class="GtkLabel" id="label-POSITION">
                <property name="can_focus">False</property>
                <property name="use_markup">True</property>
                <property name="track_visited_links">False</property>
                <property name="wrap">True</property>
                <property name="wrap_mode">2</property>
                <property name="xalign">0</property>
                <property name="label" translatable="no">SPLITMARKER'''
        self.header_end = '''SPLITMARKER</property>
                <style>
                    <class name="h[[[LEVEL]]]"/>
                </style>
            </object>
            <packing>
                <property name="expand">False</property>
                <property name="fill">False</property>
                <property name="position">POSITION</property>
            </packing>
        </child>SPLITMARKER'''

    def set_query_string(self, query_string):
        self.query_string = query_string
        
    def evaluate(self):
        ''' evaluates markdown cell, paragraph text is handled seperately
            because gtk.builder doesn't seem to work with pango markup. 
            it is later inserted in the built gtk widget. in future it would
            probably be good to have a distinct markdown widget to
            handle this. '''
            
        self.state = 'busy'
        result_blob = markdown.markdown(self.query_string)
        
        # remove unsupported tags with bleach
        supported_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'a']
        supported_tags += ['em', 'strong', 'code', 'i', 'b', 'tt']
        supported_attributes = {'a': ['href', 'title']}
        result_blob = bleach.clean(result_blob, tags=supported_tags, attributes=supported_attributes)
        
        # markup
        result_blob = result_blob.replace('<em>', '<i>')
        result_blob = result_blob.replace('</em>', '</i>')
        result_blob = result_blob.replace('<strong>', '<b>')
        result_blob = result_blob.replace('</strong>', '</b>')
        result_blob = result_blob.replace('<code>', '<tt>')
        result_blob = result_blob.replace('</code>', '</tt>')
        
        # paragraphs
        p_count = 0
        result_blob = result_blob.replace('<p>', self.p_start)
        result_blob = result_blob.replace('</p>', self.p_end)
        
        for level in range(6):
            result_blob = result_blob.replace('<h' + str(level+1) + '>', self.header_start)
            header_end = self.header_end.replace('[[[LEVEL]]]', str(level+1))
            result_blob = result_blob.replace('</h' + str(level+1) + '>', header_end)
        
        p_count = 0
        while result_blob.find('POSITION') != -1:
            result_blob = result_blob.replace('POSITION',  str(p_count), 2)
            p_count += 1
            
        # wrapper
        result_blob = self.wrapper_start + result_blob + 'SPLITMARKER' + self.wrapper_end

        self.state = 'idle'
        return {'worksheet_id': self.worksheet_id, 'cell': self.cell, 'result_blob': result_blob}
    
    def stop_evaluation(self):
        if self.state == 'busy':
            pass
    
    def get_cell(self):
        return self.cell
        
    def get_state(self):
        return self.state
