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

import _thread as thread, queue
from backend.backendsagemath import SageMathQuery, ComputeQueue as ComputeQueueSagemath
from backend.backendmarkdown import MarkdownQuery, ComputeQueue as ComputeQueueMarkdown


class BackendControllerMarkdown():
    ''' feed markdown backend, update controller '''
    
    def __init__(self):
        self.compute_queue = ComputeQueueMarkdown()
        self.compute_queue.register_observer(self)
        
    def change_notification(self, change_code, notifying_object, parameter):
        
        if change_code == 'cell_state_change' and parameter == 'ready_for_evaluation':
            cell = notifying_object
            query_string = cell.get_text(cell.get_start_iter(), cell.get_end_iter(), False)
            query = MarkdownQuery(cell.worksheet.get_id(), cell, query_string)
            self.compute_queue.add_query(query)
            
        if change_code == 'cell_state_change' and parameter == 'evaluation_to_stop':
            cell = notifying_object
            self.compute_queue.stop_evaluation_by_cell(cell)
        
        if change_code == 'query_queued':
            query = parameter
            cell = query.get_cell()
            cell.change_state('queued_for_evaluation')
    
        if change_code == 'evaluation_started':
            query = parameter
            cell = query.get_cell()
            cell.change_state('evaluation_in_progress')

        if change_code == 'cell_evaluation_stopped':
            cell = parameter
            cell.change_state('edit')

        if change_code == 'evaluation_finished':
            result_blob = parameter
            result_blob['cell'].change_state('edit')
            result_blob['cell'].set_result_blob(result_blob['result_blob'])
            result_blob['cell'].parse_result_blob()
            result_blob['cell'].change_state('display')
    

class BackendControllerSageMath():
    ''' feed sagemath backend, update controller '''
    
    def __init__(self):
        self.compute_queue = ComputeQueueSagemath()
        self.compute_queue.register_observer(self)
    
    def change_notification(self, change_code, notifying_object, parameter):
        
        if change_code == 'changed_active_worksheet':
            worksheet = parameter
            thread.start_new_thread(self.compute_queue.start_process, (worksheet,))
            worksheet.set_kernel_state('starting')
            
        if change_code == 'kernel_started':
            worksheet = parameter
            worksheet.set_kernel_state('running')
            
        if change_code == 'kernel_to_restart':
            worksheet = notifying_object
            worksheet.stop_evaluation()
            thread.start_new_thread(self.compute_queue.restart_process, (worksheet,))
            worksheet.set_kernel_state('starting')
        
        if change_code == 'ws_evaluation_to_stop':
            worksheet = notifying_object
            self.compute_queue.stop_evaluation_by_worksheet(worksheet.get_id())
        
        if change_code == 'cell_state_change' and parameter == 'ready_for_evaluation':
            cell = notifying_object
            query_string = cell.get_text(cell.get_start_iter(), cell.get_end_iter(), False)
            query = SageMathQuery(cell.worksheet.get_id(), cell, query_string)
            self.compute_queue.add_query(query)
            
        if change_code == 'cell_state_change' and parameter == 'evaluation_to_stop':
            cell = notifying_object
            self.compute_queue.stop_evaluation_by_cell(cell)
        
        if change_code == 'query_queued':
            query = parameter
            cell = query.get_cell()
            cell.change_state('queued_for_evaluation')
    
        if change_code == 'evaluation_started':
            query = parameter
            cell = query.get_cell()
            cell.change_state('evaluation_in_progress')

        if change_code == 'cell_evaluation_stopped':
            cell = parameter
            cell.change_state('idle')

        if change_code == 'evaluation_finished':
            result_blob = parameter
            result_blob['cell'].change_state('idle')
            if result_blob['result_blob'] != None:
                result_blob['cell'].set_result_blob(result_blob['result_blob'])
                result_blob['cell'].parse_result_blob()
