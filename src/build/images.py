import json
import os
import subprocess
import sys

"""
Converts images based on manifest using rsvg
"""

class ConvertImagesException:
    """ 
    Exception class for problems when converting images 
    """
    
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return self.message

def _u2a(u_str):
    """
    Converts a unicode string to ASCII
    """
    return u_str.encode('ascii')

class ImageConverter:
    
    """
    Performs all image conversions
    """
    
    _MANIFEST_FILENAME = 'image_manifest.json'
    
    def svg2png(self, src_svg, dest_png, width, height):
        retcode = subprocess.call(
            ["rsvg", '-w '+ str(width), '-h ' + str(height), src_svg, dest_png]
        )
        if retcode != 0:
            raise ConvertImagesException("Unable to convert: " + src_svg)        
    
    def run(self, argv):
        
        # parse the arguments and check the preconditions
        if len(argv) < 2:
            raise ConvertImagesException('Invalid number of arguments')
        source_dir, dest_dir = argv
        manifest_path = os.path.join(source_dir, self._MANIFEST_FILENAME)
         
        if not os.path.exists(manifest_path):
            raise ConvertImagesException('Image manifest does not exist: ' + manifest_path )
        if not os.path.isdir(dest_dir):
            raise ConvertImagesException('Destination directory does not exist: ' + dest_dir )
        
        with open(manifest_path, 'r') as manifest_fp:
            # load the image manifest
            manifest = json.load(manifest_fp)
            
            # iterate through each source image and convert to a .png based on the
            # output requirements
            for image_source in manifest:
                for size_str in image_source['sizes']:
                    in_file = os.path.join(source_dir, image_source['name']) + '.svg'
                    width, height = size_str.split('x')

                    if 'folder' in image_source:
                        out_file = os.path.join(dest_dir, image_source['folder'], image_source['name'] + '.png')
                    else: 
                        out_file = os.path.join(dest_dir, size_str, image_source['name'] + '.png')
                    out_dir = os.path.dirname(out_file)
                    if not os.path.isdir(out_dir):
                        os.makedirs(out_dir)
                        
                    print "Converting image {0} to {1} with dimensions {2}".format(in_file, out_file, size_str)
                    self.svg2png(src_svg=in_file, dest_png=out_file, width=width, height=height)

if __name__ == "__main__":
    try:
        image_converter = ImageConverter()
        image_converter.run(argv=sys.argv[1:])
    except Exception as e:
        print >>sys.stderr, e
        sys.exit(1)
    