from common import Node, FileParser

class JPEGFileParser(FileParser):
    def __init__(self, file):
        super().__init__(file)

    def parse(self):
        self.file.seek(0)
        root = Node(b'', "JPEG file")

        # https://people.cs.umass.edu/~liberato/courses/2017-spring-compsci365/assignments/05-jpeg-and-exif/
        # https://asecuritysite.com/forensics/jpeg
        # https://www.w3.org/Graphics/JPEG/jfif3.pdf
        # https://www.w3.org/Graphics/JPEG/itu-t81.pdf
        # https://en.wikipedia.org/wiki/JPEG_File_Interchange_Format
        # root.add_child(<fileLocation>, Node(<readThisLength>, <description>))
        """root.add_child(<fileLocation>, Node(<readThisLength>, <description>)) is adding a child node to the root node. <fileLocation> is the current position in the file (in bytes) from where you're reading the data. Node(<readThisLength>, <description>) creates a new Node object. <readThisLength> is the number of bytes to read from the file, and <description> is a string that describes what the data represents. The new child node is added to the root node's list of children, and is associated with the file location key."""
        
        location = self.file.tell()
        header_check = self.file.read(2)  # adjust the number of bytes read as needed

        # Compare the read bytes to the expected values
        if header_check == b'\xff\xd8':
            # SOI
            start_of_image_marker = Node(header_check, "Start of Image marker (SOI).", name="Header")
            root.add_child(location, start_of_image_marker)
            
            # App0 section
            app0_marker = root.add_child(self.file.tell(), Node(self.file.read(2), "APP0 marker"))
            
            app0_loc = self.file.tell() # need to tell the file where we're at before reading
            app0_length = self.file.read(2)
            length_of_app0_section = root.add_child(app0_loc, Node(app0_length, "Length of APP0 section: \n\n" + str(app0_length) + "\t = \t" + str(int.from_bytes(app0_length, 'big'))))
            
            identifier = root.add_child(self.file.tell(), Node(self.file.read(5), "Identifier. 'JFIF' and null-termination. JFIF is short for JPEG Interchange Format. JPEG is short for Joint Photographic Expert Group. JFIF is a standard for compressing and decompressing digital images. When JPEG images are stored in files, they are often wrapped in a JFIF structure. This structure provides extra information that isn't part of the raw JPEG image itself."))
            version = root.add_child(self.file.tell(), Node(self.file.read(2), "First byte for major version, second byte for minor version (01 02 for 1.02)"))
            pixel_density_units = root.add_child(self.file.tell(), Node(self.file.read(1), "Units for the following pixel density fields 00 : No units; width:height pixel aspect ratio = Ydensity:Xdensity 01 : Pixels per inch (2.54 cm)02 : Pixels per centimeter"))
            horizontal_pixel_density = root.add_child(self.file.tell(), Node(self.file.read(2), "Horizontal pixel density. Must not be zero"))
            vertical_pixel_density = root.add_child(self.file.tell(), Node(self.file.read(2), "Vertical pixel density. Must not be zero"))
            horizontal_pixel_count = root.add_child(self.file.tell(), Node(self.file.read(1), "Horizontal pixel count of the following embedded RGB thumbnail. May be zero"))
            vertical_pixel_count = root.add_child(self.file.tell(), Node(self.file.read(1), "Vertical pixel count of the following embedded RGB thumbnail. May be zero"))
            uncompressed_rgb_thumbnail_data = root.add_child(self.file.tell(), Node(self.file.read(1), "Uncompressed 24 bit RGB (8 bits per color channel) raster thumbnail data in the order R0, G0, B0, ... Rn-1, Gn-1, Bn-1; with n = Xthumbnail x Ythumbnail (3xn)"))
            #The embedded RGB thumbnail data's length seems to be hardcoded to read just one byte. You might want to adjust this to read the entire thumbnail, which would be 3 x horizontal_pixel_count x vertical_pixel_count bytes.
            # Use this to add calculated values
            # uncompressed_rgb_thumbnail_data.add_more_description_content("test")

        else:
            start_of_image_marker = Node(header_check, "Unknown marker")
            root.add_child(location, start_of_image_marker)

        # Read the remaining data as unknown
        remaining_data = self.file.read()
        if remaining_data:
            root.add_child(root.children[-1][0] + 1, Node(remaining_data, "Either the parsing function has not been finalized, the file format is not valid or you've encountered a file that we should look into. Please file an issue on the git repo."))





        return root

    @classmethod
    def recognizes(cls, file):
        file.seek(0)
        header = file.read(2)
        return header == b'\xff\xd8'

