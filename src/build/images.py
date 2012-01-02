import json
import os
import sys
import PythonMagick

"""
Converts images based on manifest using Imagemagick
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
                    image = PythonMagick.Image(_u2a(os.path.join(source_dir, image_source['name']) + '.svg'))
                    image.backgroundColor()
                    image.transform(_u2a(size_str))

                    out_file = os.path.join(dest_dir, size_str, image_source['name'] + '.png')
                    out_dir = os.path.dirname(out_file)
                    if not os.path.isdir(out_dir):
                        os.makedirs(out_dir)
                    image.write(_u2a(out_file))

if __name__ == "__main__":
    try:
        image_converter = ImageConverter()
        image_converter.run(argv=sys.argv[1:])
    except Exception as e:
        print >>sys.stderr, e
        sys.exit(1)
    