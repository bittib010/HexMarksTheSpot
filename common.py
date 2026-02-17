"""
Core classes and types for HexMarksTheSpot

This module provides the fundamental building blocks for file parsing:
- Node: Represents a parsed data segment with metadata
- FileParser: Abstract base class for all file format parsers
- Custom exceptions for error handling
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Type, Union


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
        """Initialize default color if not provided."""
        if self.color is None:
            self.color = f"#{random.randint(0, 0xFFFFFF):06x}"
    
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
