# ----------------------------------------------------------------------------------------------------- 
# PROPAGATOR: Scattering experiment simulator for spheres and customized object maps
# Please type 'help propagator()' for further information.
# -----------------------------------------------------------------------------------------------------
# Author:  Max Hantke - maxhantke@gmail.com
# -----------------------------------------------------------------------------------------------------
# All variables in SI units by default. Exceptions only if expressed by variable name.

import sys, ConfigParser, numpy, types, pickle, time, math, os

this_dir = os.path.dirname(os.path.realpath(__file__))

import logging
logger = logging.getLogger("Propagator")

# Initial configuration and importing propagator files
import config
config.init_configuration()
import imgutils,proptools
from source import Source
from sample import SampleMap,SampleSphere,SampleSpheroid
from detector import Detector

# Pythontools
from python_tools import gentools,cxitools,imgtools

class Input:
    """
    The Input object that holds all necessary information for the experiment that shall be simulated. After initialization the configuration is saved to the variable Input.configuration.confDict.

    :param configuration: Either a dictionary or the location of a configuration file. Missing but necessary arguments will be set to default values.
    
    """
    
    def __init__(self,configuration={}):
        self.default_configuration = this_dir+"/data/default.conf"
        self._reconfigure(configuration)
        self._photon_changed = False
        self._detector_changed = False
    
    def _reconfigure(self,configuration={}):
        self.configuration = gentools.Configuration(configuration,self.default_configuration)

        C = self.configuration.confDict
        self.detector = Detector(parent=self,**C["detector"])
        self.source = Source(parent=self,**C["source"])

        if C["sample"]["sample_type"] == "uniform_sphere":
            self.sample = SampleSphere(parent=self,**C["sample"])
        elif C["sample"]["sample_type"] == "uniform_spheroid":
            self.sample = SampleSpheroid(parent=self,**C["sample"])
        elif C["sample"]["sample_type"] == "map3d":
            self.sample = SampleMap(parent=self,**C["sample"])
        else:
            logger.error("%s is not a valid sample type.")
            return

class Output:
    """
    An instance of the Output object is initialized with an instance of the Input object and initiates the simulation of the diffraction data.
    After completion the instance holds the results and methods to access and interpret them.

    """
    def __init__(self,input):
        if not isinstance(input,Input):
            logger.error("Illegal input. Argument has to be of instance Input.")
            return
        
        self.input_object = input 
        logger.debug("Propagation started.")
        t_start = time.time()
        outdict = self.input_object.sample.propagate()
        self.amplitudes = outdict["amplitudes"]
        self.sample_euler_angle_0 = outdict.get("euler_angle_0",None)
        self.sample_euler_angle_1 = outdict.get("euler_angle_1",None)
        self.sample_euler_angle_2 = outdict.get("euler_angle_2",None)
        self.sample_diameter = outdict.get("sample_diameter",None)        
        t_stop = time.time()
        logger.debug("Propagation finished (time = %f sec)",t_stop-t_start)

    def get_intensity_pattern(self,i=0):
        """
        Returns 2-dimensional array with intensity values in the unit photons per pixel (binned).

        :param i: Index of the image that you want to obtain.

        """
        return self.input_object.detector.detect_photons(abs(self.amplitudes[i])**2)

    def get_real_space_image(self,i=0):
        """
        Returns 2-dimensional array of back-propagated real space image from the diffraction amplitudes.

        """       
        A = self.amplitudes[i]
        A[numpy.isfinite(A)==False] = 0.
        return numpy.fft.fftshift(numpy.fft.ifftn(numpy.fft.fftshift(self.amplitudes[i])))

    def get_linear_sampling_ratio(self):
        """
        Returns the linear sampling ratio :math:`o` of the diffraction pattern:

        | :math:`o=\\frac{D\\lambda}{dp}` 

        | :math:`D`: Detector distance
        | :math:`p`: Detector pixel size (edge length)
        | :math:`\\lambda`: Photon wavelength 
        | :math:`d`: Sample diameter

        """       
        
        if self.input_object.sample.radius == None:
            return None
        else:
            pN = proptools.get_nyquist_pixel_size(self.input_object.detector.distance,self.input_object.source.photon.get_wavelength(),numpy.pi*self.input_object.sample.radius**2)
            pD = self.input_object.detector.get_pixel_size("binned")
            return pN/pD
            
    def get_full_period_edge_resolution(self):
        """
        Returns the full-period resolution :math:`R` at the edge of the detector in meter.

        | :math:`R=\\lambda / \\sin(\\arctan(Y/D))`

        | :math:`\\lambda`: Photon wavelength
        | :math:`Y`: Minimum distance between the beam axis and an edge of the detector.
        | :math:`D`: Detector distance

        """
        return proptools.get_max_crystallographic_resolution(self.input_object.source.photon.get_wavelength(),self.input_object.detector.get_minimum_center_edge_distance(),self.input_object.detector.distance)
