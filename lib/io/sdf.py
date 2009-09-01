# MolMod is a collection of molecular modelling tools for python.
# Copyright (C) 2007 - 2008 Toon Verstraelen <Toon.Verstraelen@UGent.be>
#
# This file is part of MolMod.
#
# MolMod is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# MolMod is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
# --


from molmod.units import angstrom
from molmod.periodic import periodic
from molmod.molecules import Molecule
from molmod.molecular_graphs import MolecularGraph
from molmod.io.common import FileFormatError

import numpy


__all__ = ["SDFReader"]


class SDFReader(object):
    """A basic reader for SDF files.

       Use this reader as an iterator:
       >>> sr = SDFReader("somefile.sdf")
       >>> for mol in sr:
       ...     print mol.title
    """
    def __init__(self, f):
        """Initialize an SDFReader object

           Argument:
             f  --  a filename or a file-like object
        """
        if isinstance(f, basestring):
            self.filename = f
            self.f = file(f)
            self._auto_close = True
        else:
            # try to treat f as a file-like object and hope for the best.
            self.f = f
            self._auto_close = False

    def __del__(self):
        if self._auto_close:
            self.f.close()

    def __iter__(self):
        return self

    def next(self):
        """Load the next molecule from the SDF file

           This method is part of the iterator protocol.
        """
        while True:
            title = self.f.next()
            if len(title) == 0:
                raise StopIteration
            else:
                title = title.strip()
            self.f.next() # skip line
            self.f.next() # skip empty line
            words = self.f.next().split()
            if len(words) < 2:
                raise FileFormatError("Expecting at least two numbers at fourth line.")
            try:
                num_atoms = int(words[0])
                num_bonds = int(words[1])
            except ValueError:
                raise FileFormatError("Expecting at least two numbers at fourth line.")

            numbers = numpy.zeros(num_atoms, int)
            coordinates = numpy.zeros((num_atoms,3), float)
            for i in xrange(num_atoms):
                words = self.f.next().split()
                if len(words) < 4:
                    raise FileFormatError("Expecting at least four words on an atom line.")
                try:
                    coordinates[i,0] = float(words[0])
                    coordinates[i,1] = float(words[1])
                    coordinates[i,2] = float(words[2])
                except ValueError:
                    raise FileFormatError("Coordinates must be floating point numbers.")
                atom = periodic[words[3]]
                if atom is None:
                    raise FileFormatError("Unrecognized atom symbol: %s" % words[3])
                numbers[i] = atom.number
            coordinates *= angstrom

            pairs = []
            orders = numpy.zeros(num_bonds, int)
            for i in xrange(num_bonds):
                words = self.f.next().split()
                if len(words) < 3:
                    raise FileFormatError("Expecting at least three numbers on a bond line.")
                try:
                    pairs.append((int(words[0])-1,int(words[1])-1))
                    orders[i] = int(words[2])
                except ValueError:
                    raise FileFormatError("Expecting at least three numbers on a bond line.")

            formal_charges = numpy.zeros(len(numbers), int)

            line = self.f.next()
            while line != "M  END\n":
                if line.startswith("M  CHG"):
                    words = line[6:].split()[1:] # drop the first number which is the number of charges
                    i = 0
                    while i < len(words)-1:
                        try:
                            formal_charges[int(words[i])-1] = int(words[i+1])
                        except ValueError:
                            raise FileFormatError("Expecting only integer formal charges.")
                        i += 2
                line = self.f.next()

            # Read on to the next molecule
            for line in self.f:
                if line == "$$$$\n":
                    break

            molecule = Molecule(numbers, coordinates, title)
            molecule.formal_charges = formal_charges
            molecule.formal_charges.setflags(write=False)
            molecule.graph = MolecularGraph(pairs, numbers, orders)
            return molecule

