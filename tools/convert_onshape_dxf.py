"""
Validate and repair Onshape's broken DXF output so that it works with a Flow waterjet
* Negative extrusion direction
* Non-planar Z
* Non-zero Z
* Convert units from metric (mm) to standard (inch) and vice-versa

Tested with Python 3.5.1
"""
# pylint: disable=C0103

import os
import sys
import getopt
# Get ezdxf with 'pip install ezdxf'
import ezdxf

__author__ = 'Tom Oinn, Ritchie Argue'

def flatten_coord(coord):
    """
        return 3D coordinate flattened to XY plane (discard Z), otherwise we may
        crash the waterjet head (programming software interprets Z and biases against
        the workpiece position)
    """
    return (coord[0], coord[1], 0.0)

def scale_coord(coord, conversion):
    """
        scale point coordinate units by conversion factor
    """
    return (coord[0] * conversion, coord[1] * conversion, coord[2] * conversion)

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

def validate_negative_extrusion(dwg, flags):
    """
    validate and repair entities with negative extrusion direction

    Mirror all CIRCLE, ARC, and LINE entities if their extrusion direction is negative

    Mirror CIRCLE centers
    Mirror ARC centers and angles
    Mirrow LINE start and end (not seen in the wild yet)
    """
    negative_extrusion_entities = 0
    for entity in dwg.entities:
        extrusion_z = entity.dxf.extrusion[2]
        if extrusion_z < 0:
            negative_extrusion_entities += 1
            if entity.dxftype() == 'CIRCLE':
                entity.dxf.center = mirror_coord(entity.dxf.center)
            elif entity.dxftype() == 'ARC':
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                entity.dxf.start_angle = mirror_angle(end_angle)
                entity.dxf.end_angle = mirror_angle(start_angle)
                entity.dxf.center = mirror_coord(entity.dxf.center)
            else:
                if flags['verbose']:
                    print('{0:6} {1}: type not processed!'.format(entity.dxftype(),
                                                                  entity.dxf.handle))

            # fix extrusion direction for all processed entities
            entity.dxf.extrusion = (0, 0, 1.0)
    return negative_extrusion_entities

def validate_z_plane(dwg, flags):
    """
    validate that the object is planar in Z
    """
    entity_planes = 0
    z = []
    for entity in dwg.entities:
        if entity.dxftype() == 'CIRCLE' or entity.dxftype() == 'ARC':
            z.append(entity.dxf.center[2])
        if entity.dxftype() == 'LINE':
            z.append(entity.dxf.start[2])
            z.append(entity.dxf.end[2])
    if 'verbose' in flags:
        print(set(z))
    entity_planes = len(set(z))
    return entity_planes

def validate_z_zero(dwg, flags):
    """
    validate that the object is at Z=0
    """
    non_z_zero = 0
    for entity in dwg.entities:
        if entity.dxftype() == 'CIRCLE' or entity.dxftype() == 'ARC':
            if entity.dxf.center[2] != 0:
                non_z_zero += 1
                if 'verbose' in flags:
                    print('{0:6} {1}: {2}'.format(entity.dxftype(), entity.dxf.handle,
                                                  entity.dxf.center))
            entity.dxf.center = flatten_coord(entity.dxf.center)
        elif entity.dxftype() == 'LINE':
            if entity.dxf.start[2] != 0 or entity.dxf.end[2] != 0:
                non_z_zero += 1
                if 'verbose' in flags:
                    print('{0:6} {1}: {2}'.format(entity.dxftype(), entity.dxf.handle,
                                                  entity.dxf.start))
                    print('{0:6} {1}: {2}'.format(entity.dxftype(), entity.dxf.handle,
                                                  entity.dxf.end))
            entity.dxf.start = flatten_coord(entity.dxf.start)
            entity.dxf.end = flatten_coord(entity.dxf.end)
    return non_z_zero

def scale(dwg, flags):
    """
        scale point coordinate units by conversion factor
    """
    if 'unit_conversion' not in flags:
        return

    conversion = 1.0
    if flags['unit_conversion'] == 'metric':
        conversion = 25.4
        if 'verbose' in flags:
            print('converting to metric')
    elif flags['unit_conversion'] == 'standard':
        conversion = 1/25.4
        if 'verbose' in flags:
            print('coverting to standard')

    for entity in dwg.entities:
        if entity.dxftype() == 'CIRCLE' or entity.dxftype() == 'ARC':
            entity.dxf.center = scale_coord(entity.dxf.center, conversion)
        elif entity.dxftype() == 'LINE':
            entity.dxf.start = scale_coord(entity.dxf.start, conversion)
            entity.dxf.end = scale_coord(entity.dxf.end, conversion)


def main(inputfile, flags):
    """
    :param inputfile:
        Name of a DXF file to read
    :param flags:
        command line flags
    """

    dwg = ezdxf.readfile(inputfile)

    # fix entities with negative extrusion direction
    negative_extrusion_entities = validate_negative_extrusion(dwg, flags)

    # check for non-planar in Z
    entity_planes = validate_z_plane(dwg, flags)

    # flatten all to z=0.0 otherwise we crash the waterjet head :(
    non_z_zero = validate_z_zero(dwg, flags)

    # adjust by scaling factor
    scale(dwg, flags)

    if negative_extrusion_entities > 0:
        print('VALIDATION ERROR: Found {0} entities with negative extrusion direction'
              .format(negative_extrusion_entities))

    if entity_planes > 1:
        print('VALIDATION ERROR: Found {0} non-planar entities!'.format(entity_planes))

    if non_z_zero > 0:
        print('VALIDATION ERROR: Found {0} entities not at z=0.0'.format(non_z_zero))

    if negative_extrusion_entities == 0 and entity_planes == 1 and non_z_zero == 0:
        print('SUCCESS: no DXF format errors found, no repair needed!')
        if 'unit_conversion' in flags:
            (file_root, file_ext) = os.path.splitext(inputfile)
            outputfile = file_root + ' ' + flags['unit_conversion'] + file_ext
            dwg.saveas(outputfile)
        return
    else:
        (file_root, file_ext) = os.path.splitext(inputfile)
        outputfile = file_root + ' repaired' + file_ext
        dwg.saveas(outputfile)
        print('Wrote repaired file as {0}'.format(outputfile))


if __name__ == '__main__':
    USAGE_MESSAGE = ('validate_onshape_dxf.py [-d|--dontfix] [-m|--metric] '
                     '[-s|--standard] [-v|--verbose] <input_file>')

    _inputfile = None
    _flags = {}
    _flags['unit_conversion'] = 1.0
    _flags['repair'] = True
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dmsv', ['dontfix', 'standard',
                                                          'metric', 'verbose'])
    except getopt.GetoptError:
        print(USAGE_MESSAGE)
        sys.exit(2)
    for arg in args:
        _inputfile = arg
    for opt, arg in opts:
        if opt in ("-d", "--dontfix"):
            del _flags['repair']
        elif opt in ("-s", "--standard"):
            _flags['unit_conversion'] = 'standard'
        elif opt in ("-m", "--metric"):
            _flags['unit_conversion'] = 'metric'
        elif opt in ("-v", "--verbose"):
            _flags['verbose'] = True
    if _inputfile is None:
        print(USAGE_MESSAGE)
        sys.exit(2)
    main(_inputfile, _flags)
