"""
JSON-based Config Parser for HexMarksTheSpot

This module allows non-programmers to define file format parsers using JSON configuration files.
Forensicators can create new artifact parsers without writing Python code.

Supports:
- Sequential fields
- Nested structures (struct type)
- Conditional fields (condition property)
- Dynamic sizes (reference other fields with $fieldname)
- Arrays with dynamic counts
- Sections for organizing related fields
- Bitfield-based conditional branching

Example JSON config structure:
{
    "name": "MyFileFormat",
    "description": "Parser for MyFileFormat files",
    "magic_bytes": "4D5A",
    "magic_offset": 0,
    "endianness": "little",
    "fields": [
        {"name": "header", "size": 4, "type": "bytes", "description": "File header"},
        {"name": "flags", "size": 4, "type": "bitfield", "bit_flags": {"0": "HasExtra"}},
        {
            "name": "extra_section",
            "type": "section",
            "condition": "$flags.0",
            "fields": [
                {"name": "extra_size", "size": 4, "type": "uint"},
                {"name": "extra_data", "size": "$extra_size", "type": "bytes"}
            ]
        }
    ]
}
"""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union

from common import FileParser, Node, markdown_to_html

logger = logging.getLogger(__name__)


class ParsedBitfield:
    """
    Wrapper for bitfield values that allows individual bit access.
    
    Allows conditions like $flags.0 to check if bit 0 is set.
    """
    
    def __init__(self, value: int, bit_flags: Optional[Dict[str, str]] = None):
        self.value = value
        self.bit_flags = bit_flags or {}
    
    def get_bit(self, bit: int) -> bool:
        """Check if a specific bit is set."""
        return bool(self.value & (1 << bit))
    
    def __int__(self) -> int:
        return self.value
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"ParsedBitfield({self.value})"
    
    def __and__(self, other: int) -> int:
        return self.value & other
    
    def __bool__(self) -> bool:
        return self.value != 0


class FieldType(Enum):
    """Supported field types for JSON-defined parsers."""
    
    BYTES = "bytes"           # Raw bytes (hex display)
    UINT = "uint"             # Unsigned integer
    INT = "int"               # Signed integer
    STRING = "string"         # ASCII string
    UTF16 = "utf16"           # UTF-16 string (common in Windows artifacts)
    UTF16LE = "utf16le"       # UTF-16 Little Endian
    UTF16BE = "utf16be"       # UTF-16 Big Endian
    GUID = "guid"             # Windows GUID (16 bytes)
    FILETIME = "filetime"     # Windows FILETIME (8 bytes) 
    UNIX_TIME = "unix_time"   # Unix timestamp (4 bytes)
    UNIX_TIME_64 = "unix_time_64"  # Unix timestamp (8 bytes)
    BITFIELD = "bitfield"     # Bit flags
    ARRAY = "array"           # Array of items
    STRUCT = "struct"         # Nested structure
    SECTION = "section"       # Conditional section (group of fields)
    SKIP = "skip"             # Skip bytes (padding/reserved)
    REMAINING = "remaining"   # Read all remaining bytes
    VLQ = "vlq"               # Variable-length quantity (1-4 bytes, MSB continuation)
    SWITCH = "switch"         # Switch/case based on another field
    LOOP_UNTIL = "loop_until" # Loop until condition met


@dataclass
class FieldDefinition:
    """Definition of a single field in the file format."""
    
    name: str
    size: Union[int, str] = 0  # Can be int or reference to another field like "$header_size"
    field_type: FieldType = FieldType.BYTES
    description: str = ""
    endianness: str = "little"  # "little" or "big"
    color: Optional[str] = None
    
    # For bitfield type
    bit_flags: Optional[Dict[str, str]] = None
    
    # For array type
    count: Union[int, str] = 1  # Can reference another field
    item_definition: Optional[Dict[str, Any]] = None
    
    # For struct/section type - nested fields
    fields: Optional[List[Dict[str, Any]]] = None
    
    # For conditional parsing
    condition: Optional[str] = None  # e.g., "$flags.0" or "$flags & 0x01"
    
    # For switch type
    switch_on: Optional[str] = None  # Field to switch on
    cases: Optional[Dict[str, List[Dict[str, Any]]]] = None  # Case definitions
    default_case: Optional[List[Dict[str, Any]]] = None
    
    # For loop_until type
    terminator: Optional[str] = None  # Hex string terminator
    max_iterations: int = 1000  # Safety limit
    
    # For value mappings (enums)
    value_map: Optional[Dict[str, str]] = None
    
    # Forensic importance marker - can be bool (True = default) or string category:
    # "critical", "important", "timestamp", "identifier", "path", "network"
    forensic_value: Union[bool, str] = False


@dataclass
class ConfigParserDefinition:
    """Complete definition of a file format parser."""
    
    name: str
    description: str = ""
    magic_bytes: Optional[str] = None  # Hex string like "4C000000"
    magic_offset: int = 0
    endianness: str = "little"
    fields: List[Dict[str, Any]] = field(default_factory=list)  # Keep as raw dicts for recursive parsing
    references: List[str] = field(default_factory=list)  # Documentation URLs
    version: str = "1.0"
    author: str = ""
    
    @classmethod
    def from_json(cls, json_data: Dict) -> "ConfigParserDefinition":
        """Create a parser definition from JSON data."""
        return cls(
            name=json_data.get("name", "Unknown"),
            description=json_data.get("description", ""),
            magic_bytes=json_data.get("magic_bytes"),
            magic_offset=json_data.get("magic_offset", 0),
            endianness=json_data.get("endianness", "little"),
            fields=json_data.get("fields", []),  # Keep as raw dicts
            references=json_data.get("references", []),
            version=json_data.get("version", "1.0"),
            author=json_data.get("author", ""),
        )
    
    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> "ConfigParserDefinition":
        """Load a parser definition from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return cls.from_json(json.load(f))


class ConfigBasedParser(FileParser):
    """
    A file parser that uses JSON configuration files to define the parsing rules.
    
    This allows forensicators to create new parsers without writing Python code.
    Simply create a JSON file with the field definitions and place it in the
    Artefacts/configs/ directory.
    """
    
    # Class-level storage for registered configs
    _registered_configs: Dict[str, ConfigParserDefinition] = {}
    
    def __init__(self, file: BinaryIO, config: ConfigParserDefinition):
        super().__init__(file)
        self.config = config
        self.parsed_values: Dict[str, Any] = {}  # Store parsed values for references
        self.current_color = [0x33, 0x33, 0x33]
        self.root: Optional[Node] = None
    
    @classmethod
    def register_config(cls, config: ConfigParserDefinition) -> None:
        """Register a parser configuration."""
        cls._registered_configs[config.name] = config
    
    @classmethod
    def get_registered_parsers(cls) -> Dict[str, ConfigParserDefinition]:
        """Get all registered parser configurations."""
        return cls._registered_configs.copy()
    
    @classmethod
    def recognizes(cls, file: BinaryIO) -> bool:
        """Check if this parser recognizes the file based on magic bytes."""
        # This needs to be overridden per-config
        return False
    
    @classmethod
    def create_parser_class(cls, config: ConfigParserDefinition) -> type:
        """
        Dynamically create a parser class for a specific configuration.
        
        This allows each JSON config to have its own recognizes() method.
        """
        class DynamicConfigParser(ConfigBasedParser):
            _config = config
            
            def __init__(self, file: BinaryIO):
                super().__init__(file, self._config)
            
            @classmethod
            def recognizes(cls, file: BinaryIO) -> bool:
                if cls._config.magic_bytes is None:
                    return False
                
                file.seek(cls._config.magic_offset)
                magic_bytes = bytes.fromhex(cls._config.magic_bytes)
                header = file.read(len(magic_bytes))
                file.seek(0)
                return header == magic_bytes
        
        # Set a meaningful class name
        DynamicConfigParser.__name__ = f"{config.name}Parser"
        DynamicConfigParser.__qualname__ = f"{config.name}Parser"
        
        return DynamicConfigParser
    
    def get_next_color(self) -> str:
        """Generate the next default color via ColorGenerator."""
        from common import ColorGenerator
        return ColorGenerator.get_next_color()
    
    def resolve_reference(self, ref: str) -> Any:
        """
        Resolve a reference to a parsed value.
        
        Supports:
        - $field_name - direct field reference
        - $field_name.N - bit N of a bitfield
        - $field_name * 2 - expressions
        """
        if not isinstance(ref, str):
            return ref
        
        if not ref.startswith("$"):
            try:
                return int(ref)
            except:
                return ref
        
        # Handle bit access like $flags.0
        bit_match = re.match(r'\$(\w+)\.(\d+)', ref)
        if bit_match:
            field_name = bit_match.group(1)
            bit_num = int(bit_match.group(2))
            value = self.parsed_values.get(field_name)
            if isinstance(value, ParsedBitfield):
                return value.get_bit(bit_num)
            elif isinstance(value, int):
                return bool(value & (1 << bit_num))
            return False
        
        # Handle simple reference $field_name
        simple_match = re.match(r'\$(\w+)$', ref)
        if simple_match:
            field_name = simple_match.group(1)
            value = self.parsed_values.get(field_name, 0)
            if isinstance(value, ParsedBitfield):
                return value.value
            return value
        
        # Handle expressions like $size * 2
        expr = ref
        for key, value in self.parsed_values.items():
            if isinstance(value, ParsedBitfield):
                val = value.value
            else:
                val = value
            val_str = str(val)
            expr = re.sub(rf'\${key}\b', lambda m, v=val_str: v, expr)
        
        try:
            return eval(expr)
        except:
            return 0
    
    def resolve_size(self, size: Union[int, str]) -> int:
        """Resolve a size that may be a reference to another field."""
        if isinstance(size, int):
            return size
        
        result = self.resolve_reference(size)
        return int(result) if result else 0
    
    def evaluate_condition(self, condition: str) -> bool:
        """
        Evaluate a conditional expression.
        
        Supports:
        - $flags.0 - check if bit 0 of flags is set
        - $flags & 0x01 - bitwise AND
        - $value == 5 - equality
        - $size > 0 - comparison
        """
        if not condition:
            return True
        
        # Handle bit access conditions like $flags.0
        bit_match = re.match(r'^(\$\w+)\.(\d+)$', condition.strip())
        if bit_match:
            field_ref = bit_match.group(1)
            bit_num = int(bit_match.group(2))
            value = self.resolve_reference(field_ref)
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return bool(value & (1 << bit_num))
            if isinstance(value, ParsedBitfield):
                return value.get_bit(bit_num)
            return bool(value)
        
        # Replace all $references with their values
        expr = condition
        for key, value in self.parsed_values.items():
            if isinstance(value, ParsedBitfield):
                val = value.value
            elif isinstance(value, str):
                val = repr(value)
            else:
                val = value
            val_str = str(val)
            expr = re.sub(rf'\${key}\b', lambda m, v=val_str: v, expr)
        
        try:
            return bool(eval(expr))
        except Exception as e:
            print(f"Condition evaluation error: {condition} -> {expr}: {e}")
            return True
    
    def bytes_to_guid(self, guid_bytes: bytes) -> str:
        """Convert 16 bytes to a GUID string."""
        if len(guid_bytes) != 16:
            return "Invalid GUID"
        
        part1 = int.from_bytes(guid_bytes[0:4], byteorder='little')
        part2 = int.from_bytes(guid_bytes[4:6], byteorder='little')
        part3 = int.from_bytes(guid_bytes[6:8], byteorder='little')
        part4 = guid_bytes[8:10]
        part5 = guid_bytes[10:16]
        
        return f"{part1:08x}-{part2:04x}-{part3:04x}-{''.join([f'{x:02x}' for x in part4])}-{''.join([f'{x:02x}' for x in part5])}"
    
    def filetime_to_datetime(self, filetime_bytes: bytes) -> str:
        """Convert Windows FILETIME to datetime string."""
        try:
            filetime_int = int.from_bytes(filetime_bytes, byteorder='little')
            if filetime_int == 0:
                return "Not set (0)"
            
            # Check for valid range
            max_microseconds = (datetime.max - datetime(1601, 1, 1)).total_seconds() * 1_000_000
            if filetime_int // 10 > max_microseconds:
                return f"Out of range: {filetime_int}"
            
            windows_epoch = datetime(1601, 1, 1)
            delta = timedelta(microseconds=filetime_int // 10)
            result = windows_epoch + delta
            return result.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception as e:
            return f"Invalid FILETIME: {e}"
    
    def unix_time_to_datetime(self, timestamp_bytes: bytes) -> str:
        """Convert Unix timestamp to datetime string."""
        try:
            timestamp = int.from_bytes(timestamp_bytes, byteorder=self.config.endianness)
            if timestamp == 0:
                return "Not set (0)"
            return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception as e:
            return f"Invalid timestamp: {e}"
    
    def _validate_expected_value(self, field_name: str, parsed_value: Any, 
                                  expected: Any, offset: int, raw_data: bytes) -> None:
        """
        Validate a parsed value against expected_values constraints.
        
        Logs a warning when the value doesn't match expectations, including
        the field location, raw hex, and what was expected vs found.
        
        Args:
            field_name: Name of the field being validated
            parsed_value: The parsed/interpreted value
            expected: Either a list of valid values or a dict with min/max range
            offset: File offset where the field was read
            raw_data: Raw bytes of the field
        """
        # Normalize parsed_value for comparison
        compare_value = parsed_value
        if isinstance(parsed_value, ParsedBitfield):
            compare_value = parsed_value.value
        
        matched = False
        expected_desc = ""
        
        if isinstance(expected, list):
            # List of allowed values - check membership
            # Compare as same type: try int comparison for numeric values
            for ev in expected:
                if isinstance(ev, int) and isinstance(compare_value, int):
                    if compare_value == ev:
                        matched = True
                        break
                elif isinstance(ev, str) and isinstance(compare_value, str):
                    if compare_value == ev:
                        matched = True
                        break
                else:
                    # Cross-type: try string comparison
                    if str(compare_value) == str(ev):
                        matched = True
                        break
            expected_desc = f"one of {expected}"
            
        elif isinstance(expected, dict):
            # Range constraint with min/max
            min_val = expected.get("min")
            max_val = expected.get("max")
            if isinstance(compare_value, (int, float)):
                above_min = min_val is None or compare_value >= min_val
                below_max = max_val is None or compare_value <= max_val
                matched = above_min and below_max
            else:
                matched = False  # Can't range-check non-numeric
            
            parts = []
            if min_val is not None:
                parts.append(f">= {min_val}")
            if max_val is not None:
                parts.append(f"<= {max_val}")
            expected_desc = f"value {' and '.join(parts)}" if parts else "any value"
        else:
            return  # Unknown constraint format, skip
        
        if not matched:
            raw_hex = raw_data.hex() if raw_data else "N/A"
            logger.warning(
                f"UNEXPECTED VALUE at offset 0x{offset:X} ({offset}): "
                f"Field '{field_name}' has value {compare_value} (raw: 0x{raw_hex}), "
                f"expected {expected_desc}. "
                f"This may indicate file corruption, tampering, a format update, or "
                f"an unknown variant."
            )
    
    def format_bitfield(self, value: int, bit_flags: Optional[Dict[int, str]]) -> str:
        """Format a bitfield value with flag names."""
        if not bit_flags:
            return f"0x{value:08x} (binary: {bin(value)})"
        
        active_flags = []
        for bit, name in bit_flags.items():
            if value & (1 << int(bit)):
                active_flags.append(f"<li>{name}: True</li>")
            else:
                active_flags.append(f"<li>{name}: False</li>")
        
        return f"<ul>{''.join(active_flags)}</ul>"
    
    def format_output(self, data: bytes, output_format: str, endianness: str = "little") -> str:
        """
        Format raw bytes into a human-readable string based on output_format.
        
        This is the central dispatch for the output_format config field.
        It converts raw field bytes into the requested display format,
        independent of how the field type parsed the data.
        
        Args:
            data: The raw bytes of the field
            output_format: One of the supported format strings
            endianness: Byte order for multi-byte integer conversions
            
        Returns:
            Formatted string for display in Value column and Description pane
        """
        byteorder = "little" if endianness == "little" else "big"
        
        if output_format == "hex":
            return self._format_hex(data)
        elif output_format == "decimal":
            return self._format_decimal(data, byteorder)
        elif output_format == "ascii":
            return self._format_ascii(data)
        elif output_format == "base64":
            return self._format_base64(data)
        elif output_format == "binary":
            return self._format_binary(data)
        elif output_format == "datetime_filetime":
            return self.filetime_to_datetime(data)
        elif output_format == "datetime_unix":
            return self.unix_time_to_datetime(data)
        elif output_format == "datetime_unix_ms":
            return self._format_unix_ms(data, byteorder)
        elif output_format == "datetime_dos":
            return self._format_dos_datetime(data, byteorder)
        elif output_format == "ip4":
            return self._format_ipv4(data)
        elif output_format == "ip6":
            return self._format_ipv6(data)
        elif output_format == "size_bytes":
            return self._format_size_bytes(data, byteorder)
        elif output_format == "bool":
            return self._format_bool(data, byteorder)
        else:
            logger.warning(f"Unknown output_format '{output_format}', falling back to hex")
            return self._format_hex(data)
    
    def _format_hex(self, data: bytes) -> str:
        """Format bytes as hex with 0x prefix, grouped for readability."""
        if len(data) <= 8:
            return "0x" + data.hex().upper()
        # For larger data, space-separate each byte
        return ' '.join(f'{b:02X}' for b in data)
    
    def _format_decimal(self, data: bytes, byteorder: str) -> str:
        """Format bytes as an unsigned decimal integer."""
        value = int.from_bytes(data, byteorder=byteorder)
        return f"{value:,}"
    
    def _format_ascii(self, data: bytes) -> str:
        """Format bytes as ASCII text, replacing non-printable chars with dots."""
        chars = []
        for b in data:
            if 32 <= b < 127:
                chars.append(chr(b))
            else:
                chars.append('.')
        return ''.join(chars).rstrip('\x00').rstrip('.')
    
    def _format_base64(self, data: bytes) -> str:
        """Format bytes as a Base64 encoded string."""
        return base64.b64encode(data).decode('ascii')
    
    def _format_binary(self, data: bytes) -> str:
        """Format bytes as a binary bit string."""
        if len(data) <= 4:
            value = int.from_bytes(data, byteorder='big')
            bit_width = len(data) * 8
            return f"0b{value:0{bit_width}b}"
        # For larger data, group by byte
        return ' '.join(f'{b:08b}' for b in data)
    
    def _format_unix_ms(self, data: bytes, byteorder: str) -> str:
        """Format bytes as a Unix timestamp in milliseconds."""
        try:
            timestamp_ms = int.from_bytes(data, byteorder=byteorder)
            if timestamp_ms == 0:
                return "Not set (0)"
            timestamp_s = timestamp_ms / 1000.0
            return datetime.utcfromtimestamp(timestamp_s).strftime("%Y-%m-%d %H:%M:%S.%f UTC")[:-3]
        except Exception as e:
            return f"Invalid timestamp: {e}"
    
    def _format_dos_datetime(self, data: bytes, byteorder: str) -> str:
        """Format 4 bytes as a DOS date/time stamp (FAT format).
        
        DOS timestamps pack date and time into 4 bytes (2 for date + 2 for time):
        - Date word: bits 0-4 = day, bits 5-8 = month, bits 9-15 = year (offset from 1980)
        - Time word: bits 0-4 = seconds/2, bits 5-10 = minutes, bits 11-15 = hours
        
        In little-endian format: time_word comes first (bytes 0-1), date_word second (bytes 2-3).
        """
        try:
            if len(data) != 4:
                return f"Invalid DOS datetime ({len(data)} bytes, need 4)"
            # DOS timestamps store time word first, then date word (in little-endian files)
            time_word = int.from_bytes(data[0:2], byteorder=byteorder)
            date_word = int.from_bytes(data[2:4], byteorder=byteorder)
            
            if date_word == 0 and time_word == 0:
                return "Not set (0)"
            
            # Decode date: day (bits 0-4), month (bits 5-8), year offset (bits 9-15)
            day = date_word & 0x1F
            month = (date_word >> 5) & 0x0F
            year = ((date_word >> 9) & 0x7F) + 1980
            
            # Decode time: seconds/2 (bits 0-4), minutes (bits 5-10), hours (bits 11-15)
            seconds = (time_word & 0x1F) * 2
            minutes = (time_word >> 5) & 0x3F
            hours = (time_word >> 11) & 0x1F
            
            # Validate ranges
            if not (1 <= month <= 12 and 1 <= day <= 31 and hours <= 23 and minutes <= 59 and seconds <= 59):
                return f"Invalid DOS date/time (raw: 0x{data.hex().upper()})"
            
            return f"{year:04d}-{month:02d}-{day:02d} {hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception as e:
            return f"Invalid DOS datetime: {e}"

    def _format_ipv4(self, data: bytes) -> str:
        """Format 4 bytes as a dotted-decimal IPv4 address."""
        if len(data) != 4:
            return f"Invalid IPv4 ({len(data)} bytes, need 4)"
        return f"{data[0]}.{data[1]}.{data[2]}.{data[3]}"
    
    def _format_ipv6(self, data: bytes) -> str:
        """Format 16 bytes as a colon-separated IPv6 address."""
        if len(data) != 16:
            return f"Invalid IPv6 ({len(data)} bytes, need 16)"
        groups = []
        for i in range(0, 16, 2):
            groups.append(f'{data[i]:02x}{data[i+1]:02x}')
        return ':'.join(groups)
    
    def _format_size_bytes(self, data: bytes, byteorder: str) -> str:
        """Format bytes as a human-readable file size."""
        value = int.from_bytes(data, byteorder=byteorder)
        if value < 1024:
            return f"{value} B"
        elif value < 1024 * 1024:
            return f"{value / 1024:.1f} KB ({value:,} bytes)"
        elif value < 1024 * 1024 * 1024:
            return f"{value / (1024 * 1024):.2f} MB ({value:,} bytes)"
        else:
            return f"{value / (1024 * 1024 * 1024):.2f} GB ({value:,} bytes)"
    
    def _format_bool(self, data: bytes, byteorder: str) -> str:
        """Format bytes as a boolean value."""
        value = int.from_bytes(data, byteorder=byteorder)
        return "True" if value != 0 else "False"
    
    def parse_field(self, field_dict: Dict[str, Any], parent_node: Node) -> Optional[Node]:
        """Parse a single field according to its definition."""
        name = field_dict.get("name", "unknown")
        size = field_dict.get("size", 0)
        field_type_str = field_dict.get("type", "bytes")
        description = field_dict.get("description", "")
        endianness = field_dict.get("endianness", self.config.endianness)
        color = field_dict.get("color")
        condition = field_dict.get("condition")
        bit_flags = field_dict.get("bit_flags")
        value_map = field_dict.get("value_map")
        forensic_value = field_dict.get("forensic_value", False)
        output_format = field_dict.get("output_format")
        
        # Check enabled flag - skip disabled fields entirely
        enabled = field_dict.get("enabled", True)
        if not enabled:
            return None
        
        # Check condition first
        if condition and not self.evaluate_condition(condition):
            return None
        
        try:
            field_type = FieldType(field_type_str)
        except ValueError:
            field_type = FieldType.BYTES
        
        # Handle complex types that contain nested fields
        if field_type == FieldType.SECTION or field_type == FieldType.STRUCT:
            return self.parse_section(field_dict, parent_node)
        
        if field_type == FieldType.ARRAY:
            return self.parse_array(field_dict, parent_node)
        
        if field_type == FieldType.SWITCH:
            return self.parse_switch(field_dict, parent_node)
        
        if field_type == FieldType.LOOP_UNTIL:
            return self.parse_loop_until(field_dict, parent_node)
        
        # Handle VLQ (variable-length quantity) — reads 1-4 bytes dynamically
        if field_type == FieldType.VLQ:
            return self.parse_vlq_field(field_dict, parent_node)
        
        # Handle simple field types
        resolved_size = self.resolve_size(size)
        
        # Handle REMAINING type
        if field_type == FieldType.REMAINING:
            current_pos = self.file.tell()
            self.file.seek(0, 2)  # Seek to end
            resolved_size = self.file.tell() - current_pos
            self.file.seek(current_pos)
        
        if resolved_size <= 0 and field_type != FieldType.REMAINING:
            return None
        
        offset = self.file.tell()
        data = self.file.read(resolved_size)
        
        if len(data) < resolved_size:
            return None
        
        # Determine endianness
        byteorder = "little" if endianness == "little" else "big"
        
        # Parse based on type
        table_value: Any = None
        
        if field_type == FieldType.BYTES:
            table_value = data.hex()
            
        elif field_type == FieldType.UINT:
            table_value = int.from_bytes(data, byteorder=byteorder)
            if value_map and str(table_value) in value_map:
                description += f" = {value_map[str(table_value)]}"
            
        elif field_type == FieldType.INT:
            table_value = int.from_bytes(data, byteorder=byteorder, signed=True)
            
        elif field_type == FieldType.STRING:
            table_value = data.decode('ascii', errors='ignore').rstrip('\x00')
            
        elif field_type == FieldType.UTF16:
            table_value = data.decode('utf-16', errors='ignore').rstrip('\x00')
            
        elif field_type == FieldType.UTF16LE:
            table_value = data.decode('utf-16-le', errors='ignore').rstrip('\x00')
            
        elif field_type == FieldType.UTF16BE:
            table_value = data.decode('utf-16-be', errors='ignore').rstrip('\x00')
            
        elif field_type == FieldType.GUID:
            table_value = self.bytes_to_guid(data)
            
        elif field_type == FieldType.FILETIME:
            table_value = self.filetime_to_datetime(data)
            
        elif field_type == FieldType.UNIX_TIME:
            table_value = self.unix_time_to_datetime(data)
            
        elif field_type == FieldType.UNIX_TIME_64:
            table_value = self.unix_time_to_datetime(data)
            
        elif field_type == FieldType.BITFIELD:
            int_value = int.from_bytes(data, byteorder=byteorder)
            # Store as ParsedBitfield for bit access in conditions
            table_value = ParsedBitfield(int_value, bit_flags)
            description += self.format_bitfield(int_value, bit_flags)
            
        elif field_type == FieldType.SKIP:
            table_value = f"[{resolved_size} bytes skipped]"
            
        else:
            table_value = data.hex()
        
        # Store parsed value for references
        self.parsed_values[name] = table_value
        
        # Validate against expected_values if defined
        expected_values = field_dict.get("expected_values")
        if expected_values is not None:
            self._validate_expected_value(name, table_value, expected_values, offset, data)
        
        # Create node - determine color based on category
        from common import ColorGenerator
        
        if forensic_value:
            # Forensic takes highest precedence
            if isinstance(forensic_value, str):
                node_color = ColorGenerator.get_forensic_color(forensic_value)
            else:
                node_color = ColorGenerator.get_forensic_color()
        elif field_dict.get("informational"):
            # Informational fields get green/teal
            node_color = ColorGenerator.get_informational_color()
        elif color:
            node_color = color
        else:
            node_color = ColorGenerator.get_next_color()
        
        # Format value for display
        display_value = table_value
        if isinstance(table_value, ParsedBitfield):
            display_value = f"0x{table_value.value:08x}"
        elif value_map and str(table_value) in value_map:
            display_value = f"{table_value} ({value_map[str(table_value)]})"
        
        # Apply output_format override if specified in config
        if output_format:
            try:
                display_value = self.format_output(data, output_format, endianness)
            except Exception as e:
                logger.warning(f"output_format '{output_format}' failed for field '{name}': {e}")
        
        # Determine if the display value is just the raw hex (same as hex viewer)
        raw_hex = data.hex()
        is_unparsed = (str(display_value) == raw_hex)
        
        # Build HTML description (convert markdown in descriptions to HTML)
        html_desc = f"<h1>{name}</h1>"
        if description:
            html_desc += f"<p>{markdown_to_html(description)}</p>"
        if is_unparsed:
            html_desc += f"<p><b>Value:</b> <i>currently unparsed</i></p>"
        else:
            html_desc += f"<p><b>Value:</b> {display_value}</p>"
        if output_format:
            html_desc += f"<p><b>Format:</b> {output_format}</p>"
        html_desc += f"<p><b>Size:</b> {resolved_size} bytes</p>"
        html_desc += f"<p><b>Offset:</b> 0x{offset:X} ({offset})</p>"
        
        node = Node(
            data=data,
            info=html_desc,
            name=name,
            table_value=str(display_value),
            color=node_color
        )
        
        parent_node.add_child(offset, node)
        return node
    
    def parse_vlq_field(self, field_dict: Dict[str, Any], parent_node: Node) -> Optional[Node]:
        """Parse a Variable-Length Quantity (VLQ) field.
        
        VLQ encoding uses 7 bits per byte for data with the MSB (bit 7) as a
        continuation flag. If bit 7 is 1, more bytes follow. If bit 7 is 0,
        this is the last byte. Reads 1 to 4 bytes.
        
        Used in MIDI delta times, protobuf varints, Git packfiles, etc.
        
        Example: bytes [0x81, 0x00] → value 128
                 bytes [0x00]       → value 0
                 bytes [0xC0, 0x00] → value 8192
        """
        name = field_dict.get("name", "Unknown")
        description = field_dict.get("description", "")
        color = field_dict.get("color")
        forensic_value = field_dict.get("forensic_value")
        value_map = field_dict.get("value_map")
        output_format = field_dict.get("output_format")
        
        offset = self.file.tell()
        
        # Read bytes until MSB is 0 or we hit 4 bytes (max VLQ length)
        vlq_bytes = bytearray()
        value = 0
        for _ in range(4):
            byte_data = self.file.read(1)
            if len(byte_data) == 0:
                if len(vlq_bytes) == 0:
                    return None
                break
            b = byte_data[0]
            vlq_bytes.append(b)
            value = (value << 7) | (b & 0x7F)
            if (b & 0x80) == 0:
                break  # MSB clear = last byte
        
        data = bytes(vlq_bytes)
        table_value = value
        
        # Store parsed value for references (as integer for use in $field expressions)
        self.parsed_values[name] = table_value
        # Also store the byte count consumed so configs can use $name_bytes in size expressions
        self.parsed_values[f"{name}_bytes"] = len(data)
        
        # Validate against expected_values if defined
        expected_values = field_dict.get("expected_values")
        if expected_values is not None:
            self._validate_expected_value(name, table_value, expected_values, offset, data)
        
        # Determine color
        from common import ColorGenerator
        
        if forensic_value:
            if isinstance(forensic_value, str):
                node_color = ColorGenerator.get_forensic_color(forensic_value)
            else:
                node_color = ColorGenerator.get_forensic_color()
        elif field_dict.get("informational"):
            node_color = ColorGenerator.get_informational_color()
        elif color:
            node_color = color
        else:
            node_color = ColorGenerator.get_next_color()
        
        # Format display value
        display_value = table_value
        if value_map and str(table_value) in value_map:
            display_value = f"{table_value} ({value_map[str(table_value)]})"
            description += f" = {value_map[str(table_value)]}"
        
        # Apply output_format override if specified
        if output_format:
            try:
                display_value = self.format_output(data, output_format, field_dict.get("endianness", self.endianness))
            except Exception as e:
                logger.warning(f"output_format '{output_format}' failed for VLQ field '{name}': {e}")
        
        # Build HTML description
        hex_repr = ' '.join(f'{b:02X}' for b in data)
        html_desc = f"<h1>{name}</h1>"
        if description:
            html_desc += f"<p>{markdown_to_html(description)}</p>"
        html_desc += f"<p><b>Value:</b> {value}</p>"
        html_desc += f"<p><b>VLQ bytes:</b> {hex_repr} ({len(data)} byte{'s' if len(data) != 1 else ''})</p>"
        if output_format:
            html_desc += f"<p><b>Format:</b> {output_format}</p>"
        html_desc += f"<p><b>Offset:</b> 0x{offset:X} ({offset})</p>"
        
        node = Node(
            data=data,
            info=html_desc,
            name=name,
            table_value=str(display_value),
            color=node_color
        )
        
        parent_node.add_child(offset, node)
        return node
    
    def parse_section(self, field_dict: Dict[str, Any], parent_node: Node) -> Optional[Node]:
        """Parse a section or struct - a group of nested fields.
        
        Supports optional repeat properties for looping:
        - repeat: number, "$field_ref", expression, "eof", or "until" for condition-based looping
        - repeat_step: fixed byte size per iteration (e.g., page size) - ensures each
          iteration advances exactly this many bytes regardless of inner field parsing
        - repeat_until: condition expression evaluated after each iteration;
          when it evaluates to True the loop stops (use with repeat: "until")
        """
        name = field_dict.get("name", "section")
        description = field_dict.get("description", "")
        color = field_dict.get("color")
        nested_fields = field_dict.get("fields", [])
        repeat = field_dict.get("repeat")
        repeat_step = field_dict.get("repeat_step")
        repeat_until = field_dict.get("repeat_until")
        use_gradient = field_dict.get("color_gradient", False)
        
        if not nested_fields:
            return None
        
        # Resolve repeat count
        if repeat is None:
            # No repeat - parse once as before
            return self._parse_section_once(name, description, color, nested_fields, parent_node,
                                            use_gradient=use_gradient)
        
        # Has repeat - resolve the count
        if isinstance(repeat, str) and repeat.lower() == "eof":
            repeat_count = -1  # Sentinel for "until EOF"
        elif isinstance(repeat, str) and repeat.lower() == "until":
            repeat_count = -1  # Sentinel for "until condition met" (controlled by repeat_until)
        elif isinstance(repeat, str):
            repeat_count = self.resolve_size(repeat)
        else:
            repeat_count = int(repeat)
        
        if repeat_count == 0:
            return None
        
        # Resolve repeat_step if present
        resolved_step = None
        if repeat_step is not None:
            resolved_step = self.resolve_size(repeat_step) if isinstance(repeat_step, str) else int(repeat_step)
        
        # Create container node for all iterations
        offset = self.file.tell()
        if repeat_count == -1:
            count_label = "until condition" if repeat_until else "until EOF"
        else:
            count_label = str(repeat_count)
        container_node = Node(
            data=b'',
            info=f"<h1>{name}</h1><p>{markdown_to_html(description)}</p><p><b>Repeat:</b> {count_label} iterations</p>",
            name=name,
            color=color or self.get_next_color()
        )
        
        iteration = 0
        max_iterations = repeat_count if repeat_count > 0 else 100000  # Safety limit for EOF mode
        
        while iteration < max_iterations:
            iter_start = self.file.tell()
            
            # Check for EOF - applies to all modes to prevent reading past file end
            peek = self.file.read(1)
            if not peek:
                break  # Reached EOF
            self.file.seek(iter_start)
            
            # If repeat_step is set, check we have enough bytes for a full step
            if resolved_step:
                self.file.seek(0, 2)
                file_size = self.file.tell()
                self.file.seek(iter_start)
                if iter_start + resolved_step > file_size:
                    break
            
            # Create node for this iteration
            iter_name = f"{name}[{iteration}]"
            iter_node = self._parse_section_once(
                iter_name, f"{description} (iteration {iteration})", 
                color, nested_fields, container_node,
                use_gradient=use_gradient
            )
            
            if iter_node is None:
                break
            
            # Check repeat_until condition after each iteration
            if repeat_until and self.evaluate_condition(repeat_until):
                break
            
            # If repeat_step is set, advance to exact position for next iteration
            if resolved_step:
                next_pos = iter_start + resolved_step
                current_pos = self.file.tell()
                if next_pos > current_pos:
                    # Skip remaining bytes in this step
                    self.file.seek(next_pos)
                elif next_pos < current_pos:
                    # Inner fields read past the step boundary - something is wrong
                    # but continue from current position to avoid data loss
                    pass
            
            iteration += 1
        
        parent_node.add_child(offset, container_node)
        return container_node
    
    def _parse_section_once(self, name: str, description: str, color: Optional[str],
                            nested_fields: List[Dict[str, Any]], parent_node: Node,
                            use_gradient: bool = False) -> Optional[Node]:
        """Parse a single instance of a section/struct.
        
        When use_gradient is True, children inherit progressively brighter
        variants of the section's base color, visually grouping them.
        """
        offset = self.file.tell()
        base_color = color or self.get_next_color()
        section_node = Node(
            data=b'',
            info=f"<h1>{name}</h1><p>{markdown_to_html(description)}</p>",
            name=name,
            color=base_color
        )
        
        start_offset = offset
        
        # Pre-compute gradient colors if enabled
        gradient_colors = None
        if use_gradient:
            from common import ColorGenerator
            # Count only enabled, non-container fields for gradient steps
            active_count = sum(1 for f in nested_fields if f.get("enabled", True))
            gradient_colors = ColorGenerator.get_gradient_series(base_color, active_count)
        
        # Parse all fields in the section
        gradient_idx = 0
        for child_field_dict in nested_fields:
            if use_gradient and gradient_colors and child_field_dict.get("enabled", True):
                # Inject gradient color into child field (without modifying the original dict)
                child_copy = dict(child_field_dict)
                if "color" not in child_copy:
                    child_copy["color"] = gradient_colors[min(gradient_idx, len(gradient_colors) - 1)]
                gradient_idx += 1
                self.parse_field(child_copy, section_node)
            else:
                self.parse_field(child_field_dict, section_node)
        
        # Don't set section_node.data - children already hold the bytes.
        # Setting data on the container would cause double-counting in hex display
        # and shift all offsets by the container's size.
        
        parent_node.add_child(start_offset, section_node)
        return section_node
    
    def parse_array(self, field_dict: Dict[str, Any], parent_node: Node) -> Optional[Node]:
        """Parse an array of items."""
        name = field_dict.get("name", "array")
        description = field_dict.get("description", "")
        color = field_dict.get("color")
        count = field_dict.get("count", 1)
        item_definition = field_dict.get("item_definition")
        
        resolved_count = self.resolve_size(count) if isinstance(count, str) else count
        
        if resolved_count <= 0 or not item_definition:
            return None
        
        offset = self.file.tell()
        array_node = Node(
            data=b'',
            info=f"<h1>{name}</h1><p>Array of {resolved_count} items</p><p>{markdown_to_html(description)}</p>",
            name=name,
            color=color or self.get_next_color()
        )
        
        start_offset = offset
        
        for i in range(resolved_count):
            item_def = item_definition.copy()
            item_def['name'] = f"{name}[{i}]"
            self.parse_field(item_def, array_node)
        
        # Don't set array_node.data - children already hold the bytes
        
        parent_node.add_child(start_offset, array_node)
        return array_node
    
    def parse_switch(self, field_dict: Dict[str, Any], parent_node: Node) -> Optional[Node]:
        """Parse a switch/case structure based on another field's value."""
        name = field_dict.get("name", "switch")
        description = field_dict.get("description", "")
        color = field_dict.get("color")
        switch_on = field_dict.get("switch_on")
        cases = field_dict.get("cases", {})
        default_case = field_dict.get("default")
        
        if not switch_on or not cases:
            return None
        
        switch_value = self.resolve_reference(switch_on)
        switch_key = str(switch_value)
        
        # Find matching case or use default
        case_fields = cases.get(switch_key)
        if case_fields is None:
            case_fields = default_case
        
        if not case_fields:
            return None
        
        offset = self.file.tell()
        switch_node = Node(
            data=b'',
            info=f"<h1>{name}</h1><p>Switch on {switch_on} = {switch_value}</p><p>{markdown_to_html(description)}</p>",
            name=name,
            color=color or self.get_next_color()
        )
        
        start_offset = offset
        
        for child_field_dict in case_fields:
            self.parse_field(child_field_dict, switch_node)
        
        # Don't set switch_node.data - children already hold the bytes
        
        parent_node.add_child(start_offset, switch_node)
        return switch_node
    
    def parse_loop_until(self, field_dict: Dict[str, Any], parent_node: Node) -> Optional[Node]:
        """Parse items in a loop until a terminator is found."""
        name = field_dict.get("name", "loop")
        description = field_dict.get("description", "")
        color = field_dict.get("color")
        item_definition = field_dict.get("item_definition")
        terminator_hex = field_dict.get("terminator", "0000")
        max_iterations = field_dict.get("max_iterations", 1000)
        
        if not item_definition:
            return None
        
        terminator = bytes.fromhex(terminator_hex)
        
        offset = self.file.tell()
        loop_node = Node(
            data=b'',
            info=f"<h1>{name}</h1><p>Loop until terminator</p><p>{markdown_to_html(description)}</p>",
            name=name,
            color=color or self.get_next_color()
        )
        
        start_offset = offset
        iterations = 0
        
        while iterations < max_iterations:
            # Check for terminator
            peek_data = self.file.read(len(terminator))
            if peek_data == terminator or len(peek_data) < len(terminator):
                # Found terminator or EOF - add it as a node
                if peek_data == terminator:
                    term_node = Node(
                        data=peek_data,
                        info="<h1>Terminator</h1><p>End of loop</p>",
                        name="Terminator",
                        table_value=peek_data.hex()
                    )
                    loop_node.add_child(self.file.tell() - len(terminator), term_node)
                break
            
            # Rewind and parse item
            self.file.seek(self.file.tell() - len(terminator))
            
            item_def = item_definition.copy()
            item_def['name'] = f"{name}[{iterations}]"
            self.parse_field(item_def, loop_node)
            
            iterations += 1
        
        # Don't set loop_node.data - children already hold the bytes
        
        parent_node.add_child(start_offset, loop_node)
        return loop_node
    
    def parse(self) -> Node:
        """Parse the file according to the configuration."""
        self.file.seek(0)
        self.root = Node(b'', f"{self.config.name} File")
        self.parsed_values = {}
        
        for field_dict in self.config.fields:
            self.parse_field(field_dict, self.root)
        
        return self.root


def load_config_parsers(config_dir: Union[str, Path]) -> List[type]:
    """
    Load all JSON config files from a directory and create parser classes.
    
    Args:
        config_dir: Directory containing JSON config files
        
    Returns:
        List of dynamically created parser classes
    """
    config_path = Path(config_dir)
    parsers = []
    
    if not config_path.exists():
        return parsers
    
    for json_file in config_path.glob("*.json"):
        # Skip template and schema files
        if json_file.stem.startswith("_") or json_file.stem.endswith(".schema"):
            continue
            
        try:
            config = ConfigParserDefinition.from_file(json_file)
            parser_class = ConfigBasedParser.create_parser_class(config)
            parsers.append(parser_class)
            print(f"Loaded config parser: {config.name} from {json_file.name}")
        except Exception as e:
            print(f"Error loading config from {json_file}: {e}")
    
    return parsers


# Make sure the configs directory exists
def ensure_configs_directory():
    """Ensure the Artefacts/configs directory exists."""
    configs_dir = Path(__file__).parent / "Artefacts" / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    return configs_dir
