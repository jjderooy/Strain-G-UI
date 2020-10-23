from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QFileDialog
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg
import sys 
import os
import numpy as np
from serial import Serial 
import time
import linecache
from datetime import datetime

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        
        super(MainWindow, self).__init__(*args, **kwargs)
        # Load the UI Page. uic is the thing that lets us use a .ui file
        uic.loadUi('rocket_strain_visualizer.ui', self)

        # This is used to name our log files. It's just a string with the date and time
        self.date_and_time = str(datetime.now().time())

        # Wait until the user has configured everything, and pressed start
        self.start_button.clicked.connect(self.setup)
    
    def setup(self):
        self.setup_signals()
        self.setup_arduino()
        self.setup_graphs()
        self.draw_rocket()
        self.set_framerate()

    def setup_signals(self):
        # Alright so basically since there is not a "loop" to put methods in that
        # you want to update based on things that have changed in the GUI,
        # PyQt has these things called signals and slots. They let you connect
        # changes or "signals" of objects in the GUI to methods.

        # For instance we can connect the valueChanged() "signal" to our set_framerate()
        # method so that when we move the slider, the framerate changes too.
        self.framerate_slider.valueChanged.connect(self.set_framerate)
        self.fuselage_length.valueChanged.connect(self.draw_rocket)
        self.import_data_button.clicked.connect(self.open_data_file)
        self.step_frame_left_button.clicked.connect(self.step_frame_left)
        self.step_frame_right_button.clicked.connect(self.step_frame_right)

    def setup_arduino(self):
        # Stuff for reading arduino serial.println()
        try:
            serial_port = self.usb_line_edit.text();
            baud_rate = 115200; # In arduino .ino file, Serial.begin(baud_rate)
            self.ser = Serial(serial_port, baud_rate)
        except:
            print("Could not set up serial connection with Arduino. Check the connection and try again!")

    def setup_graphs(self):
        # strain_plot_x,y are PlotWidgets created in Designer.
        # If you want to change the x range, its the numbers one the next
        # line multiplied by 20
        self.strain_plot_x.setXRange(-3,3, padding=10)
        self.strain_plot_x.showGrid(x=True,y=True)
        self.strain_plot_x.setTitle("X,Z View")
        self.strain_plot_x.setLabel('left', 'Fuselage (m)')
        self.strain_plot_x.setLabel('bottom', 'Deflection (mm)')

        self.strain_plot_y.setTitle("Y,Z View")
        self.strain_plot_y.setLabel('left', 'Fuselage (m)')
        self.strain_plot_y.setLabel('bottom', 'Deflection (mm)')
        self.strain_plot_y.setXRange(-3,3, padding=10)
        self.strain_plot_y.showGrid(x=True,y=True)

    def draw_rocket(self):
        # Our rocket is represented as a vertical line of points
        # that we will adjust based on readings from strain gauges
        
        # First remove any existing line on the plots (this method is called every time say
        # the fuselage length is changed. If we didn't clear it, there would be a metric
        # fuckton of lines everywherea)
        self.strain_plot_x.clear()
        self.strain_plot_y.clear()

        # Get our length from the counter box in the GUI
        length = self.fuselage_length.value()

        # Here are our y points
        self.y = np.linspace(-length/2, length/2, 50)
        
        # And x points. These will be adjusted based on strain gauges
        # Right now they are all the same so they appear as a vertical line
        self.x = np.linspace(0.5, 0.5, 50)
        
        # We draw our graph with a qt pen
        # We can set things like width, color, etc.
        # Here we make the width fairly large so the line looks like a fuselage (lol)
        pen = pg.mkPen(color=(255, 0, 0))
        pen.setWidth(25)

        # Calling .plot draws our line (rocket), and returns a line object that we can change
        # the data of. By changing the data instead of re-plotting, we can get a much higher
        # framerate. Data is updated in update()
        self.linex = self.strain_plot_x.plot(self.x, self.y, pen=pen)
        self.liney = self.strain_plot_y.plot(self.x, self.y, pen=pen)
    
    def set_framerate(self):
        # This is how we update the graphs with new data
        # setInterval() is a delay between frames.
        self.timer = QtCore.QTimer()
        self.timer.setInterval(int(1000/(self.framerate_slider.value())))
        self.timer.timeout.connect(self.update)
        self.timer.start()
 
    def update(self):
        # Here is where we update the plot data from our strain gauges

        # Check if the user has toggled the pause button. This is mainly used when reading from 
        # a file and you want to stop and step frame by frame.
        if(self.pause_button.isChecked() == False):
            # The user has the option to select a file to read from instead. 
            # If reading from Arduino, the user will have entered the usb port path     
            if(self.usb_line_edit.text() != ""):
                
                # This is where we read from our Arduino thats doing serial.println(strain_gauge_value)   
                self.ser.flushInput()

                line = self.ser.readline()
                #ser.readline returns a binary, convert to string
                line = line.decode("utf-8") 
                
                # We read the line in as a list. The first value is the x strain gauge, the second is y
                # We have to strip() the line of any \n and \r chars so that we can convert to a float
                stripped_line = line.strip()

                # Add the line to a new data file called todays date/time
                self.append_to_data_file(stripped_line)

                # split() converts each value seperated by a space into an entry in a list.
                line_list = stripped_line.split()
                
                try:
                    s_value_x = float(line_list[0])
                    s_value_y = float(line_list[1])
                    self.linex.setData(self.x + (s_value_x*self.y**2), self.y)
                    self.liney.setData(self.x + (s_value_y*self.y**2), self.y)                    
                except:
                    print("Unexpected value / invalid data over serial. Check that your Arduino Serial.println()'s in the form: <x_strain> <y_strain>")

            # Check to see if there is a . meaning there is a file path with .txt in it
            elif('.' in self.data_source_line_edit.text()):
                
                 # Update the line number displayed in the GUI so that the next time update is called
                # it gets the next line of data. Also this allows the user to set the line number they want
                # to start displaying data at, or use the frame stepping buttons to navigate
                self.line_number_line_edit.setText(str(1 + int(self.line_number_line_edit.text())))

                # This is the data file the user selected.
                # We imported the linecache module so we can read a specific line
                # We read the line in as a list. The first value is the x strain gauge, the second is y
                # We have to strip() the line of any \n and \r chars so that we can convert to a float
                try:
                    line = linecache.getline(self.data_source_line_edit.text(), int(self.line_number_line_edit.text()))
                    stripped_line = line.strip()
                    line_list = stripped_line.split()
                except:
                    print("Unexpected value / data in data file.")

                # Data is strings so we convert to float for plotting
                s_value_x = float(line_list[0])
                s_value_y = float(line_list[1])

                self.linex.setData(self.x + (s_value_x*self.y**2), self.y)
                self.liney.setData(self.x + (s_value_y*self.y**2), self.y)

    def open_data_file(self):
        # This creates a file dialog box so we can select a data file
        # getOpenFileName() returns the file path selected by the user AND the filter used 
        # as a tuple. In our case the filter is *.txt but we only want the file path so we 
        # seperate them with this cool line courtesy of stack overflow.
        # https://stackoverflow.com/questions/43509220/qtwidgets-qfiledialog-getopenfilename-returns-a-tuple
        fname, filter_ = QFileDialog.getOpenFileName(self, 'Open file', "Data files (*.txt)")

        # Update the lineEdit beside "Data Source:" on the GUI. This is necessary so that update()
        # knows that we aren't reading from an Arduino live anymore.
        self.data_source_line_edit.setText(fname)

    def step_frame_left(self):
        # By changing the line number on the GUI, and calling update(), we can step back.
        # We force the pause button to be disabled so we can update(), then re-enable it 
        # after we've updated.
        # We have to step twice because update() increases line number by 1 automatically
        self.pause_button.setChecked(False)
        self.line_number_line_edit.setText(str(int(self.line_number_line_edit.text()) - 2))
        self.update()
        self.pause_button.setChecked(True)
 
    def step_frame_right(self):
        # We don't need to change the line number for stepping forward because update() already does that
        self.pause_button.setChecked(False)
        self.update()
        self.pause_button.setChecked(True)

    def append_to_data_file(self, line):
        # date_and_time is created in __init__. It is our data file name
        with open(self.date_and_time, "a") as data_file:
            data_file.write(line)
            data_file.write("\n")


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())

if __name__ == '__main__':      
    main()
