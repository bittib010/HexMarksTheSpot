# SQLite File Parser Guide for Contributors

## Overview

This guide aims to help you understand how to add new parsers that can be easily integrated into the application.

## Table of Contents

1. [Adding Nodes](#adding-nodes)
    - [Static Values](#static-values)
    - [Dynamic Values](#dynamic-values)
2. [Handling Unknown Data](#handling-unknown-data)
3. [Color Control](#color-control)
4. [Recognition Function](#recognition-function)

---

### Adding Nodes

Nodes are fundamental units that represent parsed data. Here's how you can add them:

#### Static Values

If you have a set of static fields you need to parse, you can define them in a dictionary-like structure as seen in the `parse` method:

```python
fields = [
    (HEADER_LENGTH, "SQLite header string.", "Header string"),
    ...
]
```

Each tuple contains the length, description, and name of the field. You can then iterate through this list to add nodes dynamically:

```python
for index, (length, description, name) in enumerate(fields):
    data = self.file.read(length)
    node = Node(data, description, name)
    self.root.add_child(self.file.tell() - length, node)
```

#### Dynamic Values

For more dynamic data, you can add nodes manually:

```python
data = self.file.read(interval)
self.root.add_child(self.file.tell() - interval, Node(data, "Description", name="Name"))
```

### Handling Unknown Data

You can use the `parse_unknown_data` method to handle data that cannot be parsed:

```python
def parse_unknown_data(self, interval, details=None, name="Unparsed data"):
    unknown_data = self.file.read(interval)
    self.root.add_child(self.file.tell() - interval, Node(unknown_data, f"Unparsed!nn{details}", name=f"{name}", color="#FF0000"))
```

### Color Control

You can control the color of nodes by passing a `color` argument when creating a Node:

```python
node = Node(data, description, name, color="#FF0000")
```

Alternatively, you can dynamically generate colors using the `get_next_color` method:

```python
cur_col = self.get_next_color(size=0x05)
node = Node(data, description, name, color=cur_col)
```

### Recognition Function

The `recognizes` class method checks if the given file is an SQLite file. You should implement this method to recognize the type of file your parser is designed to handle:

```python
@classmethod
def recognizes(cls, file):
    file.seek(0)
    header = file.read(16)
    return header == b"SQLite format 3x00"
```

---

This guide focuses on the unique features of adding nodes, handling unknown data, controlling color, and using the `recognizes` function in the SQLite File Parser. These guidelines should help you in creating your own custom parsers.


### Beginner Template

```python
from common import Node, FileParser
import os


class LNKFileParser(FileParser):
    """
    DOC string for your parser
    """

    def __init__(self, file):
        super().__init__(file)
        self.current_color = [0x33, 0x33, 0x33]  # Initialize as a list of integers
        self.parsed_fields = {}  # Dictionary to store parsed fields from dictionary way of coding

    def get_next_color(self, size):
        # Increase the color value for each channel
        self.current_color = [(c + size) % 256 for c in self.current_color]
        return f"#{self.current_color[0]:02x}{self.current_color[1]:02x}{self.current_color[2]:02x}"

    def parse(self):
        self.file.seek(0)
        self.root = Node(b'', "<INSERT FILENAME>") 

        # read file outside loop to avoid rereading the file everytime.
        file_size = os.path.getsize(self.file.name)
        if self.page_counter == 1: # DB Header page
            # Define fields and their respective properties
            fields = [
                (4, "", "link_flags"),
                (4, "", "file_attributes"),
                (8, "", "creation_time"),
                (8, "", "access_time"),
                (8, "", "write_time"),
                (4, "", "file_size"),
                (4, "", "icon_index"),
                (4, "", "show_command"),
                (4, "", "hotkey"),
                (4, "", "reserved")
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

            # Number of cells in this page
            guid = self.file.read(16)
            guid_bytes = int.from_bytes(guid, byteorder="big")
            self.root.add_child(self.file.tell() - 16, Node(guid_bytes,f"no_of_cells: {guid_bytes}", name="GUID"))
            


            if name:
                # Store the data in the dictionary
                self.parsed_fields[name] = data
            """ 
            remaining_data = self.file.read(file_size-82)

            if remaining_data:
                self.root.add_child(self.file.tell() - len(remaining_data),
                            Node(remaining_data, f"Rest unknown currently.", color="#DDAACC")) """

            return self.root
        
    @classmethod
    def recognizes(cls, file):
        # reads the header and sets seeker here
        file.seek(0)
        header = file.read(4)
        return header == b"\x4c\x00\x00\x00"

```