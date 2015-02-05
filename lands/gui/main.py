#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
GUI Interface for Lands
"""

import sys
from PyQt4 import QtGui, QtCore
import random
import threading
import platec
from lands.world import World
import lands.geo
from lands.geo import *
from view import *
from lands.plates import *

class GenerateDialog(QtGui.QDialog):

    def __init__(self,parent):
        QtGui.QDialog.__init__(self, parent)
        self._init_ui()

    def _init_ui(self):            
        self.resize(500, 300)
        self.setWindowTitle('Generate a new world')
        grid = QtGui.QGridLayout()

        seed =  random.randint(0, 65535)

        name_label = QtGui.QLabel('Name')
        grid.addWidget(name_label, 0,0,1,1)
        name = 'world_seed_%i' % seed 
        self.name_value = QtGui.QLineEdit(name)
        grid.addWidget(self.name_value, 0,1,1,2)

        seed_label = QtGui.QLabel('Seed')
        grid.addWidget(seed_label, 1,0,1,1)        
        self.seed_value = self._spinner_box(0, 65525, seed)
        grid.addWidget(self.seed_value, 1,1,1,2)

        width_label = QtGui.QLabel('Width')
        grid.addWidget(width_label, 2,0,1,1)        
        self.width_value = self._spinner_box(100, 8192, 512)
        grid.addWidget(self.width_value, 2,1,1,2)

        height_label = QtGui.QLabel('Height')
        grid.addWidget(height_label, 3,0,1,1)
        self.height_value = self._spinner_box(100, 8192, 512)
        grid.addWidget(self.height_value, 3,1,1,2)        

        plates_num_label = QtGui.QLabel('Number of plates')
        grid.addWidget(plates_num_label, 4,0,1,1)
        self.plates_num_value = self._spinner_box(2, 100, 10)
        grid.addWidget(self.plates_num_value, 4,1,1,2)

        platesres_w_label = QtGui.QLabel('Plates resolution (width)')
        grid.addWidget(platesres_w_label, 5,0,1,1)
        self.platesres_w_value = self._spinner_box(50, 4096, 512)
        grid.addWidget(self.platesres_w_value, 5,1,1,2)

        platesres_h_label = QtGui.QLabel('Plates resolution (height)')
        grid.addWidget(platesres_h_label, 6,0,1,1)
        self.platesres_h_value = self._spinner_box(50, 4096, 512)
        grid.addWidget(self.platesres_h_value, 6,1,1,2)

        buttons_row = 7
        cancel   = QtGui.QPushButton('Cancel')
        generate = QtGui.QPushButton('Generate')
        grid.addWidget(cancel,   buttons_row, 1, 1, 1)
        grid.addWidget(generate, buttons_row, 2, 1, 1)
        cancel.clicked.connect(self._on_cancel)
        generate.clicked.connect(self._on_generate)

        self.setLayout(grid)

    def _spinner_box(self, min, max, value):
        spinner = QtGui.QSpinBox()
        spinner.setMinimum(min)
        spinner.setMaximum(max)
        spinner.setValue(value)
        return spinner

    def _on_cancel(self):
        QtGui.QDialog.reject(self)

    def _on_generate(self):        
        QtGui.QDialog.accept(self)

    def seed(self):
        return self.seed_value.value()

    def width(self):
        return self.platesres_w_value.value()

    def height(self):
        return self.platesres_h_value.value()

    def num_plates(self):        
        return self.plates_num_value.value()

    def name(self):
        return self.name_value.text()        

class GenerationProgressDialog(QtGui.QDialog):

    def __init__(self, parent, seed, name, width, height, num_plates):
        QtGui.QDialog.__init__(self, parent)
        self._init_ui()
        self.world = None
        self.gen_thread = GenerationThread(self, seed, name, width, height, num_plates)
        self.gen_thread.start()

    def _init_ui(self):            
        self.resize(400, 100)
        self.setWindowTitle('Generating a new world...')
        grid = QtGui.QGridLayout()

        self.status = QtGui.QLabel('....') 
        grid.addWidget(self.status, 0, 0, 1, 3)          

        cancel   = QtGui.QPushButton('Cancel')
        grid.addWidget(cancel, 1, 0, 1, 1)
        cancel.clicked.connect(self._on_cancel)

        done   = QtGui.QPushButton('Done')
        grid.addWidget(done, 1, 2, 1, 1)
        done.clicked.connect(self._on_done)
        done.setEnabled(False)
        self.done = done

        self.setLayout(grid)

    def _on_cancel(self):
        QtGui.QDialog.reject(self)       

    def _on_done(self):        
        QtGui.QDialog.accept(self)       

    def on_finish(self):
        self.done.setEnabled(True) 

    def set_status(self, message):
        self.status.setText(message)


class GenerationThread(threading.Thread):

    def __init__(self, ui, seed, name, width, height, num_plates):
        threading.Thread.__init__(self)
        self.plates_generation = PlatesGeneration(seed, name, width, height, num_plates=num_plates)
        self.ui = ui
    
    def run(self):
        # FIXME it should be merged with world_gen
        finished = False
        while not finished:
            (finished, n_steps) = self.plates_generation.step() 
            self.ui.set_status('Plate simulation: step %i' % n_steps)
        self.ui.set_status('Plate simulation: terminating plates simulation')
        w = self.plates_generation.world()
        self.ui.set_status('Plate simulation: center land')
        center_land(w)
        self.ui.set_status('Plate simulation: adding noise')
        elevnoise_on_world(w, random.randint(0, 4096))
        self.ui.set_status('Plate simulation: forcing oceans at borders')
        place_oceans_at_map_borders_on_world(w)
        self.ui.set_status('Plate simulation: finalization (can take a while)')
        initialize_ocean_and_thresholds(w)
        self.ui.set_status('Plate simulation: completed')
        self.ui.world = w
        self.ui.on_finish()


class PlatesGeneration():

    def __init__(self, seed, name, width, height, 
                 sea_level=0.65, erosion_period=60,
                 folding_ratio=0.02, aggr_overlap_abs=1000000, aggr_overlap_rel=0.33,
                 cycle_count=2, num_plates=10):
        self.name   = name
        self.width  = width
        self.height = height
        self.p = platec.create(seed, width, height, sea_level, erosion_period, folding_ratio,
                               aggr_overlap_abs, aggr_overlap_rel, cycle_count, num_plates)
        self.steps = 0

    def step(self):
        if platec.is_finished(self.p) == 0:
            platec.step(self.p)
            self.steps += 1
            return (False, self.steps)
        else:
            return (True, self.steps)      

    def world(self):
        world = World(self.name, self.width, self.height)
        hm = platec.get_heightmap(self.p)
        pm = platec.get_platesmap(self.p)
        world.set_elevation(array_to_matrix(hm, self.width, self.height), None)
        world.set_plates(array_to_matrix(pm, self.width, self.height))
        return world

class MapCanvas(QtGui.QImage):

    def __init__(self, label, width, height):
        QtGui.QImage.__init__(self, width, height, QtGui.QImage.Format_RGB32);
        self.label = label
        self._update()

    def draw_world(self, world, view):
        self.label.resize(world.width, world.height)
        if view == 'bw':
            draw_bw_elevation_on_screen(world, self)
        elif view == 'plates':
            draw_plates_on_screen(world, self)
        elif view == 'plates and elevation':
            draw_plates_and_elevation_on_screen(world, self)
        elif view == 'land':
            draw_land_on_screen(world, self)
        elif view == 'precipitations':
            draw_precipitations_on_screen(world, self)
        else:
            raise Exception("Unknown view %s" % view)
        self._update()

    def _update(self):
        self.label.setPixmap(QtGui.QPixmap.fromImage(self))

class OperationDialog(QtGui.QDialog):

    def __init__(self, parent, world, operation):
        QtGui.QDialog.__init__(self, parent)
        self.operation = operation
        self._init_ui()
        self.op_thread = OperationThread(world, operation, self)
        self.op_thread.start()

    def _init_ui(self):
        self.resize(400, 100)
        self.setWindowTitle(self.operation.title())
        grid = QtGui.QGridLayout()

        self.status = QtGui.QLabel('....')
        grid.addWidget(self.status, 0, 0, 1, 3)

        cancel   = QtGui.QPushButton('Cancel')
        grid.addWidget(cancel, 1, 0, 1, 1)
        cancel.clicked.connect(self._on_cancel)

        done   = QtGui.QPushButton('Done')
        grid.addWidget(done, 1, 2, 1, 1)
        done.clicked.connect(self._on_done)
        done.setEnabled(False)
        self.done = done

        self.setLayout(grid)

    def _on_cancel(self):
        QtGui.QDialog.reject(self)

    def _on_done(self):
        QtGui.QDialog.accept(self)

    def on_finish(self):
        self.done.setEnabled(True)

    def set_status(self, message):
        self.status.setText(message)

class OperationThread(threading.Thread):

    def __init__(self, world, operation, ui):
        threading.Thread.__init__(self)
        self.world = world
        self.operation = operation
        self.ui = ui

    def run(self):
        self.operation.execute(self.world, self.ui)

class PrecipitationsOp():

    def __init__(self):
        pass

    def title(self):
        return "Simulation precipitations"

    def execute(self, world, ui):
        """

        :param ui: the dialog with the set_status and on_finish methods
        :return:
        """
        seed = random.randint(0, 65536)
        ui.set_status("Precipitation: started (seed %i)" % seed)
        world_gen_precipitation(world, seed, False)
        ui.set_status("Precipitation: done (seed %i)" % seed)
        ui.on_finish()


class SimulationOp():

    def __init__(self, title, simulation):
        self._title = title
        self.simulation = simulation

    def title(self):
        return self._title

    def execute(self, world, ui):
        """

        :param ui: the dialog with the set_status and on_finish methods
        :return:
        """
        ui.set_status("%s: started" % self.title())
        self.simulation.execute(world)
        ui.set_status("%s: done" % self.title())
        ui.on_finish()

class LandsGui(QtGui.QMainWindow):
    
    def __init__(self):
        super(LandsGui, self).__init__()        
        self._init_ui()
        self.world = None
        self.current_view = None

    def set_status(self, message):
        self.statusBar().showMessage(message)
        
    def _init_ui(self):            
        self.resize(800, 600)
        self.setWindowTitle('Lands - A world generator')        
        self.set_status('No world selected: create or load a world')
        self._prepare_menu()
        self.label = QtGui.QLabel()
        self.canvas = MapCanvas(self.label, 0, 0)            

        self.main_widget = QtGui.QWidget(self) # dummy widget to contain the
                                               # layout manager
        self.setCentralWidget(self.main_widget)
        self.layout = QtGui.QGridLayout(self.main_widget)
        # Set the stretch
        self.layout.setColumnStretch(0, 1)
        self.layout.setColumnStretch(2, 1)
        self.layout.setRowStretch(0, 1)
        self.layout.setRowStretch(2, 1)
        # Add widgets
        self.layout.addWidget(self.label, 1, 1)
        self.show()

    def set_world(self, world):
        self.world = world
        self.canvas = MapCanvas(self.label, self.world.width, self.world.height)
        self._on_bw_view()
        self.saveproto_action.setEnabled(world != None)
        self.bw_view.setEnabled(world != None)
        self.plates_view.setEnabled(world != None)
        self.plates_bw_view.setEnabled(world != None)
        self.land_and_ocean_view.setEnabled(world != None)
        self.precipitations_action.setEnabled(world != None and (not world.has_precipitations()))
        self.precipitations_view.setEnabled(world != None and world.has_precipitations())
        self.watermap_action.setEnabled( WatermapSimulation().is_applicable(world) )

    def _prepare_menu(self):
        generate_action = QtGui.QAction('&Generate', self)
        generate_action.setShortcut('Ctrl+G')
        generate_action.setStatusTip('Generate new world')
        generate_action.triggered.connect(self._on_generate)

        exit_action = QtGui.QAction('Leave', self)
        exit_action.setShortcut('Ctrl+L')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(QtGui.qApp.quit)

        open_action = QtGui.QAction('&Open', self)
        open_action.triggered.connect(self._on_open)

        self.saveproto_action = QtGui.QAction('&Save (protobuf)', self)
        self.saveproto_action.setEnabled(False)
        self.saveproto_action.setShortcut('Ctrl+S')
        self.saveproto_action.setStatusTip('Save (protobuf format)')
        self.saveproto_action.triggered.connect(self._on_save_protobuf)

        self.bw_view = QtGui.QAction('Black and white', self)
        self.bw_view.triggered.connect(self._on_bw_view)
        self.plates_view = QtGui.QAction('Plates', self)
        self.plates_view.triggered.connect(self._on_plates_view)
        self.plates_bw_view = QtGui.QAction('Plates and elevation', self)
        self.plates_bw_view.triggered.connect(self._on_plates_and_elevation_view)
        self.land_and_ocean_view = QtGui.QAction('Land and ocean', self)
        self.land_and_ocean_view.triggered.connect(self._on_land_view)
        self.precipitations_view = QtGui.QAction('Precipitations', self)
        self.precipitations_view.triggered.connect(self._on_precipitations_view)

        self.bw_view.setEnabled(False)
        self.plates_view.setEnabled(False)
        self.plates_bw_view.setEnabled(False)
        self.land_and_ocean_view.setEnabled(False)
        self.precipitations_view.setEnabled(False)

        self.precipitations_action = QtGui.QAction('Precipitations', self)
        self.precipitations_action.triggered.connect(self._on_precipitations)
        self.precipitations_action.setEnabled(False)

        self.erosion_action = QtGui.QAction('Erosion', self)
        self.erosion_action.triggered.connect(self._on_erosion)
        self.erosion_action.setEnabled(False)

        self.watermap_action = QtGui.QAction('Watermap', self)
        self.watermap_action.triggered.connect(self._on_watermap)
        self.watermap_action.setEnabled(False)

        self.irrigation_action = QtGui.QAction('Irrigation', self)
        self.irrigation_action.triggered.connect(self._on_irrigation)
        self.irrigation_action.setEnabled(False)

        self.humidity_action = QtGui.QAction('Humidity', self)
        self.humidity_action.triggered.connect(self._on_humidity)
        self.humidity_action.setEnabled(False)

        self.temperature_action = QtGui.QAction('Temperature', self)
        self.temperature_action.triggered.connect(self._on_temperature)
        self.temperature_action.setEnabled(False)

        self.permeability_action = QtGui.QAction('Permeability', self)
        self.permeability_action.triggered.connect(self._on_permeability)
        self.permeability_action.setEnabled(False)

        self.biome_action = QtGui.QAction('Biome', self)
        self.biome_action.triggered.connect(self._on_biome)
        self.biome_action.setEnabled(False)

        menubar = self.menuBar()

        file_menu = menubar.addMenu('&File')
        file_menu.addAction(generate_action)
        file_menu.addAction(open_action)
        file_menu.addAction(self.saveproto_action)
        file_menu.addAction(exit_action)

        simulations_menu = menubar.addMenu('&Simulations')
        simulations_menu.addAction(self.precipitations_action)
        simulations_menu.addAction(self.erosion_action)
        simulations_menu.addAction(self.watermap_action)
        simulations_menu.addAction(self.irrigation_action)
        simulations_menu.addAction(self.humidity_action)
        simulations_menu.addAction(self.temperature_action)
        simulations_menu.addAction(self.permeability_action)
        simulations_menu.addAction(self.biome_action)

        view_menu = menubar.addMenu('&View')
        view_menu.addAction(self.bw_view)
        view_menu.addAction(self.plates_view)
        view_menu.addAction(self.plates_bw_view)
        view_menu.addAction(self.land_and_ocean_view)
        view_menu.addAction(self.precipitations_view)

    def _on_bw_view(self):
        self.current_view = 'bw'
        self.canvas.draw_world(self.world, self.current_view)

    def _on_plates_view(self):
        self.current_view = 'plates'
        self.canvas.draw_world(self.world, self.current_view)

    def _on_plates_and_elevation_view(self):
        self.current_view = 'plates and elevation'
        self.canvas.draw_world(self.world, self.current_view)

    def _on_land_view(self):
        self.current_view = 'land'
        self.canvas.draw_world(self.world, self.current_view)

    def _on_precipitations_view(self):
        self.current_view = 'precipitations'
        self.canvas.draw_world(self.world, self.current_view)

    def _on_generate(self):
        dialog = GenerateDialog(self)
        ok = dialog.exec_()
        if ok:            
            seed = dialog.seed()
            width = dialog.width()
            height = dialog.height()
            num_plates = dialog.num_plates()
            name = str(dialog.name())
            dialog2 = GenerationProgressDialog(self, seed, name, width, height, num_plates)            
            ok2 = dialog2.exec_()
            if ok2:
                self.set_world(dialog2.world)

    def _on_save_protobuf(self):
        filename = QtGui.QFileDialog.getSaveFileName(self, "Save world", "", "*.world")
        self.world.protobuf_to_file(filename)

    def _on_open(self):
        filename = QtGui.QFileDialog.getOpenFileName(self, "Open world", "", "*.world")
        world = World.open_protobuf(filename)
        self.set_world(world)

    def _on_precipitations(self):
        dialog = OperationDialog(self, self.world, PrecipitationsOp())
        ok = dialog.exec_()
        if ok:
            # just to refresh things to enable
            self.set_world(self.world)

    def _on_erosion(self):
        pass

    def _on_watermap(self):
        dialog = OperationDialog(self, self.world, SimulationOp("Simulating water flow", WatermapSimulation()))
        ok = dialog.exec_()
        if ok:
            # just to refresh things to enable
            self.set_world(self.world)

    def _on_irrigation(self):
        pass

    def _on_humidity(self):
        pass

    def _on_temperature(self):
        pass

    def _on_permeability(self):
        pass

    def _on_biome(self):
        pass


def main():
    
    app = QtGui.QApplication(sys.argv)

    lg = LandsGui()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()