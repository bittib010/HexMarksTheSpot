# Standard Libraries
import os
import sys
import threading
import time
import csv
import hashlib
import logging
import tempfile
import re
from datetime import datetime

# Third-Party Libraries
from tkinter import Tk, Text, N, S, E, W, Frame, Canvas
from tkinter import filedialog, messagebox, Button, Scrollbar, Label
from tkinter import SEL, SEL_LAST, SEL_FIRST, END
from tkinter import TclError, Entry, Listbox, ttk
from tkinter import StringVar, DoubleVar, IntVar, BooleanVar, NO, Toplevel, BOTH, LEFT, RIGHT, X, Y, TOP, BOTTOM, Spinbox, Checkbutton
from tkinter import Menu as tk_Menu
from tkhtmlview import HTMLText

# Application-specific - use the new dynamic parser loader
from parser_loader import get_file_parser, discover_all_parsers
from common import ColorGenerator, Node, markdown_to_html
import cache_manager


def _win32_open_file_dialog(initialdir="", title="Select File", filetypes=None):
    """
    Windows-native file open dialog that does NOT resolve .lnk shortcuts.
    
    Uses ctypes to call GetOpenFileNameW with OFN_NODEREFERENCELINKS flag,
    so that selecting a .lnk file returns the .lnk path itself rather than
    following the shortcut to its target.
    
    Returns the selected file path, or "" if cancelled.
    """
    import ctypes
    import ctypes.wintypes

    OFN_FILEMUSTEXIST = 0x00001000
    OFN_NODEREFERENCELINKS = 0x00100000
    OFN_EXPLORER = 0x00080000
    OFN_HIDEREADONLY = 0x00000004
    MAX_PATH_BUF = 4096

    class OPENFILENAME(ctypes.Structure):
        _fields_ = [
            ("lStructSize", ctypes.wintypes.DWORD),
            ("hwndOwner", ctypes.wintypes.HWND),
            ("hInstance", ctypes.wintypes.HINSTANCE),
            ("lpstrFilter", ctypes.wintypes.LPCWSTR),
            ("lpstrCustomFilter", ctypes.wintypes.LPWSTR),
            ("nMaxCustFilter", ctypes.wintypes.DWORD),
            ("nFilterIndex", ctypes.wintypes.DWORD),
            ("lpstrFile", ctypes.wintypes.LPWSTR),
            ("nMaxFile", ctypes.wintypes.DWORD),
            ("lpstrFileTitle", ctypes.wintypes.LPWSTR),
            ("nMaxFileTitle", ctypes.wintypes.DWORD),
            ("lpstrInitialDir", ctypes.wintypes.LPCWSTR),
            ("lpstrTitle", ctypes.wintypes.LPCWSTR),
            ("Flags", ctypes.wintypes.DWORD),
            ("nFileOffset", ctypes.wintypes.WORD),
            ("nFileExtension", ctypes.wintypes.WORD),
            ("lpstrDefExt", ctypes.wintypes.LPCWSTR),
            ("lCustData", ctypes.wintypes.LPARAM),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", ctypes.wintypes.LPCWSTR),
            ("pvReserved", ctypes.c_void_p),
            ("dwReserved", ctypes.wintypes.DWORD),
            ("FlagsEx", ctypes.wintypes.DWORD),
        ]

    # Build filter string: pairs of (description, pattern) separated by \0, ending with double \0
    filter_parts = []
    if filetypes:
        for desc, pattern in filetypes:
            filter_parts.append(desc)
            filter_parts.append(pattern)
    else:
        filter_parts.append("All Files")
        filter_parts.append("*.*")
    filter_str = "\0".join(filter_parts) + "\0\0"

    file_buf = ctypes.create_unicode_buffer(MAX_PATH_BUF)

    ofn = OPENFILENAME()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
    ofn.hwndOwner = None
    ofn.lpstrFilter = filter_str
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.cast(file_buf, ctypes.wintypes.LPWSTR)
    ofn.nMaxFile = MAX_PATH_BUF
    ofn.lpstrInitialDir = initialdir or None
    ofn.lpstrTitle = title
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_NODEREFERENCELINKS | OFN_EXPLORER | OFN_HIDEREADONLY

    result = ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn))
    if result:
        return file_buf.value
    return ""


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ============================================================================
# Modern Color Theme
# ============================================================================
class ModernTheme:
    """Modern, calm color theme for the application."""
    
    # Primary colors
    BG_PRIMARY = "#F8FAFC"       # Very light gray-blue background
    BG_SECONDARY = "#F1F5F9"     # Slightly darker background for cards
    BG_DARK = "#1E293B"          # Dark background for hex view
    
    # Accent colors
    ACCENT_PRIMARY = "#3B82F6"   # Soft blue
    ACCENT_SUCCESS = "#10B981"   # Soft green
    ACCENT_WARNING = "#F59E0B"   # Soft amber
    ACCENT_DANGER = "#EF4444"    # Soft red
    
    # Text colors
    TEXT_PRIMARY = "#1E293B"     # Dark text
    TEXT_SECONDARY = "#64748B"   # Muted text
    TEXT_LIGHT = "#94A3B8"       # Light text
    TEXT_ON_DARK = "#E2E8F0"     # Text on dark backgrounds
    
    # Hex view colors
    HEX_BG = "#1E293B"           # Dark blue-gray
    HEX_FG = "#A5F3FC"           # Cyan text
    ASCII_FG = "#86EFAC"         # Green text
    
    # Border colors
    BORDER = "#E2E8F0"           # Light border
    BORDER_FOCUS = "#3B82F6"     # Focus border
    
    # Button colors
    BTN_PRIMARY = "#3B82F6"
    BTN_PRIMARY_HOVER = "#2563EB"
    BTN_SECONDARY = "#64748B"
    BTN_TEXT = "#FFFFFF"
    
    # Status colors
    SELECTION_BG = "#BFDBFE"     # Light blue selection
    
    # Forensic importance colors - these stand out prominently
    FORENSIC_BG = "#FF4757"          # Bright red background
    FORENSIC_BG_ALT = "#FF6B81"      # Lighter red variant
    FORENSIC_HIGHLIGHT = "#C0392B"   # Dark red highlight
    FORENSIC_TEXT = "#FFFFFF"        # White text on forensic fields
    
    # Additional forensic palette for variety (manually assignable)
    FORENSIC_PALETTE = {
        "critical": "#E74C3C",    # Strong red - most critical evidence
        "important": "#F39C12",   # Amber/orange - important findings
        "timestamp": "#9B59B6",   # Purple - timestamps
        "identifier": "#E91E63",  # Pink - identifiers (GUIDs, serials)
        "path": "#00BCD4",        # Cyan - paths and locations
        "network": "#FF5722",     # Deep orange - network-related
    }


def setup_modern_style():
    """Configure ttk styles for a modern appearance."""
    style = ttk.Style()
    
    # Use clam theme as base (more customizable)
    style.theme_use('clam')
    
    # Configure Treeview
    style.configure(
        "Modern.Treeview",
        background=ModernTheme.BG_SECONDARY,
        foreground=ModernTheme.TEXT_PRIMARY,
        fieldbackground=ModernTheme.BG_SECONDARY,
        borderwidth=0,
        relief="flat",
        rowheight=28,
        font=('Segoe UI', 10)
    )
    style.configure(
        "Modern.Treeview.Heading",
        background=ModernTheme.BG_PRIMARY,
        foreground=ModernTheme.TEXT_PRIMARY,
        relief="flat",
        font=('Segoe UI', 10, 'bold'),
        padding=(10, 8),
        anchor='w'
    )
    style.map(
        "Modern.Treeview",
        background=[('selected', ModernTheme.SELECTION_BG)],
        foreground=[('selected', ModernTheme.TEXT_PRIMARY)]
    )
    
    # Configure Combobox
    style.configure(
        "Modern.TCombobox",
        fieldbackground=ModernTheme.BG_SECONDARY,
        background=ModernTheme.BG_SECONDARY,
        foreground=ModernTheme.TEXT_PRIMARY,
        borderwidth=1,
        padding=(6, 4),
        font=('Segoe UI', 9)
    )
    style.map(
        "Modern.TCombobox",
        fieldbackground=[('readonly', ModernTheme.BG_SECONDARY)],
        selectbackground=[('readonly', ModernTheme.BG_SECONDARY)],
        selectforeground=[('readonly', ModernTheme.TEXT_PRIMARY)]
    )
    
    # Configure Button
    style.configure(
        "Modern.TButton",
        background=ModernTheme.BTN_PRIMARY,
        foreground=ModernTheme.BTN_TEXT,
        borderwidth=0,
        focusthickness=0,
        padding=(16, 10),
        font=('Segoe UI', 10)
    )
    style.map(
        "Modern.TButton",
        background=[('active', ModernTheme.BTN_PRIMARY_HOVER), ('pressed', ModernTheme.BTN_PRIMARY_HOVER)]
    )
    
    # Secondary button style
    style.configure(
        "Secondary.TButton",
        background=ModernTheme.BG_SECONDARY,
        foreground=ModernTheme.TEXT_PRIMARY,
        borderwidth=1,
        padding=(16, 10),
        font=('Segoe UI', 10)
    )
    
    # Configure Entry
    style.configure(
        "Modern.TEntry",
        fieldbackground=ModernTheme.BG_SECONDARY,
        borderwidth=1,
        relief="flat",
        padding=(10, 8),
        font=('Segoe UI', 10)
    )
    
    # Configure Progressbar
    style.configure(
        "Modern.Horizontal.TProgressbar",
        background=ModernTheme.ACCENT_PRIMARY,
        troughcolor=ModernTheme.BG_SECONDARY,
        borderwidth=0,
        thickness=6
    )
    
    # Configure Scrollbar - wider and more visible
    style.configure(
        "Modern.Vertical.TScrollbar",
        background=ModernTheme.TEXT_SECONDARY,
        troughcolor=ModernTheme.BG_SECONDARY,
        borderwidth=0,
        arrowsize=14,
        width=16
    )
    style.map(
        "Modern.Vertical.TScrollbar",
        background=[('active', ModernTheme.ACCENT_PRIMARY), ('pressed', ModernTheme.ACCENT_PRIMARY)]
    )
    
    # Configure Horizontal Scrollbar
    style.configure(
        "Modern.Horizontal.TScrollbar",
        background=ModernTheme.TEXT_SECONDARY,
        troughcolor=ModernTheme.BG_SECONDARY,
        borderwidth=0,
        arrowsize=14,
        width=14
    )
    style.map(
        "Modern.Horizontal.TScrollbar",
        background=[('active', ModernTheme.ACCENT_PRIMARY), ('pressed', ModernTheme.ACCENT_PRIMARY)]
    )
    
    # Stop button style - soft red
    style.configure(
        "Stop.TButton",
        background="#DC6B6B",
        foreground=ModernTheme.BTN_TEXT,
        borderwidth=0,
        focusthickness=0,
        padding=(16, 10),
        font=('Segoe UI', 10)
    )
    style.map(
        "Stop.TButton",
        background=[('active', '#C45555'), ('pressed', '#C45555'), ('disabled', ModernTheme.BG_SECONDARY)],
        foreground=[('disabled', ModernTheme.TEXT_LIGHT)]
    )
    
    return style


# ============================================================================
# Custom Rounded Widgets for Modern UI
# ============================================================================

class RoundedButton(Canvas):
    """A modern button with rounded corners using Canvas drawing."""
    
    def __init__(self, parent, text="", command=None, radius=10,
                 bg_color=None, fg_color=None, hover_color=None,
                 font=('Segoe UI', 10), width=None, height=38,
                 style="primary", state="normal", **kwargs):
        """
        Create a rounded button.
        
        :param parent: Parent widget
        :param text: Button text
        :param command: Callback function
        :param radius: Corner radius in pixels
        :param bg_color: Background color (auto from style if None)
        :param fg_color: Text color (auto from style if None) 
        :param hover_color: Hover background color (auto from style if None)
        :param font: Font tuple
        :param width: Button width (None = auto from parent)
        :param height: Button height
        :param style: "primary", "secondary", "danger", or "small"
        """
        # Resolve colors from style presets
        styles = {
            "primary": {
                "bg": ModernTheme.BTN_PRIMARY,
                "fg": ModernTheme.BTN_TEXT,
                "hover": ModernTheme.BTN_PRIMARY_HOVER,
                "disabled_bg": ModernTheme.BG_SECONDARY,
                "disabled_fg": ModernTheme.TEXT_LIGHT,
            },
            "secondary": {
                "bg": ModernTheme.BG_SECONDARY,
                "fg": ModernTheme.TEXT_PRIMARY,
                "hover": ModernTheme.BORDER,
                "disabled_bg": ModernTheme.BG_SECONDARY,
                "disabled_fg": ModernTheme.TEXT_LIGHT,
            },
            "danger": {
                "bg": "#DC6B6B",
                "fg": ModernTheme.BTN_TEXT,
                "hover": "#C45555",
                "disabled_bg": ModernTheme.BG_SECONDARY,
                "disabled_fg": ModernTheme.TEXT_LIGHT,
            },
            "small": {
                "bg": ModernTheme.BG_SECONDARY,
                "fg": ModernTheme.TEXT_PRIMARY,
                "hover": ModernTheme.BORDER,
                "disabled_bg": ModernTheme.BG_SECONDARY,
                "disabled_fg": ModernTheme.TEXT_LIGHT,
            },
        }
        
        preset = styles.get(style, styles["primary"])
        self._bg_color = bg_color or preset["bg"]
        self._fg_color = fg_color or preset["fg"]
        self._hover_color = hover_color or preset["hover"]
        self._disabled_bg = preset["disabled_bg"]
        self._disabled_fg = preset["disabled_fg"]
        self._current_bg = self._bg_color
        
        self._text = text
        self._command = command
        self._radius = radius
        self._font = font
        self._state = state
        self._style = style
        self._btn_height = height
        
        # Determine parent background color
        parent_bg = ModernTheme.BG_PRIMARY
        try:
            parent_bg = parent.cget('bg')
        except Exception:
            pass
        
        # Use width=0 by default so the canvas doesn't request excessive space
        # Let the grid/pack geometry manager control actual width via sticky=E+W
        if 'width' not in kwargs:
            kwargs['width'] = 0
        
        super().__init__(
            parent,
            height=height,
            bg=parent_bg,
            highlightthickness=0,
            borderwidth=0,
            **kwargs
        )
        
        # Draw initial state
        self.bind('<Configure>', self._on_resize)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        
        if self._state == "disabled":
            self._current_bg = self._disabled_bg
    
    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Draw a rounded rectangle on the canvas."""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius,
            x2, y2, x2 - radius, y2,
            x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius,
            x1, y1, x1 + radius, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _redraw(self):
        """Redraw the button."""
        try:
            if not self.winfo_exists():
                return
        except:
            return
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return
        
        # Draw rounded rectangle background
        fill = self._current_bg
        if self._state == "disabled":
            fill = self._disabled_bg
        
        # Optional subtle border for secondary buttons
        outline_color = ""
        outline_width = 0
        if self._style in ("secondary", "small"):
            outline_color = ModernTheme.BORDER
            outline_width = 1
        
        self._create_rounded_rect(
            1, 1, w - 1, h - 1,
            self._radius,
            fill=fill,
            outline=outline_color,
            width=outline_width
        )
        
        # Draw text
        text_color = self._fg_color if self._state != "disabled" else self._disabled_fg
        self.create_text(
            w / 2, h / 2,
            text=self._text,
            fill=text_color,
            font=self._font
        )
    
    def _on_resize(self, event):
        self._redraw()
    
    def _on_enter(self, event):
        if self._state != "disabled":
            self._current_bg = self._hover_color
            self._redraw()
            self.config(cursor="hand2")
    
    def _on_leave(self, event):
        if self._state != "disabled":
            self._current_bg = self._bg_color
            self._redraw()
            self.config(cursor="")
    
    def _on_press(self, event):
        if self._state != "disabled":
            # Darken slightly on press
            self._current_bg = self._hover_color
            self._redraw()
    
    def _on_release(self, event):
        if self._state != "disabled" and self._command:
            # Check if mouse is still over button
            x, y = event.x, event.y
            if 0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height():
                self._command()
        if self._state != "disabled":
            self._current_bg = self._bg_color
            self._redraw()
    
    def configure_state(self, state):
        """Update button state ('normal' or 'disabled')."""
        self._state = state
        if state == "disabled":
            self._current_bg = self._disabled_bg
            self.config(cursor="")
        else:
            self._current_bg = self._bg_color
        self._redraw()
    
    def configure_text(self, text):
        """Update button text."""
        self._text = text
        self._redraw()
    
    # Compatibility aliases for ttk.Button interface
    def config(self, **kwargs):
        if 'state' in kwargs:
            self.configure_state(str(kwargs.pop('state')))
        if 'text' in kwargs:
            self.configure_text(kwargs.pop('text'))
        if 'command' in kwargs:
            self._command = kwargs.pop('command')
        if kwargs:
            super().config(**kwargs)
    
    def configure(self, **kwargs):
        self.config(**kwargs)
    
    def cget(self, key):
        if key == 'state':
            return self._state
        if key == 'text':
            return self._text
        return super().cget(key)


class RoundedEntry(Frame):
    """A text entry with rounded border styling."""
    
    def __init__(self, parent, textvariable=None, font=('Segoe UI', 10),
                 radius=10, placeholder="", **kwargs):
        parent_bg = ModernTheme.BG_PRIMARY
        try:
            parent_bg = parent.cget('bg')
        except Exception:
            pass
        
        super().__init__(parent, bg=parent_bg, **kwargs)
        
        self._radius = radius
        self._placeholder = placeholder
        self._has_focus = False
        
        # Canvas for the rounded border
        self._canvas = Canvas(
            self, bg=parent_bg,
            highlightthickness=0, borderwidth=0,
            height=38, width=0
        )
        self._canvas.pack(fill=X, expand=True)
        
        # The actual entry widget (placed inside canvas)
        self._entry = Entry(
            self,
            textvariable=textvariable,
            font=font,
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.TEXT_PRIMARY,
            insertbackground=ModernTheme.TEXT_PRIMARY,
            relief='flat',
            borderwidth=0
        )
        self._entry_window = None
        
        self._canvas.bind('<Configure>', self._on_resize)
        self._entry.bind('<FocusIn>', self._on_focus_in)
        self._entry.bind('<FocusOut>', self._on_focus_out)
    
    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius,
            x2, y2, x2 - radius, y2,
            x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius,
            x1, y1, x1 + radius, y1,
        ]
        return self._canvas.create_polygon(points, smooth=True, **kwargs)
    
    def _redraw(self):
        self._canvas.delete("all")
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        
        border_color = ModernTheme.BORDER_FOCUS if self._has_focus else ModernTheme.BORDER
        
        # Rounded background
        self._create_rounded_rect(
            1, 1, w - 1, h - 1,
            self._radius,
            fill=ModernTheme.BG_SECONDARY,
            outline=border_color,
            width=1.5 if self._has_focus else 1
        )
        
        # Place entry widget inside the rounded rect
        pad = self._radius
        if self._entry_window:
            self._canvas.delete(self._entry_window)
        self._entry_window = self._canvas.create_window(
            pad, h / 2,
            window=self._entry,
            anchor='w',
            width=w - 2 * pad,
            height=h - 12
        )
    
    def _on_resize(self, event):
        self._redraw()
    
    def _on_focus_in(self, event):
        self._has_focus = True
        self._redraw()
    
    def _on_focus_out(self, event):
        self._has_focus = False
        self._redraw()
    
    # Delegate common Entry methods
    def get(self):
        return self._entry.get()
    
    def delete(self, first, last=None):
        return self._entry.delete(first, last)
    
    def insert(self, index, string):
        return self._entry.insert(index, string)
    
    def bind(self, sequence, func=None, add=None):
        """Bind events to the inner entry widget for key/focus, frame for others."""
        if sequence in ('<FocusIn>', '<FocusOut>', '<Key>', '<Return>', '<KeyRelease>'):
            return self._entry.bind(sequence, func, add)
        return super().bind(sequence, func, add)
    
    def focus_set(self):
        return self._entry.focus_set()
    
    def icursor(self, index):
        return self._entry.icursor(index)
    
    def select_range(self, start, end):
        return self._entry.select_range(start, end)


class RoundedPanel(Frame):
    """A container frame with rounded corners and optional border."""
    
    def __init__(self, parent, radius=12, bg_color=None,
                 border_color=None, border_width=1, pad=12, **kwargs):
        parent_bg = ModernTheme.BG_PRIMARY
        try:
            parent_bg = parent.cget('bg')
        except Exception:
            pass
        
        super().__init__(parent, bg=parent_bg, **kwargs)
        
        self._radius = radius
        self._bg_color = bg_color or ModernTheme.BG_SECONDARY
        self._border_color = border_color or ModernTheme.BORDER
        self._border_width = border_width
        self._pad = pad
        
        self._canvas = Canvas(
            self, bg=parent_bg,
            highlightthickness=0, borderwidth=0
        )
        self._canvas.pack(fill=BOTH, expand=True)
        
        # Inner frame where child widgets go
        self.inner = Frame(self._canvas, bg=self._bg_color)
        self._inner_window = None
        
        self._canvas.bind('<Configure>', self._on_resize)
    
    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius,
            x2, y2, x2 - radius, y2,
            x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius,
            x1, y1, x1 + radius, y1,
        ]
        return self._canvas.create_polygon(points, smooth=True, **kwargs)
    
    def _on_resize(self, event):
        self._canvas.delete("all")
        w = event.width
        h = event.height
        if w <= 1 or h <= 1:
            return
        
        # Draw rounded background
        self._create_rounded_rect(
            1, 1, w - 1, h - 1,
            self._radius,
            fill=self._bg_color,
            outline=self._border_color,
            width=self._border_width
        )
        
        # Place inner frame
        pad = self._pad
        if self._inner_window:
            self._canvas.delete(self._inner_window)
        self._inner_window = self._canvas.create_window(
            pad, pad,
            window=self.inner,
            anchor='nw',
            width=w - 2 * pad,
            height=h - 2 * pad
        )


class TextWidget:
    """
    A class to create and manage text widgets for displaying hex and ASCII data.
    Modern design with soft colors and clean typography.
    Includes offset column and column headers for position reference.
    """

    def __init__(self, master):
        """
        Initialize the TextWidget with scrollbars, offset column, headers, and modern styling.

        :param master: The parent widget for this TextWidget.
        """
        # Create a container frame with padding - only column 0 (sidebar is in column 1)
        self.container = Frame(master, bg=ModernTheme.BG_PRIMARY)
        self.container.grid(row=1, column=0, sticky=N+S+E+W, padx=(20, 10), pady=(15, 0))
        
        # Configure grid weights for the container
        # col 0 = offset column, col 1 = hex view, col 2 = ASCII view, col 3 = scrollbar, col 4 = info panel
        self.container.grid_columnconfigure(0, weight=0)  # Offset column (fixed)
        self.container.grid_columnconfigure(1, weight=0)  # Hex view (fixed width)
        self.container.grid_columnconfigure(2, weight=0)  # ASCII view (fixed width)
        self.container.grid_columnconfigure(3, weight=0)  # Scrollbar (fixed)
        self.container.grid_columnconfigure(4, weight=1)  # Info panel (expands)
        self.container.grid_rowconfigure(0, weight=0)     # Labels
        self.container.grid_rowconfigure(1, weight=0)     # Column headers
        self.container.grid_rowconfigure(2, weight=1)     # Content
        
        mono_font = ('Consolas', 10)
        header_font = ('Consolas', 9)
        
        # Labels for sections
        hex_label = Label(
            self.container, 
            text="HEX VIEW", 
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9, 'bold')
        )
        hex_label.grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 3))
        
        ascii_label = Label(
            self.container,
            text="ASCII",
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9, 'bold')
        )
        ascii_label.grid(row=0, column=2, sticky=W, pady=(0, 3))
        
        info_label = Label(
            self.container,
            text="FIELD DETAILS",
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9, 'bold')
        )
        info_label.grid(row=0, column=4, sticky=W, padx=(15, 0), pady=(0, 3))
        
        # Column headers row — use same mono_font as content to ensure pixel-perfect alignment
        # Offset column header
        offset_header = Label(
            self.container,
            text="  Offset  ",
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.TEXT_LIGHT,
            font=mono_font,
            anchor=W,
            padx=6,
            pady=3,
            relief='flat',
            bd=0
        )
        offset_header.grid(row=1, column=0, sticky=E+W+N+S)
        
        # Hex column header (00 01 02 ... 0F)
        # padx must match textWidget's padx (6) for column alignment
        hex_header_text = " ".join(f"{i:02X}" for i in range(16))
        hex_column_header = Label(
            self.container,
            text=hex_header_text,
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.TEXT_LIGHT,
            font=mono_font,
            anchor=W,
            padx=6,
            pady=3,
            relief='flat',
            bd=0
        )
        hex_column_header.grid(row=1, column=1, sticky=E+W+N+S)
        
        # ASCII column header (0123456789ABCDEF)
        # padx must match asciiText's padx (6) for column alignment
        ascii_header_text = "0123456789ABCDEF"
        ascii_column_header = Label(
            self.container,
            text=ascii_header_text,
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.TEXT_LIGHT,
            font=mono_font,
            anchor=W,
            padx=6,
            pady=3,
            relief='flat',
            bd=0
        )
        ascii_column_header.grid(row=1, column=2, sticky=E+W+N+S)

        # Offset/index column (row numbers)
        self.offsetText = Text(
            self.container,
            exportselection=False,
            width=10,
            height=38,
            font=mono_font,
            padx=6,
            pady=12,
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.TEXT_LIGHT,
            relief='flat',
            bd=0,
            state='disabled',
            cursor='arrow',
            highlightthickness=0,
            takefocus=0
        )
        self.offsetText.grid(row=2, column=0, sticky=N+S)

        # Hex view text widget - dark theme with modern colors
        self.textWidget = Text(
            self.container,
            exportselection=False,
            width=52,
            height=38,
            font=mono_font,
            padx=6,
            pady=12,
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.HEX_FG,
            relief='flat',
            bd=0,
            insertbackground=ModernTheme.HEX_FG,
            selectbackground=ModernTheme.SELECTION_BG,
            selectforeground=ModernTheme.TEXT_PRIMARY,
            highlightthickness=0,
            highlightbackground=ModernTheme.BORDER,
            highlightcolor=ModernTheme.BORDER_FOCUS
        )

        # Scrollbar with modern styling
        self.scrollbar = ttk.Scrollbar(
            self.container,
            command=self.yscroll,
            style="Modern.Vertical.TScrollbar"
        )

        # Info panel - light theme with HTML support
        self.popupText = HTMLText(
            self.container,
            width=40,
            height=38,
            font=('Segoe UI', 10),
            padx=15,
            pady=15,
            bg=ModernTheme.BG_SECONDARY,
            relief='flat',
            bd=0,
            highlightthickness=1,
            highlightbackground=ModernTheme.BORDER,
            highlightcolor=ModernTheme.BORDER_FOCUS
        )
        
        # ASCII view text widget
        self.asciiText = Text(
            self.container,
            exportselection=False,
            width=18,
            height=38,
            font=mono_font,
            padx=6,
            pady=12,
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.ASCII_FG,
            relief='flat',
            bd=0,
            insertbackground=ModernTheme.ASCII_FG,
            selectbackground=ModernTheme.SELECTION_BG,
            selectforeground=ModernTheme.TEXT_PRIMARY,
            highlightthickness=0,
            highlightbackground=ModernTheme.BORDER,
            highlightcolor=ModernTheme.BORDER_FOCUS
        )

        # Only textWidget drives the scrollbar position — this avoids
        # two widgets fighting over scrollbar.set and causing jitter
        self.textWidget.configure(yscrollcommand=self._on_textwidget_scroll)

        # Grid layout - hex and ASCII are fixed width (sticky=N+S only), info panel expands
        self.textWidget.grid(row=2, column=1, sticky=N+S)
        self.asciiText.grid(row=2, column=2, sticky=N+S)
        self.scrollbar.grid(row=2, column=3, sticky=N+S, padx=2)
        self.popupText.grid(row=2, column=4, sticky=N+S+E+W, padx=(10, 0))

        # Selection styling
        self.textWidget.tag_configure(
            "sel", background=ModernTheme.SELECTION_BG, foreground=ModernTheme.TEXT_PRIMARY)
        self.asciiText.tag_configure(
            "sel", background=ModernTheme.SELECTION_BG, foreground=ModernTheme.TEXT_PRIMARY)

        # Link mouse wheel scrolling for all panes
        self.textWidget.bind("<MouseWheel>", self.scrollBoth)
        self.asciiText.bind("<MouseWheel>", self.scrollBoth)
        self.offsetText.bind("<MouseWheel>", self.scrollBoth)

    def _on_textwidget_scroll(self, *args):
        """Callback for textWidget's yscrollcommand — keeps the scrollbar
        and the sibling panes (ASCII, offset) in sync with the hex view.
        This is the single source of truth for vertical scroll position."""
        self.scrollbar.set(*args)
        # Sync the other two panes to exactly match the hex view position
        self.asciiText.yview_moveto(args[0])
        self.offsetText.configure(state='normal')
        self.offsetText.yview_moveto(args[0])
        self.offsetText.configure(state='disabled')

    def yscroll(self, *args):
        """Handle scrollbar drag — move all three text panes together.

        :param args: Scrolling arguments passed by the scrollbar widget.
        """
        self.textWidget.yview(*args)
        self.asciiText.yview(*args)
        self.offsetText.configure(state='normal')
        self.offsetText.yview(*args)
        self.offsetText.configure(state='disabled')

    def scrollBoth(self, event):
        """Handle mouse wheel scrolling — move all three text panes together.

        On Windows, event.delta is typically ±120 per wheel notch.
        We scroll 3 lines per notch for smooth, responsive feel.

        :param event: Mouse wheel event.
        """
        # Normalize: -1 for scroll down, +1 for scroll up, then scale
        direction = -1 if event.delta > 0 else 1
        scroll_lines = 3

        self.textWidget.yview("scroll", direction * scroll_lines, "units")
        self.asciiText.yview("scroll", direction * scroll_lines, "units")
        self.offsetText.configure(state='normal')
        self.offsetText.yview("scroll", direction * scroll_lines, "units")
        self.offsetText.configure(state='disabled')
        return "break"

    def update_popup_text(self, text, tag):
        """
        Update the popup text with the given text and apply the specified tag.

        :param text: The text to be displayed in the popup.
        :param tag: The tag to be applied to the text.
        """
        self.popupText.delete("1.0", "end")
        self.popupText.set_html(text)

class Main:
    """
    The main class of the application, containing the logic for the GUI layout, file parsing, and other functionalities.
    Modern design with soft colors and clean layout.
    """

    def __init__(self, master):
        """
        Initialize the main application window with widgets and layout configurations.

        :param master: The parent widget for this application.
        """
        self.master = master
        self.bookmark_treeview = None
        self.bookmark_window = None
        self.bookmarks = []  # Store bookmarks as list of {name, offset, comment} dicts
        self.file_hash = None  # SHA-256 hash of the currently loaded file
        
        # Maximum character width for the Value column in the treeview
        self.VALUE_COLUMN_MAX_WIDTH = 40
        
        # Set up modern styling
        self.style = setup_modern_style()
        
        # Configure master background
        master.configure(bg=ModernTheme.BG_PRIMARY)

        # ========== MENU BAR ==========
        # Centralizes all actions previously spread across buttons,
        # freeing sidebar space for the parsed fields treeview.
        self._create_menu_bar()

        # Configure rows and columns in the master frame
        master.grid_rowconfigure(0, weight=0)  # Header row
        master.grid_rowconfigure(1, weight=1)  # Main content row
        master.grid_rowconfigure(2, weight=0)  # Status bar row

        master.grid_columnconfigure(0, weight=1)  # Content area (hex/ASCII fixed, info panel expands)
        master.grid_columnconfigure(1, weight=1)  # Sidebar
        
        # ========== HEADER SECTION ==========
        header_frame = Frame(master, bg=ModernTheme.BG_PRIMARY)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=E+W, padx=20, pady=(15, 0))
        header_frame.grid_columnconfigure(0, weight=1)
        
        # App title
        title_label = Label(
            header_frame,
            text="HexMarksTheSpot",
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_PRIMARY,
            font=('Segoe UI', 18, 'bold')
        )
        title_label.grid(row=0, column=0, sticky=W)
        
        subtitle_label = Label(
            header_frame,
            text="Forensic Hex File Analysis Tool",
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 10)
        )
        subtitle_label.grid(row=1, column=0, sticky=W)

        # ========== MAIN CONTENT ==========
        self.text_widget = TextWidget(master)
        
        # ========== SIDEBAR ==========
        sidebar_frame = Frame(master, bg=ModernTheme.BG_PRIMARY)
        sidebar_frame.grid(row=1, column=1, sticky=N+S+E+W, padx=(0, 20), pady=(15, 5))
        sidebar_frame.grid_rowconfigure(1, weight=1)
        sidebar_frame.grid_columnconfigure(0, weight=1)
        
        # Search section
        search_frame = Frame(sidebar_frame, bg=ModernTheme.BG_PRIMARY)
        search_frame.grid(row=0, column=0, sticky=E+W, pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)
        
        # Header row with label and offset format dropdown
        header_row = Frame(search_frame, bg=ModernTheme.BG_PRIMARY)
        header_row.grid(row=0, column=0, columnspan=2, sticky=E+W, pady=(0, 8))
        header_row.grid_columnconfigure(0, weight=1)
        
        search_label = Label(
            header_row,
            text="PARSED FIELDS",
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9, 'bold')
        )
        search_label.grid(row=0, column=0, sticky=W)
        
        # Offset format dropdown
        self.offset_format_var = StringVar(value="Hex")
        offset_format_label = Label(
            header_row,
            text="Offset:",
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 8)
        )
        offset_format_label.grid(row=0, column=1, sticky=E, padx=(5, 2))
        
        self.offset_format_combo = ttk.Combobox(
            header_row,
            textvariable=self.offset_format_var,
            values=["Hex", "Decimal"],
            state="readonly",
            style="Modern.TCombobox",
            width=8
        )
        self.offset_format_combo.grid(row=0, column=2, sticky=E)
        self.offset_format_combo.bind("<<ComboboxSelected>>", self._on_offset_format_changed)
        
        # Search scope checkboxes — let user choose which columns to search
        scope_frame = Frame(search_frame, bg=ModernTheme.BG_PRIMARY)
        scope_frame.grid(row=1, column=0, columnspan=2, sticky=W, pady=(0, 4))
        
        self.search_scope_name = BooleanVar(value=True)
        self.search_scope_value = BooleanVar(value=True)
        self.search_scope_hex = BooleanVar(value=False)
        self.search_scope_ascii = BooleanVar(value=False)
        
        scope_font = ('Segoe UI', 8)
        scope_fg = ModernTheme.TEXT_SECONDARY
        scope_bg = ModernTheme.BG_PRIMARY
        scope_active_bg = ModernTheme.BG_PRIMARY
        
        Checkbutton(scope_frame, text="Name", variable=self.search_scope_name,
                    font=scope_font, fg=scope_fg, bg=scope_bg, activebackground=scope_active_bg,
                    selectcolor=ModernTheme.BG_SECONDARY).pack(side=LEFT, padx=(0, 4))
        Checkbutton(scope_frame, text="Value", variable=self.search_scope_value,
                    font=scope_font, fg=scope_fg, bg=scope_bg, activebackground=scope_active_bg,
                    selectcolor=ModernTheme.BG_SECONDARY).pack(side=LEFT, padx=(0, 4))
        Checkbutton(scope_frame, text="Hex", variable=self.search_scope_hex,
                    font=scope_font, fg=scope_fg, bg=scope_bg, activebackground=scope_active_bg,
                    selectcolor=ModernTheme.BG_SECONDARY).pack(side=LEFT, padx=(0, 4))
        Checkbutton(scope_frame, text="ASCII", variable=self.search_scope_ascii,
                    font=scope_font, fg=scope_fg, bg=scope_bg, activebackground=scope_active_bg,
                    selectcolor=ModernTheme.BG_SECONDARY).pack(side=LEFT, padx=(0, 4))
        
        self.search_var = StringVar()
        self.search_entry = RoundedEntry(
            search_frame,
            textvariable=self.search_var,
            font=('Segoe UI', 10),
            radius=8
        )
        self.search_entry.grid(row=2, column=0, sticky=E+W, padx=(0, 5))
        self.search_entry.insert(0, "Search...")
        self.search_entry.bind("<FocusIn>", lambda e: self.search_entry.delete(0, END) if self.search_entry.get() == "Search..." else None)
        self.search_entry.bind("<FocusOut>", lambda e: self.search_entry.insert(0, "Search...") if not self.search_entry.get() else None)
        # Enter key: if search results already exist and query unchanged, advance
        # to next match; otherwise perform a new search.  Blank/placeholder clears.
        self.search_entry.bind("<Return>", lambda e: self._on_search_enter())
        # Escape key clears the search and restores all fields
        self.search_entry.bind("<Escape>", lambda e: self.clear_search())
        
        search_buttons = Frame(search_frame, bg=ModernTheme.BG_PRIMARY)
        search_buttons.grid(row=2, column=1, sticky=E)
        
        self.search_button = RoundedButton(
            search_buttons,
            text="🔍",
            command=self.search_sequence,
            style="small",
            radius=8,
            width=38,
            height=38
        )
        self.search_button.pack(side=LEFT, padx=2)
        
        self.clear_button = RoundedButton(
            search_buttons,
            text="✕",
            command=self.clear_search,
            style="small",
            radius=8,
            width=38,
            height=38
        )
        self.clear_button.pack(side=LEFT, padx=2)
        
        # Search results info row — shows match count and prev/next navigation
        results_frame = Frame(search_frame, bg=ModernTheme.BG_PRIMARY)
        results_frame.grid(row=3, column=0, columnspan=2, sticky=E+W, pady=(2, 0))
        results_frame.grid_columnconfigure(0, weight=1)
        
        self._search_results_label = Label(
            results_frame, text="", bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY, font=('Segoe UI', 8), anchor=W
        )
        self._search_results_label.grid(row=0, column=0, sticky=W)
        
        nav_frame = Frame(results_frame, bg=ModernTheme.BG_PRIMARY)
        nav_frame.grid(row=0, column=1, sticky=E)
        
        self._search_prev_btn = RoundedButton(
            nav_frame, text="▲", command=self._search_prev,
            style="small", radius=6, width=28, height=24
        )
        self._search_prev_btn.pack(side=LEFT, padx=1)
        
        self._search_next_btn = RoundedButton(
            nav_frame, text="▼", command=self._search_next,
            style="small", radius=6, width=28, height=24
        )
        self._search_next_btn.pack(side=LEFT, padx=1)
        
        # Track search match state for prev/next navigation
        self._search_match_items = []  # list of treeview item IDs from current search
        self._search_match_index = -1  # current index within matches
        self._last_search_term = ''    # tracks the last executed search query
        
        # Treeview with modern styling
        treeview_frame = Frame(sidebar_frame, bg=ModernTheme.BG_PRIMARY)
        treeview_frame.grid(row=1, column=0, sticky=N+S+E+W)
        treeview_frame.grid_rowconfigure(0, weight=1)
        treeview_frame.grid_columnconfigure(0, weight=1)
        
        self.sequence_treeview = ttk.Treeview(
            treeview_frame,
            columns=('Offset', 'Name', 'Value'),
            style="Modern.Treeview",
            show="headings"
        )
        self.sequence_treeview.heading('Offset', text='Offset', anchor=W)
        self.sequence_treeview.heading('Name', text='Name', anchor=W)
        self.sequence_treeview.heading('Value', text='Value', anchor=W)
        
        self.sequence_treeview.column('Offset', width=60, minwidth=50, anchor=W)
        self.sequence_treeview.column('Name', width=120, minwidth=80, anchor=W)
        self.sequence_treeview.column('Value', width=150, minwidth=100, anchor=W)
        
        self.sequence_treeview.grid(row=0, column=0, sticky=N+S+E+W)
        
        # Vertical scrollbar for treeview
        self.sequence_vscrollbar = ttk.Scrollbar(
            treeview_frame,
            orient="vertical",
            style="Modern.Vertical.TScrollbar"
        )
        self.sequence_vscrollbar.grid(row=0, column=1, sticky=N+S)
        self.sequence_treeview.configure(yscrollcommand=self._treeview_yscroll_callback)
        self.sequence_vscrollbar.config(command=self.sequence_treeview.yview)
        
        # Horizontal scrollbar for treeview
        self.sequence_hscrollbar = ttk.Scrollbar(
            treeview_frame,
            orient="horizontal",
            style="Modern.Horizontal.TScrollbar"
        )
        self.sequence_hscrollbar.grid(row=1, column=0, sticky=E+W)
        self.sequence_treeview.configure(xscrollcommand=self.sequence_hscrollbar.set)
        self.sequence_hscrollbar.config(command=self.sequence_treeview.xview)
        
        # Action buttons — only primary actions kept in sidebar;
        # all other actions moved to the menu bar for a cleaner layout.
        actions_frame = Frame(sidebar_frame, bg=ModernTheme.BG_PRIMARY)
        actions_frame.grid(row=2, column=0, sticky=E+W+S, pady=(10, 0))
        actions_frame.grid_columnconfigure(0, weight=1)
        actions_frame.grid_columnconfigure(1, weight=1)
        
        # Open File and Stop buttons (primary actions)
        self.open_button = RoundedButton(
            actions_frame,
            text="📂 Open File",
            command=self.open_file,
            style="primary",
            radius=10
        )
        self.open_button.grid(row=0, column=0, sticky=E+W, padx=(0, 5), pady=3)
        
        self.stop_parsing = False
        self.stop_button = RoundedButton(
            actions_frame,
            text="⏹ Stop",
            command=self.stop,
            state="disabled",
            style="danger",
            radius=10
        )
        self.stop_button.grid(row=0, column=1, sticky=E+W, padx=(5, 0), pady=3)
        
        # ========== STATUS BAR ==========
        status_frame = Frame(master, bg=ModernTheme.BG_SECONDARY)
        status_frame.grid(row=2, column=0, columnspan=2, sticky=E+W+S)
        status_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_var = DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            style="Modern.Horizontal.TProgressbar",
            mode="determinate"
        )
        self.progress_bar.grid(row=0, column=0, sticky=E+W)
        
        # Progress percentage label (shown during loading)
        self.progress_percent_var = StringVar()
        self.progress_percent_label = Label(
            status_frame,
            textvariable=self.progress_percent_var,
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.ACCENT_PRIMARY,
            font=('Segoe UI', 9, 'bold'),
            padx=10
        )
        # Will be shown during loading
        
        self.progress_message = StringVar()
        self.status_bar = Label(
            status_frame,
            textvariable=self.progress_message,
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9),
            anchor=W,
            padx=20,
            pady=8
        )
        self.status_bar.grid(row=1, column=0, sticky=E+W)
        
        # Progress tracking variables
        self.last_progress_milestone = 0
        self.loading_start_time = None

        self.last_clicked = None
        
        # Store original sequence items for search
        self.sequence_items = []
        
        # Mappings for click synchronization
        self.tag_to_treeview_item = {}  # tag -> treeview item id
        self.tag_to_child = {}           # tag -> child Node
        self.offset_to_tag = {}          # offset -> tag (first tag at that offset)
        self.current_highlight_tag = None  # Currently highlighted tag
        
        # Treeview border highlight (4 thin frames forming a black border)
        self._highlight_item_id = None
        self._border_frames = []
        # Parent container border highlight (4 thin frames, colored border)
        self._parent_highlight_item_id = None
        self._parent_border_frames = []
        self._current_parent_highlight_tag = None
        self._current_parent_sibling_tags = []
        self._tag_to_parent_tag = {}
        self._parent_tag_to_children = {}
        self._from_hex_click = False  # Flag to prevent scroll loop on hex click
        
        # Raw offset storage for format switching
        self._item_raw_offsets = {}  # treeview item_id -> raw int offset
        
        # Don't start in fullscreen by default for better usability
        # self.master.attributes("-fullscreen", True)
        
        # Set a reasonable default window size
        self.master.geometry("1400x900")
        self.master.minsize(1200, 700)

        # Allow toggling fullscreen mode with F11
        self.master.bind("<F11>", self.toggle_fullscreen)
        
        # Bind treeview selection
        self.sequence_treeview.bind("<<TreeviewSelect>>", self.listbox_item_selected)
        
        # Right-click context menu for treeview
        self._treeview_context_menu = self._create_treeview_context_menu()
        self.sequence_treeview.bind("<Button-3>", self._show_treeview_context_menu)
        
        # Keyboard shortcuts for copy operations
        self.master.bind("<Control-Shift-H>", self.copy_as_hex)
        self.master.bind("<Control-Shift-D>", self.copy_as_decimal)
        self.master.bind("<Control-Shift-A>", self.copy_as_ascii)
        self.master.bind("<Control-Shift-V>", self.copy_as_parsed_value)
        
        # Bind scroll/resize events to update treeview highlight border position
        # (both the selection border and the parent container border)
        self.sequence_treeview.bind('<Configure>', lambda e: self.master.after_idle(self._update_all_treeview_borders))
        self.sequence_treeview.bind('<MouseWheel>', lambda e: self.master.after(10, self._update_all_treeview_borders))

    def _create_menu_bar(self):
        """Create the application menu bar (File, Edit, View, Help).
        
        Centralizes actions that were previously spread across sidebar buttons,
        freeing vertical space for the parsed fields treeview.
        """
        menubar = tk_Menu(self.master, bg=ModernTheme.BG_SECONDARY,
                          fg=ModernTheme.TEXT_PRIMARY,
                          activebackground=ModernTheme.ACCENT_PRIMARY,
                          activeforeground='white',
                          relief='flat', bd=0)
        
        # --- File menu ---
        file_menu = tk_Menu(menubar, tearoff=0,
                            bg=ModernTheme.BG_SECONDARY,
                            fg=ModernTheme.TEXT_PRIMARY,
                            activebackground=ModernTheme.ACCENT_PRIMARY,
                            activeforeground='white')
        file_menu.add_command(label="Open File...", command=self.open_file,
                              accelerator="")
        file_menu.add_command(label="Import Hex Text...", command=self.import_hex_text)
        file_menu.add_separator()
        file_menu.add_command(label="Export CSV...", command=self.export_to_csv)
        file_menu.add_command(label="Export Hex Dump...", command=self.export_as_hex_txt)
        file_menu.add_separator()
        file_menu.add_command(label="File Info", command=self.show_file_info)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_app)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # --- Edit menu ---
        edit_menu = tk_Menu(menubar, tearoff=0,
                            bg=ModernTheme.BG_SECONDARY,
                            fg=ModernTheme.TEXT_PRIMARY,
                            activebackground=ModernTheme.ACCENT_PRIMARY,
                            activeforeground='white')
        edit_menu.add_command(label="Copy as Hex", command=self.copy_as_hex,
                              accelerator="Ctrl+Shift+H")
        edit_menu.add_command(label="Copy as Decimal", command=self.copy_as_decimal,
                              accelerator="Ctrl+Shift+D")
        edit_menu.add_command(label="Copy as ASCII", command=self.copy_as_ascii,
                              accelerator="Ctrl+Shift+A")
        edit_menu.add_command(label="Copy Parsed Value", command=self.copy_as_parsed_value,
                              accelerator="Ctrl+Shift+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Add Bookmark", command=self.add_bookmark)
        edit_menu.add_command(label="Bookmarks...", command=self.show_bookmarks)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # --- View menu ---
        view_menu = tk_Menu(menubar, tearoff=0,
                            bg=ModernTheme.BG_SECONDARY,
                            fg=ModernTheme.TEXT_PRIMARY,
                            activebackground=ModernTheme.ACCENT_PRIMARY,
                            activeforeground='white')
        view_menu.add_command(label="Toggle Fullscreen", command=self.toggle_fullscreen,
                              accelerator="F11")
        menubar.add_cascade(label="View", menu=view_menu)
        
        # --- Help menu ---
        help_menu = tk_Menu(menubar, tearoff=0,
                            bg=ModernTheme.BG_SECONDARY,
                            fg=ModernTheme.TEXT_PRIMARY,
                            activebackground=ModernTheme.ACCENT_PRIMARY,
                            activeforeground='white')
        help_menu.add_command(label="About HexMarksTheSpot", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.master.config(menu=menubar)

    def _show_about(self):
        """Show the About dialog with app version and description."""
        messagebox.showinfo(
            "About HexMarksTheSpot",
            "HexMarksTheSpot\n\n"
            "Forensic Hex File Analysis Tool\n\n"
            "A Python-based hex file analysis and annotation tool\n"
            "for digital forensics. Parse binary file formats using\n"
            "declarative JSON configurations and visualize their\n"
            "structure with color-coded hex highlighting.\n\n"
            "github.com/bittib010/HexMarksTheSpot",
            parent=self.master
        )

    def export_to_csv(self):
        # Ask the user where to save the CSV file
        filename = filedialog.asksaveasfilename(defaultextension=".csv", 
                                                filetypes=[("CSV files", "*.csv")])
        if filename:
            with open(filename, "w", newline="") as csvfile:
                csvwriter = csv.writer(csvfile)
                # Write the headers
                csvwriter.writerow(["Offset", "Name", "Value"])
                # Iterate through the Treeview items and write them to the CSV
                for item in self.sequence_treeview.get_children():
                    item_data = self.sequence_treeview.item(item)
                    csvwriter.writerow([item_data['values'][0], item_data['values'][1], item_data['values'][2], item_data.get('value', '')])

    def export_as_hex_txt(self):
        """Export the currently loaded file as a hex dump to a .txt file.
        
        Format: standard hex dump with offset, hex bytes, and ASCII representation.
        Example line: 00000000  4C 00 00 00 01 14 02 00  00 00 00 00 C0 00 00 00  |L...............|
        """
        if not hasattr(self, 'current_file') or not self.current_file:
            self.update_status("No file loaded")
            return
        
        default_name = os.path.splitext(os.path.basename(self.current_file))[0] + "_hexdump.txt"
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name,
            title="Export Hex Dump"
        )
        if not filename:
            return
        
        try:
            with open(self.current_file, 'rb') as infile:
                data = infile.read()
            
            lines = []
            for offset in range(0, len(data), 16):
                chunk = data[offset:offset + 16]
                # Offset column
                hex_offset = f"{offset:08X}"
                # Hex bytes in two groups of 8
                hex_left = ' '.join(f'{b:02X}' for b in chunk[:8])
                hex_right = ' '.join(f'{b:02X}' for b in chunk[8:])
                hex_part = f"{hex_left:<23s}  {hex_right:<23s}"
                # ASCII representation
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                lines.append(f"{hex_offset}  {hex_part}  |{ascii_part}|")
            
            with open(filename, 'w') as outfile:
                outfile.write('\n'.join(lines))
                outfile.write('\n')
            
            self.update_status(f"Hex dump exported to {os.path.basename(filename)} ({len(data):,} bytes)")
        except Exception as e:
            self.update_status(f"Export failed: {e}")

    def import_hex_text(self):
        """Import a hex text file, decode it to binary bytes, and parse the result.
        
        Accepts text files containing hex data in common formats:
        - Raw hex: "4D5A9000..."
        - Spaced hex: "4D 5A 90 00..."
        - Hex dump lines: "00000000  4D 5A 90 00...  |MZ...|" (offset and ASCII columns stripped)
        - 0x-prefixed: "0x4D, 0x5A, 0x90..."
        
        All non-hex characters (whitespace, offsets, ASCII sidebar, commas, 0x prefixes)
        are stripped. The remaining hex digits are decoded to bytes,
        written to a temp file, and parsed normally.
        """
        filename = filedialog.askopenfilename(
            title="Import Hex Text File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filename:
            return
        
        # Show loading overlay immediately — decoding large files can take a moment
        source_name = os.path.basename(filename)
        self.sequence_treeview.delete(*self.sequence_treeview.get_children())
        self.progress_var.set(0)
        self.progress_bar.grid(row=3, column=0, columnspan=5, sticky=W+E+S, pady=(5, 0))
        self.progress_message.set("Decoding hex...")
        self._show_loading_overlay(f"Importing hex from {source_name}...")
        self._update_loading_message(
            f"Importing hex from {source_name}...",
            "Reading and decoding hex text"
        )
        
        # Run decoding + parsing in background thread
        threading.Thread(target=self._import_hex_worker, args=(filename,)).start()

    def _import_hex_worker(self, filename):
        """Background worker for hex text import — decodes hex and triggers parse."""
        source_name = os.path.basename(filename)
        
        try:
            with open(filename, 'r', encoding='utf-8', errors='replace') as f:
                raw_text = f.read()
        except Exception as e:
            self.master.after(0, lambda: self._hide_loading_overlay())
            self.update_status(f"Failed to read file: {e}")
            return
        
        # Process each line to handle hex dump format
        # Strip offset column (leading hex + whitespace) and ASCII sidebar (|...|)
        cleaned_lines = []
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Remove ASCII sidebar: 2+ spaces then |1-16 chars| at end of line
            # Using .{1,16} anchored by "  |" avoids mismatching when | appears in hex data
            line = re.sub(r'\s{2}\|.{1,16}\|\s*$', '', line)
            # Remove hex dump offset column: "00000000  " or "0000:  " at start
            line = re.sub(r'^[0-9A-Fa-f]{4,8}:?\s{1,4}', '', line)
            cleaned_lines.append(line)
        
        cleaned = ' '.join(cleaned_lines)
        
        # Remove 0x prefixes, commas, and all non-hex characters
        cleaned = cleaned.replace('0x', '').replace('0X', '')
        cleaned = re.sub(r'[^0-9A-Fa-f]', '', cleaned)
        
        if len(cleaned) == 0:
            self.master.after(0, lambda: self._hide_loading_overlay())
            self.update_status("No hex data found in the file")
            return
        
        if len(cleaned) % 2 != 0:
            # Try to recover by trimming the last digit
            self.master.after(0, lambda: self._update_loading_message(
                "Trimming trailing nibble...",
                f"{len(cleaned):,} hex digits (odd) — dropping last digit"
            ))
            cleaned = cleaned[:-1]
        
        try:
            binary_data = bytes.fromhex(cleaned)
        except ValueError as e:
            self.master.after(0, lambda: self._hide_loading_overlay())
            self.update_status(f"Invalid hex data: {e}")
            return
        
        if len(binary_data) == 0:
            self.master.after(0, lambda: self._hide_loading_overlay())
            self.update_status("Hex text decoded to 0 bytes")
            return
        
        # Write to a temp file and parse it
        source_basename = os.path.splitext(source_name)[0]
        try:
            temp_dir = tempfile.mkdtemp(prefix="hexmarks_")
            temp_path = os.path.join(temp_dir, source_basename + ".bin")
            with open(temp_path, 'wb') as f:
                f.write(binary_data)
        except Exception as e:
            self.master.after(0, lambda: self._hide_loading_overlay())
            self.update_status(f"Failed to create temp file: {e}")
            return
        
        self.update_status(
            f"Imported {len(binary_data):,} bytes from {source_name} — parsing..."
        )
        self.master.after(0, lambda: self._update_loading_message(
            "Parsing imported data...",
            f"Decoded {len(binary_data):,} bytes"
        ))
        
        # Continue with normal parse flow
        self.parse_file(temp_path)

    def exit_app(self):
        """
        Close the application window and exit the program.
        """
        self.master.quit()
        self.master.destroy()

    def _on_search_enter(self):
        """Handle Enter key in search field.
        
        If the query matches the previous search, advance to the next result.
        If the field is empty or placeholder, clear the search.
        Otherwise, run a new search.
        """
        search_term = self.search_var.get().strip()
        if not search_term or search_term == "Search...":
            self.clear_search()
            return
        if search_term == self._last_search_term and self._search_match_items:
            # Same query — just cycle to next match
            self._search_next()
        else:
            self.search_sequence()

    def search_sequence(self):
        """
        Search fields across selected scopes (Name, Value, Hex, ASCII).
        Filters the treeview to show only matching items, with match count
        and prev/next navigation.
        """
        search_term = self.search_var.get().strip()
        if not search_term or search_term == "Search...":
            self.clear_search()
            return
        
        search_lower = search_term.lower()
        # For hex search, also prepare a no-space uppercase version so users
        # can search for "4D5A" or "4D 5A" and both match
        search_hex_upper = search_term.upper().replace(' ', '')
        
        check_name = self.search_scope_name.get()
        check_value = self.search_scope_value.get()
        check_hex = self.search_scope_hex.get()
        check_ascii = self.search_scope_ascii.get()
        
        # If no scope selected, default to searching name + value
        if not any([check_name, check_value, check_hex, check_ascii]):
            check_name = True
            check_value = True
        
        matching_items = []
        for item in self.sequence_items:
            data_tuple = item[0]
            # Unpack — handles both old 3-tuple and new 5-tuple formats
            offset, name, table_val = data_tuple[0], data_tuple[1], data_tuple[2]
            hex_str = data_tuple[3] if len(data_tuple) > 3 else ''
            ascii_str = data_tuple[4] if len(data_tuple) > 4 else ''
            
            matched = False
            if check_name and name and search_lower in name.lower():
                matched = True
            if not matched and check_value and table_val is not None:
                if search_lower in str(table_val).lower():
                    matched = True
            if not matched and check_hex and hex_str:
                # Match with and without spaces for flexible hex search
                if search_hex_upper in hex_str.replace(' ', ''):
                    matched = True
            if not matched and check_ascii and ascii_str:
                if search_lower in ascii_str.lower():
                    matched = True
            
            if matched:
                matching_items.append(item)
        
        # Rebuild the treeview with matching items
        self.sequence_treeview.delete(*self.sequence_treeview.get_children())
        self._search_match_items = []
        for data_tuple, tags in matching_items:
            raw_offset = data_tuple[0]
            name = data_tuple[1]
            table_val = data_tuple[2]
            display_offset = self._format_offset(raw_offset)
            item_id = self.sequence_treeview.insert('', 'end', values=(
                display_offset, name, self._truncate_value(table_val)), tags=tags)
            self._item_raw_offsets[item_id] = raw_offset
            self._search_match_items.append(item_id)
        
        # Update results label and reset navigation index
        total = len(self.sequence_items)
        found = len(matching_items)
        self._search_results_label.config(text=f"{found} of {total} fields")
        self._search_match_index = 0 if found > 0 else -1
        self._last_search_term = search_term
        
        # Auto-select and scroll to the first match
        if self._search_match_items:
            first = self._search_match_items[0]
            self.sequence_treeview.selection_set(first)
            self.sequence_treeview.see(first)

    def clear_search(self):
        """Clear the search filter and restore all items in the treeview."""
        self.search_var.set('')
        self._search_results_label.config(text="")
        self._search_match_items = []
        self._search_match_index = -1
        self._last_search_term = ''
        self.sequence_treeview.delete(*self.sequence_treeview.get_children())
        for data_tuple, tags in self.sequence_items:
            raw_offset = data_tuple[0]
            name = data_tuple[1]
            table_val = data_tuple[2]
            display_offset = self._format_offset(raw_offset)
            item_id = self.sequence_treeview.insert('', 'end', values=(
                display_offset, name, self._truncate_value(table_val)), tags=tags)
            self._item_raw_offsets[item_id] = raw_offset

    def _search_prev(self):
        """Navigate to the previous search result in the treeview."""
        if not self._search_match_items:
            return
        self._search_match_index = (self._search_match_index - 1) % len(self._search_match_items)
        item_id = self._search_match_items[self._search_match_index]
        self.sequence_treeview.selection_set(item_id)
        self.sequence_treeview.see(item_id)
        n = len(self._search_match_items)
        self._search_results_label.config(
            text=f"{self._search_match_index + 1}/{n} of {len(self.sequence_items)} fields")

    def _search_next(self):
        """Navigate to the next search result in the treeview."""
        if not self._search_match_items:
            return
        self._search_match_index = (self._search_match_index + 1) % len(self._search_match_items)
        item_id = self._search_match_items[self._search_match_index]
        self.sequence_treeview.selection_set(item_id)
        self.sequence_treeview.see(item_id)
        n = len(self._search_match_items)
        self._search_results_label.config(
            text=f"{self._search_match_index + 1}/{n} of {len(self.sequence_items)} fields")

    def get_complementary_color(hex_color):
        # TODO: add posibility to change text color to this to avoid "hiding" text in same color
        hex_color = hex_color.lstrip("#")
        # Convert the hex color to RGB
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        # Calculate the complementary color
        comp_r, comp_g, comp_b = 255 - r, 255 - g, 255 - b
        # Convert the complementary color back to hex
        comp_hex = "#{:02X}{:02X}{:02X}".format(comp_r, comp_g, comp_b)
        return comp_hex
    
    def toggle_fullscreen(self, event=None):
        """
        Toggle fullscreen mode on or off.

        :param event: Optional event object, not used in this method.
        """
        if self.master.attributes("-fullscreen"):
            self.master.attributes("-fullscreen", False)
        else:
            self.master.attributes("-fullscreen", True)

    def stop(self):
        """
        Stop the file parsing process and update the buttons' states accordingly.
        """
        self.stop_parsing = True
        self.open_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def _treeview_yscroll_callback(self, *args):
        """Wrapper for treeview yscrollcommand that also updates the highlight borders."""
        self.sequence_vscrollbar.set(*args)
        self.master.after_idle(self._update_all_treeview_borders)

    def _create_highlight_border(self):
        """Create 4 thin Frame widgets to form a black border around treeview items."""
        if self._border_frames:
            return
        for _ in range(4):  # top, bottom, left, right
            f = Frame(self.sequence_treeview, bg='black')
            self._border_frames.append(f)

    def _show_treeview_border(self, item_id):
        """Show a black border around the specified treeview item."""
        self._create_highlight_border()
        self._highlight_item_id = item_id
        # Use after_idle so bbox reflects the current layout
        self.master.after_idle(self._update_treeview_border_position)

    def _update_treeview_border_position(self):
        """Update the border frame positions based on current item bbox."""
        if not self._highlight_item_id or not self._border_frames:
            return
        try:
            bbox = self.sequence_treeview.bbox(self._highlight_item_id)
        except TclError:
            self._hide_treeview_border()
            return
        if not bbox:
            # Item scrolled out of view - hide border
            for f in self._border_frames:
                f.place_forget()
            return
        x, y, w, h = bbox
        bw = 2  # border width
        top, bottom, left, right = self._border_frames
        top.place(x=x, y=y, width=w, height=bw)
        bottom.place(x=x, y=y + h - bw, width=w, height=bw)
        left.place(x=x, y=y, width=bw, height=h)
        right.place(x=x + w - bw, y=y, width=bw, height=h)

    def _hide_treeview_border(self):
        """Hide the treeview item border."""
        for f in self._border_frames:
            f.place_forget()
        self._highlight_item_id = None

    def _update_all_treeview_borders(self):
        """Update both selection and parent border positions (called on scroll/resize)."""
        self._update_treeview_border_position()
        self._update_parent_treeview_border_position()

    def _create_parent_highlight_border(self, color='#FFFFFF'):
        """Create 4 thin Frame widgets for a white parent border in the treeview.
        
        Uses white to contrast with the black selection border, making it
        immediately clear which treeview row is the parent container.
        """
        # Destroy old frames if they exist
        for f in self._parent_border_frames:
            f.destroy()
        self._parent_border_frames = []
        for _ in range(4):  # top, bottom, left, right
            f = Frame(self.sequence_treeview, bg=color)
            self._parent_border_frames.append(f)

    def _show_parent_treeview_border(self, item_id, color='#FFFFFF'):
        """Show a white border around the parent container's treeview item.
        
        White contrasts with the black selection border, making the parent
        container immediately visible alongside the selected child.
        """
        self._create_parent_highlight_border(color)
        self._parent_highlight_item_id = item_id
        self.master.after_idle(self._update_parent_treeview_border_position)

    def _update_parent_treeview_border_position(self):
        """Update the parent border frame positions based on current item bbox."""
        if not self._parent_highlight_item_id or not self._parent_border_frames:
            return
        try:
            bbox = self.sequence_treeview.bbox(self._parent_highlight_item_id)
        except TclError:
            self._hide_parent_treeview_border()
            return
        if not bbox:
            for f in self._parent_border_frames:
                f.place_forget()
            return
        x, y, w, h = bbox
        bw = 3  # border width (thicker than selection border for visibility)
        top, bottom, left, right = self._parent_border_frames
        top.place(x=x, y=y, width=w, height=bw)
        bottom.place(x=x, y=y + h - bw, width=w, height=bw)
        left.place(x=x, y=y, width=bw, height=h)
        right.place(x=x + w - bw, y=y, width=bw, height=h)

    def _hide_parent_treeview_border(self):
        """Hide the parent container treeview border."""
        for f in self._parent_border_frames:
            f.place_forget()
        self._parent_highlight_item_id = None

    def _format_offset(self, offset):
        """Format an integer offset based on the current display preference."""
        try:
            offset = int(offset)
        except (ValueError, TypeError):
            return str(offset)
        if self.offset_format_var.get() == "Hex":
            return f"0x{offset:X}"
        return str(offset)

    def _truncate_value(self, value):
        """Truncate a value string to the configured max width for the Value column.
        
        Values longer than VALUE_COLUMN_MAX_WIDTH are truncated with an ellipsis.
        The full value is still available in the Description pane on click.
        """
        s = str(value)
        if len(s) > self.VALUE_COLUMN_MAX_WIDTH:
            return s[:self.VALUE_COLUMN_MAX_WIDTH - 1] + '\u2026'
        return s

    def _parse_offset(self, value):
        """Parse an offset string back to an integer, handling both hex and decimal formats."""
        s = str(value).strip()
        if s.startswith("0x") or s.startswith("0X"):
            return int(s, 16)
        return int(s)

    def _on_offset_format_changed(self, event=None):
        """Re-format all offsets in the treeview and hex viewer when the dropdown changes."""
        # Update treeview offsets
        for item_id in self.sequence_treeview.get_children():
            if item_id in self._item_raw_offsets:
                raw = self._item_raw_offsets[item_id]
                current = self.sequence_treeview.item(item_id, 'values')
                self.sequence_treeview.item(
                    item_id, values=(self._format_offset(raw), current[1], current[2]))
        
        # Update hex viewer offset column
        self._refresh_viewer_offsets()

    def _format_viewer_offset(self, byte_offset):
        """Format a byte offset for the hex viewer's offset column."""
        if self.offset_format_var.get() == "Hex":
            return f"{byte_offset:08X}"
        return str(byte_offset).rjust(10)

    def _refresh_viewer_offsets(self):
        """Rewrite all offset lines in the hex viewer to match current format preference."""
        self.text_widget.offsetText.configure(state='normal')
        content = self.text_widget.offsetText.get('1.0', 'end-1c')
        lines = content.split('\n')
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            self.text_widget.offsetText.configure(state='disabled')
            return
        
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                new_lines.append('')
                continue
            # Parse the existing offset value (could be hex or decimal)
            try:
                if stripped.startswith('0x') or stripped.startswith('0X'):
                    val = int(stripped, 16)
                else:
                    val = int(stripped, 16) if all(c in '0123456789abcdefABCDEF' for c in stripped) and len(stripped) == 8 else int(stripped)
            except ValueError:
                new_lines.append(line)
                continue
            new_lines.append(self._format_viewer_offset(val))
        
        self.text_widget.offsetText.delete('1.0', 'end')
        self.text_widget.offsetText.insert('1.0', '\n'.join(new_lines))
        self.text_widget.offsetText.configure(state='disabled')

    def listbox_item_selected(self, event):
        """
        Handle the selection event in the sequence treeview.
        Scrolls to the corresponding hex position, highlights it, and shows the description.

        :param event: Event object containing information about the selection event.
        """
        # Get selected index
        selected = self.sequence_treeview.selection()
        if selected:
            item = self.sequence_treeview.item(selected)
            offset = self._parse_offset(item['values'][0])
            tags = item.get('tags', ())
            
            # Resolve the tag first so we can use display_pos for scrolling
            tag = None
            if tags:
                if isinstance(tags, (list, tuple)) and len(tags) > 0:
                    tag = tags[0]
                else:
                    tag = str(tags)
            
            # Only scroll hex view if the selection came from treeview click,
            # not from a hex viewer click (avoids scroll jump loop)
            if not self._from_hex_click:
                # Use display position (byte_counter at time of insertion) for scroll calc
                # This correctly maps to where the bytes are in the hex widget
                display_pos = self.tag_to_display_pos.get(tag, offset) if tag else offset
                
                # Calculate the corresponding row and column in the Text widget
                row = display_pos // 16 + 1  # Text widget indices start from 1
                col_hex = (display_pos % 16) * 3
                col_ascii = display_pos % 16
                
                # Scroll both views to the selected position
                self.text_widget.textWidget.see(f"{row}.{col_hex}")
                self.text_widget.asciiText.see(f"{row}.{col_ascii}")
            self._from_hex_click = False
            
            # Show black border around the selected treeview item
            self._show_treeview_border(selected[0])
            
            # Highlight the corresponding hex bytes
            if tag:
                self._highlight_tag(tag)
                
                # Show description in the info panel if we have the child node
                if tag in self.tag_to_child:
                    child = self.tag_to_child[tag]
                    self.last_clicked = child
                    self.popItUp(self._get_info_with_parent_context(child.info, tag), tag)
                    
                    # Update status bar with offset info
                    if hasattr(self, 'current_file') and self.current_file:
                        self.status_bar.config(
                            text=f"File: {self.current_file}\t\tOffset: {self._format_offset(offset)}  (Dec: {offset}  Hex: 0x{offset:X})")

    def show_bookmarks(self):
        """
        Display the bookmarks window containing the saved bookmarks.
        """
        # Create or raise the bookmark window
        if self.bookmark_window is not None and self.bookmark_window.winfo_exists():
            self.bookmark_window.lift()
            return
            
        self.bookmark_window = Toplevel(self.master)
        self.bookmark_window.title("Bookmarks")
        self.bookmark_window.geometry("750x500")
        self.bookmark_window.configure(bg=ModernTheme.BG_PRIMARY)
        
        # Header
        header = Label(
            self.bookmark_window,
            text="Saved Bookmarks",
            font=('Segoe UI', 12, 'bold'),
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_PRIMARY
        )
        header.pack(pady=(15, 10))
        
        self.bookmark_treeview = ttk.Treeview(
            self.bookmark_window, columns=('Name', 'Offset', 'Value', 'Comment'),
            style="Modern.Treeview", show="headings")
        self.bookmark_treeview.heading('Name', text='Name')
        self.bookmark_treeview.heading('Offset', text='Offset')
        self.bookmark_treeview.heading('Value', text='Value')
        self.bookmark_treeview.heading('Comment', text='Comment')
        self.bookmark_treeview.column('Name', width=180)
        self.bookmark_treeview.column('Offset', width=80)
        self.bookmark_treeview.column('Value', width=180)
        self.bookmark_treeview.column('Comment', width=250)
        self.bookmark_treeview.pack(fill=BOTH, expand=True, padx=15, pady=(0, 10))
        
        # Populate with existing bookmarks
        for bm in self.bookmarks:
            val = bm.get('value', '')
            truncated = self._truncate_value(val) if val else ''
            self.bookmark_treeview.insert('', 'end', values=(
                bm['name'], self._format_offset(bm['offset']),
                truncated, bm.get('comment', '')))
        
        # Bind the selection event
        self.bookmark_treeview.bind(
            "<<TreeviewSelect>>", self.bookmark_item_selected)
        # Double-click to edit comment
        self.bookmark_treeview.bind("<Double-1>", self._edit_bookmark_comment)
        
        # Button row
        btn_frame = Frame(self.bookmark_window, bg=ModernTheme.BG_PRIMARY)
        btn_frame.pack(fill=X, padx=15, pady=(0, 15))
        
        delete_btn = RoundedButton(
            btn_frame, text="Delete Selected", command=self.delete_bookmark,
            style="secondary", radius=10, height=36)
        delete_btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        
        export_btn = RoundedButton(
            btn_frame, text="Export Bookmarks", command=self._export_bookmarks,
            style="secondary", radius=10, height=36)
        export_btn.pack(side=LEFT, fill=X, expand=True, padx=(5, 0))
    
    def delete_bookmark(self):
        """Delete the selected bookmark."""
        if self.bookmark_treeview is None:
            return
        selected = self.bookmark_treeview.selection()
        if selected:
            item = self.bookmark_treeview.item(selected)
            name = item['values'][0]
            raw_offset = self._parse_offset(item['values'][1])
            # Remove from bookmarks list (stored as dicts)
            self.bookmarks = [
                bm for bm in self.bookmarks
                if not (bm['name'] == name and bm['offset'] == raw_offset)
            ]
            # Remove from treeview
            self.bookmark_treeview.delete(selected)
            self._save_bookmarks_to_cache() 
        
    def jump_to_bookmark(self, event):
        """
        Scroll to the offset of the selected bookmark.

        :param event: Event object containing information about the selection event.
        """
        selected = self.bookmark_treeview.selection()
        if selected:
            item = self.bookmark_treeview.item(selected)
            offset = int(item['values'][1])

            # Calculate the corresponding row and column in the Text widget
            row = offset // 16 + 1  # Adding 1 because Text widget indices start from 1
            # Every byte in hex view is 3 characters (e.g., "FF ")
            col_hex = (offset % 16) * 3
            col_ascii = offset % 16
            # Scroll both views to the selected position
            self.text_widget.textWidget.see(f"{row}.{col_hex}")
            self.text_widget.asciiText.see(f"{row}.{col_ascii}")

    def add_bookmark(self):
        """
        Add a bookmark for the selected item in the sequence treeview.
        """
        selected = self.sequence_treeview.selection()
        if not selected:
            self.update_status("Select a field to bookmark")
            return
            
        item = self.sequence_treeview.item(selected)
        values = item['values']
        if len(values) >= 2:
            raw_offset = self._parse_offset(values[0])
            name = values[1]
            # Capture the full parsed value (not truncated)
            full_value = ''
            is_raw_hex = False
            tags = item.get('tags', ())
            tag = None
            if tags:
                tag = tags[0] if isinstance(tags, (list, tuple)) and len(tags) > 0 else str(tags)
            if tag and tag in self.tag_to_child:
                node = self.tag_to_child[tag]
                full_value = str(node.table_value) if node.table_value is not None else ''
                # Detect if value is just raw hex (unparsed bytes)
                if node.data and full_value == node.data.hex():
                    is_raw_hex = True
            elif len(values) >= 3:
                full_value = str(values[2])
            
            display_offset = self._format_offset(raw_offset)
            
            # Check if already bookmarked
            already = any(
                bm['name'] == name and bm['offset'] == raw_offset
                for bm in self.bookmarks
            )
            if not already:
                bookmark = {'name': name, 'offset': raw_offset,
                            'value': full_value, 'is_raw_hex': is_raw_hex,
                            'comment': ''}
                self.bookmarks.append(bookmark)
                self.update_status(f"Bookmarked: {name} at offset {display_offset}")
                self._save_bookmarks_to_cache()
                
                # If bookmark window is open, update it
                if self.bookmark_treeview is not None and self.bookmark_window is not None:
                    try:
                        if self.bookmark_window.winfo_exists():
                            truncated = self._truncate_value(full_value) if full_value else ''
                            self.bookmark_treeview.insert(
                                '', 'end', values=(name, display_offset, truncated, ''))
                    except:
                        pass
            else:
                self.update_status(f"Already bookmarked: {name}")

    def _get_selected_node(self):
        """Get the Node object for the currently selected treeview item, or None."""
        selected = self.sequence_treeview.selection()
        if not selected:
            return None
        item = self.sequence_treeview.item(selected[0])
        tags = item.get('tags', ())
        tag = None
        if tags:
            tag = tags[0] if isinstance(tags, (list, tuple)) and len(tags) > 0 else str(tags)
        if tag and tag in self.tag_to_child:
            return self.tag_to_child[tag]
        return None

    def _copy_to_clipboard(self, text, label="Value"):
        """Copy text to the system clipboard and show a status message."""
        self.master.clipboard_clear()
        self.master.clipboard_append(text)
        # Truncate the status preview so it doesn't flood the status bar
        preview = text if len(text) <= 60 else text[:57] + '...'
        self.update_status(f"Copied {label}: {preview}")

    def copy_as_hex(self, event=None):
        """Copy the selected field's raw bytes as a hex string (e.g., '4C 00 00 00')."""
        node = self._get_selected_node()
        if not node:
            self.update_status("Select a field to copy")
            return
        if not node.data:
            self.update_status("Selected field has no data")
            return
        hex_str = ' '.join(f'{b:02X}' for b in node.data)
        self._copy_to_clipboard(hex_str, "Hex")

    def copy_as_decimal(self, event=None):
        """Copy the selected field's raw bytes as a decimal integer."""
        node = self._get_selected_node()
        if not node:
            self.update_status("Select a field to copy")
            return
        if not node.data:
            self.update_status("Selected field has no data")
            return
        # Interpret as little-endian unsigned integer (most common in forensic formats)
        val = int.from_bytes(node.data, byteorder='little', signed=False)
        self._copy_to_clipboard(str(val), "Decimal")

    def copy_as_ascii(self, event=None):
        """Copy the selected field's raw bytes as an ASCII string (non-printable as dots)."""
        node = self._get_selected_node()
        if not node:
            self.update_status("Select a field to copy")
            return
        if not node.data:
            self.update_status("Selected field has no data")
            return
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in node.data)
        self._copy_to_clipboard(ascii_str, "ASCII")

    def copy_as_parsed_value(self, event=None):
        """Copy the selected field's parsed/interpreted value as shown in the Value column."""
        node = self._get_selected_node()
        if not node:
            self.update_status("Select a field to copy")
            return
        val = node.table_value if node.table_value is not None else ''
        self._copy_to_clipboard(str(val), "Parsed value")

    def _create_treeview_context_menu(self):
        """Create the right-click context menu for the parsed fields treeview."""
        menu = tk_Menu(self.master, tearoff=0)
        menu.add_command(label="Copy as Hex          Ctrl+Shift+H", command=self.copy_as_hex)
        menu.add_command(label="Copy as Decimal      Ctrl+Shift+D", command=self.copy_as_decimal)
        menu.add_command(label="Copy as ASCII        Ctrl+Shift+A", command=self.copy_as_ascii)
        menu.add_command(label="Copy Parsed Value    Ctrl+Shift+V", command=self.copy_as_parsed_value)
        menu.add_separator()
        menu.add_command(label="Bookmark", command=self.add_bookmark)
        return menu

    def _show_treeview_context_menu(self, event):
        """Show the right-click context menu on the treeview."""
        # Select the item under the cursor
        item_id = self.sequence_treeview.identify_row(event.y)
        if item_id:
            self.sequence_treeview.selection_set(item_id)
            self.sequence_treeview.focus(item_id)
            self._treeview_context_menu.tk_popup(event.x_root, event.y_root)
        self._treeview_context_menu.grab_release()

    def bookmark_item_selected(self, event):
        """
        Handle the bookmark selection event, scrolling to the corresponding position.

        :param event: Event object containing information about the selection event.
        """
        # Get selected index
        selected = self.bookmark_treeview.selection()
        if selected:
            item = self.bookmark_treeview.item(selected)
            # Columns are (Name, Offset, Comment)
            offset = self._parse_offset(item['values'][1])

            # Calculate the corresponding row and column in the Text widget
            row = offset // 16 + 1  # Adding 1 because Text widget indices start from 1
            # Every byte in hex view is 3 characters (e.g., "FF ")
            col_hex = (offset % 16) * 3
            col_ascii = offset % 16
            # Scroll both views to the selected position
            self.text_widget.textWidget.see(f"{row}.{col_hex}")
            self.text_widget.asciiText.see(f"{row}.{col_ascii}")

    def generate_file_hash(self):
        # Assuming the file is stored in self.current_file
        hash_obj = hashlib.sha256()
        with open(self.current_file, 'rb') as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    def show_file_info(self):
        """Show file information in a modal overlay within the main window."""
        if not hasattr(self, 'current_file') or not self.current_file:
            self.update_status("No file loaded")
            return
            
        # Create overlay frame that covers the entire window
        # Note: Tkinter doesn't support alpha in hex colors, use solid dark
        self.overlay = Frame(self.master, bg='#2c2c2c')
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Create modal card in the center
        modal = Frame(
            self.overlay,
            bg=ModernTheme.BG_SECONDARY,
            highlightthickness=1,
            highlightbackground=ModernTheme.BORDER,
            padx=30,
            pady=25
        )
        modal.place(relx=0.5, rely=0.5, anchor='center')
        
        # Header with title and close button
        header_frame = Frame(modal, bg=ModernTheme.BG_SECONDARY)
        header_frame.pack(fill=X, pady=(0, 20))
        
        title = Label(
            header_frame,
            text="File Information",
            font=('Segoe UI', 14, 'bold'),
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.TEXT_PRIMARY
        )
        title.pack(side=LEFT)
        
        close_btn = RoundedButton(
            header_frame,
            text="✕",
            command=self.close_file_info_modal,
            style="small",
            radius=8,
            width=36,
            height=32
        )
        close_btn.pack(side=RIGHT)
        
        # File info content
        info_frame = Frame(modal, bg=ModernTheme.BG_SECONDARY)
        info_frame.pack(fill=X)
        
        # File name
        self._add_info_row(info_frame, "File Name:", os.path.basename(self.current_file), 0)
        
        # Full path
        self._add_info_row(info_frame, "Full Path:", self.current_file, 1)
        
        # File size
        file_size = os.path.getsize(self.current_file)
        size_str = self._format_file_size(file_size)
        self._add_info_row(info_frame, "Size:", f"{size_str} ({file_size:,} bytes)", 2)
        
        # SHA-256 Hash (show loading initially, then update)
        hash_label = Label(
            info_frame,
            text="SHA-256:",
            font=('Segoe UI', 10, 'bold'),
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.TEXT_SECONDARY,
            anchor=W
        )
        hash_label.grid(row=3, column=0, sticky=W, pady=5)
        
        self.hash_value_label = Label(
            info_frame,
            text="Calculating...",
            font=('Consolas', 9),
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.TEXT_PRIMARY,
            anchor=W,
            wraplength=350
        )
        self.hash_value_label.grid(row=3, column=1, sticky=W, pady=5, padx=(10, 0))
        
        # Calculate hash in background
        threading.Thread(target=self._update_hash_display, daemon=True).start()
        
        # Parsed fields count
        if hasattr(self, 'total_nodes'):
            self._add_info_row(info_frame, "Parsed Fields:", str(self.total_nodes), 4)
        
        # Bind Escape key to close modal
        self.master.bind('<Escape>', lambda e: self.close_file_info_modal())
        
        # Click outside modal to close
        self.overlay.bind('<Button-1>', lambda e: self.close_file_info_modal() if e.widget == self.overlay else None)
    
    def _add_info_row(self, parent, label_text, value_text, row):
        """Helper to add an info row to the modal."""
        label = Label(
            parent,
            text=label_text,
            font=('Segoe UI', 10, 'bold'),
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.TEXT_SECONDARY,
            anchor=W
        )
        label.grid(row=row, column=0, sticky=W, pady=5)
        
        value = Label(
            parent,
            text=value_text,
            font=('Segoe UI', 10),
            bg=ModernTheme.BG_SECONDARY,
            fg=ModernTheme.TEXT_PRIMARY,
            anchor=W,
            wraplength=350
        )
        value.grid(row=row, column=1, sticky=W, pady=5, padx=(10, 0))
    
    def _format_file_size(self, size_bytes):
        """Format file size to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def _update_hash_display(self):
        """Update the hash display after calculation."""
        try:
            hash_value = self.generate_file_hash()
            self.master.after(0, lambda: self.hash_value_label.config(text=hash_value))
        except Exception as e:
            self.master.after(0, lambda: self.hash_value_label.config(text=f"Error: {e}"))
    
    def close_file_info_modal(self):
        """Close the file info modal overlay."""
        if hasattr(self, 'overlay') and self.overlay:
            self.master.unbind('<Escape>')
            self.overlay.destroy()
            self.overlay = None
    
    def _show_loading_overlay(self, message="Loading..."):
        """
        Initialize loading state with progress tracking.
        Uses non-blocking progress updates in the status bar.
        
        :param message: The message to display
        """
        import time as time_module
        self.loading_start_time = time_module.time()
        self.last_progress_milestone = 0
        self.last_progress_update_time = self.loading_start_time
        
        # Show progress percentage label
        self.progress_percent_var.set("0%")
        self.progress_percent_label.grid(row=0, column=1, sticky=E, padx=(0, 10))
        
        # Update status message
        self.progress_message.set(message)
        
        # Store message for updates
        self._loading_base_message = message
    
    def _animate_spinner(self):
        """Not used in non-blocking mode - kept for compatibility."""
        pass
    
    def _update_loading_message(self, message, detail=""):
        """
        Update the loading progress message.
        
        :param message: Main message to display
        :param detail: Detail text (e.g., progress info)
        """
        if detail:
            self.progress_message.set(f"{message} - {detail}")
        else:
            self.progress_message.set(message)
    
    def _update_progress_with_milestones(self, current, total):
        """
        Update progress with milestone notifications.
        Shows updates at every 10% and time estimates for long operations.
        
        :param current: Current progress count
        :param total: Total items to process
        """
        if total == 0:
            return
            
        progress = (current / total) * 100
        current_milestone = int(progress // 10) * 10
        
        # Update progress bar
        self.progress_var.set(progress)
        self.progress_percent_var.set(f"{progress:.0f}%")
        
        # Calculate elapsed and estimated time
        import time as time_module
        now = time_module.time()
        elapsed = now - self.loading_start_time
        
        # Update only at 10% milestones or when done (not every call)
        if current_milestone <= self.last_progress_milestone and current != total:
            return
        
        self.last_progress_milestone = current_milestone
        self.last_progress_update_time = now
        
        # Build status message with time info
        if elapsed > 2:  # Only show time for operations > 2 seconds
            if progress > 0:
                estimated_total = elapsed / (progress / 100)
                remaining = estimated_total - elapsed
                if remaining > 60:
                    time_str = f"~{remaining/60:.0f}m remaining"
                elif remaining > 0:
                    time_str = f"~{remaining:.0f}s remaining"
                else:
                    time_str = "Almost done..."
            else:
                time_str = "Calculating..."
            
            detail = f"{current}/{total} fields ({progress:.0f}%) - {time_str}"
        else:
            detail = f"{current}/{total} fields ({progress:.0f}%)"
        
        self._update_loading_message("Processing", detail)
    
    def _hide_loading_overlay(self):
        """Complete loading state and hide progress indicators."""
        import time as time_module
        
        # Calculate final elapsed time
        if self.loading_start_time:
            elapsed = time_module.time() - self.loading_start_time
            if elapsed > 1:
                self.progress_message.set(f"Completed in {elapsed:.1f}s")
        
        # Hide progress percentage label
        self.progress_percent_label.grid_forget()
        
        # Reset tracking
        self.loading_start_time = None
        self.last_progress_milestone = 0


    def open_file(self):
        """
        Open a file dialog and initiate the parsing of the selected file.
        
        On Windows, uses a native Win32 dialog with OFN_NODEREFERENCELINKS
        so that .lnk shortcut files are opened as-is (for forensic analysis)
        rather than being resolved to their target.
        """
        current_directory = os.getcwd()  # Get current working directory
        file_types = (("All Files", "*.*"),
                      ("SQLite Files", "*.sqlite"),
                      ("PNG Files", "*.png"),
                      ("JPG Files", "*.jpg"),
                      ("JPEG Files", "*.jpeg"),
                      ("MFT Files", "$MFT"),
                      ("LNK Files", "*.lnk"),
                      ("Prefetch Files", "*.pf"))

        if sys.platform == "win32":
            # Use Windows-native dialog with OFN_NODEREFERENCELINKS to
            # prevent .lnk files from being resolved to their targets
            filename = _win32_open_file_dialog(
                initialdir=current_directory,
                title="Select File",
                filetypes=file_types
            )
        else:
            filename = filedialog.askopenfilename(
                initialdir=current_directory,
                title="Select File",
                filetypes=file_types
            )
        if filename:
            # Warn for large files (>10MB) — parsing may be slow or cause high memory usage
            file_size = os.path.getsize(filename)
            self.file_size = file_size  # Store for hex integrity verification
            if file_size > 10 * 1024 * 1024:  # 10 MB threshold
                size_str = self._format_file_size(file_size)
                proceed = messagebox.askyesno(
                    "Large File Warning",
                    f"The selected file is {size_str}.\n\n"
                    "Parsing a large file may take a while and consume "
                    "significant memory.\n\nDo you want to continue?",
                    icon='warning'
                )
                if not proceed:
                    return
            
            # reset previous file treeview
            self.sequence_treeview.delete(
                *self.sequence_treeview.get_children())  # Clear previous entries
            # Reset progress bar and show it
            self.progress_var.set(0)
            self.progress_bar.grid(
                row=3, column=0, columnspan=5, sticky=W+E+S, pady=(5, 0))
            self.progress_message.set("Loading...")
            
            # Show loading overlay for better UX
            self._show_loading_overlay(f"Loading {os.path.basename(filename)}...")
            self._update_loading_message(
                f"Loading {os.path.basename(filename)}...",
                f"Size: {self._format_file_size(file_size)}"
            )
            
            threading.Thread(target=self.parse_file, args=(filename,)).start()

    def parse_file(self, filename):
        """
        Parse the selected file, displaying the content and controlling the progress.
        
        Checks for a cached parsed tree first (by file SHA-256 hash).
        If found, loads from cache instead of re-parsing.
        After parsing, saves the result to cache for future use.
        Also loads any cached bookmarks for the file.

        :param filename: The path to the file to be parsed.
        """
        self.stop_parsing = False
        self.open_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.current_file = filename
        
        # Reset color generator for new file
        ColorGenerator.reset()
        
        try:
            import time as _time
            t0 = _time.perf_counter()
            
            # Compute file hash for caching
            self.master.after(0, lambda: self._update_loading_message(
                "Computing file hash...",
                "Checking cache"
            ))
            self.file_hash = cache_manager.compute_file_hash(filename)
            t_hash = _time.perf_counter()
            
            # Check for cached parsed data
            cached_root = cache_manager.load_parsed_cache(self.file_hash)
            t_load = _time.perf_counter()
            
            if cached_root is not None:
                self.master.after(0, lambda: self._update_loading_message(
                    "Loading from cache...",
                    "Using previously parsed data"
                ))
                self.root = cached_root
                self.total_nodes = self.count_nodes(self.root)
                self.processed_nodes = 0
                self.show_parsed_data(self.root)
                
                # Load cached bookmarks
                self._load_cached_bookmarks()
                
                cache_meta = cache_manager.get_cache_meta(self.file_hash)
                cached_at = cache_meta.get("cached_at", "") if cache_meta else ""
                t_render = _time.perf_counter()
                timing = (f"hash {t_hash-t0:.2f}s, "
                          f"cache load {t_load-t_hash:.2f}s, "
                          f"render {t_render-t_load:.2f}s, "
                          f"total {t_render-t0:.2f}s")
                self.update_status(
                    f"Loaded from cache ({self.total_nodes} fields) [{timing}]"
                )
            else:
                # Parse fresh
                self.master.after(0, lambda: self._update_loading_message(
                    "Parsing file structure...",
                    "Analyzing binary data"
                ))
                
                parser_name = ""
                with open(filename, "rb") as file:
                    parser = get_file_parser(file, filename)
                    parser_name = type(parser).__name__
                    self.root = parser.parse()
                    t_parse = _time.perf_counter()
                    self.total_nodes = self.count_nodes(self.root)
                    self.processed_nodes = 0
                    
                    self.master.after(0, lambda: self._update_loading_message(
                        "Rendering hex view...",
                        f"Processing {self.total_nodes} fields"
                    ))
                    
                    self.show_parsed_data(self.root)
                    self.write_parse_log(filename, self.root)
                
                # Save to cache in background
                threading.Thread(
                    target=cache_manager.save_parsed_cache,
                    args=(self.file_hash, self.root, filename, parser_name),
                    daemon=True
                ).start()
                
                # Load cached bookmarks (may exist from a previous session)
                self._load_cached_bookmarks()
                
                t_done = _time.perf_counter()
                timing = (f"hash {t_hash-t0:.2f}s, "
                          f"parse {t_parse-t_hash:.2f}s, "
                          f"render {t_done-t_parse:.2f}s, "
                          f"total {t_done-t0:.2f}s")
                self.update_status(
                    f"Parsed {self.total_nodes} fields [{timing}]"
                )
            
            if self.stop_parsing:
                self.update_status(f"Parsing of {filename} stopped.")
        except Exception as e:
            self.update_status(f"Could not parse file: {e}")
            self.master.after(0, self._hide_loading_overlay)

        self.master.after(10000, self.clear_status)
        self.open_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def _load_cached_bookmarks(self):
        """Load bookmarks from cache for the current file hash."""
        if not self.file_hash:
            return
        cached_bookmarks = cache_manager.load_bookmarks(self.file_hash)
        if cached_bookmarks:
            self.bookmarks = cached_bookmarks
            self.update_status(
                f"Loaded {len(cached_bookmarks)} bookmarks from cache"
            )
            # Refresh bookmark window if open
            self._refresh_bookmark_window()
        else:
            self.bookmarks = []

    def _save_bookmarks_to_cache(self):
        """Save current bookmarks to cache (called on any bookmark change)."""
        if not self.file_hash:
            return
        threading.Thread(
            target=cache_manager.save_bookmarks,
            args=(self.file_hash, self.bookmarks),
            daemon=True
        ).start()

    def _refresh_bookmark_window(self):
        """Clear and repopulate the bookmark treeview if the window is open."""
        if (self.bookmark_treeview is None or self.bookmark_window is None):
            return
        try:
            if not self.bookmark_window.winfo_exists():
                return
        except:
            return
        # Clear all items
        for item in self.bookmark_treeview.get_children():
            self.bookmark_treeview.delete(item)
        # Repopulate
        for bm in self.bookmarks:
            val = bm.get('value', '')
            truncated = self._truncate_value(val) if val else ''
            self.bookmark_treeview.insert('', 'end', values=(
                bm['name'], self._format_offset(bm['offset']),
                truncated, bm.get('comment', '')))

    def _edit_bookmark_comment(self, event):
        """Handle double-click on a bookmark row to edit its comment."""
        if self.bookmark_treeview is None:
            return
        # Only act on the Comment column (#4 now)
        region = self.bookmark_treeview.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col = self.bookmark_treeview.identify_column(event.x)
        if col != '#4':  # Comment is the 4th column
            return
        selected = self.bookmark_treeview.identify_row(event.y)
        if not selected:
            return

        item = self.bookmark_treeview.item(selected)
        current_comment = item['values'][3] if len(item['values']) > 3 else ''
        name = item['values'][0]
        raw_offset = self._parse_offset(item['values'][1])

        # Simple dialog for editing the comment
        from tkinter.simpledialog import askstring
        new_comment = askstring(
            "Edit Comment",
            f"Comment for '{name}':",
            initialvalue=str(current_comment),
            parent=self.bookmark_window
        )
        if new_comment is None:
            return  # Cancelled

        # Update the bookmark dict
        for bm in self.bookmarks:
            if bm['name'] == name and bm['offset'] == raw_offset:
                bm['comment'] = new_comment
                break
        # Update the treeview cell
        self.bookmark_treeview.set(selected, 'Comment', new_comment)
        self._save_bookmarks_to_cache()

    def _export_bookmarks(self):
        """Export bookmarks to JSON, CSV, or Markdown via a save dialog."""
        if not self.bookmarks:
            self.update_status("No bookmarks to export")
            return

        # Ask for hex value length limit before exporting
        hex_limit = self._ask_hex_limit()
        if hex_limit is None:
            return  # User cancelled

        from tkinter.filedialog import asksaveasfilename
        filepath = asksaveasfilename(
            title="Export Bookmarks",
            defaultextension=".md",
            filetypes=[
                ("Markdown report", "*.md"),
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
            ],
            parent=self.bookmark_window or self.master
        )
        if not filepath:
            return
        try:
            source_name = os.path.basename(self.current_file) if hasattr(self, 'current_file') and self.current_file else ''
            cache_manager.export_bookmarks_to_file(
                self.bookmarks, filepath, source_name, hex_limit=hex_limit)
            self.update_status(f"Exported {len(self.bookmarks)} bookmarks to {filepath}")
        except Exception as e:
            self.update_status(f"Export failed: {e}")

    def _ask_hex_limit(self):
        """Show a small dialog to configure the raw hex byte limit for export.
        
        Returns the limit as an integer, or None if cancelled.
        Only applies to raw hex (unparsed) values; parsed values are always shown in full.
        """
        # Check if any bookmarks have raw hex values
        has_raw = any(bm.get('is_raw_hex', False) for bm in self.bookmarks)
        if not has_raw:
            return 128  # Default, won't matter since no raw hex

        dialog = Toplevel(self.bookmark_window or self.master)
        dialog.title("Export Settings")
        dialog.geometry("340x150")
        dialog.configure(bg=ModernTheme.BG_PRIMARY)
        dialog.resizable(False, False)
        dialog.transient(self.bookmark_window or self.master)
        dialog.grab_set()

        Label(
            dialog, text="Max bytes for raw hex values:",
            font=('Segoe UI', 10), bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_PRIMARY
        ).pack(pady=(20, 5))

        Label(
            dialog, text="(Parsed values like timestamps, strings, integers\nare always shown in full)",
            font=('Segoe UI', 8), bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY
        ).pack(pady=(0, 8))

        limit_var = IntVar(value=128)
        spin = Spinbox(
            dialog, from_=16, to=65536, textvariable=limit_var,
            width=8, font=('Segoe UI', 10), justify='center'
        )
        spin.pack(pady=(0, 10))

        result = [None]

        def on_ok():
            try:
                result[0] = max(16, int(limit_var.get()))
            except (ValueError, TclError):
                result[0] = 128
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = Frame(dialog, bg=ModernTheme.BG_PRIMARY)
        btn_frame.pack(pady=(0, 10))
        RoundedButton(
            btn_frame, text="OK", command=on_ok,
            style="primary", radius=8, height=30, width=80
        ).pack(side=LEFT, padx=5)
        RoundedButton(
            btn_frame, text="Cancel", command=on_cancel,
            style="secondary", radius=8, height=30, width=80
        ).pack(side=LEFT, padx=5)

        dialog.wait_window()
        return result[0]

    def count_nodes(self, node):
        """
        Recursively count the total number of nodes in the given node.

        :param node: The root node for counting.
        :return: The total number of nodes.
        """
        count = 1
        for _, child in node.children:
            count += self.count_nodes(child)
        return count

    def write_parse_log(self, filename, root):
        """
        Write parsed content to a log file in table format.
        
        Format: Index | From:To | Field Name | Description
        
        :param filename: The original file that was parsed
        :param root: The root node of the parsed data
        """
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Generate log filename based on parsed file and timestamp
        base_name = os.path.basename(filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = os.path.join(logs_dir, f'{base_name}_{timestamp}.log')
        
        try:
            with open(log_filename, 'w', encoding='utf-8') as log_file:
                # Write header
                log_file.write(f"{'='*80}\n")
                log_file.write(f"HexMarksTheSpot - Parse Log\n")
                log_file.write(f"{'='*80}\n")
                log_file.write(f"File: {filename}\n")
                log_file.write(f"Parsed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"{'='*80}\n\n")
                
                # Write table header
                log_file.write(f"{'Index':<8} | {'From:To':<20} | {'Field Name':<30} | {'Value'}\n")
                log_file.write(f"{'-'*8}-+-{'-'*20}-+-{'-'*30}-+-{'-'*40}\n")
                
                # Write parsed fields
                self._write_node_to_log(log_file, root, index=[0], offset=[0])
                
                log_file.write(f"\n{'='*80}\n")
                log_file.write(f"End of parse log\n")
                
            logging.info(f"Parse log written to: {log_filename}")
        except Exception as e:
            logging.error(f"Failed to write parse log: {e}")

    def _write_node_to_log(self, log_file, node, index, offset, depth=0):
        """
        Recursively write node data to log file.
        
        :param log_file: Open file handle for writing
        :param node: Current node to process
        :param index: Mutable list containing current index (for reference passing)
        :param offset: Mutable list containing current byte offset
        :param depth: Current depth for indentation
        """
        for _, child in node.children:
            start_offset = offset[0]
            end_offset = start_offset + len(child.data) - 1 if child.data else start_offset
            
            # Format the range
            offset_range = f"0x{start_offset:04X}:0x{end_offset:04X}"
            
            # Get description (clean HTML if present)
            description = child.table_value or ''
            # Truncate long descriptions
            if len(description) > 50:
                description = description[:47] + '...'
            
            # Indent nested fields
            indent = '  ' * depth
            field_name = f"{indent}{child.name}"
            
            log_file.write(f"{index[0]:<8} | {offset_range:<20} | {field_name:<30} | {description}\n")
            
            index[0] += 1
            offset[0] += len(child.data) if child.data else 0
            
            # Process children recursively
            self._write_node_to_log(log_file, child, index, offset, depth + 1)

    def update_progress(self, progress):
        """
        Update the progress bar with the given progress value.

        :param progress: The progress value to be set (0 to 100).
        """
        self.progress_var.set(progress)
        # Show percentage in status message
        if progress < 100:
            self.progress_message.set(f"Loading... {progress:.1f}% ({self.processed_nodes}/{self.total_nodes} fields)")
        else:
            self.progress_bar.grid_forget()  # Hide the progress bar when done

    def update_status(self, message):
        """
        Update the status bar with the given message.

        :param message: The status message to be displayed.
        """
        self.progress_message.set(message)

    def clear_status(self):
        """
        Clear the status message from the status bar.
        """
        self.update_status("")

    def mirror_selection(self, event):
        """
        Mirror the text selection between the hex and ASCII text widgets.

        :param event: Event object containing information about the selection event.
        """
        # Identify the widget where the event was triggered
        source_widget = event.widget
        target_widget = self.text_widget.asciiText if source_widget == self.text_widget.textWidget else self.text_widget.textWidget

        # Check if there's a selection in the source widget
        try:
            start, end = source_widget.index(
                SEL_FIRST), source_widget.index(SEL_LAST)
            start_index, end_index = list(
                map(lambda x: int(x.split(".")[1]), [start, end]))

            # Mirror the selection in the target widget
            target_widget.tag_remove(SEL, "1.0", END)
            target_widget.tag_add(SEL, f"1.{start_index}", f"1.{end_index}")

            target_widget.see(start)
            target_widget.see(end)

        except TclError:
            # This exception is raised when there's no selection.
            pass

    def show_parsed_data(self, root):
        """
        Display the parsed data from the given root node.
        Collects all data first, then updates GUI on main thread.

        :param root: The root node of the parsed data.
        """
        self.sequence_items = []  # Initialize the sequence items list
        self.byte_counter = 0  # Global byte counter for hex display
        
        # Reset click synchronization mappings
        self.tag_to_treeview_item = {}
        self.tag_to_child = {}
        self.offset_to_tag = {}
        self.tag_to_display_pos = {}   # tag -> display byte position in hex widget
        self.current_highlight_tag = None
        self._current_parent_highlight_tag = None  # Currently highlighted parent container tag
        self._current_parent_sibling_tags = []     # Tags currently showing parent border
        self._hide_treeview_border()
        self._hide_parent_treeview_border()
        self._from_hex_click = False
        self._item_raw_offsets = {}
        
        # Parent-child relationship tracking (derived from JSON nesting structure)
        # Maps each tag to its nearest parent container tag (struct/section)
        self._tag_to_parent_tag = {}       # child_tag -> parent_container_tag
        # Maps each parent container tag to its list of child tags
        self._parent_tag_to_children = {}  # parent_tag -> [child_tags]
        
        # Pre-build lookup table for ASCII conversion (avoids per-byte branching)
        self._ascii_table = ''.join(
            chr(b) if 32 <= b < 127 else '.' for b in range(256)
        )
        # Cache for contrast text colors (few unique colors)
        self._contrast_cache = {}
        
        # Collect all node data first (can be done in background thread)
        self.collected_nodes = []
        self._collect_nodes(root)
        
        # Fill gaps between parsed nodes with "Unparsed Data" entries
        # so the hex viewer always shows every byte of the file
        self._fill_unparsed_gaps()
        
        # Verify parsed bytes match actual file content (hex safeguard)
        self._verify_hex_integrity()
        
        # Schedule GUI updates on main thread in batches
        self.master.after(0, self._update_gui_batch, 0)
    
    def _collect_nodes(self, node):
        """
        Recursively collect all node data for display.
        Pre-builds hex and ASCII strings for bulk insertion.
        Also pre-computes formatted offsets and contrast colors.
        Tracks parent-child relationships from the JSON nesting structure
        so the GUI can highlight parent containers when a child is selected.
        This can safely run in a background thread.
        """
        if self.stop_parsing:
            return
        
        # Local references for tight loop performance
        collected = self.collected_nodes
        byte_counter = self.byte_counter
        ascii_table = self._ascii_table
        contrast_cache = self._contrast_cache
        is_hex_fmt = self.offset_format_var.get() == "Hex"
        max_val_width = self.VALUE_COLUMN_MAX_WIDTH
        stop_check = lambda: self.stop_parsing
        tag_to_parent = self._tag_to_parent_tag
        parent_to_children = self._parent_tag_to_children
        
        # Stack entries: (node, child_idx, parent_container_tag)
        # parent_container_tag is the tag of the nearest ancestor container
        # (struct/section with data=b'') — None for top-level fields.
        stack = [(node, 0, None)]  # iterative DFS to avoid recursion limit
        while stack:
            current_node, child_idx, parent_container_tag = stack[-1]
            children = current_node.children
            
            if child_idx >= len(children) or stop_check():
                stack.pop()
                continue
            
            # Advance index for next iteration
            stack[-1] = (current_node, child_idx + 1, parent_container_tag)
            
            key, child = children[child_idx]
            offset = key if key is not None else byte_counter
            tag = f"color{byte_counter}_{child_idx}"
            data = child.data
            data_len = len(data) if data else 0
            color = child.color or '#ffffff'
            
            # Track parent-child relationships from the JSON nesting.
            # Every node records which container it belongs to.
            if parent_container_tag is not None:
                tag_to_parent[tag] = parent_container_tag
                if parent_container_tag not in parent_to_children:
                    parent_to_children[parent_container_tag] = []
                parent_to_children[parent_container_tag].append(tag)
            
            # Pre-compute contrast text color.
            # If the Node has an explicit fg_color (e.g., anti-forensics red-on-black),
            # use it directly instead of auto-calculating contrast.
            if child.fg_color:
                fg_color = child.fg_color
            else:
                fg_color = contrast_cache.get(color)
                if fg_color is None:
                    fg_color = ColorGenerator.get_contrast_text_color(color)
                    contrast_cache[color] = fg_color
            
            # Pre-format offset string
            if is_hex_fmt:
                display_offset = f"0x{offset:X}"
            else:
                display_offset = str(offset)
            
            # Pre-truncate value
            table_val = child.table_value or ''
            truncated_val = str(table_val)
            if len(truncated_val) > max_val_width:
                truncated_val = truncated_val[:max_val_width - 1] + '\u2026'
            
            # Pre-build hex and ASCII strings using C-level operations
            hex_str = ''
            ascii_str = ''
            if data:
                # bytes.hex(' ') is C-level fast, then add trailing space
                hex_str = data.hex(' ') + ' '
                # translate is C-level fast for ASCII mapping
                ascii_str = ''.join(ascii_table[b] for b in data)
            
            collected.append({
                'tag': tag,
                'color': color,
                'fg_color': fg_color,
                'name': child.name,
                'data_len': data_len,
                'hex_str': hex_str,
                'ascii_str': ascii_str,
                'table_val': table_val,
                'truncated_val': truncated_val,
                'display_offset': display_offset,
                'offset': offset,
                'child': child,
                'display_pos': byte_counter,
            })
            
            byte_counter += data_len
            
            # Push child for DFS traversal.
            # If this node is a container (has children but no data), it becomes
            # the parent_container_tag for all its descendants. This follows the
            # JSON nesting: struct/section nodes wrap their child fields.
            if child.children:
                # Container nodes (data=b'') become the new parent context.
                # Leaf-with-children (rare) also become parent context.
                new_parent_tag = tag if data_len == 0 else parent_container_tag
                stack.append((child, 0, new_parent_tag))
        
        self.byte_counter = byte_counter
    
    def _fill_unparsed_gaps(self):
        """
        Fill gaps between parsed nodes with 'Unparsed Data' entries so the
        hex viewer always displays every byte of the file.
        
        Scans the collected_nodes list for byte ranges not covered by any
        parsed field, reads those bytes from the actual file, and inserts
        placeholder nodes. This ensures the hex viewer is the authoritative
        representation of the file — parsed fields are interactive, while
        unparsed regions are shown in a neutral gray.
        """
        if not hasattr(self, 'current_file') or not self.current_file:
            return
        if not hasattr(self, 'file_size') or self.file_size == 0:
            return
        
        file_size = self.file_size
        
        # Build a sorted list of (start, end) ranges covered by parsed nodes
        # Only consider leaf nodes that have actual data (data_len > 0)
        covered = []
        for nd in self.collected_nodes:
            if nd['data_len'] > 0:
                covered.append((nd['offset'], nd['offset'] + nd['data_len']))
        
        if not covered:
            # Nothing parsed at all — fill entire file as unparsed
            covered = []
        
        # Sort by start offset
        covered.sort(key=lambda x: x[0])
        
        # Find gaps: byte ranges not covered by any parsed node
        gaps = []
        cursor = 0
        for start, end in covered:
            if start > cursor:
                gaps.append((cursor, start))
            cursor = max(cursor, end)
        # Trailing gap at end of file
        if cursor < file_size:
            gaps.append((cursor, file_size))
        
        if not gaps:
            return  # No gaps — full coverage
        
        # Read the file to extract gap bytes
        try:
            with open(self.current_file, 'rb') as f:
                file_data = f.read()
        except (OSError, IOError):
            return
        
        # Styling for unparsed data nodes
        unparsed_color = '#D3D3D3'  # Light gray
        ascii_table = self._ascii_table
        contrast_cache = self._contrast_cache
        is_hex_fmt = self.offset_format_var.get() == "Hex"
        max_val_width = self.VALUE_COLUMN_MAX_WIDTH
        
        fg_color = contrast_cache.get(unparsed_color)
        if fg_color is None:
            fg_color = ColorGenerator.get_contrast_text_color(unparsed_color)
            contrast_cache[unparsed_color] = fg_color
        
        # Create gap nodes
        gap_nodes = []
        for gap_start, gap_end in gaps:
            gap_data = file_data[gap_start:gap_end]
            gap_len = len(gap_data)
            if gap_len == 0:
                continue
            
            tag = f"unparsed_{gap_start}"
            if is_hex_fmt:
                display_offset = f"0x{gap_start:X}"
            else:
                display_offset = str(gap_start)
            
            hex_str = gap_data.hex(' ') + ' '
            ascii_str = ''.join(ascii_table[b] for b in gap_data)
            
            # Create a placeholder Node for the gap
            gap_node = Node(
                data=gap_data,
                info=markdown_to_html(
                    f"**Unparsed Data** — {gap_len} bytes at offset "
                    f"0x{gap_start:X} not covered by any parser field.\n\n"
                    "These bytes exist in the file but are not recognized by "
                    "the current parser template. This may indicate:\n"
                    "- Incomplete parser coverage\n"
                    "- Padding or reserved bytes not accounted for\n"
                    "- Data structures not yet implemented in the template"
                ),
                name="Unparsed Data",
                color=unparsed_color,
                table_value=f"{gap_len} bytes"
            )
            
            table_val = gap_node.table_value
            truncated_val = str(table_val)
            if len(truncated_val) > max_val_width:
                truncated_val = truncated_val[:max_val_width - 1] + '\u2026'
            
            gap_nodes.append({
                'tag': tag,
                'color': unparsed_color,
                'fg_color': fg_color,
                'name': "Unparsed Data",
                'data_len': gap_len,
                'hex_str': hex_str,
                'ascii_str': ascii_str,
                'table_val': table_val,
                'truncated_val': truncated_val,
                'display_offset': display_offset,
                'offset': gap_start,
                'child': gap_node,
                'display_pos': gap_start,  # will be recalculated after merge
            })
        
        if not gap_nodes:
            return
        
        # Merge gap nodes into collected_nodes and re-sort by offset
        self.collected_nodes.extend(gap_nodes)
        self.collected_nodes.sort(key=lambda x: x['offset'])
        
        # Recalculate display_pos (cumulative byte position) after merge
        running_pos = 0
        for nd in self.collected_nodes:
            nd['display_pos'] = running_pos
            running_pos += nd['data_len']
        
        # Update byte counter to reflect full file coverage
        self.byte_counter = running_pos
    
    def _verify_hex_integrity(self):
        """
        Post-parse safeguard: compare total parsed bytes and their content
        against the actual file on disk.
        
        Performs four checks:
        1. Byte count — do parsed leaf nodes cover exactly the file size?
        2. Overlap detection — do any nodes claim the same byte range?
        3. Per-node data — does each node's data match the file at its offset?
        4. Sequential stream — does the reconstructed display stream match
           the file when read sequentially?
        
        On mismatch, logs the exact offset where divergence first occurs,
        the field name, expected vs actual bytes, and surrounding context.
        Parsing proceeds regardless — this is purely informational to help
        identify template errors or truncated files.
        """
        if not hasattr(self, 'current_file') or not self.current_file:
            return
        if not hasattr(self, 'file_size'):
            return
        
        import logging
        file_size = self.file_size
        parsed_bytes = self.byte_counter
        
        # Step 1: Check byte count mismatch
        if parsed_bytes != file_size:
            diff = file_size - parsed_bytes
            if parsed_bytes < file_size:
                size_msg = (f"Hex safeguard: parsed {parsed_bytes:,} bytes but "
                            f"file is {file_size:,} bytes "
                            f"({diff:,} bytes unparsed)")
            else:
                size_msg = (f"Hex safeguard: parsed {parsed_bytes:,} bytes but "
                            f"file is only {file_size:,} bytes "
                            f"({abs(diff):,} bytes over-read)")
            logging.warning(size_msg)
            self.master.after(0, lambda msg=size_msg: self._show_hex_safeguard_warning(msg))
            # Don't return — continue to find exact divergence location
        
        # Only do byte-level verification for files up to 50MB
        if file_size > 50 * 1024 * 1024:
            return
        
        try:
            with open(self.current_file, 'rb') as f:
                file_data = f.read()
        except (OSError, IOError):
            return
        
        # Step 2: Overlap detection — check if any nodes claim the same bytes
        # Build sorted list of (start, end, name) for leaf nodes only
        ranges = []
        for nd in self.collected_nodes:
            if nd['data_len'] > 0 and nd['name'] != 'Unparsed Data':
                ranges.append((nd['offset'], nd['offset'] + nd['data_len'], nd['name']))
        ranges.sort(key=lambda x: x[0])
        
        for i in range(len(ranges) - 1):
            curr_start, curr_end, curr_name = ranges[i]
            next_start, next_end, next_name = ranges[i + 1]
            if curr_end > next_start:
                overlap_bytes = curr_end - next_start
                msg = (f"Hex safeguard: OVERLAP — '{curr_name}' "
                       f"(0x{curr_start:X}..0x{curr_end:X}) overlaps "
                       f"'{next_name}' (0x{next_start:X}..0x{next_end:X}) "
                       f"by {overlap_bytes} bytes")
                logging.warning(msg)
                self.master.after(0, lambda m=msg: self._show_hex_safeguard_warning(m))
                return
        
        # Step 3: Per-node data verification — each node's bytes must match
        # the file at its declared offset
        for nd in self.collected_nodes:
            if nd['data_len'] == 0 or nd['name'] == 'Unparsed Data':
                continue
            offset = nd['offset']
            data = nd['child'].data
            data_len = nd['data_len']
            
            # Bounds check
            if offset + data_len > len(file_data):
                msg = (f"Hex safeguard: '{nd['name']}' at offset "
                       f"0x{offset:X} extends beyond file end "
                       f"(needs {data_len} bytes, "
                       f"only {len(file_data) - offset} available)")
                logging.warning(msg)
                self.master.after(0, lambda m=msg: self._show_hex_safeguard_warning(m))
                return
            
            # Compare bytes at declared offset
            file_chunk = file_data[offset:offset + data_len]
            if data != file_chunk:
                # Find first mismatched byte within this field
                for i in range(data_len):
                    if data[i] != file_chunk[i]:
                        abs_offset = offset + i
                        # Context: show ±8 bytes from the file around mismatch
                        ctx_start = max(0, abs_offset - 8)
                        ctx_end = min(len(file_data), abs_offset + 9)
                        file_ctx = ' '.join(f'{file_data[j]:02X}' for j in range(ctx_start, ctx_end))
                        parsed_ctx = ' '.join(
                            f'{data[j]:02X}' if offset <= (offset + j) < offset + data_len
                            else '..'
                            for j in range(max(0, i - 8), min(data_len, i + 9))
                        )
                        msg = (f"Hex safeguard: byte mismatch at file offset "
                               f"0x{abs_offset:X} in field '{nd['name']}' — "
                               f"parsed 0x{data[i]:02X}, "
                               f"file has 0x{file_chunk[i]:02X}")
                        detail = (f"  Field: '{nd['name']}' at 0x{offset:X}, "
                                  f"byte {i} of {data_len}\n"
                                  f"  File context around 0x{abs_offset:X}:\n"
                                  f"    {file_ctx}")
                        logging.warning(msg)
                        logging.warning(detail)
                        self.master.after(0, lambda m=msg: self._show_hex_safeguard_warning(m))
                        return
        
        # Step 4: Sequential stream verification — reconstruct the byte stream
        # as concatenated from nodes in display order and compare against file
        reconstructed = bytearray()
        node_boundaries = []  # (stream_pos, name, file_offset) for lookups
        for nd in self.collected_nodes:
            if nd['data_len'] > 0:
                node_boundaries.append((len(reconstructed), nd['name'], nd['offset']))
                reconstructed.extend(nd['child'].data)
        
        min_len = min(len(reconstructed), len(file_data))
        for i in range(min_len):
            if reconstructed[i] != file_data[i]:
                # Find which node owns this stream position
                field_name = "unknown"
                field_file_offset = 0
                byte_within = 0
                for idx, (stream_pos, name, foffset) in enumerate(node_boundaries):
                    next_pos = (node_boundaries[idx + 1][0]
                                if idx + 1 < len(node_boundaries)
                                else len(reconstructed))
                    if stream_pos <= i < next_pos:
                        field_name = name
                        field_file_offset = foffset
                        byte_within = i - stream_pos
                        break
                
                # Context: ±8 bytes around mismatch
                ctx_start = max(0, i - 8)
                ctx_end = min(min_len, i + 9)
                parsed_line = ' '.join(f'{reconstructed[j]:02X}' for j in range(ctx_start, ctx_end))
                actual_line = ' '.join(f'{file_data[j]:02X}' for j in range(ctx_start, ctx_end))
                marker_offset = (i - ctx_start) * 3
                marker = ' ' * marker_offset + '^^'
                
                msg = (f"Hex safeguard: stream mismatch at position "
                       f"0x{i:X} (file offset 0x{field_file_offset + byte_within:X}) "
                       f"in field '{field_name}' — "
                       f"parsed 0x{reconstructed[i]:02X}, "
                       f"file has 0x{file_data[i]:02X}")
                detail = (f"  Stream position {i}, byte {byte_within} of "
                          f"'{field_name}' (file offset 0x{field_file_offset:X})\n"
                          f"  Parsed:  {parsed_line}\n"
                          f"  Actual:  {actual_line}\n"
                          f"           {marker}")
                logging.warning(msg)
                logging.warning(detail)
                self.master.after(0, lambda m=msg: self._show_hex_safeguard_warning(m))
                return
    
    def _show_hex_safeguard_warning(self, message):
        """
        Display a hex safeguard warning to the user via a non-blocking
        warning dialog and update the status bar.
        """
        self.update_status(f"\u26A0 {message}")
        messagebox.showwarning("Hex Integrity Warning", message)
    
    def _update_gui_batch(self, start_idx):
        """
        Update GUI in batches to prevent freezing.
        Runs on main thread via after().
        Uses large batches since hex/ASCII strings are pre-built.
        """
        if self.stop_parsing:
            self._hide_loading_overlay()
            return
        
        total_nodes = len(self.collected_nodes)
        
        # Large batches — most work is pre-computed, GUI inserts are bulk
        BATCH_SIZE = 2000
            
        end_idx = min(start_idx + BATCH_SIZE, total_nodes)
        
        # First batch: initialize widgets
        if start_idx == 0:
            self.text_widget.textWidget.configure(state='normal')
            self.text_widget.asciiText.configure(state='normal')
            self.text_widget.offsetText.configure(state='normal')
            self.text_widget.textWidget.delete('1.0', 'end')
            self.text_widget.asciiText.delete('1.0', 'end')
            self.text_widget.offsetText.delete('1.0', 'end')
            
            # Insert first offset line
            self.text_widget.offsetText.insert('end', self._format_viewer_offset(0) + '\n')
            
            # Mark text mirror
            self.text_widget.textWidget.bind(
                "<ButtonRelease-1>", lambda e: self.mirror_highlight(self.text_widget.textWidget))
            self.text_widget.asciiText.bind(
                "<ButtonRelease-1>", lambda e: self.mirror_highlight(self.text_widget.asciiText))
            self.text_widget.textWidget.bind(
                "<Button-1>", lambda e: self.clear_mirror_highlight())
            self.text_widget.asciiText.bind(
                "<Button-1>", lambda e: self.clear_mirror_highlight())
            
            self.display_byte_counter = 0
        
        # Process batch
        for i in range(start_idx, end_idx):
            node_data = self.collected_nodes[i]
            self._display_node(node_data)
            self.processed_nodes += 1
        
        # Update progress with milestones (every 10% or time-based)
        self._update_progress_with_milestones(end_idx, total_nodes)
        
        # Schedule next batch or finalize
        if end_idx < total_nodes:
            # Use after_idle for smoother UI updates during rendering
            self.master.after(1, self._update_gui_batch, end_idx)
        else:
            # Finalize
            self.text_widget.textWidget.configure(state='disabled')
            self.text_widget.asciiText.configure(state='disabled')
            self.text_widget.offsetText.configure(state='disabled')
            
            # Hide loading overlay
            self._hide_loading_overlay()
    
    def _display_node(self, node_data):
        """
        Display a single node's data in the GUI.
        Uses bulk string insertion and pre-computed values.
        Must run on main thread.
        """
        tag = node_data['tag']
        color = node_data['color']
        fg_color = node_data['fg_color']
        offset = node_data['offset']
        child = node_data['child']
        table_val = node_data['table_val']
        
        # Insert into treeview with pre-formatted values
        item_id = self.sequence_treeview.insert('', 'end', values=(
            node_data['display_offset'], node_data['name'],
            node_data['truncated_val']), tags=(tag,))
        
        # Store mappings for click synchronization
        self.tag_to_treeview_item[tag] = item_id
        self.tag_to_child[tag] = child
        self.tag_to_display_pos[tag] = node_data['display_pos']
        self._item_raw_offsets[item_id] = offset
        if offset not in self.offset_to_tag:
            self.offset_to_tag[offset] = tag
        
        # Configure all three tags at once
        self.sequence_treeview.tag_configure(tag, background=color, foreground=fg_color)
        self.text_widget.textWidget.tag_configure(tag, background=color, foreground=fg_color)
        self.text_widget.asciiText.tag_configure(tag, background=color, foreground=fg_color)
        
        # Store for search/format switching — include hex and ASCII strings
        # for multi-scope search (Name, Value, Hex, ASCII)
        hex_search = node_data['hex_str'].upper().rstrip() if node_data['hex_str'] else ''
        ascii_search = node_data['ascii_str'] if node_data.get('ascii_str') else ''
        self.sequence_items.append(((offset, node_data['name'], table_val, hex_search, ascii_search), (tag,)))
        
        # Bulk-insert hex and ASCII data with newline splitting at 16-byte boundaries
        data_len = node_data['data_len']
        if data_len > 0:
            hex_str = node_data['hex_str']
            ascii_str = node_data['ascii_str']
            
            pos_in_line = self.display_byte_counter % 16
            bytes_consumed = 0
            
            # Fast references to avoid repeated attribute lookup
            hex_widget = self.text_widget.textWidget
            ascii_widget = self.text_widget.asciiText
            offset_widget = self.text_widget.offsetText
            fmt_offset = self._format_viewer_offset
            
            while bytes_consumed < data_len:
                remaining_in_line = 16 - pos_in_line
                chunk_size = min(remaining_in_line, data_len - bytes_consumed)
                
                hex_start = bytes_consumed * 3
                hex_end = (bytes_consumed + chunk_size) * 3
                
                hex_widget.insert('end', hex_str[hex_start:hex_end], (tag,))
                ascii_widget.insert('end', ascii_str[bytes_consumed:bytes_consumed + chunk_size], (tag,))
                
                bytes_consumed += chunk_size
                self.display_byte_counter += chunk_size
                pos_in_line += chunk_size
                
                if pos_in_line >= 16:
                    hex_widget.insert('end', '\n')
                    ascii_widget.insert('end', '\n')
                    offset_widget.insert('end', fmt_offset(self.display_byte_counter) + '\n')
                    pos_in_line = 0
        
        # Bind click handlers
        self.text_widget.textWidget.tag_bind(tag, "<Button-1>",
            lambda event, currentTag=tag, c=child: self.handle_click(event, currentTag, c))
        self.text_widget.asciiText.tag_bind(tag, "<Button-1>",
            lambda event, currentTag=tag, c=child: self.handle_click(event, currentTag, c))

    def mirror_highlight(self, source_widget):
        try:
            # Get the current selection in the source widget
            start, end = source_widget.index(
                SEL_FIRST), source_widget.index(SEL_LAST)

            # Determine the target widget based on the source widget
            target_widget = self.text_widget.asciiText if source_widget == self.text_widget.textWidget else self.text_widget.textWidget

            # Clear any previous temporary highlighting
            target_widget.tag_remove("mirror_highlight", "1.0", END)

            # Adjust selection start and end based on source and target widgets
            if source_widget == self.text_widget.textWidget:
                # Hex to ASCII
                start_byte = int(start.split('.')[1]) // 3
                end_byte = int(end.split('.')[1]) // 3
                adjusted_start = f"{start.split('.')[0]}.{start_byte}"
                adjusted_end = f"{end.split('.')[0]}.{end_byte}"
            else:
                # ASCII to Hex
                start_byte = int(start.split('.')[1])
                end_byte = int(end.split('.')[1])
                adjusted_start = f"{start.split('.')[0]}.{start_byte * 3}"
                adjusted_end = f"{end.split('.')[0]}.{end_byte * 3}"

            # Apply the temporary highlighting to the corresponding segment in the target widget
            target_widget.tag_add("mirror_highlight",
                                  adjusted_start, adjusted_end)
            target_widget.tag_configure(
                "mirror_highlight", background="#c3c3c3")

        except TclError:
            # Expected when clicking without dragging a selection - suppress
            pass

    def clear_mirror_highlight(self):
        for widget in [self.text_widget.textWidget, self.text_widget.asciiText]:
            widget.tag_remove("mirror_highlight", "1.0", END)

    def popItUp(self, text, currTag):
        """
        Display the given text in a popup with the specified tag.

        :param text: The text to be displayed in the popup.
        :param currTag: The tag to be applied to the text.
        """
        self.text_widget.update_popup_text(text, currTag)

    def handle_click(self, event, tag, child):
        """
        Handle a mouse click event in the text widgets, displaying additional information.
        Also synchronizes selection with the treeview.

        :param event: Event object containing information about the click event.
        :param tag: The tag associated with the clicked text.
        :param child: The child node associated with the clicked text.
        """
        self.last_clicked = child
        self.popItUp(self._get_info_with_parent_context(child.info, tag), tag)
        
        # Highlight the clicked tag
        self._highlight_tag(tag)

        # Calculate the exact offset
        if event.widget == self.text_widget.textWidget:
            clicked_index = self.text_widget.textWidget.index(
                f"@{event.x},{event.y}")
            row, col = map(int, clicked_index.split('.'))
            byte_offset = (row - 1) * 16 + col // 3
        elif event.widget == self.text_widget.asciiText:
            clicked_index = self.text_widget.asciiText.index(
                f"@{event.x},{event.y}")
            row, col = map(int, clicked_index.split('.'))
            byte_offset = (row - 1) * 16 + col
        
        # Select corresponding item in treeview
        if tag in self.tag_to_treeview_item:
            item_id = self.tag_to_treeview_item[tag]
            try:
                # Set flag so listbox_item_selected won't scroll hex view back
                self._from_hex_click = True
                # Select and scroll treeview to show the item
                self.sequence_treeview.selection_set(item_id)
                self.sequence_treeview.see(item_id)
                # Show black border around the treeview item
                self._show_treeview_border(item_id)
            except TclError:
                self._from_hex_click = False
                pass

        self.status_bar.config(
            text=f"File: {(self.current_file)}\t\tOffset: {self._format_offset(byte_offset)}  (Dec: {byte_offset}  Hex: 0x{byte_offset:X})")
    
    def _highlight_tag(self, tag):
        """
        Highlight a specific tag in the hex and ASCII views.
        Removes highlighting from previously highlighted tag.
        Also highlights the parent container: applies a colored border to all
        sibling tags (children of the same parent struct/section) in the hex
        viewer, and shows a colored border on the parent's treeview item.
        
        :param tag: The tag to highlight
        """
        # Remove previous active highlight (selected field)
        if self.current_highlight_tag:
            self._restore_tag_style(self.current_highlight_tag)
        
        # Remove previous parent highlight (sibling borders in hex viewer)
        self._clear_parent_hex_highlight()
        
        # Apply parent container highlight BEFORE the selection border,
        # so the selection border draws on top of the parent border.
        self._apply_parent_highlight(tag)
        
        # Apply a black border highlight with bright background for clear visibility.
        # relief='solid' draws the border using the foreground color, so we set
        # foreground to black temporarily to get a visible black outline.
        self.text_widget.textWidget.tag_configure(
            tag, foreground='#000000', borderwidth=2, relief='solid')
        self.text_widget.asciiText.tag_configure(
            tag, foreground='#000000', borderwidth=2, relief='solid')
        
        self.current_highlight_tag = tag

    def _restore_tag_style(self, tag):
        """Restore a tag to its original color and flat border in the hex viewer."""
        try:
            for node_data in self.collected_nodes:
                if node_data['tag'] == tag:
                    original_color = node_data['color']
                    fg = ColorGenerator.get_contrast_text_color(original_color or '#ffffff')
                    self.text_widget.textWidget.tag_configure(
                        tag,
                        background=original_color,
                        foreground=fg,
                        borderwidth=0,
                        relief='flat')
                    self.text_widget.asciiText.tag_configure(
                        tag,
                        background=original_color,
                        foreground=fg,
                        borderwidth=0,
                        relief='flat')
                    break
        except Exception:
            pass

    def _apply_parent_highlight(self, selected_tag):
        """
        Highlight the parent container of the selected tag.
        
        Looks up the parent container (struct/section) from the JSON nesting
        structure and applies a colored border to all sibling tags in the hex
        viewer. Also shows a colored border on the parent's treeview row.
        
        This provides visual context: 'these fields all belong to the same
        parent structure as the one you selected.'
        """
        parent_tag = self._tag_to_parent_tag.get(selected_tag)
        if not parent_tag:
            # No parent (top-level field) — hide parent border
            self._hide_parent_treeview_border()
            return
        
        # Get the parent container's color (still used for context, but border is white)
        parent_color = '#888888'
        if parent_tag in self.tag_to_child:
            parent_node = self.tag_to_child[parent_tag]
            parent_color = parent_node.color or '#888888'
        
        # Use white for the parent border — contrasts with the black selection border
        parent_border_color = '#FFFFFF'
        
        # Apply a subtle colored border (groove relief) to all sibling tags
        # in the hex viewer — this visually groups them as 'same parent'
        sibling_tags = self._parent_tag_to_children.get(parent_tag, [])
        self._current_parent_sibling_tags = []
        for sibling_tag in sibling_tags:
            if sibling_tag == selected_tag:
                continue  # Skip selected — it gets the black border instead
            # Only apply border to leaf nodes that have hex data
            self.text_widget.textWidget.tag_configure(
                sibling_tag, borderwidth=1, relief='groove')
            self.text_widget.asciiText.tag_configure(
                sibling_tag, borderwidth=1, relief='groove')
            self._current_parent_sibling_tags.append(sibling_tag)
        
        # Also store the parent tag itself for tracking
        self._current_parent_highlight_tag = parent_tag
        
        # Show colored border on the parent's treeview row
        if parent_tag in self.tag_to_treeview_item:
            parent_item_id = self.tag_to_treeview_item[parent_tag]
            self._show_parent_treeview_border(parent_item_id, parent_border_color)
        else:
            self._hide_parent_treeview_border()

    def _clear_parent_hex_highlight(self):
        """Remove the parent highlight (groove borders) from all sibling tags."""
        for sibling_tag in self._current_parent_sibling_tags:
            # Restore each sibling to flat border (original color stays)
            try:
                self.text_widget.textWidget.tag_configure(
                    sibling_tag, borderwidth=0, relief='flat')
                self.text_widget.asciiText.tag_configure(
                    sibling_tag, borderwidth=0, relief='flat')
            except Exception:
                pass
        self._current_parent_sibling_tags = []
        self._current_parent_highlight_tag = None

    @staticmethod
    def _darken_color(hex_color, factor=0.7):
        """Darken a hex color by a factor (0.0=black, 1.0=unchanged).
        
        Used to create a visible border color from a parent container's
        potentially light pastel color.
        """
        try:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            return f'#{r:02X}{g:02X}{b:02X}'
        except (ValueError, IndexError):
            return '#888888'

    def _get_info_with_parent_context(self, info_html, tag):
        """Prepend parent container context to a field's info HTML.
        
        Adds a small header line showing which parent structure (struct/section)
        contains this field, derived from the JSON nesting hierarchy. This gives
        users immediate context about where in the file structure they are.
        
        Args:
            info_html: The field's existing HTML description
            tag: The field's display tag for parent lookup
        
        Returns:
            Modified HTML with parent context prepended, or original if no parent
        """
        parent_tag = self._tag_to_parent_tag.get(tag)
        if not parent_tag:
            return info_html
        
        # Walk up the parent chain to build the full path (with cycle guard)
        path_parts = []
        current_tag = parent_tag
        visited = set()
        while current_tag and current_tag not in visited:
            visited.add(current_tag)
            if current_tag in self.tag_to_child:
                parent_node = self.tag_to_child[current_tag]
                parent_name = parent_node.name or 'Unknown'
                path_parts.append(parent_name)
            current_tag = self._tag_to_parent_tag.get(current_tag)
        
        if not path_parts:
            return info_html
        
        # Reverse to get root → leaf order
        path_parts.reverse()
        path_str = ' \u203A '.join(path_parts)  # Use › (single right-pointing angle) as separator
        
        parent_line = (
            f'<div style="margin-bottom:6px; padding:3px 6px; '
            f'background-color:#e8e8e8; border-left:3px solid #888; '
            f'font-size:0.9em; color:#555;">'
            f'\U0001F4C2 <b>Parent:</b> {path_str}</div>'
        )
        return parent_line + info_html


def main():
    """Main entry point for the GUI application."""
    # Discover all available parsers on startup
    discover_all_parsers()
    
    root = Tk()
    app = Main(root)
    root.title("HexMarksTheSpot - Hex File Analysis")
    root.configure(bg='#F0F0F0')
    root.mainloop()


if __name__ == "__main__":
    main()

# TODO: Consider adding menu: File
# TODO: Add information showing related info for the current file chosen as a questionmark button in a corner to represent the file in its birdseye view.
# TODO: Add fucntionality to export as CSV the bookmarks and the complete treeview
# TODO: Add funcitonality to import CSV bookmarks?? Should be the same file - hash check? Import a full parsed file instead?