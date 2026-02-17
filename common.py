"""
Core classes and types for HexMarksTheSpot

This module provides the fundamental building blocks for file parsing:
- Node: Represents a parsed data segment with metadata
- FileParser: Abstract base class for all file format parsers
- Custom exceptions for error handling
"""

from __future__ import annotations

import random
import colorsys
from abc import ABC, abstractmethod
import re
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Type, Union


def markdown_to_html(text: str) -> str:
    """
    Convert lightweight markdown syntax to HTML for display in tkhtmlview.
    
    Supports:
    - **bold** → <b>bold</b>
    - *italic* → <i>italic</i>
    - `code` → <code>code</code>
    - Newlines (\n\n) → <br/>
    - Unordered lists (- item) → <ul><li>item</li></ul>
    - Ordered lists (1. item) → <ol><li>item</li></ol>
    """
    if not text:
        return text
    
    # Process block-level elements first (lists)
    lines = text.split('\n')
    result_lines = []
    in_ul = False
    in_ol = False
    
    for line in lines:
        stripped = line.strip()
        
        # Unordered list item: - item or * item (at start)
        ul_match = re.match(r'^[-*]\s+(.+)$', stripped)
        # Ordered list item: 1. item, 2. item, etc.
        ol_match = re.match(r'^\d+\.\s+(.+)$', stripped)
        
        if ul_match:
            if not in_ul:
                if in_ol:
                    result_lines.append('</ol>')
                    in_ol = False
                result_lines.append('<ul>')
                in_ul = True
            result_lines.append(f'<li>{ul_match.group(1)}</li>')
        elif ol_match:
            if not in_ol:
                if in_ul:
                    result_lines.append('</ul>')
                    in_ul = False
                result_lines.append('<ol>')
                in_ol = True
            result_lines.append(f'<li>{ol_match.group(1)}</li>')
        else:
            if in_ul:
                result_lines.append('</ul>')
                in_ul = False
            if in_ol:
                result_lines.append('</ol>')
                in_ol = False
            result_lines.append(line)
    
    if in_ul:
        result_lines.append('</ul>')
    if in_ol:
        result_lines.append('</ol>')
    
    text = '\n'.join(result_lines)
    
    # Inline formatting (order matters: bold before italic to avoid conflicts)
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic: *text* (but not inside bold tags)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # Inline code: `text`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    
    # Double newlines → paragraph break
    text = text.replace('\n\n', '<br/><br/>')
    # Single newlines → line break (within paragraphs)
    text = text.replace('\n', '<br/>')
    
    # Clean up stray <br/> inside list structures
    for tag in ['<ul>', '</ul>', '<ol>', '</ol>', '<li>', '</li>']:
        text = text.replace(f'<br/>{tag}', tag)
        text = text.replace(f'{tag}<br/>', tag)
    
    return text


class ColorGenerator:
    """
    Generates category-based colors for hex highlighting with guaranteed
    adjacent uniqueness and automatic contrast text colors.
    
    Color categories (precedence order - highest first):
    1. Forensic: Red/warm tones - for forensically important fields
    2. Informational: Green/teal light tones - for descriptive/informational fields
    3. Default: Neutral pastel tones (blue, purple, gray) - for everything else
    
    A field can be both informational and forensic, but forensic takes precedence.
    """
    
    _last_hue = 0.0
    _last_color = ""
    
    # Hue ranges for each category (0-1 scale, maps to 0-360 degrees)
    # Red/warm range for forensic: ~330-30 degrees (wraps around)
    _FORENSIC_HUE_MIN = 0.92   # ~331 degrees
    _FORENSIC_HUE_MAX = 0.08   # ~29 degrees (wraps)
    _FORENSIC_SAT = (0.55, 0.75)
    _FORENSIC_LIT = (0.50, 0.65)
    
    # Green/teal range for informational: ~90-170 degrees
    _INFO_HUE_MIN = 0.25       # ~90 degrees
    _INFO_HUE_MAX = 0.47       # ~170 degrees
    _INFO_SAT = (0.30, 0.50)
    _INFO_LIT = (0.75, 0.88)
    
    # Blue/purple/neutral range for default: ~190-310 degrees
    _DEFAULT_HUE_MIN = 0.53    # ~190 degrees
    _DEFAULT_HUE_MAX = 0.86    # ~310 degrees
    _DEFAULT_SAT = (0.30, 0.50)
    _DEFAULT_LIT = (0.75, 0.88)
    
    # Forensic sub-category fixed colors (for explicit category strings)
    FORENSIC_CATEGORY_COLORS = {
        "critical":    {"bg": "#C0392B", "fg": "#FFFFFF"},
        "important":   {"bg": "#D35400", "fg": "#FFFFFF"},
        "timestamp":   {"bg": "#8E44AD", "fg": "#FFFFFF"},
        "identifier":  {"bg": "#C2185B", "fg": "#FFFFFF"},
        "path":        {"bg": "#00838F", "fg": "#FFFFFF"},
        "network":     {"bg": "#BF360C", "fg": "#FFFFFF"},
    }
    
    @classmethod
    def reset(cls):
        """Reset the color generator for a new file."""
        cls._last_hue = random.random()
        cls._last_color = ""
    
    @classmethod
    def _random_hue_in_range(cls, hue_min: float, hue_max: float) -> float:
        """Generate a random hue within a range, handling wrap-around."""
        if hue_min <= hue_max:
            return hue_min + random.random() * (hue_max - hue_min)
        else:
            # Wraps around 1.0 (e.g., red: 0.92 -> 0.08)
            span = (1.0 - hue_min) + hue_max
            h = hue_min + random.random() * span
            return h % 1.0
    
    @classmethod
    def _ensure_distinct(cls, color: str, min_distance: float = 0.06) -> str:
        """
        Ensure a color is sufficiently different from the last generated color.
        If too similar, shift the lightness instead of hue to stay in the same
        category range.
        """
        if not cls._last_color:
            return color
        
        def hex_to_hls(hex_color: str):
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16) / 255
            g = int(hex_color[2:4], 16) / 255
            b = int(hex_color[4:6], 16) / 255
            return colorsys.rgb_to_hls(r, g, b)
        
        h1, l1, s1 = hex_to_hls(cls._last_color)
        h2, l2, s2 = hex_to_hls(color)
        
        hue_diff = min(abs(h1 - h2), 1 - abs(h1 - h2))
        light_diff = abs(l1 - l2)
        
        # If hue AND lightness are both too similar, shift lightness
        # (not hue — shifting hue could leave the category range)
        if hue_diff < min_distance and light_diff < 0.08:
            # Flip lightness direction to create visible contrast
            if l2 > 0.5:
                l2 = max(0.55, l2 - 0.12)
            else:
                l2 = min(0.90, l2 + 0.12)
            r, g, b = colorsys.hls_to_rgb(h2, l2, s2)
            color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        
        return color
    
    @classmethod
    def get_forensic_color(cls, category: str = "default") -> str:
        """
        Get a forensic importance color.
        
        If category is a specific sub-category (critical, important, timestamp, etc.),
        returns a fixed distinctive color. Otherwise generates a random red/warm tone.
        Forensic colors are NOT subject to adjacent-uniqueness — they must always
        stand out in their warm/red tones regardless of surrounding colors.
        """
        if category in cls.FORENSIC_CATEGORY_COLORS:
            color = cls.FORENSIC_CATEGORY_COLORS[category]["bg"]
            cls._last_color = color
            return color
        
        # Generate random red/warm forensic color (no _ensure_distinct — must stay red)
        h = cls._random_hue_in_range(cls._FORENSIC_HUE_MIN, cls._FORENSIC_HUE_MAX)
        s = cls._FORENSIC_SAT[0] + random.random() * (cls._FORENSIC_SAT[1] - cls._FORENSIC_SAT[0])
        l = cls._FORENSIC_LIT[0] + random.random() * (cls._FORENSIC_LIT[1] - cls._FORENSIC_LIT[0])
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        cls._last_color = color
        return color
    
    @classmethod
    def get_informational_color(cls) -> str:
        """
        Get an informational color (green/teal light tones).
        Used for descriptive fields that have documentation value but aren't forensic.
        """
        h = cls._random_hue_in_range(cls._INFO_HUE_MIN, cls._INFO_HUE_MAX)
        s = cls._INFO_SAT[0] + random.random() * (cls._INFO_SAT[1] - cls._INFO_SAT[0])
        l = cls._INFO_LIT[0] + random.random() * (cls._INFO_LIT[1] - cls._INFO_LIT[0])
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        color = cls._ensure_distinct(color)
        cls._last_color = color
        return color
    
    @classmethod
    def get_next_color(cls) -> str:
        """
        Generate the next default color (blue/purple/neutral pastel).
        Uses golden ratio for hue spacing within the default range.
        """
        h = cls._random_hue_in_range(cls._DEFAULT_HUE_MIN, cls._DEFAULT_HUE_MAX)
        s = cls._DEFAULT_SAT[0] + random.random() * (cls._DEFAULT_SAT[1] - cls._DEFAULT_SAT[0])
        l = cls._DEFAULT_LIT[0] + random.random() * (cls._DEFAULT_LIT[1] - cls._DEFAULT_LIT[0])
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        color = cls._ensure_distinct(color)
        cls._last_color = color
        return color
    
    @classmethod
    def get_contrast_text_color(cls, bg_color: str) -> str:
        """
        Calculate the optimal contrasting text color for a given background.
        Uses WCAG relative luminance formula for accessibility.
        
        Returns black or white text depending on background brightness,
        or a strongly contrasted hue-shifted color for medium backgrounds.
        """
        bg = bg_color.lstrip('#')
        r = int(bg[0:2], 16) / 255
        g = int(bg[2:4], 16) / 255
        b = int(bg[4:6], 16) / 255
        
        # WCAG relative luminance
        def linearize(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        
        luminance = 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
        
        # High contrast: dark text on light bg, light text on dark bg
        if luminance > 0.4:
            return "#1a1a2e"  # Very dark blue-black
        else:
            return "#f0f0f0"  # Near-white
    
    @classmethod
    def is_color_too_similar(cls, color1: str, color2: str, threshold: float = 0.15) -> bool:
        """Check if two colors are too similar based on hue distance."""
        def hex_to_hue(hex_color: str) -> float:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16) / 255
            g = int(hex_color[2:4], 16) / 255
            b = int(hex_color[4:6], 16) / 255
            h, _, _ = colorsys.rgb_to_hls(r, g, b)
            return h
        
        h1 = hex_to_hue(color1)
        h2 = hex_to_hue(color2)
        hue_diff = min(abs(h1 - h2), 1 - abs(h1 - h2))
        return hue_diff < threshold
    
    @classmethod
    def get_gradient_series(cls, base_color: str, count: int) -> List[str]:
        """
        Generate a series of progressively brighter colors from a base color.
        
        Used when child fields should visually indicate they belong to the same
        parent structure. Each successive color keeps the same hue but gets
        lighter, creating a gradient effect.
        
        Args:
            base_color: The parent's hex color (e.g., '#c4c4e1')
            count: How many gradient steps to generate
            
        Returns:
            List of hex color strings from base towards brighter
        """
        if count <= 0:
            return []
        if count == 1:
            return [base_color]
        
        bg = base_color.lstrip('#')
        r = int(bg[0:2], 16) / 255
        g = int(bg[2:4], 16) / 255
        b = int(bg[4:6], 16) / 255
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        
        # Calculate lightness range — go from base towards brighter
        # Leave headroom so we don't hit pure white
        max_lightness = min(l + 0.25, 0.93)
        if max_lightness <= l:
            # Already very light — go slightly darker instead
            max_lightness = l
            l = max(l - 0.20, 0.40)
        
        colors = []
        for i in range(count):
            # Linear interpolation from base lightness to max
            t = i / max(count - 1, 1)
            li = l + t * (max_lightness - l)
            ri, gi, bi = colorsys.hls_to_rgb(h, li, s)
            colors.append(f"#{int(ri*255):02x}{int(gi*255):02x}{int(bi*255):02x}")
        
        return colors


class UnknownFileTypeException(Exception):
    """Raised when a file type cannot be recognized by any parser."""
    pass


class InvalidFileException(Exception):
    """Raised when a file fails validation for a specific format."""
    pass


class ParsingException(Exception):
    """Raised when an error occurs during file parsing."""
    pass


@dataclass
class Node:
    """
    Represents a parsed segment of a file.
    
    Each Node contains:
    - The raw bytes of the segment
    - Human-readable information about what the segment represents
    - Metadata for display (color, name, parsed value)
    - Optional child nodes for hierarchical structures
    
    Attributes:
        data: The raw bytes of this segment
        info: HTML-formatted description of the segment
        name: Short name for display in the UI
        color: Hex color code for highlighting (auto-generated if not provided)
        table_value: Parsed/interpreted value for table display
        children: List of (offset, Node) tuples for child segments
    """
    
    data: bytes
    info: str
    name: Optional[str] = None
    color: Optional[str] = None
    table_value: Optional[Any] = None
    children: List[Tuple[int, "Node"]] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize default color if not provided using smart color generation."""
        if self.color is None:
            self.color = ColorGenerator.get_next_color()
    
    def add_child(self, offset: int, node: "Node") -> "Node":
        """
        Add a child node at the specified offset.
        
        Args:
            offset: File offset where this child's data begins
            node: The child Node to add
            
        Returns:
            The added child node (for chaining)
        """
        self.children.append((offset, node))
        return node
    
    def add_more_description_content(self, more_info: str) -> None:
        """
        Append additional content to the info field.
        
        Args:
            more_info: Additional HTML/text content to append
        """
        self.info += more_info
    
    def search_child(self, key: int) -> "Node":
        """
        Search for a child node by offset.
        
        Args:
            key: The offset to search for
            
        Returns:
            The child node at that offset
            
        Raises:
            ValueError: If no child with the given offset exists
        """
        for child_offset, child_node in self.children:
            if child_offset == key:
                return child_node
        raise ValueError(f"No child with offset {key} found.")
    
    def get_all_children_flat(self) -> List[Tuple[int, "Node"]]:
        """
        Get all children in a flat list (including nested children).
        
        Returns:
            List of (offset, Node) tuples for all descendants
        """
        result = []
        for offset, child in self.children:
            result.append((offset, child))
            result.extend(child.get_all_children_flat())
        return result
    
    @property
    def size(self) -> int:
        """Get the size of this node's data in bytes."""
        return len(self.data)
    
    def __repr__(self) -> str:
        return f"Node(name={self.name!r}, size={self.size}, children={len(self.children)})"


class FileParser(ABC):
    """
    Abstract base class for all file format parsers.
    
    To create a new parser:
    1. Subclass FileParser
    2. Implement the recognizes() class method to identify file types
    3. Implement the parse() method to create the Node tree
    
    Example:
        class MyParser(FileParser):
            @classmethod
            def recognizes(cls, file):
                file.seek(0)
                return file.read(4) == b'MYFT'
            
            def parse(self):
                root = Node(b'', "My File Type")
                # ... parsing logic ...
                return root
    """
    
    def __init__(self, file: BinaryIO):
        """
        Initialize the parser with a file.
        
        Args:
            file: A binary file object opened for reading
        """
        self.file = file
    
    @abstractmethod
    def parse(self) -> Node:
        """
        Parse the file and return the root Node.
        
        This method should read through the file and create a tree
        of Node objects representing the file structure.
        
        Returns:
            The root Node of the parsed file tree
        """
        pass
    
    @classmethod
    @abstractmethod
    def recognizes(cls, file: BinaryIO) -> bool:
        """
        Check if this parser can handle the given file.
        
        This method should check magic bytes or other identifying
        features at the start of the file. It should NOT consume
        the file - reset the seek position if needed.
        
        Args:
            file: A binary file object to check
            
        Returns:
            True if this parser can handle the file, False otherwise
        """
        pass
    
    @classmethod
    def validate(cls, file: BinaryIO) -> None:
        """
        Validate that a file is the correct format for this parser.
        
        Args:
            file: The file to validate
            
        Raises:
            InvalidFileException: If the file is not valid for this parser
        """
        if not cls.recognizes(file):
            raise InvalidFileException(
                f"File {getattr(file, 'name', 'unknown')} is not a valid {cls.__name__} file"
            )
    
    def get_file_size(self) -> int:
        """Get the total size of the file being parsed."""
        current_pos = self.file.tell()
        self.file.seek(0, 2)  # Seek to end
        size = self.file.tell()
        self.file.seek(current_pos)  # Restore position
        return size
    
    def read_at_offset(self, offset: int, size: int) -> bytes:
        """
        Read bytes at a specific offset without changing current position.
        
        Args:
            offset: The offset to read from
            size: Number of bytes to read
            
        Returns:
            The bytes read
        """
        current_pos = self.file.tell()
        self.file.seek(offset)
        data = self.file.read(size)
        self.file.seek(current_pos)
        return data
