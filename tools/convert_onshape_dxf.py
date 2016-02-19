"""
Fix Onshape's busted DXF output.
Entities with negative extrusion direction are mirrored back to positive direction

Tested with Python 3.5.1
"""
# pylint: disable=C0103

import sys
import getopt
# Get ezdxf with 'pip install ezdxf'
import ezdxf

__author__ = 'Tom Oinn'

def mirror_coord(coord):
    """
    return coordinate mirrored around Y axis

    :param c:
        a coordinate (x,y,z)

    :returns:
        A flattened (Z set to -Z) and mirrored about Y (X set to -X) copy of the input
    """
    return (-coord[0], coord[1], -coord[2])

def mirror_angle(angle):
    """
    Return angle rotated 180 degrees
    """
    return (180 - angle) % 360

def main(inputfile, outputfile):
    """
    Mirror all CIRCLE, ARC, and LINE entities if their extrusion direction is negative

    Mirror CIRCLE centers
    Mirror ARC centers and angles
    Mirrow LINE start and end (not seen in the wild yet)

    :param inputfile:
        Name of a DXF file to read
    :param outputfile:
        Name of a DXF file to write
    """
    dwg = ezdxf.readfile(inputfile)

    for entity in dwg.entities:
        if entity.dxf.extrusion[2] < 0:
            if entity.dxftype() == 'CIRCLE':
                entity.dxf.center = mirror_coord(entity.dxf.center)
            elif entity.dxftype() == 'ARC':
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                entity.dxf.start_angle = mirror_angle(end_angle)
                entity.dxf.end_angle = mirror_angle(start_angle)
                entity.dxf.center = mirror_coord(entity.dxf.center)
            elif entity.dxftype() == 'LINE':
                entity.dxf.start = mirror_coord(entity.dxf.end)
                entity.dxf.end = mirror_coord(entity.dxf.start)
            else:
                print('{0:6} {1}: type not processed!'.format(entity.dxftype(), entity.dxf.handle))

            # fix extrusion direction for all processed entities
            entity.dxf.extrusion = (0, 0, 1.0)

    # check for non-planar in Z
    z = []
    for entity in dwg.entities:
        if entity.dxftype() == 'CIRCLE' or entity.dxftype() == 'ARC':
            z.append(entity.dxf.center[2])
        if entity.dxftype() == 'LINE':
            z.append(entity.dxf.start[2])
            z.append(entity.dxf.end[2])
    if len(set(z)) > 1:
        print('WARNING: Not all elements in same Z plane! ' + repr(set(z)))

    dwg.saveas(outputfile)


USAGE_MESSAGE = 'convert_onshape_dxf.py [-i|--ifile] <input_file> [-o|--ofile] <outputfile>'

if __name__ == '__main__':
    input_file = None
    output_file = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'i:o:', ['ifile=', 'ofile='])
    except getopt.GetoptError:
        print(USAGE_MESSAGE)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-i", "--ifile"):
            input_file = arg
        elif opt in ("-o", "--ofile"):
            output_file = arg
    if input_file is None or output_file is None:
        print(USAGE_MESSAGE)
        sys.exit(2)
    main(input_file, output_file)
