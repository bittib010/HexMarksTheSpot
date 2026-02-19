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


def verify_parsed_bytes(file_path: str, root: Node) -> bool:
    """
    Verify that parsed nodes reconstruct the original file byte-for-byte.
    
    Performs four checks:
    1. Byte count — do leaf nodes cover exactly the file size?
    2. Overlap detection — do any nodes claim the same byte range?
    3. Per-node data — does each node's data match the file at its offset?
    4. Sequential stream — does the concatenated display match the file?
    
    Prints the exact offset and field name of the first divergence with
    surrounding hex context for easy debugging.
    
    Returns True if all checks pass, False on any mismatch.
    """
    path = Path(file_path)
    file_data = path.read_bytes()
    file_size = len(file_data)
    
    # Collect all leaf nodes via iterative DFS
    leaves = []
    stack = [(root, 0)]
    while stack:
        current, child_idx = stack[-1]
        if child_idx >= len(current.children):
            stack.pop()
            continue
        stack[-1] = (current, child_idx + 1)
        key, child = current.children[child_idx]
        offset = key if key is not None else 0
        data_len = len(child.data) if child.data else 0
        if data_len > 0:
            leaves.append({'name': child.name, 'offset': offset,
                           'data_len': data_len, 'data': child.data})
        if child.children:
            stack.append((child, 0))
    
    leaves.sort(key=lambda x: x['offset'])
    total_parsed = sum(nd['data_len'] for nd in leaves)
    passed = True
    
    # Step 1: Byte count
    if total_parsed != file_size:
        diff = file_size - total_parsed
        if total_parsed < file_size:
            print(f"  FAIL  Byte count: parsed {total_parsed:,} bytes, "
                  f"file is {file_size:,} bytes ({diff:,} unparsed)")
        else:
            print(f"  FAIL  Byte count: parsed {total_parsed:,} bytes, "
                  f"file is only {file_size:,} bytes ({abs(diff):,} over-read)")
        passed = False
    else:
        print(f"  PASS  Byte count: {total_parsed:,} / {file_size:,} bytes")
    
    # Step 2: Overlap detection
    overlap_found = False
    for i in range(len(leaves) - 1):
        curr = leaves[i]
        nxt = leaves[i + 1]
        curr_end = curr['offset'] + curr['data_len']
        if curr_end > nxt['offset']:
            overlap_bytes = curr_end - nxt['offset']
            print(f"  FAIL  Overlap: '{curr['name']}' "
                  f"(0x{curr['offset']:X}..0x{curr_end:X}) overlaps "
                  f"'{nxt['name']}' (0x{nxt['offset']:X}) by {overlap_bytes} bytes")
            overlap_found = True
            passed = False
    if not overlap_found:
        print(f"  PASS  No overlapping fields")
    
    # Step 3: Per-node offset verification
    node_mismatch = False
    for nd in leaves:
        offset = nd['offset']
        data = nd['data']
        if offset + nd['data_len'] > len(file_data):
            print(f"  FAIL  '{nd['name']}' at 0x{offset:X} extends {nd['data_len']} bytes "
                  f"beyond file end (only {len(file_data) - offset} available)")
            node_mismatch = True
            passed = False
            break
        file_chunk = file_data[offset:offset + nd['data_len']]
        if data != file_chunk:
            for i in range(nd['data_len']):
                if data[i] != file_chunk[i]:
                    abs_off = offset + i
                    ctx_s = max(0, abs_off - 8)
                    ctx_e = min(len(file_data), abs_off + 9)
                    file_ctx = ' '.join(f'{file_data[j]:02X}' for j in range(ctx_s, ctx_e))
                    parsed_ctx = ' '.join(f'{data[j]:02X}'
                                         for j in range(max(0, i - 8), min(nd['data_len'], i + 9)))
                    marker_pos = (abs_off - ctx_s) * 3
                    print(f"  FAIL  Byte mismatch at 0x{abs_off:X} in '{nd['name']}' "
                          f"(byte {i} of {nd['data_len']}): "
                          f"parsed 0x{data[i]:02X}, file has 0x{file_chunk[i]:02X}")
                    print(f"         File:   {file_ctx}")
                    print(f"         Parsed: {parsed_ctx}")
                    print(f"                 {' ' * marker_pos}^^")
                    node_mismatch = True
                    passed = False
                    break
            break
    if not node_mismatch:
        print(f"  PASS  All field data matches file at declared offsets")
    
    # Step 4: Sequential stream comparison
    reconstructed = bytearray()
    boundaries = []  # (stream_pos, name, file_offset)
    for nd in leaves:
        boundaries.append((len(reconstructed), nd['name'], nd['offset']))
        reconstructed.extend(nd['data'])
    
    stream_mismatch = False
    min_len = min(len(reconstructed), len(file_data))
    for i in range(min_len):
        if reconstructed[i] != file_data[i]:
            # Identify which field owns this stream position
            field_name = "unknown"
            byte_within = 0
            field_file_offset = 0
            for idx, (spos, name, foff) in enumerate(boundaries):
                next_pos = (boundaries[idx + 1][0]
                            if idx + 1 < len(boundaries) else len(reconstructed))
                if spos <= i < next_pos:
                    field_name = name
                    field_file_offset = foff
                    byte_within = i - spos
                    break
            ctx_s = max(0, i - 8)
            ctx_e = min(min_len, i + 9)
            parsed_line = ' '.join(f'{reconstructed[j]:02X}' for j in range(ctx_s, ctx_e))
            actual_line = ' '.join(f'{file_data[j]:02X}' for j in range(ctx_s, ctx_e))
            marker_pos = (i - ctx_s) * 3
            print(f"  FAIL  Stream mismatch at position 0x{i:X} "
                  f"(file offset 0x{field_file_offset + byte_within:X}) "
                  f"in '{field_name}': "
                  f"parsed 0x{reconstructed[i]:02X}, file has 0x{file_data[i]:02X}")
            print(f"         Parsed: {parsed_line}")
            print(f"         Actual: {actual_line}")
            print(f"                 {' ' * marker_pos}^^")
            stream_mismatch = True
            passed = False
            break
    if not stream_mismatch:
        print(f"  PASS  Sequential stream matches file ({min_len:,} bytes)")
    
    return passed


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
        parser = get_file_parser(file, str(path))
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
    python main.py --verify path/to/file    # Verify parsing integrity
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
        "--verify",
        metavar="FILE",
        help="Parse a file and verify hex integrity (byte-by-byte comparison)"
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
    
    if args.verify:
        try:
            root = parse_file(args.verify)
            file_size = Path(args.verify).stat().st_size
            print(f"\n=== Verify: {args.verify} ({file_size:,} bytes) ===\n")
            passed = verify_parsed_bytes(args.verify, root)
            print(f"\n{'ALL CHECKS PASSED' if passed else 'VERIFICATION FAILED'}")
            return 0 if passed else 1
        except FileNotFoundError as e:
            logger.error(str(e))
            return 1
        except UnknownFileTypeException as e:
            logger.error(str(e))
            return 1
        except Exception as e:
            logger.exception(f"Error verifying file: {e}")
            return 1
    
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
