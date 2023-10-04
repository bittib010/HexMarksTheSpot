from common import Node, FileParser
import struct

# ChatGPT generated starter.. not looked at yet

class MFTFileParser(FileParser):
    def __init__(self, file):
        super().__init__(file)
        self.root = None

    def parse(self):
        self.file.seek(0)
        self.root = Node(b'', "NTFS Boot Sector")

        # Define and parse the boot sector fields
        fields = [
            (3, "x86 JMP and NOP instructions", "JMP and NOP"),
            (8, "OEM ID", "NTFS String"),
            (2, "Bytes per sector", "BPB"),
            (1, "Sectors Per Cluster", "Sectors Per Cluster"),
            (2, "Reserved Sectors, unused", "Reserved Sectors"),
            (3, "Unused", "Unused"),
            (2, "Unused by NTFS", "Unused by NTFS"),
            (1, "Media Descriptor", "Media Descriptor"),
            (2, "Unused", "Unused"),
            (2, "Sectors Per Track", "Sectors Per Track"),
            (2, "Number Of Heads", "Number Of Heads"),
            (4, "Hidden Sectors", "Hidden Sectors"),
            (4, "Unused", "Unused"),
            (4, "EBPB Unused", "EBPB Unused"),
            (8, "Total sectors", "Total sectors"),
            (8, "$MFT cluster number", "$MFT cluster number"),
            (8, "$MFTMirr cluster number", "$MFTMirr cluster number"),
            (1, "Bytes or Clusters Per File Record Segment", "Bytes/Clusters Per File Record Segment"),
            (3, "Unused", "Unused"),
            (1, "Bytes or Clusters Per Index Buffer", "Bytes/Clusters Per Index Buffer"),
            (3, "Unused", "Unused"),
            (8, "Volume Serial Number", "Volume Serial Number"),
            (4, "Checksum, unused", "Checksum"),
            (426, "Bootstrap Code", "Bootstrap Code"),
            (2, "End-of-sector Marker", "End-of-sector Marker")
        ]
        for length, description, name in fields:
            data = self.file.read(length)
            node = Node(data, description, name)
            self.root.add_child(self.file.tell() - length, node)

        # Parse MFT Entries
        self.parse_mft_entries()

        return self.root

    def parse_mft_entries(self):
        mft_root = Node(b'', "Master File Table")
        self.root.add_child(self.file.tell(), mft_root)

        while True:
            entry_start = self.file.tell()
            entry_data = self.file.read(1024)  # Standard size of an MFT entry
            
            if entry_data[:4] != b'FILE':
                break

            entry_node = Node(entry_data, "MFT Entry")
            mft_root.add_child(entry_start, entry_node)

            # Parse specific attributes within the MFT entry
            self.parse_standard_information(entry_data, entry_node)
            self.parse_file_name(entry_data, entry_node)
            # Add more attribute parsing methods here

    def parse_standard_information(self, entry_data, parent_node):
        # Example: Parse the $STANDARD_INFORMATION attribute
        offset = 0x30  # Example offset; actual value may vary
        data = entry_data[offset:offset + 72]
        node = Node(data, "$STANDARD_INFORMATION Attribute")
        parent_node.add_child(offset, node)

    def parse_file_name(self, entry_data, parent_node):
        # Example: Parse the $FILE_NAME attribute
        offset = 0x60  # Example offset; actual value may vary
        length = struct.unpack_from('<I', entry_data, offset + 4)[0] - 0x18
        data = entry_data[offset + 0x18:offset + 0x18 + length]
        node = Node(data, "$FILE_NAME Attribute")
        parent_node.add_child(offset, node)

    # Add more parsing methods for other attributes and metafiles

    @classmethod
    def recognizes(cls, file):
        # Read the first 4 bytes of the first MFT entry
        file.seek(0)
        signature = file.read(4)

        # Check if the signature matches "FILE"
        return signature == b'FILE'
