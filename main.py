"""
HexMarksTheSpot - Advanced Hex File Analysis and Annotation

This is the main entry point for the HexMarksTheSpot application.
It provides both a command-line interface for testing parsers
and serves as the core parser discovery module.

Usage:
    python main.py              # Run the GUI
    python main.py --cli file   # Parse a file from command line
    python main.py --list       # List all available parsers
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import BinaryIO, Optional, Type

from common import Node, FileParser, UnknownFileTypeException
from parser_loader import (
    discover_all_parsers,
    get_file_parser,
    list_available_parsers,
    ParserRegistry,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def print_node(node: Node, indent: int = 0) -> None:
    """
    Print a node and its children in a tree format.
    
    Args:
        node: The node to print
        indent: Current indentation level
    """
    data_str = ' '.join(f'{byte:02x}' for byte in node.data[:32])
    if len(node.data) > 32:
        data_str += " ..."
    
    name = node.name or "Unnamed"
    print(' ' * indent + f"[{name}] {data_str}")
    
    for offset, child in node.children:
        print_node(child, indent + 2)


def find_node(node: Node, key: int) -> Optional[Node]:
    """
    Find a child node by offset key.
    
    Args:
        node: The parent node to search in
        key: The offset key to find
        
    Returns:
        The found node or None
    """
    try:
        return node.search_child(key)
    except ValueError:
        return None


def parse_file(file_path: str) -> Node:
    """
    Parse a file and return the root node.
    
    Args:
        file_path: Path to the file to parse
        
    Returns:
        The root Node of the parsed file
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        UnknownFileTypeException: If no parser recognizes the file
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(path, "rb") as file:
        parser = get_file_parser(file)
        logger.info(f"Using parser: {parser.__class__.__name__}")
        return parser.parse()


def main_cli():
    """Command-line interface for HexMarksTheSpot."""
    parser = argparse.ArgumentParser(
        description="HexMarksTheSpot - Advanced Hex File Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                          # Start the GUI
    python main.py --cli path/to/file       # Parse file from command line
    python main.py --list                   # List available parsers
    python main.py --refresh                # Refresh parser cache
        """
    )
    
    parser.add_argument(
        "--cli",
        metavar="FILE",
        help="Parse a file from the command line (no GUI)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available parsers"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the parser registry"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Discover parsers
    discover_all_parsers()
    
    if args.list:
        print("\n=== Available Parsers ===\n")
        for info in list_available_parsers():
            print(f"  {info['name']}")
            if args.verbose:
                doc = info['doc'].split('\n')[0][:60]
                print(f"    {doc}...")
        print()
        return 0
    
    if args.refresh:
        print("Parser registry refreshed.")
        return 0
    
    if args.cli:
        try:
            root = parse_file(args.cli)
            print(f"\n=== Parsed: {args.cli} ===\n")
            print_node(root)
            return 0
        except FileNotFoundError as e:
            logger.error(str(e))
            return 1
        except UnknownFileTypeException as e:
            logger.error(str(e))
            return 1
        except Exception as e:
            logger.exception(f"Error parsing file: {e}")
            return 1
    
    # Default: start GUI
    return start_gui()


def start_gui() -> int:
    """Start the graphical user interface."""
    try:
        from gui import main as gui_main
        gui_main()
        return 0
    except ImportError as e:
        logger.error(f"Could not start GUI: {e}")
        logger.info("Try running with --cli option for command-line mode")
        return 1


def main():
    """Main entry point."""
    sys.exit(main_cli())


if __name__ == "__main__":
    main()
