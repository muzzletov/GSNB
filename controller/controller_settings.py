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
import os.path
import pickle


class Settings(object):
    ''' Settings controller for saving application state. '''
    
    def __init__(self):
        self.gtksettings = Gtk.Settings.get_default()
        
        self.pathname = os.path.expanduser('~') + '/.sage/gsnb'
        
        self.data = dict()
        
        if not self.unpickle():
            self.set_default()
            self.pickle()
            
        # load gsettings schema concerning application menu / window decorations
        self.button_layout = self.gtksettings.get_property('gtk-decoration-layout')
    
    def set_default(self):
        self.data['window_state'] = dict()
        self.data['window_state']['width'] = 1020
        self.data['window_state']['height'] = 550
        self.data['window_state']['is_maximized'] = False
        self.data['window_state']['is_fullscreen'] = False
        self.data['window_state']['paned_position'] = 250
        #self.data['window_state']['sidebar_paned_position'] = 300
        
    def unpickle(self):
        ''' Load settings from gsnb path. '''
        
        # create folder if it does not exist
        if not os.path.isdir(self.pathname):
            os.makedirs(self.pathname)
        
        try: filehandle = open(self.pathname + '/settings.pickle', 'rb')
        except IOError: return False
        else:
            try: self.data = pickle.load(filehandle)
            except EOFError: False
            
        return True
        
    def pickle(self):
        ''' Save settings in gsnb path. '''
        
        try: filehandle = open(self.pathname + '/settings.pickle', 'wb')
        except IOError: return False
        else: pickle.dump(self.data, filehandle)
        


