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
import pexpect
import os
import sys
import tempfile
import shutil
import time
import _thread as thread, queue
from os.path import expanduser


class ComputeQueue(object):

    def __init__(self):
        self.observers = set()
        self.states = dict()
        self.query_queues = dict() # put computation tasks on here
        self.query_ignore_counter = dict()
        self.active_queries = dict()
        self.result_blobs_queue = queue.Queue() # computation results are put on here
        self.change_code_queue = queue.Queue() # change code for observers are put on here
        self.interface = InterfacePexpect()
        GObject.timeout_add(50, self.results_loop)
        GObject.timeout_add(50, self.change_code_loop)
        
    def compute_loop(self, worksheet_id):
        ''' wait for queries, run them and put results on the queue.
            this method runs in thread. '''

        while True:
            time.sleep(0.05)
            
            # if query complete set state idle
            if self.get_state(worksheet_id) == 'busy':
                self.states[worksheet_id] = self.active_queries[worksheet_id].get_state()
            
            # check for tasks, start computation
            if self.get_state(worksheet_id) == 'idle':
                try:
                    self.active_queries[worksheet_id] = self.query_queues[worksheet_id].get(block=False)
                except queue.Empty:
                    pass
                else:
                    cell = self.active_queries[worksheet_id].get_cell()
                    if self.active_queries[worksheet_id].ignore_counter >= self.query_ignore_counter.get(cell, 0):
                        self.states[worksheet_id] = 'busy'
                        self.add_change_code('evaluation_started', self.active_queries[worksheet_id])
                        result_blob = self.active_queries[worksheet_id].evaluate(self.interface)
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
                
    def add_change_code_now(self, change_code, parameter):
        for observer in self.observers:
                observer.change_notification(change_code, self, parameter)
                
    def results_loop(self):
        ''' wait for results and add them to their cells '''

        try:
            result_blob = self.result_blobs_queue.get(block=False)
        except queue.Empty:
            pass
        else:
            self.add_change_code('evaluation_finished', result_blob)
        return True
        
    def get_state(self, worksheet_id):
        if not worksheet_id in self.states.keys():
            self.states[worksheet_id] = 'idle'
        return self.states[worksheet_id]
        
    def get_active_query(self, worksheet_id):
        if not worksheet_id in self.active_queries.keys():
            self.active_queries[worksheet_id] = None
        return self.active_queries[worksheet_id]
        
    def get_query_queue(self, worksheet_id):
        if not worksheet_id in self.query_queues.keys():
            self.query_queues[worksheet_id] = queue.Queue()
            thread.start_new_thread(self.compute_loop, (worksheet_id,))
        return self.query_queues[worksheet_id]
    
    def add_query(self, query):
        queue = self.get_query_queue(query.worksheet_id)
        query.ignore_counter = self.query_ignore_counter.get(query.get_cell(), 0) + 1
        queue.put(query)
        self.add_change_code('query_queued', query)
        
    def stop_evaluation_by_cell(self, cell):
        worksheet_id = cell.get_worksheet().get_id()
        queue = self.get_query_queue(worksheet_id)
        self.query_ignore_counter[cell] = 1 + self.query_ignore_counter.get(cell, 0)
        if self.get_state(worksheet_id) == 'busy' and self.get_active_query(worksheet_id).get_cell() == cell:
            self.active_queries[worksheet_id].stop_evaluation()
            self.states[worksheet_id] = 'idle'
        self.add_change_code_now('cell_evaluation_stopped', cell)
        
    def stop_evaluation_by_worksheet(self, worksheet_id):
        queue = self.get_query_queue(worksheet_id)

        while not queue.empty():
            query = queue.get(block=False)
            cell = query.get_cell()
            self.add_change_code_now('cell_evaluation_stopped', cell)
            
        if self.get_state(worksheet_id) == 'busy':
            cell = self.get_active_query(worksheet_id).get_cell()
            self.get_active_query(worksheet_id).stop_evaluation()
            self.add_change_code_now('cell_evaluation_stopped', cell)

        self.states[worksheet_id] = 'idle'
        
    def add_result_blob(self, result):
        self.result_blobs_queue.put(result)
            
    def start_process(self, worksheet):
        self.interface.get_process(worksheet.get_id())
        self.add_change_code('kernel_started', worksheet)
    
    def restart_process(self, worksheet):
        while len(worksheet.busy_cells) > 0:
            time.sleep(0.05)
        self.interface.stop_process(worksheet.get_id())
        thread.start_new_thread(self.start_process, (worksheet,))
    

class SageMathQuery():

    def __init__(self, worksheet_id, cell, query_string = ''):
        self.set_query_string(query_string)
        self.worksheet_id = worksheet_id
        self.cell = cell
        self.state = 'idle'
        self.interface = None
        self.ignore_counter = 0

    def set_query_string(self, query_string):
        self.query_string = query_string
        
    def evaluate(self, interface, sage_mode = True):
        self.interface = interface
        self.state = 'busy'
        query_string = self.query_string
        result_blob = interface.run(self.query_string, self.worksheet_id, sage_mode)
        
        self.state = 'idle'
        return {'worksheet_id': self.worksheet_id, 'cell': self.cell, 'result_blob': result_blob}
    
    def stop_evaluation(self):
        if self.state == 'busy':
            self.interface.stop_computation()
            self.state = 'idle'
    
    def get_cell(self):
        return self.cell
        
    def get_state(self):
        return self.state


class SageMathProcess():

    def __init__(self):

        self.state = 'not started'

    def start(self):
        ''' initialize python process '''
        
        os.environ['SAGE_LOCAL'] = '/usr/share/sagemath/'
        self.process = pexpect.spawn('python2.7')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('import sys')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('import tempfile')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('import shutil')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('import os; import base64')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('import sagenb.misc.support as _support_; from sage.all_notebook import *')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('from sage.misc.displayhook import DisplayHook')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('sys.displayhook = DisplayHook()')
        self.process.expect('>>> ', timeout=None)
        self.process.sendline('sage.plot.plot.EMBEDDED_MODE = True')
        self.process.expect('>>> ', timeout=None)
        
        self.expect_result = True

        # list of temporary directory paths
        self.temporary_directory_paths = []

        # create permanent directory
        self.permanent_directory_path = expanduser('~/.sage/sc_store/' )
        if not os.path.exists(self.permanent_directory_path):
            os.mkdir(self.permanent_directory_path)
            
        self.state = 'started'
    
    def run(self, query_string, sage_mode = True):

        self.expect_result = True

        # move to temporary directory
        self.process.sendline('print tempfile.mkdtemp()')
        self.process.expect('>>> ', timeout=None)
        td_path = str(self.process.before).split('\\r\\n')
        td_path = td_path[1]
        self.temporary_directory_paths.append(td_path)
        self.process.sendline('os.chdir(\'' + td_path + '\')')
        self.process.expect('>>> ', timeout=None)
        
        # run query
        if sage_mode == True:
            self.process.sendline('exec(_support_.preparse_worksheet_cell('+repr(query_string.strip())+', globals()))')
        else:
            self.process.sendline(query_string)
            
        # return results
        self.process.expect('>>> ', timeout=None)
        if self.expect_result == True:
            results_text = '\n'.join(str(self.process.before).split('\\r\\n')[1:-1])
            results_files = os.listdir(td_path)
            result_blob = {'text' : results_text, 'files' : results_files, 'path' : td_path + '/'}
            self.process.sendline('os.chdir(\'' + self.permanent_directory_path + '\')')
            self.process.expect('>>> ', timeout=None)
            return result_blob
        else:
            return None
    
    def delete_temporary_directories(self):
        for td_path in self.temporary_directory_paths:
            self.process.sendline('shutil.rmtree(\'' + td_path + '\')')
            self.process.expect('>>> ', timeout=None)
        
    def stop_computation(self):
        self.expect_result = False
        self.process.sendline(chr(3)) # ctrl-c
        self.process.expect('>>> ', timeout=None)

    def __del__(self):
        self.delete_temporary_directories()
        self.process.kill(1)


class InterfacePexpect():

    def __init__(self):
        
        self.sagemath_processes = {}
    
    def get_process(self, worksheet_id):
        ''' Returns present or new sagemath process. '''
        
        if not str(worksheet_id) in self.sagemath_processes.keys():
            self.sagemath_processes[str(worksheet_id)] = SageMathProcess()
            self.sagemath_processes[str(worksheet_id)].start()
        else:
            while self.sagemath_processes[str(worksheet_id)].state == 'not started':
                time.sleep(0.05)
            return self.sagemath_processes[str(worksheet_id)]
        
    def stop_process(self, worksheet_id):
        ''' Kills sagemath process if present. '''

        if str(worksheet_id) in self.sagemath_processes.keys():
            del(self.sagemath_processes[str(worksheet_id)])

    def run(self, query_string, worksheet_id, sage_mode = True):
        process = self.get_process(worksheet_id)
        process.stop_computation()
        return process.run(query_string, sage_mode)
        
    def stop_computation_by_worksheet(self, worksheet_id):
        process = self.get_process(worksheet_id)
        process.stop_computation()
        
    def stop_computation(self):
        for process in self.sagemath_processes:
            if self.sagemath_processes[process].state == 'started':
                self.sagemath_processes[process].stop_computation()
        
    def __del__(self):
        ''' destructor, unlinks all processes '''
        self.sagemath_processes = {}
        

