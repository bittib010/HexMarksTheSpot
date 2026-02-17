# HexMarksTheSpot Contribution Guide

## Overview

This guide helps you contribute to HexMarksTheSpot by creating new file format parsers. **You can now create parsers without any programming knowledge** using JSON configuration files!

## Table of Contents

1. [Quick Start: JSON Parser (No Programming!)](#quick-start-json-parser-no-programming)
2. [JSON Parser Reference](#json-parser-reference)
3. [Python Parser Guide](#python-parser-guide)
4. [Testing Your Parser](#testing-your-parser)

---

## Quick Start: JSON Parser (No Programming!)

The easiest way to add support for a new file format is to create a JSON configuration file.

### Step 1: Create Your JSON File

Create a new file in `Artefacts/configs/` with a `.json` extension:

```json
{
    "name": "MyFormat",
    "description": "My custom file format",
    "magic_bytes": "4D594654",
    "magic_offset": 0,
    "endianness": "little",
    "references": [
        "https://link-to-format-documentation.com"
    ],
    "fields": [
        {
            "name": "signature",
            "size": 4,
            "type": "string",
            "description": "File signature - should be 'MYFT'"
        },
        {
            "name": "version",
            "size": 2,
            "type": "uint",
            "description": "File format version"
        }
    ]
}
```

### Step 2: Restart the Application

That's it! The parser will be automatically discovered and loaded.

---

## JSON Parser Reference

### Root Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Name of the file format |
| `description` | string | No | Description of the format |
| `magic_bytes` | string | Yes | Hex string of magic bytes (e.g., "504B0304") |
| `magic_offset` | int | No | Offset where magic bytes appear (default: 0) |
| `endianness` | string | No | "little" or "big" (default: "little") |
| `references` | array | No | URLs to format documentation |
| `version` | string | No | Parser version |
| `author` | string | No | Parser author |
| `fields` | array | Yes | Array of field definitions |

### Field Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Field name (used as identifier) |
| `size` | int/string | Yes* | Size in bytes, or reference like "$header_size" |
| `type` | string | No | Field type (default: "bytes") |
| `description` | string | No | Human-readable description |
| `endianness` | string | No | Override parent endianness |
| `color` | string | No | Hex color code (e.g., "#FF0000") |
| `forensic_value` | bool | No | Mark as forensically important (highlighted red) |
| `value_map` | object | No | Map integer values to descriptions |
| `bit_flags` | object | No | For bitfield type - map bit positions to names |
| `condition` | string | No | Conditional expression (e.g., "$flags.0") |
| `fields` | array | No | Nested fields (for section/struct types) |
| `count` | int/string | No | Number of items (for array type) |
| `item_definition` | object | No | Template for array items (for array/loop_until) |
| `switch_on` | string | No | Field reference to switch on (for switch type) |
| `cases` | object | No | Case definitions (for switch type) |
| `default` | array | No | Default case fields (for switch type) |
| `terminator` | string | No | Hex terminator bytes (for loop_until type) |
| `max_iterations` | int | No | Safety limit for loops (default: 1000) |

*Size is not required for `section`, `struct`, `array`, `switch`, `loop_until`, and `remaining` types.

### Supported Field Types

#### Basic Types

```json
{"name": "raw_data", "size": 16, "type": "bytes"}
{"name": "count", "size": 4, "type": "uint"}
{"name": "offset", "size": 4, "type": "int"}
{"name": "name", "size": 32, "type": "string"}
```

#### String Types

```json
{"name": "ascii_name", "size": 32, "type": "string"}
{"name": "unicode_name", "size": 64, "type": "utf16le"}
{"name": "utf16_be", "size": 64, "type": "utf16be"}
```

#### Timestamp Types

```json
{"name": "created", "size": 8, "type": "filetime", "forensic_value": true}
{"name": "modified", "size": 4, "type": "unix_time"}
{"name": "accessed", "size": 8, "type": "unix_time_64"}
```

#### Special Types

```json
{"name": "guid", "size": 16, "type": "guid"}
{"name": "padding", "size": 8, "type": "skip"}
{"name": "rest", "size": 0, "type": "remaining"}
```

#### Complex/Nested Types

| Type | Description |
|------|-------------|
| `section` | Group of fields that can be conditionally parsed |
| `struct` | Nested structure (always parsed, unlike conditional sections) |
| `array` | Repeated items with count from another field |
| `switch` | Different structures based on a field's value |
| `loop_until` | Parse items until terminator found |

#### Bitfield with Named Flags

```json
{
    "name": "attributes",
    "size": 4,
    "type": "bitfield",
    "description": "File attributes",
    "bit_flags": {
        "0": "ReadOnly",
        "1": "Hidden",
        "2": "System",
        "3": "VolumeLabel",
        "4": "Directory",
        "5": "Archive"
    }
}
```

#### Value Maps (Enums)

```json
{
    "name": "file_type",
    "size": 2,
    "type": "uint",
    "description": "Type of content",
    "value_map": {
        "0": "Empty",
        "1": "Text",
        "2": "Binary",
        "3": "Compressed"
    }
}
```

### Dynamic Sizes

Reference other fields for dynamic sizing:

```json
{"name": "data_size", "size": 4, "type": "uint"},
{"name": "data", "size": "$data_size", "type": "bytes"}
```

You can also use expressions:

```json
{"name": "char_count", "size": 2, "type": "uint"},
{"name": "string_data", "size": "$char_count * 2", "type": "utf16le"}
```

### Conditional Fields

Parse fields only when conditions are met:

```json
{"name": "flags", "size": 4, "type": "uint"},
{"name": "optional_data", "size": 16, "type": "bytes", "condition": "$flags & 0x01"}
```

### Nested Structures (Sections)

Group related fields into sections. Sections can be conditional:

```json
{
    "name": "OptionalHeader",
    "type": "section",
    "description": "Optional header data",
    "condition": "$has_optional_header",
    "fields": [
        {"name": "header_size", "size": 4, "type": "uint"},
        {"name": "header_data", "size": "$header_size", "type": "bytes"}
    ]
}
```

### Bitfield-Based Conditions

For formats like LNK where sections depend on specific bits:

```json
{
    "name": "link_flags",
    "size": 4,
    "type": "bitfield",
    "bit_flags": {
        "0": "HasLinkTargetIDList",
        "1": "HasLinkInfo",
        "2": "HasName"
    }
},
{
    "name": "LinkTargetIDList",
    "type": "section",
    "condition": "$link_flags.0",
    "description": "Only present if bit 0 (HasLinkTargetIDList) is set",
    "fields": [
        {"name": "id_list_size", "size": 2, "type": "uint"},
        {"name": "id_list_data", "size": "$id_list_size", "type": "bytes"}
    ]
}
```

The syntax `$field_name.N` checks if bit N is set in the bitfield.

### Arrays

Parse repeated structures:

```json
{
    "name": "entries",
    "type": "array",
    "count": "$entry_count",
    "item_definition": {
        "size": 16,
        "type": "bytes"
    }
}
```

### Switch/Case

Parse different structures based on a field's value:

```json
{
    "name": "record_type",
    "size": 2,
    "type": "uint"
},
{
    "name": "record_data",
    "type": "switch",
    "switch_on": "$record_type",
    "cases": {
        "1": [
            {"name": "name", "size": 32, "type": "string"}
        ],
        "2": [
            {"name": "data", "size": 64, "type": "bytes"}
        ]
    },
    "default": [
        {"name": "unknown", "size": 16, "type": "bytes"}
    ]
}
```

### Loop Until Terminator

Parse items until a terminator is found:

```json
{
    "name": "items",
    "type": "loop_until",
    "terminator": "0000",
    "max_iterations": 1000,
    "item_definition": {
        "name": "item_size",
        "size": 2,
        "type": "uint"
    }
}
```

---

## Python Parser Guide

For complex file formats that require custom logic, create a Python parser.

### File Location

Place your parser in `Artefacts/` with a filename ending in `FileParser.py`:
- `MyFormatFileParser.py` ✓
- `CustomFileParser.py` ✓

### Basic Template

```python
from common import Node, FileParser


class MyFormatFileParser(FileParser):
    """
    Parser for MyFormat files.
    
    References:
    - https://example.com/format-spec
    """

    def __init__(self, file):
        super().__init__(file)
        self.current_color = [0x33, 0x33, 0x33]

    @classmethod
    def recognizes(cls, file):
        """Check if this file is a MyFormat file."""
        file.seek(0)
        header = file.read(4)
        file.seek(0)  # Reset position
        return header == b"MYFT"

    def get_next_color(self, size=5):
        """Generate next color for highlighting."""
        self.current_color = [(c + size) % 256 for c in self.current_color]
        return f"#{self.current_color[0]:02x}{self.current_color[1]:02x}{self.current_color[2]:02x}"

    def parse(self):
        """Parse the file and return the root Node."""
        self.file.seek(0)
        root = Node(b'', "MyFormat File")

        # Example: Parse header
        header = self.file.read(4)
        root.add_child(0, Node(
            data=header,
            info="<h1>Header</h1><p>File signature 'MYFT'</p>",
            name="Header",
            table_value=header.decode('ascii', errors='ignore'),
            color=self.get_next_color()
        ))

        # Example: Parse version (2 bytes, little-endian)
        version_data = self.file.read(2)
        version = int.from_bytes(version_data, byteorder='little')
        root.add_child(4, Node(
            data=version_data,
            info=f"<h1>Version</h1><p>Format version: {version}</p>",
            name="Version",
            table_value=version,
            color=self.get_next_color()
        ))

        # Continue parsing...
        
        return root
```

### Node Constructor

```python
Node(
    data: bytes,           # Raw bytes
    info: str,             # HTML description
    name: str = None,      # Display name
    color: str = None,     # Hex color (e.g., "#FF0000")
    table_value: Any = None  # Parsed value for table
)
```

### Best Practices

1. **Always reset file position** in `recognizes()`:
   ```python
   file.seek(0)  # At the end
   ```

2. **Use HTML in descriptions** for rich formatting:
   ```python
   info="<h1>Title</h1><p>Description</p><ul><li>Item</li></ul>"
   ```

3. **Mark forensically important fields** with red color:
   ```python
   color="#FF6B6B"
   ```

4. **Handle unknown data** gracefully:
   ```python
   remaining = self.file.read()
   root.add_child(offset, Node(
       data=remaining,
       info="<h1>Unparsed Data</h1><p>Unknown or not yet implemented</p>",
       name="Unparsed",
       color="#FF0000"
   ))
   ```

5. **Parse timestamps** properly:
   ```python
   from datetime import datetime, timedelta
   
   def filetime_to_datetime(self, filetime_bytes):
       filetime = int.from_bytes(filetime_bytes, byteorder='little')
       if filetime == 0:
           return "Not set"
       windows_epoch = datetime(1601, 1, 1)
       delta = timedelta(microseconds=filetime // 10)
       return (windows_epoch + delta).strftime("%Y-%m-%d %H:%M:%S")
   ```

---

## Testing Your Parser

### Quick Test

```bash
# List available parsers (your new parser should appear)
python main.py --list

# Test parsing a file
python main.py --cli path/to/your/file
```

### Using the GUI

1. Start the GUI: `python gui.py`
2. Click "Open File"
3. Select your test file
4. Verify the parsing results

---

## Need Help?

- Check existing parsers in `Artefacts/` for examples
- Look at JSON configs in `Artefacts/configs/` for simpler formats
- Open an issue on GitHub for questions