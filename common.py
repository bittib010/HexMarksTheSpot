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
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Type, Union


class ColorGenerator:
    """
    Generates visually distinct, semi-transparent pastel colors for hex highlighting.
    Ensures adjacent colors are sufficiently different.
    Also provides forensic importance colors that stand out prominently.
    """
    
    # Pastel color palette - light, readable backgrounds
    # Using HSL: high lightness (0.7-0.85) for pastel effect
    _instance = None
    _last_hue = 0.0
    _used_colors = []
    
    # Forensic importance colors - these MUST stand out
    FORENSIC_COLORS = {
        # Category-specific forensic colors
        "critical": "#E74C3C",       # Strong red - most critical evidence
        "important": "#F39C12",      # Amber/orange - important findings
        "timestamp": "#9B59B6",      # Purple - timestamps
        "identifier": "#E91E63",     # Pink - IDs (GUIDs, serials, MACs)
        "path": "#00BCD4",           # Cyan - file paths and locations
        "network": "#FF5722",        # Deep orange - network-related data
        "default": "#FF4757",        # Default forensic highlight (bright red)
    }
    
    @classmethod
    def reset(cls):
        """Reset the color generator for a new file."""
        cls._last_hue = random.random()  # Start at random point
        cls._used_colors = []
    
    @classmethod
    def get_next_color(cls) -> str:
        """
        Generate the next visually distinct pastel color.
        Uses golden ratio to ensure good distribution of hues.
        
        Returns:
            Hex color string like '#RRGGBB'
        """
        # Golden ratio conjugate for optimal hue distribution
        golden_ratio = 0.618033988749895
        
        # Move to next hue using golden ratio
        cls._last_hue = (cls._last_hue + golden_ratio) % 1.0
        
        # High saturation (0.4-0.6) and high lightness (0.75-0.88) for pastel
        saturation = 0.45 + random.random() * 0.15  # 0.45-0.6
        lightness = 0.78 + random.random() * 0.1   # 0.78-0.88
        
        # Convert HSL to RGB
        r, g, b = colorsys.hls_to_rgb(cls._last_hue, lightness, saturation)
        
        # Convert to hex
        color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        
        cls._used_colors.append(color)
        return color
    
    @classmethod
    def is_color_too_similar(cls, color1: str, color2: str, threshold: float = 0.15) -> bool:
        """
        Check if two colors are too similar.
        
        Args:
            color1: First hex color
            color2: Second hex color  
            threshold: Minimum hue distance (0-1)
            
        Returns:
            True if colors are too similar
        """
        def hex_to_hsl(hex_color: str) -> Tuple[float, float, float]:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16) / 255
            g = int(hex_color[2:4], 16) / 255
            b = int(hex_color[4:6], 16) / 255
            h, l, s = colorsys.rgb_to_hls(r, g, b)
            return h, s, l
        
        h1, _, _ = hex_to_hsl(color1)
        h2, _, _ = hex_to_hsl(color2)
        
        # Calculate circular hue distance
        hue_diff = min(abs(h1 - h2), 1 - abs(h1 - h2))
        return hue_diff < threshold
    
    @classmethod
    def get_forensic_color(cls, category: str = "default") -> str:
        """
        Get a forensic importance color.
        
        These colors are designed to stand out prominently from the regular
        pastel palette, making forensically important fields immediately visible.
        
        Args:
            category: The forensic category. Options:
                - "critical": Most critical evidence (red)
                - "important": Important findings (amber)
                - "timestamp": Time-related evidence (purple)
                - "identifier": IDs like GUIDs, MACs, serials (pink)
                - "path": File paths and locations (cyan)
                - "network": Network-related data (deep orange)
                - "default": Generic forensic highlight (bright red)
                
        Returns:
            Hex color string
        """
        return cls.FORENSIC_COLORS.get(category, cls.FORENSIC_COLORS["default"])


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
