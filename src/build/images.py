import json
import optparse
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
    
    def _svg2png(self, src_svg, dest_png, width, height):
        retcode = subprocess.call(
            ["rsvg-convert", '-w', str(width), '-h', str(height), '-o', dest_png, src_svg]
        )
        if retcode != 0:
            raise ConvertImagesException("Unable to convert: " + src_svg)
        
    def _check_common_preconditions(self):
        if not self.options.source_dir:
            raise ConvertImagesException('Source directory not specified')
        if not self.options.dest_dir:
            raise ConvertImagesException('Destination directory not specified')             
        if not self.manifest:
            raise ConvertImagesException('Unable to load manifest')
        
    def _get_output_info(self, image_source):
        """
        Returns the output file information for a given image set as an array of tuples in the format:
        
        (size_str, width, height, out_file) 
        """
        output_info = []
        for curr_size in image_source['sizes']:
            width, height = curr_size.split('x')
            sub_folder = image_source.get('folder', curr_size)
            out_file = os.path.join(self.options.dest_dir, sub_folder, image_source['name'] + '.png')
            output_info.append( ( curr_size, width, height, out_file) )
        return output_info
    
    def _build(self):
        # check preconditions
        self._check_common_preconditions()
        if not os.path.isdir(self.options.dest_dir):
            raise ConvertImagesException('Destination directory does not exist: ' + self.options.dest_dir )
    
        # iterate through each source image and convert to a .png based on the
        # output requirements
        for image_source in self.manifest:
            
            in_file = os.path.join(self.options.source_dir, image_source['name']) + '.svg'
            output_info = self._get_output_info(image_source)
            for t in output_info:

                (size_str, width, height, out_file) = t
                out_dir = os.path.dirname(out_file)
                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)
                print "Converting image {0} to {1} with dimensions {2}".format(in_file, out_file, size_str)
                self._svg2png(src_svg=in_file, dest_png=out_file, width=width, height=height)
    
    
    def _output_sources(self):
        self._check_common_preconditions()
        
        # output each source file
        for image_source in self.manifest:
            in_file = os.path.join(self.options.source_dir, image_source['name']) + '.svg'
            print in_file
    
    def _output_destfiles(self):
        self._check_common_preconditions()
        
        # output each destination file        
        for image_source in self.manifest:
            output_info = self._get_output_info(image_source)
            for t in output_info:
                print t[3]
                        
    
    def run(self, argv):
        
        # parse the arguments and check the preconditions
        usage = "\n\
            images.py [options] build      - Converts the images\n\
            images.py [options] sources    - Outputs the source files\n\
            images.py [options] destfiles  - Outputs the destination files\n\
            images.py help                 - Outputs help information"
        parser = optparse.OptionParser(usage=usage)
        parser.add_option("-s", "--srcdir", action="store", dest="source_dir", 
                          help="source directory")
        parser.add_option("-d", "--destdir", action="store", dest="dest_dir",
                          help="output directory")
        (self.options, args) = parser.parse_args(argv)
        if len(args) < 2 or args[1]=='help':
            parser.print_help()
            return
        
        manifest_path = os.path.join(self.options.source_dir, self._MANIFEST_FILENAME)
        if not os.path.exists(manifest_path):
            raise ConvertImagesException('Image manifest does not exist: ' + manifest_path )

        with open(manifest_path, 'r') as manifest_fp:
            # load the image manifest
            self.manifest = json.load(manifest_fp)

            command = args[1]
            if command == 'build':
                self._build()
            elif command == 'sources':
                self._output_sources()
            elif command == 'destfiles':
                self._output_destfiles()
            else:
                raise ConvertImagesException('Invalid command: ' + command)
            

if __name__ == "__main__":
    try:
        image_converter = ImageConverter()
        image_converter.run(argv=sys.argv)
    except Exception as e:
        print >>sys.stderr, e
        sys.exit(1)
    