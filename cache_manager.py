"""
Cache Manager for HexMarksTheSpot

Provides file-hash-based caching for:
- Parsed Node trees (serialized via pickle for fast loading)
- Bookmarks with comments (persisted per-file by SHA-256 hash)

Cache layout:
    cache/
        <sha256_hex>/
            parsed.pkl        # Pickled Node tree (fast binary format)
            bookmarks.json    # Bookmarks with comments
            meta.json         # File metadata (name, size, parser, timestamp)
"""

import hashlib
import json
import logging
import os
import pickle
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from common import Node

logger = logging.getLogger(__name__)

# Cache directory lives next to the application
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


def _ensure_cache_dir():
    """Create the cache root directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file.
    
    Args:
        filepath: Path to the file to hash
        
    Returns:
        Hex string of the SHA-256 digest
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def _get_cache_path(file_hash: str) -> str:
    """Get the cache directory path for a given file hash."""
    return os.path.join(CACHE_DIR, file_hash)


# ──────────────────────────────────────────────
# Node Serialization / Deserialization
# ──────────────────────────────────────────────

def node_to_dict(node: Node) -> Dict[str, Any]:
    """Recursively serialize a Node tree to a JSON-compatible dict.
    
    Binary data is base64-encoded for safe JSON storage.
    """
    return {
        "data": base64.b64encode(node.data).decode("ascii") if node.data else "",
        "info": node.info,
        "name": node.name,
        "color": node.color,
        "table_value": str(node.table_value) if node.table_value is not None else None,
        "children": [
            {"offset": offset, "node": node_to_dict(child)}
            for offset, child in node.children
        ],
    }


def dict_to_node(d: Dict[str, Any]) -> Node:
    """Recursively deserialize a dict back to a Node tree.
    
    Bypasses __post_init__ color generation to preserve cached colors.
    """
    data = base64.b64decode(d["data"]) if d.get("data") else b""
    node = Node.__new__(Node)
    node.data = data
    node.info = d.get("info", "")
    node.name = d.get("name")
    node.color = d.get("color")
    node.table_value = d.get("table_value")
    node.children = []
    for child_entry in d.get("children", []):
        child_node = dict_to_node(child_entry["node"])
        node.children.append((child_entry["offset"], child_node))
    return node


# ──────────────────────────────────────────────
# Parsed Data Cache
# ──────────────────────────────────────────────

def save_parsed_cache(file_hash: str, root: Node, filepath: str, parser_name: str) -> bool:
    """Save a parsed Node tree to the cache using pickle.
    
    Pickle is used instead of JSON because:
    - Native bytes support (no base64 overhead)
    - No recursive dict conversion needed
    - ~10-50x faster serialization/deserialization
    
    Args:
        file_hash: SHA-256 hash of the source file
        root: Root Node of the parsed tree
        filepath: Original file path (for metadata)
        parser_name: Name of the parser used
        
    Returns:
        True if saved successfully, False on error
    """
    try:
        _ensure_cache_dir()
        cache_path = _get_cache_path(file_hash)
        os.makedirs(cache_path, exist_ok=True)
        
        # Save the Node tree as pickle (protocol 5 for best bytes performance)
        parsed_path = os.path.join(cache_path, "parsed.pkl")
        with open(parsed_path, "wb") as f:
            pickle.dump(root, f, protocol=5)
        
        # Save metadata (JSON is fine for this small file)
        meta_path = os.path.join(cache_path, "meta.json")
        meta = {
            "filename": os.path.basename(filepath),
            "filepath": filepath,
            "file_size": os.path.getsize(filepath) if os.path.exists(filepath) else 0,
            "parser": parser_name,
            "cached_at": datetime.now().isoformat(),
            "hash": file_hash,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        
        logger.info(f"Cached parsed data for {os.path.basename(filepath)} ({file_hash[:12]}...)")
        return True
    except Exception as e:
        logger.error(f"Failed to save parsed cache: {e}")
        return False


def load_parsed_cache(file_hash: str) -> Optional[Node]:
    """Load a parsed Node tree from the cache.
    
    Checks for pickle format first, falls back to legacy JSON format.
    
    Args:
        file_hash: SHA-256 hash of the source file
        
    Returns:
        Root Node if cache exists, None otherwise
    """
    cache_dir = _get_cache_path(file_hash)
    
    # Try pickle first (fast path)
    pkl_path = os.path.join(cache_dir, "parsed.pkl")
    if os.path.exists(pkl_path):
        try:
            with open(pkl_path, "rb") as f:
                root = pickle.load(f)
            logger.info(f"Loaded parsed data from pickle cache ({file_hash[:12]}...)")
            return root
        except Exception as e:
            logger.error(f"Failed to load pickle cache: {e}")
    
    # Fall back to legacy JSON format
    json_path = os.path.join(cache_dir, "parsed.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            root = dict_to_node(data)
            logger.info(f"Loaded parsed data from JSON cache ({file_hash[:12]}...)")
            # Upgrade: save as pickle for next time, remove old JSON
            try:
                with open(pkl_path, "wb") as f:
                    pickle.dump(root, f, protocol=5)
                os.remove(json_path)
                logger.info("Upgraded cache from JSON to pickle")
            except Exception:
                pass
            return root
        except Exception as e:
            logger.error(f"Failed to load JSON cache: {e}")
    
    return None


def has_parsed_cache(file_hash: str) -> bool:
    """Check if a parsed cache exists for the given file hash."""
    cache_dir = _get_cache_path(file_hash)
    return (os.path.exists(os.path.join(cache_dir, "parsed.pkl"))
            or os.path.exists(os.path.join(cache_dir, "parsed.json")))


def get_cache_meta(file_hash: str) -> Optional[Dict[str, Any]]:
    """Get cache metadata for a file hash."""
    try:
        meta_path = os.path.join(_get_cache_path(file_hash), "meta.json")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ──────────────────────────────────────────────
# Bookmark Persistence
# ──────────────────────────────────────────────

def save_bookmarks(file_hash: str, bookmarks: List[Dict[str, Any]]) -> bool:
    """Save bookmarks for a file to the cache.
    
    Each bookmark is a dict with keys: name, offset, comment
    
    Args:
        file_hash: SHA-256 hash of the source file
        bookmarks: List of bookmark dicts
        
    Returns:
        True if saved successfully
    """
    try:
        _ensure_cache_dir()
        cache_path = _get_cache_path(file_hash)
        os.makedirs(cache_path, exist_ok=True)
        
        bookmarks_path = os.path.join(cache_path, "bookmarks.json")
        with open(bookmarks_path, "w", encoding="utf-8") as f:
            json.dump(bookmarks, f, indent=2)
        
        logger.info(f"Saved {len(bookmarks)} bookmarks ({file_hash[:12]}...)")
        return True
    except Exception as e:
        logger.error(f"Failed to save bookmarks: {e}")
        return False


def load_bookmarks(file_hash: str) -> List[Dict[str, Any]]:
    """Load bookmarks for a file from the cache.
    
    Returns:
        List of bookmark dicts, or empty list if none found
    """
    try:
        bookmarks_path = os.path.join(_get_cache_path(file_hash), "bookmarks.json")
        if not os.path.exists(bookmarks_path):
            return []
        
        with open(bookmarks_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load bookmarks: {e}")
        return []


def export_bookmarks_to_file(bookmarks: List[Dict[str, Any]], filepath: str,
                              source_filename: str = "") -> bool:
    """Export bookmarks to a standalone JSON or CSV file.
    
    Args:
        bookmarks: List of bookmark dicts
        filepath: Destination file path (.json or .csv)
        source_filename: Original filename for metadata
        
    Returns:
        True if exported successfully
    """
    try:
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext == ".csv":
            import csv
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Offset", "Offset (Hex)", "Comment"])
                for bm in bookmarks:
                    offset = bm.get("offset", 0)
                    writer.writerow([
                        bm.get("name", ""),
                        offset,
                        f"0x{offset:X}",
                        bm.get("comment", ""),
                    ])
        else:
            # Default to JSON
            export_data = {
                "source_file": source_filename,
                "exported_at": datetime.now().isoformat(),
                "bookmark_count": len(bookmarks),
                "bookmarks": bookmarks,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported {len(bookmarks)} bookmarks to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to export bookmarks: {e}")
        return False
