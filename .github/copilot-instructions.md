# Copilot Instructions for HexMarksTheSpot

## Project Overview

HexMarksTheSpot is a Python-based hex file analysis and annotation tool for digital forensics. It parses binary file formats and displays their structure with color-coded hex highlighting, descriptions, and forensic context.

The application has two main modes:
- **GUI** (`gui.py`) - Tkinter-based desktop application with hex viewer, parsed field list, and detail pane
- **CLI** (`main.py --cli <file>`) - Command-line output for scripted analysis

## Architecture

### Core Modules

| Module | Responsibility |
|--------|---------------|
| `common.py` | `Node` (parsed data segment), `FileParser` (abstract base), `ColorGenerator`, exceptions |
| `config_parser.py` | JSON-based parser engine - reads `Artefacts/configs/*.json` and parses files without Python code |
| `parser_loader.py` | `ParserRegistry` singleton, auto-discovery of Python and JSON parsers |
| `gui.py` | Tkinter GUI with hex view, ASCII view, field list, detail pane, search, bookmarks, CSV export |
| `main.py` | Entry point, CLI interface, `parse_file()` convenience function |

### Parser Types

1. **JSON Config Parsers** (preferred, no code required) - defined in `Artefacts/configs/*.json`, loaded by `config_parser.py`
2. **Python Parsers** (for complex logic) - `.py` files in `Artefacts/`, subclass `FileParser`

### Data Flow

```
File → ParserRegistry.find_parser_for_file() → Parser.recognizes() → Parser.parse() → Node tree → GUI/CLI display
```

The `Node` dataclass is the universal output:
```python
@dataclass
class Node:
    data: bytes          # Raw bytes of this segment
    info: str            # HTML description (supports basic markdown converted to HTML)
    name: str            # Short display name
    color: str           # Hex color for highlighting (auto-generated via ColorGenerator)
    table_value: Any     # Parsed/interpreted value for table column
    children: List[Tuple[int, Node]]  # (offset, child_node) pairs
```

## JSON Parser Configuration (Primary Development Path)

New artifact parsers should be JSON configs in `Artefacts/configs/`. The schema is defined in `Artefacts/configs/parser-config.schema.json`.

### Key Features

- **Magic bytes matching**: `magic_bytes` (hex string) at `magic_offset` for file identification
- **Field types**: `bytes`, `uint`, `int`, `string`, `utf16`/`utf16le`/`utf16be`, `guid`, `filetime`, `unix_time`, `unix_time_64`, `bitfield`, `skip`, `remaining`, `struct`, `section`
- **Dynamic sizes**: Reference other fields with `$field_name` (e.g., `"size": "$data_length"`)
- **Expressions**: `"size": "$header_size - 16"`, `"size": "$count * 2"`
- **Conditions**: `"condition": "$flags.0"` (bit check), `"condition": "$type == 5 or $type == 2"`
- **Bitfield access**: `$flags.0` checks bit 0 of a bitfield named `flags`
- **Value maps**: Map integer values to human-readable descriptions
- **Expected values**: Validate parsed values against allowed lists or ranges
- **Forensic highlighting**: `"forensic_value": true` or category strings (`"critical"`, `"important"`, `"timestamp"`, `"identifier"`, `"path"`, `"network"`)
- **Informational highlighting**: `"informational": true` for green/teal descriptive fields
- **Output format override**: `"output_format"` controls how a parsed value is *displayed* without changing how it is *parsed* (see `type` vs `output_format` below)
- **Repeating structures**: `"repeat": N`, `"repeat": "$field"`, `"repeat": "eof"`, `"repeat": "until"` with `"repeat_until": "$condition"`
- **Repeat step**: `"repeat_step": 1024` for fixed-size record iteration (e.g., MFT records)
- **Nested structs**: `"type": "struct"` or `"type": "section"` with `"fields": [...]`
- **Disabled fields**: `"enabled": false` to skip structures (useful for separate file types like WAL headers in SQLite)

### Field Reference Resolution

All `$name` references resolve against `self.parsed_values` - a flat dict populated as fields are parsed. Field names must be unique across the entire parser (or at least non-conflicting within scope). Use prefixes for attributes with similar fields (e.g., `SI_CreationTime`, `FN_CreationTime`).

### `type` vs `output_format`

These two field properties serve different purposes:

- **`type`** controls **parsing** — how raw bytes are read from the file and converted into a native Python value. For example, `"type": "uint"` reads N bytes as an unsigned integer, `"type": "filetime"` reads 8 bytes as a Windows FILETIME and converts to a datetime.
- **`output_format`** controls **display** — how the already-parsed value appears in the GUI's Value column. It is an optional post-parse presentation override that does not affect parsing logic.

A field's `type` determines what goes into `parsed_values` and what the parser uses for conditions/references. The `output_format` only changes what the user sees in the table.

**Available `output_format` values:**

| Format | Display example | Use case |
|--------|----------------|----------|
| `hex` | `0x0000004C` | Signatures, offsets, serial numbers, flags |
| `decimal` | `16,885,952` | Counts, lengths (with thousand separators) |
| `ascii` | `MZ` | Magic bytes shown as text |
| `base64` | `SGVsbG8gV29ybGQh` | Binary blobs for safe copy/paste |
| `binary` | `0b10101011` | Bit patterns, masks |
| `datetime_filetime` | `2023-03-15 14:30:00 UTC` | Raw bytes interpreted as Windows FILETIME |
| `datetime_unix` | `2019-01-13 08:15:32 UTC` | Raw bytes interpreted as Unix timestamp |
| `datetime_unix_ms` | `2023-03-15 14:30:00.123 UTC` | Unix timestamp in milliseconds |
| `ip4` | `192.168.1.1` | 4-byte IPv4 address |
| `ip6` | `2001:0db8:...` | 16-byte IPv6 address |
| `size_bytes` | `4.0 KB` | File sizes in human-readable form |
| `bool` | `True` / `False` | Non-zero = True, zero = False |

**When to use `output_format`:**
- A `uint` field holding a file size → add `"output_format": "size_bytes"` for human-readable display
- A `uint` field holding a signature → add `"output_format": "hex"` so it shows `0xA0000003` instead of `2684354563`
- A `bytes` field containing an IP address → add `"output_format": "ip4"` for dotted-decimal display

**When NOT to use it:** If the `type` already produces the desired display (e.g., `filetime` already shows a datetime, `guid` already shows a GUID string), `output_format` is unnecessary.

### Color System

Colors are auto-generated by `ColorGenerator` in three categories:
1. **Forensic** (red/warm) - `forensic_value: true` or category string
2. **Informational** (green/teal) - `informational: true`
3. **Default** (blue/purple/neutral pastels) - everything else

Adjacent colors are guaranteed distinct. Forensic colors always stand out.

### Descriptions

Field descriptions support lightweight markdown converted to HTML via `markdown_to_html()`:
- `**bold**`, `*italic*`, `` `code` ``
- `\n\n` for paragraph breaks
- `- item` for unordered lists, `1. item` for ordered lists

## Converting 010 Editor Templates (.bt) to JSON Config

The `Artefacts/` directory contains `.bt` files from the [SweetScape 010 Editor Template Repository](https://www.sweetscape.com/010editor/repository/templates/). These serve as reference specifications to convert into JSON configs.

### Conversion Checklist

1. **Read the .bt file** to understand the complete structure
2. **Identify magic bytes** from the `ID Bytes` comment or initial struct reads
3. **Map data types**: `char[N]` → `string`, `short`/`ushort` → `uint` (2 bytes), `int`/`uint` → `uint`/`int` (4 bytes), `int64`/`uint64` → `uint` (8 bytes), `FILETIME` → `filetime`, `wchar_t[N]` → `utf16le`
4. **Handle enums**: Convert to `value_map` for simple enums, `bitfield` with `bit_flags` for flag enums
5. **Handle conditionals**: `if (condition)` → `"condition": "$field_name == value"`
6. **Handle loops**: `while`/`for` → `"repeat"` on struct/section
7. **Handle variable-length fields**: Use `$field_ref` for dynamic sizes
8. **Add forensic context**: Documentation, `forensic_value` markers, `forensic_notes` at top level
9. **Validate field byte totals**: Ensure all bytes in each struct are accounted for
10. **Add references**: Link to official format documentation

### Common Patterns

```json
// Repeating struct until end condition
{
    "name": "Records",
    "type": "struct",
    "repeat": "until",
    "repeat_until": "$MarkerField == -1",
    "fields": [...]
}

// Conditional section based on flag
{
    "name": "OptionalSection",
    "type": "section",
    "condition": "$Flags.0",
    "fields": [...]
}

// Dynamic-sized field
{
    "name": "Data",
    "size": "$DataLength",
    "type": "bytes"
}

// Type-dispatched attributes (read type first, then conditional sections)
{
    "name": "AttrType", "size": 4, "type": "int"
},
{
    "name": "TypeASection", "type": "section", "condition": "$AttrType == 16",
    "fields": [...]
},
{
    "name": "TypeBSection", "type": "section", "condition": "$AttrType == 48",
    "fields": [...]
}
```

## Existing Reference Parsers

High-quality JSON parsers to use as examples:

- **`sqlite.json`** - Big-endian format, extensive `expected_values` validation, `enabled: false` for separate file structures (WAL, journal)
- **`lnk_shell_link.json`** - Complex conditional parsing based on bitfield flags, `forensic_notes` at top level, `repeat: "until"` with `repeat_until`, deeply nested sections
- **`mft.json`** - Type-dispatched attribute loop using `repeat: "until"`, prefixed field names to avoid collisions (`SI_`, `FN_`), comprehensive forensic timestomping detection documentation

## Quality Standards for New Parsers

1. **Include `$schema`**: `"$schema": "./parser-config.schema.json"`
2. **Document everything**: Every field should have a `description` with forensic context where relevant
3. **Add forensic notes**: Top-level `forensic_notes` string explaining the artifact's forensic significance
4. **Mark forensic fields**: Use `forensic_value` with appropriate categories
5. **Add references**: Official specification URLs in the `references` array
6. **Validate values**: Use `expected_values` for fields with known valid ranges
7. **Use value maps**: For enum-like fields, add `value_map` for human-readable display
8. **Test with real files**: Verify the parser works with actual sample files in `TestFiles/`
9. **Account for all bytes**: Ensure no gaps between fields; use `skip` for padding/reserved bytes
10. **Handle alignment**: Many formats use 4-byte or 8-byte alignment; add padding fields as needed

## Development Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -e ".[dev]"      # Install with dev dependencies
python gui.py                # Run the application
python main.py --list        # List available parsers
```

### Dependencies
- Runtime: `tkhtmlview>=0.2.0` (HTML rendering in Tkinter)
- Dev: `pytest`, `pytest-cov`, `black`, `isort`, `mypy`, `pyinstaller`

## File Structure

```
HexMarksTheSpot/
├── gui.py                  # Tkinter GUI application
├── main.py                 # CLI entry point
├── common.py               # Node, FileParser, ColorGenerator, exceptions
├── config_parser.py        # JSON config → parser engine
├── parser_loader.py        # Auto-discovery, ParserRegistry singleton
├── pyproject.toml           # Package config (Python 3.9+)
├── Artefacts/
│   ├── *.bt                # 010 Editor templates (conversion source)
│   ├── *.py                # Python-based parsers (legacy)
│   └── configs/
│       ├── parser-config.schema.json  # JSON schema for parser configs
│       ├── _template.json             # Starter template for new parsers
│       └── *.json                     # Active parser configurations
├── TestFiles/              # Sample files for testing parsers
└── images/                 # GUI assets
```

## Important Implementation Notes

- `parsed_values` is a **flat dict** - field names from nested structs share the same namespace. Use prefixed names to avoid collisions in complex parsers.
- `resolve_reference()` handles `$field`, `$field.N` (bit access), and expressions like `$field * 2 - 8`
- `evaluate_condition()` replaces `$references` then calls Python `eval()` - conditions are Python expressions
- Sections/structs with `repeat` create container nodes with indexed children (`Name[0]`, `Name[1]`, ...)
- Container nodes (`struct`, `section`) have `data=b''` - only leaf fields hold actual bytes to avoid double-counting in hex display
- The `remaining` type reads from current position to EOF - use only at the end of a parser
- `enabled: false` completely skips a field/struct - useful for documenting structures in alternate files (WAL, journal) without parsing them
