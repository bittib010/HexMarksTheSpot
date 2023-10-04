from common import Node, FileParser
import os
# https://www.sciencedirect.com/science/article/pii/S1742287618300471
# https://digitalforensicforest.com/2015/07/27/sqlite-data-carving-a-way-to-trace/
# https://digitalcorpora.org/corpora/sql/sqlite-forensic-corpus/
# https://medium.com/technology-in-essence/database-btree-indexing-in-sqlite-d5144cb2850b
# https://www.computer.org/csdl/proceedings-article/imf/2018/663200a089/17D45WnnFUl
# https://downloads.digitalcorpora.org/corpora/sql
# https://github.com/mdegrazia/SQLite-Deleted-Records-Parser
# https://digitalforensicforest.com/2015/07/27/sqlite-data-carving-a-way-to-trace/
# https://belkasoft.com/forensic-analysis-of-lnk-files
HEADER_LENGTH = 16
PAGE_SIZE_LENGTH = 2
WRITE_VERSION_LENGTH = 1
READ_VERSION_LENGTH = 1
UNUSED_SPACE_LENGTH = 1
MAX_PAYLOAD_FRACTION_LENGTH = 1
MIN_PAYLOAD_FRACTION_LENGTH = 1
LEAF_PAYLOAD_FRACTION_LENGTH = 1
FILE_CHANGE_COUNTER_LENGTH = 4
IN_HEADER_DB_SIZE_LENGTH = 4
FIRST_FREELIST_TRUNK_PAGE_LENGTH = 4
TOTAL_FREELIST_PAGES_LENGTH = 4
SCHEMA_COOKIE_LENGTH = 4
SCHEMA_FORMAT_NUMBER_LENGTH = 4
DEFAULT_PAGE_CACHE_SIZE_LENGTH = 4
LARGEST_ROOT_B_TREE_LENGTH = 4
DATABASE_TEXT_ENCODING_LENGTH = 4
USER_VERSION_LENGTH = 4
INCREMENTAL_VACUUM_MODE_LENGTH = 4
APP_ID_LENGTH = 4
RESERVED_EXPANSION_LENGTH = 20
VERSION_VALID_FOR_NUMBER_LENGTH = 4
SQLITE_VERSION_NUMBER_LENGTH = 4

PAGE_TYPES = {
    0x02: "interior_index_btree",
    0x05: "interior_table_btree",
    0x0A: "leaf_index_btree",
    0x0D: "leaf_table_btree"
}

class SQLiteFileParser(FileParser):
    """
    A parser for SQLite files. This parser reads the file's header and determines
    its basic properties, such as the version of SQLite it was written with, the 
    page size, and so on.
    """

    def __init__(self, file):
        super().__init__(file)
        self.parsed_fields = {}  # Dictionary to store parsed fields from dictionary way of coding
        self.page_size = None
        self.autovacuum = None
        self.current_color = [0x33, 0x33, 0x33]  # Initialize as a list of integers
        self.root = None
        self.page_counter = 0

    def determine_page_type(self, first_byte):
        """
        Determine the page type based on the first byte.

        Args:
        - first_byte (int): The first byte of the page.

        Returns:
        - str: The page type.
        """
        mapping = {
            0x02: "Interior Index BTree",
            0x05: "Interior Table BTree",
            0x0A: "Leaf Index BTree",
            0x0D: "Leaf Table BTree"
        }
        return mapping.get(first_byte, "unknown")

    def get_field(self, field_name):
        """Retrieve a parsed field by its name."""
        return self.parsed_fields.get(field_name)
    
    def get_page_offset(self, page_num, current_offset):
        """
            Calculate the offset of a given sequence within its own page.

            Args:
            - page_num (int): The page number where the sequence resides.
            - current_offset (int): The current offset of the sequence in the file.

            Returns:
            - int: The offset of the sequence within its own page.

            Description:
            This function calculates the offset of a given sequence within its own page,
            taking into account the page size and any adjustments needed for the specific
            format of the SQLite pages. For the first page, the function returns the difference
            between the current offset and the start of the page. For subsequent pages, the
            function adjusts the offset to account for the page header and any other format
            specific adjustments.
            """        
        page_start_offset = (page_num - 1) * self.page_size
        if page_num == 1:
            return current_offset - page_start_offset
        return (current_offset - page_start_offset) - page_num + 1 - self.page_size

    def get_next_color(self, size):
        # Increase the color value for each channel
        self.current_color = [(c + size) % 256 for c in self.current_color]
        return f"#{self.current_color[0]:02x}{self.current_color[1]:02x}{self.current_color[2]:02x}"
    
    def parse_unknown_data(self, interval, details=None, name="Unparsed data"):
        unknown_data = self.file.read(interval)
        self.root.add_child(self.file.tell() - interval, Node(unknown_data, f"Unparsed!\n\n{details}", name=f"{name}", color="#FF0000"))

    def parse_payload(self, interval):
        payload = self.file.read(interval)
        self.root.add_child(self.file.tell() - interval, Node(payload, f"Payload: {payload}", name="Payload"))

    def parse_cell_pointer(self, cellpointer_array_bytes):
        cellpointer_offsets = []
        for i in range(0, len(cellpointer_array_bytes), 2):
            two_bytes = cellpointer_array_bytes[i:i+2]
            cellpointer = int.from_bytes(two_bytes, "big")
            cellpointer_offsets.append(cellpointer)
            self.root.add_child(self.file.tell() - 2, Node(two_bytes, f"Cell Pointer: {cellpointer}", name=f"cellpointer: {cellpointer}"))
        return cellpointer_offsets
    
    def interior_index_btree(self):
        flag = self.file.read(1)
        flag_byte = int.from_bytes(flag, byteorder='big')
        self.root.add_child(self.file.tell() - 1, Node(flag,
                    f"Btree page {self.page_counter}: {flag_byte}.  Indicating a {self.determine_page_type(flag_byte)}", name=f"Page {self.page_counter}: Interior Index"))

    def interior_table_btree(self):
        flag = self.file.read(1)
        flag_byte = int.from_bytes(flag, byteorder='big')
        self.root.add_child(self.file.tell() - 1, Node(flag,
                    f"Btree page {self.page_counter}: {flag_byte}.  Indicating a {self.determine_page_type(flag_byte)}", name=f"Page {self.page_counter}: Interior Table"))

        # MISSING HEADER! ADD
        first_freeblock_bytes = self.file.read(2)
        first_freeblock = int.from_bytes(first_freeblock_bytes, byteorder='big')
        self.root.add_child(self.file.tell() - 2, Node(first_freeblock_bytes,
                    "Start of the first freeblock", name="1st freeblock start"))

        num_cells_bytes = self.file.read(2)
        num_cells = int.from_bytes(num_cells_bytes, byteorder='big')
        self.root.add_child(self.file.tell() - 2, Node(num_cells_bytes,
                    f"Number of cells: {num_cells}", name="Num. of cells"))

        cell_content_start_bytes = self.file.read(2)
        cell_content_start = int.from_bytes(cell_content_start_bytes, byteorder='big', signed=True)
        cell_content_start = 65536 if cell_content_start == 0 else cell_content_start
        self.root.add_child(self.file.tell() - 2, Node(cell_content_start_bytes,
                    f"Start of the cell content area: {cell_content_start}", name="Cell content start"))

        fragmented_free_bytes_byte = self.file.read(1)
        fragmented_free_bytes = int.from_bytes(fragmented_free_bytes_byte, byteorder='big')
        self.root.add_child(self.file.tell() - 1, Node(fragmented_free_bytes_byte,
                    f"Fragmented free bytes: {fragmented_free_bytes}"))

        # Handle the specific page type
        right_most_pointer_bytes = self.file.read(4)
        right_most_pointer = int.from_bytes(right_most_pointer_bytes, byteorder='big')
        self.root.add_child(self.file.tell() - 4, Node(right_most_pointer_bytes,
                    f"Right-most pointer: {right_most_pointer}"))

        # Handle any remaining bytes in the page
        remaining_bytes_in_page = self.page_size - \
            (1 + 2 + 2 + 2 + 1 + 4)
        remaining_data = self.file.read(remaining_bytes_in_page)

        if remaining_data:
            self.root.add_child(self.file.tell() - len(remaining_data),
                        Node(remaining_data, f"Rest unknown currently {self.get_page_offset(self.page_counter, self.file.tell())}"))

    def leaf_index_btree(self):
        flag = self.file.read(1)
        flag_byte = int.from_bytes(flag, byteorder='big')
        self.root.add_child(self.file.tell() - 1, Node(flag,
                    f"Btree page {self.page_counter}: {flag_byte}.  Indicating a {self.determine_page_type(flag_byte)}", name=f"Page {self.page_counter}: Leaf Index"))
        # Common header for all b-tree pages
        first_freeblock_bytes = self.file.read(2)
        first_freeblock = int.from_bytes(first_freeblock_bytes, byteorder='big')
        self.root.add_child(self.file.tell() - 2, Node(first_freeblock_bytes,
                    "Start of the first freeblock", name="1st freeblock start"))

        num_cells_bytes = self.file.read(2)
        num_cells = int.from_bytes(num_cells_bytes, byteorder='big')
        self.root.add_child(self.file.tell() - 2, Node(num_cells_bytes,
                    f"Number of cells: {num_cells}", name="Num. of cells"))

        cell_content_start_bytes = self.file.read(2)
        cell_content_start = int.from_bytes(cell_content_start_bytes, byteorder='big', signed=True)
        cell_content_start = 65536 if cell_content_start == 0 else cell_content_start
        self.root.add_child(self.file.tell() - 2, Node(cell_content_start_bytes,
                    f"Start of the cell content area: {cell_content_start}", name="Cell content start"))

        fragmented_free_bytes_byte = self.file.read(1)
        fragmented_free_bytes = int.from_bytes(fragmented_free_bytes_byte, byteorder='big')
        self.root.add_child(self.file.tell() - 1, Node(fragmented_free_bytes_byte,
                    f"Fragmented free bytes: {fragmented_free_bytes}"))

        # Handle any remaining bytes in the page
        remaining_bytes_in_page = self.page_size - \
            (1 + 2 + 2 + 2 + 1)
        remaining_data = self.file.read(remaining_bytes_in_page)

        if remaining_data:
            self.root.add_child(self.file.tell() - len(remaining_data),
                        Node(remaining_data, f"Rest unknown currently {self.get_page_offset(self.page_counter, self.file.tell())}"))

    def leaf_table_btree(self):

        # Header flag
        flag = self.file.read(1)
        flag_byte = int.from_bytes(flag, byteorder='big')
        self.root.add_child(self.file.tell() - 1, Node(flag,
                    f"Btree page number {self.page_counter}.  Indicating a {self.determine_page_type(flag_byte)} based on the byte {flag}", name=f"Page {self.page_counter}: Leaf Table"))
        
        # First freeblock
        first_freeblock_bytes = self.file.read(2)
        first_freeblock = int.from_bytes(first_freeblock_bytes, byteorder='big')
        self.root.add_child(self.file.tell() - 2, Node(first_freeblock_bytes,
                    f"Start of the first freeblock is set to offset: {first_freeblock}", name="1st freeblock start"))

        # Number of cells
        num_cells_bytes = self.file.read(2)
        num_cells = int.from_bytes(num_cells_bytes, byteorder='big')
        self.root.add_child(self.file.tell() - 2, Node(num_cells_bytes,
                    f"Number of cells: {num_cells}", name="Num. of cells"))

        # First byte of content
        cell_content_start_bytes = self.file.read(2)
        cell_content_start = int.from_bytes(cell_content_start_bytes, byteorder='big', signed=True)
        cell_content_start = 65536 if cell_content_start == 0 else cell_content_start
        self.root.add_child(self.file.tell() - 2, Node(cell_content_start_bytes,
                    f"Start of the first valid cell content: {cell_content_start}", name="Cell content start"))

        fragmented_free_bytes_byte = self.file.read(1)
        fragmented_free_bytes = int.from_bytes(fragmented_free_bytes_byte, byteorder='big')
        self.root.add_child(self.file.tell() - 1, Node(fragmented_free_bytes_byte,
                    f"Fragmented free bytes: {fragmented_free_bytes}", name=f"Fragmented free bytes {fragmented_free_bytes}"))

        # Handle any remaining bytes in the page
        remaining_bytes_in_page = self.page_size - \
            (1 + 2 + 2 + 2 + 1) 
        remaining_data = self.file.read(remaining_bytes_in_page)

        if remaining_data:
            self.root.add_child(self.file.tell() - len(remaining_data),
                        Node(remaining_data, f"Rest unknown currently {self.get_page_offset(self.page_counter, self.file.tell())}"))

    def parse(self):
        self.file.seek(0)
        self.root = Node(b'', "SQLite file")
        self.page_counter = 1

        PAGE_TYPES = {
                0x02: self.interior_index_btree,
                0x05: self.interior_table_btree,
                0x0A: self.leaf_index_btree,
                0x0D: self.leaf_table_btree
            }

        # read file outside loop to avoid rereading the file everytime.
        file_size = os.path.getsize(self.file.name)
        while True:
            if self.page_counter == 1: # DB Header page
                # Define fields and their respective properties
                fields = [
                    (HEADER_LENGTH, "SQLite header string. Consider this string as a validation to an SQLite file.", "Header string"),
                    (PAGE_SIZE_LENGTH, "Page size. This has to be a power of 2 byte big-endian integer between the range of 512 and 32768. The value of 1 is an exception that means that the page size is set to 65536 bytes.", "Page size"),
                    (WRITE_VERSION_LENGTH,
                     "Write version (1: legacy, 2: WAL). Write version and read version (the next sequence) are always the same.", "Write version"),
                    (READ_VERSION_LENGTH,
                     "Read version (1: legacy, 2: WAL). Write version and read version (the previous sequence) are always the same.", "Read version"),
                    (UNUSED_SPACE_LENGTH,
                     "Bytes of unused reserved space at the end of each page. Typically this is set to zero, but if another value is present, it means that the space is used for extension, most likely for encryption.", "Unused Space"),
                    (MAX_PAYLOAD_FRACTION_LENGTH,
                     "Maximum embedded payload fraction. Must be 64", "Max payload fraction"),
                    (MIN_PAYLOAD_FRACTION_LENGTH,
                     "Minimum embedded payload fraction. Must be 32", "Min. payload fraction"),
                    (LEAF_PAYLOAD_FRACTION_LENGTH,
                     "Leaf payload fraction. Must be 32", "Leaf payload fraction"),
                    (FILE_CHANGE_COUNTER_LENGTH,
                     "File change counter. This contains a value that increments every time the database is updated.", "File change counter"), # set the color of this to red? - meaning forensic value!
                    (IN_HEADER_DB_SIZE_LENGTH,
                     "Size of the database file in pages (the \"in-header database size\")", "In-header DB size"),
                    (FIRST_FREELIST_TRUNK_PAGE_LENGTH,
                     "Page number of the first freelist trunk page", "First freelist trunk page"),
                    (TOTAL_FREELIST_PAGES_LENGTH,
                     "Total number of freelist pages", "Total freelist pages"),
                    (SCHEMA_COOKIE_LENGTH, "The schema cookie", "Schema cookie"),
                    (SCHEMA_FORMAT_NUMBER_LENGTH,
                     "The schema format number. Supported schema formats are 1, 2, 3, and 4", "Schema Format Number"),
                    (DEFAULT_PAGE_CACHE_SIZE_LENGTH,
                     "Default page cache size", "Default Page Cache Size"),
                    (LARGEST_ROOT_B_TREE_LENGTH, "The page number of the largest root b-tree page when in auto-vacuum or incremental-vacuum modes, or zero otherwise", "Auto-vacuum"),
                    (DATABASE_TEXT_ENCODING_LENGTH,
                     "The database text encoding. A value of 1 means UTF-8. A value of 2 means UTF-16le. A value of 3 means UTF-16be", "DB Text Encoding"),
                    (USER_VERSION_LENGTH,
                     "The \"user version\" as read and set by the user_version pragma", "User Version"),
                    (INCREMENTAL_VACUUM_MODE_LENGTH,
                     "True (non-zero) for incremental-vacuum mode. False (zero) otherwise", "Incremental Vacuum Mode"),
                    (APP_ID_LENGTH, "The \"Application ID\" set by PRAGMA application_id", "APP ID Length"),
                    (RESERVED_EXPANSION_LENGTH,
                     "Reserved for expansion. Must be zero", "Reserved Expansion"),
                    (VERSION_VALID_FOR_NUMBER_LENGTH,
                     "The version-valid-for number", "Version Valid For Number"),
                    (SQLITE_VERSION_NUMBER_LENGTH, "SQLITE_VERSION_NUMBER_LENGTH", "SQLite Version")
                ]

                for index, (length, description, name) in enumerate(fields):
                    cur_col = self.get_next_color(size=0x05)
                    data = self.file.read(length)

                    if index == 0:  # First entry
                        table_value = data.decode('ascii', errors='ignore')  # Decode bytes to ASCII
                    else:
                        table_value = int.from_bytes(data, byteorder="big")

                    node = Node(data, description, name, table_value=table_value, color=cur_col)
                    
                    self.root.add_child(self.file.tell() - length, node)
                    if name:
                        # Store the data in the dictionary
                        self.parsed_fields[name] = data

                
                page_size_bytes = self.get_field("Page size")
                self.page_size = int.from_bytes(page_size_bytes, byteorder='big') # from _init_
                
                autovacuum_size_bytes = self.get_field("Auto-vacuum")
                self.autovacuum = int.from_bytes(autovacuum_size_bytes, byteorder='big') # from _init_
                
                # PAGE START:
                # First page page header after db header (100bytes)
                flag = self.file.read(1)
                flag_byte = int.from_bytes(flag, byteorder='big')
                self.root.add_child(self.file.tell() - 1, Node(flag,
                            f"Page header: {flag_byte}.  indicating a {self.determine_page_type(flag_byte)}. The first page of a SQLite DB is always a Table BTree type page.", name="DB Header Page Header"))

                # First freeblock offset
                first_freeblock = self.file.read(2)
                first_freeblock_offset = int.from_bytes(first_freeblock, byteorder="big")
                self.root.add_child(self.file.tell() - 2, Node(first_freeblock,
                            f"First free block at offset {first_freeblock_offset}", name="First freeblock"))
                # Number of cells in this page
                no_of_cells = self.file.read(2)
                no_of_cells_in_page = int.from_bytes(no_of_cells, byteorder="big")
                self.root.add_child(self.file.tell() - 2, Node(no_of_cells,
                            f"no_of_cells: {no_of_cells_in_page}", name="no_of_cells"))
                
                # First byte of content
                first_byte_of_content = self.file.read(2)
                first_byte_of_content_offset = int.from_bytes(first_byte_of_content, "big")
                self.root.add_child(self.file.tell() - 2, Node(first_byte_of_content,
                            f"First_byte_of_content: {first_byte_of_content_offset}", name="first_byte_of_content"))
                
                fragmented_byte_count = self.file.read(1)
                fragmented_byte_count_offset = int.from_bytes(fragmented_byte_count, "big")
                self.root.add_child(self.file.tell() -1, Node(fragmented_byte_count, f"Fragmented byte count: {fragmented_byte_count_offset}", name="Fragmented Byte count"))
                
                right_most_pointer = self.file.read(4) #  Page 1 is always using this as it always is interior btree
                rmp_value = int.from_bytes(right_most_pointer, "big")
                self.root.add_child(self.file.tell() - 4, Node(right_most_pointer,
                        f"Right most pointer at page offset {rmp_value}", name="Right most pointer"))
                
                # TODO: ADD FREEBLOCK IF EXISTING. CALCULATE UNPARSER BEFORE AND/OR AFTER

                # TODO: ADD CHECK TO SEE IF FIRST BYTE OF CONTENT MATCHES THE FIRST CELL OFFSET

                cellpointer_array_bytes = self.file.read(no_of_cells_in_page * 2) # two byte long
                cellpointer_offsets = self.parse_cell_pointer(cellpointer_array_bytes)

                cellpointer_offsets.append(self.page_size) # account for the last cells end
                # Sort the cellpointer offsets in ascending order
                cellpointer_offsets.sort()

                if len(cellpointer_offsets) >= 2:
                    intervals = [cellpointer_offsets[i+1] - cellpointer_offsets[i] for i in range(len(cellpointer_offsets)-1)]
                    # Unknown data between cells and cell pointers
                    self.parse_unknown_data(cellpointer_offsets[0] - self.file.tell(), details="Possible forensic value exists here!")
                
                    for i, interval in enumerate(intervals):                    
                        self.parse_payload(interval)
                else:
                    # Handle the case where there are not enough offsets to compute intervals
                    print("Not enough cellpointer_offsets to compute intervals.")
                

                

                self.page_counter += 1
                if self.file.tell() == self.page_size:
                    continue
                else: # Error message?
                    pass
            elif self.autovacuum != 0 and self.page_counter == 2:
                self.page_counter += 1

            # Read and lookup the page header
            page_header_byte = int.from_bytes(self.file.read(1), byteorder='big')
            self.file.seek(self.file.tell() - 1)
            page_type = PAGE_TYPES.get(page_header_byte)

            # Handle the page type
            if page_type is not None:
                page_type()
                self.page_counter += 1
            else:
                # Unknown page - add it and mark it as unknown
                self.parse_unknown_data(self.page_size, details=f"Page {self.page_counter}", name=f"Page {self.page_counter}: Unparsed/unknown data.")
                """ remaining_data = self.file.read(self.page_size)

                if remaining_data:
                    self.root.add_child(self.file.tell() - len(remaining_data),
                                Node(remaining_data, f"Rest unknown currently.", color="#DDAACC"))"""
                self.page_counter += 1 
                
            
            if self.file.tell() + self.page_size > file_size:
                return self.root
            else:
                pass

        return self.root

    @classmethod
    def recognizes(cls, file):
        # reads the header and sets seeker here
        file.seek(0)
        header = file.read(16)
        return header == b"SQLite format 3\x00"
