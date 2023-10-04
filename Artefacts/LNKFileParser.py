from common import Node, FileParser
import os
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox

# Resources: 
# https://github.com/AndrewRathbun/DFIRArtifactMuseum/tree/10a84beffdcfcd89a32978cd8d585e4fc044812d/Windows/LNK
# https://github.com/corkami/pics/blob/c44d9ee3a97007a1b93b1a460675740a5f2bd7d6/binary/lnk.png
# https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/4d25bbad-09b7-4322-8c0a-521d268481bb
# https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/16cb4ca1-9339-4d0c-a68d-bf1d6cc0f943

#TODO: Enlighten user that this standard follows latest version

LINK_FLAGS_MAPPING = {
    0: "HasLinkTargetIDList",
    1: "HasLinkInfo",
    2: "HasName",
    3: "HasRelativePath",
    4: "HasWorkingDir",
    5: "HasArguments",
    6: "HasIconLocation",
    7: "IsUnicode",
    8: "ForceNoLinkInfo",
    9: "HasExpString",
    10: "RunInSeparateThread",
    11: "Unused1",
    12: "HasDarwinID",
    13: "RunAsUser",
    14: "HasExpIcon",
    15: "NoPidlAlias",
    16: "Unused2",
    17: "RunWithShimLayer",
    18: "ForceNoLinkTrack",
    19: "EnableTargetMetadata",
    20: "DisableLinkPathTracking",
    21: "DisableKnownFolderTracking",
    22: "DisableKnownFolderAlias",
    23: "AllowLinkToLink",
    24: "UnaliasOnSave",
    25: "PreferEnvironmentPath",
    26: "KeepLocalIDListForUNCTarget", #TODO Many unused fields in the latest edition - remove non used fields
    27: "Unused3",
    28: "Unused4",
    29: "NoSpecialFolderTracking",
    30: "TargetMetadataInOptimizedFormat",
    31: "Unused5"
}

SHOW_COMMAND = {
    1: "SW_SHOWNORMAL",
    3: "SW_SHOWMAXIMIZED",
    7: "SW_SHOWMINNOACTIVE"
}

SHOW_COMMAND_INFO = {
    1: "The application is open and its window is open in a normal fashion",
    3: "The application is open, and keyboard focus is given to the application, but its window is not shown",
    7: "The application is open, but its window is not shown. It is not given the keyboard focus"
}


class InvalidLNKFileException(Exception):
    pass

class LNKFileParser(FileParser):
    """
    A parser for LNK files.
    """

    def __init__(self, file):
        super().__init__(file)
        self.current_color = [0x33, 0x33, 0x33]  # Initialize as a list of integers
        self.parsed_fields = {}  # Dictionary to store parsed fields from dictionary way of coding

    def get_next_color(self, size):
        # Increase the color value for each channel
        self.current_color = [(c + size) % 256 for c in self.current_color]
        return f"#{self.current_color[0]:02x}{self.current_color[1]:02x}{self.current_color[2]:02x}"
    
    def bytes_to_guid(self, guid_bytes):
        # Ensure the byte array contains exactly 16 bytes
        if len(guid_bytes) != 16:
            raise ValueError("Invalid length for GUID bytes")
        
        # Parse individual components of the GUID
        part1 = int.from_bytes(guid_bytes[0:4], byteorder='little')
        part2 = int.from_bytes(guid_bytes[4:6], byteorder='little')
        part3 = int.from_bytes(guid_bytes[6:8], byteorder='little')
        part4 = guid_bytes[8:10]
        part5 = guid_bytes[10:16]
        
        # Assemble the string representation
        guid_str = f"{part1:08x}-{part2:04x}-{part3:04x}-{''.join([f'{x:02x}' for x in part4])}-{''.join([f'{x:02x}' for x in part5])}"
        
        return guid_str
    
    def filetime_to_datetime(self, filetime_bytes):
        filetime_int = int.from_bytes(filetime_bytes, byteorder='little')
        print(f"Debug: filetime_int value is {filetime_int}")
        
        # Check if the timedelta will be too large
        max_microseconds = (datetime.max - datetime(1601, 1, 1)).total_seconds() * 1_000_000
        if filetime_int // 10 > max_microseconds:
            return f"Invalid FILETIME: {filetime_bytes}, would result in datetime out of range"
        
        try:
            windows_epoch = datetime(1601, 1, 1)
            delta = timedelta(microseconds=filetime_int // 10)  # Convert 100-nanoseconds to microseconds
            return windows_epoch + delta
        except Exception as e:
            return f"Exception: {e}, Invalid FILETIME: {filetime_bytes}"

    @staticmethod
    def show_error_popup(message):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("LNK Parsing Error", message)
    
    def is_valid_filetime(self, filetime_bytes):
        # Here you can add checks for validity, for example, if the byte string should not start with a space
        return not filetime_bytes.startswith(b' ')
    
    def get_active_flags(self, flags_integer):
        active_flags = {}
        for bit, flag_name in LINK_FLAGS_MAPPING.items():
            if flags_integer & (1 << bit):
                active_flags[flag_name] = True
            else:
                active_flags[flag_name] = False

        return "<ul>" + "\n".join([f"<li>{flag_name}: {str(is_active)}</li>" for flag_name, is_active in active_flags.items()]) + "</ul>"

    def is_bit_set(self, byte_data, offset):
        bit_offset_in_byte = offset % 8
        byte_offset = offset // 8
        return bool(byte_data[byte_offset] & (1 << bit_offset_in_byte))
    
    def bytes_to_binary(self, byte_data):
        return ''.join(format(byte, '08b') for byte in byte_data)

    def parse(self):
        self.file.seek(0)
        self.root = Node(b'', "LNK File")

        try:
            header = self.file.read(4)
            self.root.add_child(self.file.tell() - 4, Node(header, f"""<h1>Header</h1>
                                                           <p>Header MUST be 0x0000004C.</p>
                                                           """, name = "Header", table_value=header))

            guid = self.file.read(16)
            guid_bytes = self.bytes_to_guid(guid)
            self.root.add_child(self.file.tell() - 16, Node(guid,f"""<h1>GUID</h1>
                                                            <p>GUID: {guid_bytes}</p>""", name="GUID", table_value=guid_bytes))

            # https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/ae350202-3ba9-4790-9e9e-98935f4ee5af
            link_flags = self.file.read(4)
            link_flags_bytes = int.from_bytes(link_flags, byteorder="little")
            active_flags = self.get_active_flags(link_flags_bytes)
            self.root.add_child(self.file.tell() - 4, Node(link_flags, f"""<h1>Link Flags</h1>
                                                           <p>This structure specifies information about the shell link and the presence of optional portions of the structure.</p>
                                                           <p>Based on the decimal value {link_flags_bytes} converted to binary {self.bytes_to_binary(link_flags)} we get the active flags as:</p> {active_flags}""", name="Link Flags", table_value=self.bytes_to_binary(link_flags)))

            # TODO: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/378f485c-0be9-47a4-a261-7df467c3c9c6

            file_attributes = self.file.read(4)
            file_attributes_bytes = int.from_bytes(file_attributes, byteorder="little")
            self.root.add_child(self.file.tell() - 4, Node(file_attributes, f"""<h1>File Attributes</h1>.""", name="File Attributes", table_value=file_attributes_bytes))
            
            creation_time = self.file.read(8)
            if self.is_valid_filetime(creation_time):
                creation_time_bytes = self.filetime_to_datetime(creation_time)
            else:
                creation_time_bytes = f"Invalid FILETIME: {creation_time}"
            self.root.add_child(self.file.tell() - 8, Node(creation_time, f"""<h1>Creation time</h1>
                                                           All timestamps are stored as FILETIME type and it converts to {creation_time_bytes}""", table_value=creation_time_bytes, name="Creation Time")) 
            
            access_time = self.file.read(8)
            if self.is_valid_filetime(creation_time):
                access_time_bytes = self.filetime_to_datetime(access_time)
            else:
                access_time_bytes = f"Invalid FILETIME: {access_time}"
            access_time_bytes = self.filetime_to_datetime(access_time)
            self.root.add_child(self.file.tell() - 8, Node(access_time, f"""<h1>Access time</h1>
                                                           All timestamps are stored as FILETIME type and it converts to {access_time_bytes}""", table_value=access_time_bytes, name="Access Time")) 
            
            write_time = self.file.read(8)
            if self.is_valid_filetime(write_time):
                write_time_bytes = self.filetime_to_datetime(write_time)
            else:
                write_time_bytes = f"Invalid FILETIME: {write_time}"
            self.root.add_child(self.file.tell() - 8, Node(write_time, f"""<h1>Write time</h1>
                                                           All timestamps are stored as FILETIME type and it converts to {write_time_bytes}""", table_value=write_time_bytes, name="Write Time")) 
            
            file_size = self.file.read(4)
            file_size_bytes = int.from_bytes(file_size, byteorder="little")
            self.root.add_child(self.file.tell() - 4, Node(file_size, f"File size: {file_size_bytes}", table_value=file_size_bytes, name="File size")) 
            
            icon_index = self.file.read(4)
            icon_index_bytes = int.from_bytes(icon_index, byteorder="little")
            self.root.add_child(self.file.tell() - 4, Node(icon_index, f"Icon index: {icon_index}", table_value=icon_index_bytes, name="Icon Index")) 
            
            show_command = self.file.read(4) # https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/c3376b21-0931-45e4-b2fc-a48ac0e60d15 #TODO
            show_command_bytes = int.from_bytes(show_command, byteorder="little")
            if show_command_bytes not in SHOW_COMMAND:
                raise InvalidLNKFileException(f"Show command is not valid. Got {show_command_bytes}, but needs {SHOW_COMMAND}") # TODO: MS states "All other values MUST be treated as SW_SHOWNORMAL."
            else: 
                extra_info = f"This indicates that the command is set to {SHOW_COMMAND[show_command_bytes]} which means that {SHOW_COMMAND_INFO[show_command_bytes]}"
            self.root.add_child(self.file.tell() - 4, Node(show_command, f"Show Command: {show_command_bytes}. {extra_info}", table_value=show_command_bytes, name="Show Command")) 
            
            hotkey = self.file.read(2) # TODO: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/8cd21240-1b5d-43e6-adc4-38cf14e30cea
            icon_index_bytes = int.from_bytes(hotkey, byteorder="little")
            self.root.add_child(self.file.tell() - 2, Node(hotkey, f"Hotkey: {hotkey}", table_value=icon_index_bytes, name="Hotkey")) 
            
            reserved1 = self.file.read(2)
            reserved1_bytes = int.from_bytes(reserved1, byteorder="little")
            self.root.add_child(self.file.tell() - 2, Node(reserved1, f"Reserved bytes: {reserved1_bytes}", table_value=reserved1_bytes, name="Reserved")) 

            reserved2 = self.file.read(4)
            reserved2_bytes = int.from_bytes(reserved2, byteorder="little")
            self.root.add_child(self.file.tell() - 4, Node(reserved2, f"<h1>Reserved bytes</h1>: {reserved2_bytes}", table_value=reserved2_bytes, name="Reserved")) 

            reserved3 = self.file.read(4)
            reserved3_bytes = int.from_bytes(reserved3, byteorder="little")
            self.root.add_child(self.file.tell() - 4, Node(reserved3, f"Reserved bytes: {reserved3_bytes}", table_value=reserved3_bytes, name="Reserved")) 

            ###################################################################################################################################
            # Link Target ID List (Dynamic length)
            ###################################################################################################################################
            if self.is_bit_set(link_flags, 0): # HasLinkTargetIDList
                id_list_size_bytes = self.file.read(2)
                id_list_size_bytes2int = int.from_bytes(id_list_size_bytes, byteorder="little")
                self.root.add_child(self.file.tell() - 4, Node(id_list_size_bytes, f"Link info size: {id_list_size_bytes2int}. The next few field are fall under the category of this until we meet the offset {self.file.tell() + id_list_size_bytes2int}.", table_value=id_list_size_bytes2int, name="Link info size"))

                # Beginning of ID List
                # Beginning of Item ID list
                while True:
                    # Read the size of the item ID data block
                    item_id_size_bytes = self.file.read(2)
                    item_id_size_int = int.from_bytes(item_id_size_bytes, byteorder="little")

                    # Check for termination bytes
                    if item_id_size_int == 0:
                        break

                    # Read the actual item ID data (size - 2 to account for the bytes we've already read)
                    item_id_data_bytes = self.file.read(item_id_size_int - 2)
                    item_id_data_decoded = item_id_data_bytes.decode('utf-8', errors='ignore')

                    # Add the size as well as a child node
                    self.root.add_child(self.file.tell() - 2, Node(item_id_size_bytes, f"Item ID size {item_id_size_int}", name="Item ID size", table_value=item_id_size_int))

                    # Add this data as a child node
                    self.root.add_child(self.file.tell() - item_id_size_int, Node(item_id_data_bytes, f"Item ID Data: {item_id_data_decoded}", name="Item ID Data", table_value=item_id_data_decoded))

                self.root.add_child(self.file.tell() - 2, Node(item_id_size_bytes, f"Terminal ID.", name="Terminal ID", table_value=item_id_size_int))


                # CONTINUE https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/6813269d-0cc8-4be2-933f-e96e8e3412dc
            
            ##############################################################################################################################
            # LINK INFO
            ##############################################################################################################################
            #TODO: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/6813269d-0cc8-4be2-933f-e96e8e3412dc

            
            if self.is_bit_set(link_flags, 1): # HasLinkInfo
                link_info_size_bytes = self.file.read(4)
                link_info_size_bytes2int = int.from_bytes(link_info_size_bytes, byteorder="little")
                self.root.add_child(self.file.tell() -2, Node(link_info_size_bytes, f"Link Info Size.", name="Link info Size", table_value=link_info_size_bytes2int))

                link_info_header_size_bytes = self.file.read(4)
                link_info_header_size_bytes2int = int.from_bytes(link_info_header_size_bytes, byteorder="little")
                self.root.add_child(self.file.tell() - 4, Node(link_info_header_size_bytes, f"Link info header size", name="Link info header size", table_value=link_info_header_size_bytes2int))


                link_info_flags_bytes = self.file.read(4)
                link_info_flags_bytes2int = int.from_bytes(link_info_flags_bytes, byteorder="little")
                self.root.add_child(self.file.tell() -2, Node(link_info_flags_bytes, f"Link Info Flags.", name="Link info Flags", table_value=link_info_flags_bytes2int))


                volume_id_offsett_bytes = self.file.read(4)
                volume_id_offsett_bytes2int = int.from_bytes(volume_id_offsett_bytes, byteorder="little")
                self.root.add_child(self.file.tell() -2, Node(volume_id_offsett_bytes, f"Volume ID Offset", name="Volume ID Offset", table_value=volume_id_offsett_bytes2int))


                local_base_path_offset_bytes = self.file.read(4)
                local_base_path_offset_bytes2int = int.from_bytes(local_base_path_offset_bytes, byteorder="little")
                self.root.add_child(self.file.tell() -2, Node(local_base_path_offset_bytes, f"Local Base Path Offset", name="Local Base Path OFfset", table_value=local_base_path_offset_bytes2int))


                common_network_relative_link_offset_bytes = self.file.read(4)
                common_network_relative_link_offset_bytes2int = int.from_bytes(common_network_relative_link_offset_bytes, byteorder="little")
                self.root.add_child(self.file.tell() -2, Node(common_network_relative_link_offset_bytes, f"Common Network Relative Link Offset", name="Common Network Relative Link Offset", table_value=common_network_relative_link_offset_bytes2int))


                common_path_suffix_offset_bytes = self.file.read(4)
                common_path_suffix_offset_bytes2int = int.from_bytes(common_path_suffix_offset_bytes, byteorder="little")
                self.root.add_child(self.file.tell() -2, Node(common_path_suffix_offset_bytes, f"Common Path Suffix Offset", name="Common Path Suffix Offset", table_value=common_path_suffix_offset_bytes2int))

                # Volume ID begins
                # TODO: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/b7b3eea7-dbff-4275-bd58-83ba3f12d87a
                if link_info_flags_bytes2int == 1:
                    volume_id_size_bytes = self.file.read(4)
                    volume_id_size_bytes2int = int.from_bytes(volume_id_size_bytes, byteorder="little")
                    self.root.add_child(self.file.tell() -4, Node(volume_id_size_bytes, f"Volume ID Size Bytes", name="Volume ID Size Bytes", table_value=volume_id_size_bytes2int))

                    drive_type_bytes = self.file.read(4)
                    drive_type_bytes2int = int.from_bytes(drive_type_bytes, byteorder="little")
                    self.root.add_child(self.file.tell() -4, Node(drive_type_bytes, f"Drive Type Bytes", name="Drive Type Bytes", table_value=drive_type_bytes2int))

                    drive_serial_number_bytes = self.file.read(4)
                    drive_serial_number_bytes2int = int.from_bytes(drive_serial_number_bytes, byteorder="little")
                    self.root.add_child(self.file.tell() -4, Node(drive_serial_number_bytes, f"Drive Serial Number", name="Drive Serial Number", table_value=drive_serial_number_bytes2int))

                    volume_label_offset_bytes = self.file.read(4)
                    volume_label_offset_bytes2int = int.from_bytes(volume_label_offset_bytes, byteorder="little")
                    self.root.add_child(self.file.tell() -4, Node(volume_label_offset_bytes, f"Volume Label Offset", name="Volume Label Offset", table_value=volume_label_offset_bytes2int))

                    data_bytes = self.file.read(1)
                    data_bytes2int = int.from_bytes(data_bytes, byteorder="little")
                    self.root.add_child(self.file.tell() - 1, Node(data_bytes, f"Data bytes", name="Data Bytes", table_value=data_bytes2int))


                    local_base_path_bytes = self.file.read(14)
                    local_base_path_bytes_decoded = local_base_path_bytes.decode('utf-8', errors='ignore')
                    self.root.add_child(self.file.tell() -14, Node(local_base_path_bytes, f"Local Base Path", name="Local Base Path", table_value=local_base_path_bytes_decoded))

                common_path_suffix_bytes = self.file.read(1)
                common_path_suffix_bytes2int = int.from_bytes(common_path_suffix_bytes, byteorder="little")
                self.root.add_child(self.file.tell() -1, Node(common_path_suffix_bytes, f"Common Path Suffix", name="Common Path Suffix", table_value=common_path_suffix_bytes2int))

            ###################################################################################################################################
            # STRING_DATA section https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-shllink/17b69472-0f34-4bcf-b290-eccdb8de224b
            ###################################################################################################################################

            if self.is_bit_set(link_flags, 2): # HasName 
                name_string_bytes = self.file.read(2)
                name_string_bytes2int = int.from_bytes(name_string_bytes, byteorder="little")
                self.root.add_child(self.file.tell() - 2, Node(name_string_bytes, f"Name String Size: {name_string_bytes2int}", name="Name String Size", table_value=name_string_bytes2int))


            if self.is_bit_set(link_flags, 3): #HasRelativePath
                relative_path_bytes = self.file.read(2)
                relative_path_bytes2int = int.from_bytes(relative_path_bytes, byteorder="little")
                self.root.add_child(self.file.tell() - 2, Node(relative_path_bytes, f"Relative Path Size: {relative_path_bytes2int}", name="Relative Path Size", table_value=relative_path_bytes2int))

                # TODO: Investigate isUnicode's interference with the below
                relative_path_string = self.file.read(relative_path_bytes2int * 2) # *2 since it is unicode
                relative_path_string_decoded = relative_path_string.decode('utf-16-le', errors='ignore')
                self.root.add_child(self.file.tell() - (relative_path_bytes2int * 2), Node(relative_path_string, f"Relative Path string: {relative_path_bytes2int}", name="Relative Path String", table_value=relative_path_string_decoded))


            if self.is_bit_set(link_flags, 4): # HasWorkingDir
                working_dir_bytes = self.file.read(2)
                working_dir_bytes2int = int.from_bytes(working_dir_bytes, byteorder="little")
                self.root.add_child(self.file.tell() - 2, Node(working_dir_bytes, f"Working Dir Size: {working_dir_bytes2int}", name="Working Dir", table_value=working_dir_bytes2int))

                # TODO: Investigate isUnicode's interference with the below
                has_working_dir_bytes = self.file.read(working_dir_bytes2int * 2) # *2 since it is unicode
                has_working_dir_bytes_decoded = has_working_dir_bytes.decode("utf-16-le", errors='ignore')
                self.root.add_child(self.file.tell() - working_dir_bytes2int, Node(has_working_dir_bytes, f"Working dir: {has_working_dir_bytes_decoded}", name="Working directory", table_value=has_working_dir_bytes_decoded))

            if self.is_bit_set(link_flags, 5): # HasArguments
                cmd_arguments_bytes = self.file.read(2)
                cmd_arguments_bytes2int = int.from_bytes(cmd_arguments_bytes, byteorder="little")
                self.root.add_child(self.file.tell() - 2, Node(name_string_bytes, f"Command Line Arguments Size: {cmd_arguments_bytes2int}", name="Command Line Arguments", table_value=cmd_arguments_bytes2int))

            if self.is_bit_set(link_flags, 6): #HasIconLocation
                icon_location_bytes = self.file.read(2)
                icon_location_bytes2int = int.from_bytes(icon_location_bytes, byteorder="little")
                self.root.add_child(self.file.tell() - 2, Node(icon_location_bytes, f"Icon Location Size: {icon_location_bytes2int}", name="Icon Location", table_value=icon_location_bytes2int))

            if self.is_bit_set(link_flags, 7): # IsUnicode # here or move it?
                # Do something for bit_position 7
                pass


            return self.root
        except InvalidLNKFileException as e:
            self.show_error_popup(str(e) + f"Location of cursor when error occured was at offset {self.file.tell()}")

    # TODO: consider adding in this for validation purposes: https://twitter.com/cyb3rops/status/1042311558305669120/photo/2

        
    @classmethod
    def recognizes(cls, file):
        # reads the header and sets seeker here
        file.seek(0)
        header = file.read(4)
        return header == b"\x4c\x00\x00\x00"
