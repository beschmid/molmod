# PyChem is a general chemistry oriented python package.
# Copyright (C) 2005 Toon Verstraelen
# 
# This file is part of PyChem.
# 
# PyChem is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# 
# --


from pychem.interfaces.output_parsers import FileParser, MultiLineParser
from pychem.moldata import periodic
from pychem.molecules import Molecule
from pychem.units import from_angstrom

import re, Numeric


class LinkParser(MultiLineParser):
    extension = ".log"
    
    def __init__(self, link, label, activator=None, deactivator=None, condition=None):
        MultiLineParser.__init__(self, label, activator, deactivator, condition)
        self.link = str(link)

    def reset(self):
        MultiLineParser.reset(self)
        self.in_link = False

    def parse(self, line):
        if line[:11] == " Leave Link" and line[13:13+len(self.link)] == self.link:
            self.in_link = False
        if self.in_link:
            MultiLineParser.parse(self, line)
        if line[:8] == " (Enter " and line[-6-len(self.link):-6] == self.link:
            self.in_link = True



class ThermoChemParser(LinkParser):
    def __init__(self, label, activator=None, deactivator=None, condition=None):
        LinkParser.__init__(self, "716", label, activator, deactivator, condition)


class HessianParser(ThermoChemParser):
    def __init__(self, label="hessian", condition=None):
        ThermoChemParser.__init__(self, label,
            activator=re.compile("Force constants in Cartesian coordinates:"), 
            deactivator=re.compile("Force constants in internal coordinates:"), 
            condition=condition
        )
    
    def reset(self):
        ThermoChemParser.reset(self)
        self.hessian = []
    
    def start_collecting(self):
        self.hessian = []
    
    def collect(self, line):
        words = line.split()
        if words[1].find("D") >= 0:
            row_number = int(words[0])
            if row_number >= len(self.hessian):
                row = []
                self.hessian.append(row)
            else:
                row = self.hessian[row_number-1]
            for word in words[1:]:
                row.append(float(word.replace("D", "e")))

    def stop_collecting(self):
        hessian = Numeric.zeros((len(self.hessian), len(self.hessian)), Numeric.Float)
        for row_index, row in enumerate(self.hessian):
            for col_index, value in enumerate(row):
                hessian[row_index, col_index] = value
                if row_index != col_index:
                    hessian[col_index, row_index] = value
        self.hessian = hessian
        
    def result(self):
        return self.hessian


class FrequenciesParser(ThermoChemParser):
    def __init__(self, label, pattern, condition):
        # returns the frequencies in cm-1
        ThermoChemParser.__init__(self, label, None, None, condition)
        self.pattern = pattern
    
    def reset(self):
        ThermoChemParser.reset(self)
        self.frequencies = []
    
    def collect(self, line):
        if line[:len(self.pattern)] == self.pattern:
            words = line[len(self.pattern):].split()
            self.frequencies.extend(float(word) for word in words)
    
    def result(self):
        return Numeric.array(self.frequencies)

        
class LowFrequenciesParser(FrequenciesParser):
    def __init__(self, label="low_frequencies", condition=None):
        FrequenciesParser.__init__(self, label, " Low frequencies ---", condition)


class SelectedFrequenciesParser(FrequenciesParser):
    def __init__(self, label="selected_frequencies", condition=None):
        FrequenciesParser.__init__(self, label, " Frequencies --", condition)


class MassParser(ThermoChemParser):
    def __init__(self, label="masses", condition=None):
        ThermoChemParser.__init__(self, label,
            activator=re.compile("Temperature\s+\S+\s+Kelvin.\s+Pressure\s+\S+\s+Atm."), 
            deactivator=re.compile("Molecular mass:\s+\S+\s+amu."), 
            condition=condition
        )
        self.re = re.compile("Atom\s+\d+\s+has atomic number\s+\d+\s+and mass\s+(?P<mass>\S+)")
    
    def reset(self):
        ThermoChemParser.reset(self)
        self.masses = []
    
    def start_collecting(self):
        self.masses = []
    
    def collect(self, line):
        match = self.re.search(line)
        if match != None:
            self.masses.append(float(match.group("mass")))

    def stop_collecting(self):
        self.masses = Numeric.array(self.masses, Numeric.Float)
        
    def result(self):
        return self.masses


class ConfigurationParser(LinkParser):
    def __init__(self, label, activator=None, deactivator=None, condition=None):
        LinkParser.__init__(self, "202", label, activator, deactivator, condition)


class CoordinatesParser(ConfigurationParser):
    def __init__(self, label="coordinates", condition=None):
        ConfigurationParser.__init__(self, label,
            re.compile("Input orientation:"), 
            re.compile("Distance matrix \(angstroms\):"), 
            condition
        )
        self.re = re.compile("\d+\s+\d+\s+\d+\s+(?P<x>\S+)\s+(?P<y>\S+)\s+(?P<z>\S+)")
    
    def reset(self):
        ConfigurationParser.reset(self)
        self.coordinates = []
    
    def start_collecting(self):
        self.current_coordinates = []
        
    def collect(self, line):
        match = self.re.search(line)
        if match != None:
            self.current_coordinates.append([
                from_angstrom(float(match.group("x"))),
                from_angstrom(float(match.group("y"))),
                from_angstrom(float(match.group("z")))
            ])
        
    def stop_collecting(self):
        self.coordinates.append(Numeric.array(self.current_coordinates, Numeric.Float))
        
    def result(self):
        return self.coordinates


class SCFParser(LinkParser):
    def __init__(self, label, activator=None, deactivator=None, condition=None):
        LinkParser.__init__(self, "502", label, activator, deactivator, condition)


class EnergyParser(SCFParser):
    def __init__(self, label="energies", condition=None):
        SCFParser.__init__(self, label, None, None, condition)
        self.re = re.compile("SCF Done:\s+E\S+\s+=\s+(?P<energy>\S+)\s+A.U.")

    def reset(self):
        SCFParser.reset(self)
        self.energies = []
    
    def collect(self, line):
        match = self.re.search(line)
        if match != None:
            self.energies.append(float(match.group("energy")))

    def result(self):
        return Numeric.array(self.energies)