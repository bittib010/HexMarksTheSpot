"""
Dynamic Parser Loader for HexMarksTheSpot

This module provides automatic discovery and loading of file parsers from
JSON config files in the Artefacts/configs/ directory.

Non-programmers can add JSON configs to define new file format parsers
without writing any Python code. All configs are automatically discovered
and integrated into the application.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Dict, List, Optional, Type

if TYPE_CHECKING:
    from common import FileParser

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ParserRegistry:
    """
    Central registry for all file parsers.
    
    Provides automatic discovery and management of parsers from multiple sources.
    """
    
    _instance: Optional["ParserRegistry"] = None
    _parsers: List[Type["FileParser"]] = []
    _initialized: bool = False
    
    def __new__(cls) -> "ParserRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._parsers = []
            ParserRegistry._initialized = True
    
    @classmethod
    def get_instance(cls) -> "ParserRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(self, parser_class: Type["FileParser"]) -> None:
        """Register a parser class."""
        if parser_class not in self._parsers:
            self._parsers.append(parser_class)
            logger.info(f"Registered parser: {parser_class.__name__}")
    
    def get_parsers(self) -> List[Type["FileParser"]]:
        """Get all registered parsers."""
        return self._parsers.copy()
    
    def clear(self) -> None:
        """Clear all registered parsers."""
        self._parsers.clear()
    
    def find_parser_for_file(self, file: BinaryIO) -> Optional[Type["FileParser"]]:
        """
        Find a parser that recognizes the given file.
        
        Args:
            file: The file to check
            
        Returns:
            The parser class if found, None otherwise
        """
        for parser_class in self._parsers:
            try:
                file.seek(0)
                if parser_class.recognizes(file):
                    file.seek(0)
                    return parser_class
            except Exception as e:
                logger.debug(f"Error checking {parser_class.__name__}: {e}")
        file.seek(0)
        return None


def get_project_root() -> Path:
    """Get the project root directory."""
    # This file is in the project root
    return Path(__file__).parent


def load_json_config_parsers(configs_dir: Optional[Path] = None) -> List[Type["FileParser"]]:
    """
    Load all JSON config-based parsers from the configs directory.
    
    Args:
        configs_dir: Path to the configs directory
        
    Returns:
        List of parser classes
    """
    from config_parser import ConfigParserDefinition, ConfigBasedParser, load_config_parsers
    
    if configs_dir is None:
        configs_dir = get_project_root() / "Artefacts" / "configs"
    
    if not configs_dir.exists():
        logger.warning(f"Configs directory not found: {configs_dir}")
        # Create it for convenience
        configs_dir.mkdir(parents=True, exist_ok=True)
        return []
    
    return load_config_parsers(configs_dir)


def discover_all_parsers() -> List[Type["FileParser"]]:
    """
    Discover and load all parsers from all sources.
    
    This is the main entry point for parser discovery. It loads:
    - JSON config parsers from Artefacts/configs/
    
    Note: Python parsers have been deprecated in favor of JSON configs
    which are easier for non-programmers to create and maintain.
    
    Returns:
        List of all available parser classes
    """
    registry = ParserRegistry.get_instance()
    registry.clear()
    
    # Load JSON config parsers
    json_parsers = load_json_config_parsers()
    for parser in json_parsers:
        registry.register(parser)
    
    logger.info(f"Total parsers loaded: {len(registry.get_parsers())}")
    
    return registry.get_parsers()


def get_file_parser(file: BinaryIO) -> "FileParser":
    """
    Get the appropriate parser for a file.
    
    This function will automatically discover all available parsers
    and return an instance of the first parser that recognizes the file.
    
    Args:
        file: The file to parse
        
    Returns:
        An instance of the appropriate parser
        
    Raises:
        UnknownFileTypeException: If no parser recognizes the file
    """
    from common import UnknownFileTypeException
    
    registry = ParserRegistry.get_instance()
    
    # Ensure parsers are loaded
    if not registry.get_parsers():
        discover_all_parsers()
    
    parser_class = registry.find_parser_for_file(file)
    
    if parser_class:
        return parser_class(file)
    
    raise UnknownFileTypeException("No parser found for this file type")


def list_available_parsers() -> List[Dict[str, str]]:
    """
    List all available parsers with their information.
    
    Returns:
        List of dictionaries with parser information
    """
    registry = ParserRegistry.get_instance()
    
    if not registry.get_parsers():
        discover_all_parsers()
    
    parser_info = []
    for parser in registry.get_parsers():
        info = {
            "name": parser.__name__,
            "module": parser.__module__,
            "doc": parser.__doc__ or "No description available"
        }
        parser_info.append(info)
    
    return parser_info


# Convenience function for backward compatibility
def refresh_parsers() -> List[Type["FileParser"]]:
    """Refresh the parser registry by rediscovering all parsers."""
    return discover_all_parsers()
