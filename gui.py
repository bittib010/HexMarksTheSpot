# Standard Libraries
import os
import sys
import threading
import time
import csv
import hashlib
import logging
from datetime import datetime

# Third-Party Libraries
from tkinter import Tk, Text, N, S, E, W, Frame
from tkinter import filedialog, Button, Scrollbar, Label
from tkinter import SEL, SEL_LAST, SEL_FIRST, END
from tkinter import TclError, Entry, Listbox, ttk
from tkinter import StringVar, DoubleVar, NO, Toplevel, BOTH, LEFT, RIGHT, X, Y, TOP, BOTTOM
from tkhtmlview import HTMLText

# Application-specific - use the new dynamic parser loader
from parser_loader import get_file_parser, discover_all_parsers
from common import ColorGenerator


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
        
        # Column headers row
        # Offset column header
        offset_header = Label(
            self.container,
            text="  Offset  ",
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.TEXT_LIGHT,
            font=header_font,
            anchor=W,
            padx=6,
            pady=3,
            relief='flat',
            bd=0
        )
        offset_header.grid(row=1, column=0, sticky=E+W+N+S)
        
        # Hex column header (00 01 02 ... 0F)
        hex_header_text = " ".join(f"{i:02X}" for i in range(16))
        hex_column_header = Label(
            self.container,
            text=f" {hex_header_text} ",
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.TEXT_LIGHT,
            font=header_font,
            anchor=W,
            padx=12,
            pady=3,
            relief='flat',
            bd=0
        )
        hex_column_header.grid(row=1, column=1, sticky=E+W+N+S)
        
        # ASCII column header (0123456789ABCDEF)
        ascii_header_text = "0123456789ABCDEF"
        ascii_column_header = Label(
            self.container,
            text=f" {ascii_header_text}",
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.TEXT_LIGHT,
            font=header_font,
            anchor=W,
            padx=12,
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
            padx=12,
            pady=12,
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.HEX_FG,
            relief='flat',
            bd=0,
            insertbackground=ModernTheme.HEX_FG,
            selectbackground=ModernTheme.SELECTION_BG,
            selectforeground=ModernTheme.TEXT_PRIMARY,
            highlightthickness=1,
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
            padx=12,
            pady=12,
            bg=ModernTheme.HEX_BG,
            fg=ModernTheme.ASCII_FG,
            relief='flat',
            bd=0,
            insertbackground=ModernTheme.ASCII_FG,
            selectbackground=ModernTheme.SELECTION_BG,
            selectforeground=ModernTheme.TEXT_PRIMARY,
            highlightthickness=1,
            highlightbackground=ModernTheme.BORDER,
            highlightcolor=ModernTheme.BORDER_FOCUS
        )

        self.textWidget.configure(yscrollcommand=self.scrollbar.set)
        self.asciiText.configure(yscrollcommand=self.scrollbar.set)

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

        # Link the scrollbars
        self.textWidget.bind("<MouseWheel>", self.scrollBoth)
        self.asciiText.bind("<MouseWheel>", self.scrollBoth)
        self.offsetText.bind("<MouseWheel>", self.scrollBoth)

    def yscroll(self, *args):
        """
        Scroll the hex, ASCII, and offset text widgets vertically.

        :param args: Scrolling arguments passed by the scrollbar.
        """
        self.textWidget.yview(*args)
        self.asciiText.yview(*args)
        self.offsetText.configure(state='normal')
        self.offsetText.yview(*args)
        self.offsetText.configure(state='disabled')

    def scrollBoth(self, event):
        """
        Handle mouse wheel scrolling in all text widgets.

        :param event: Event object containing information about the scrolling event.
        """
        adjusted_delta = int(-(event.delta / 10))

        self.textWidget.yview("scroll", adjusted_delta, "units")
        self.asciiText.yview("scroll", adjusted_delta, "units")
        self.offsetText.configure(state='normal')
        self.offsetText.yview("scroll", adjusted_delta, "units")
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
        self.bookmarks = []  # Store bookmarks as list of (name, offset) tuples
        
        # Set up modern styling
        self.style = setup_modern_style()
        
        # Configure master background
        master.configure(bg=ModernTheme.BG_PRIMARY)

        # Configure rows and columns in the master frame
        master.grid_rowconfigure(0, weight=0)  # Header row
        master.grid_rowconfigure(1, weight=1)  # Main content row
        master.grid_rowconfigure(2, weight=0)  # Status bar row

        master.grid_columnconfigure(0, weight=1)  # Content area (hex/ASCII fixed, info panel expands)
        master.grid_columnconfigure(1, weight=1)  # Sidebar (expands)
        
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
        
        search_label = Label(
            search_frame,
            text="PARSED FIELDS",
            bg=ModernTheme.BG_PRIMARY,
            fg=ModernTheme.TEXT_SECONDARY,
            font=('Segoe UI', 9, 'bold')
        )
        search_label.grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 8))
        
        self.search_var = StringVar()
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            style="Modern.TEntry",
            font=('Segoe UI', 10)
        )
        self.search_entry.grid(row=1, column=0, sticky=E+W, padx=(0, 5))
        self.search_entry.insert(0, "Search fields...")
        self.search_entry.bind("<FocusIn>", lambda e: self.search_entry.delete(0, END) if self.search_entry.get() == "Search fields..." else None)
        self.search_entry.bind("<FocusOut>", lambda e: self.search_entry.insert(0, "Search fields...") if not self.search_entry.get() else None)
        
        search_buttons = Frame(search_frame, bg=ModernTheme.BG_PRIMARY)
        search_buttons.grid(row=1, column=1, sticky=E)
        
        self.search_button = ttk.Button(
            search_buttons,
            text="🔍",
            command=self.search_sequence,
            style="Secondary.TButton",
            width=3
        )
        self.search_button.pack(side=LEFT, padx=2)
        
        self.clear_button = ttk.Button(
            search_buttons,
            text="✕",
            command=self.clear_search,
            style="Secondary.TButton",
            width=3
        )
        self.clear_button.pack(side=LEFT, padx=2)
        
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
        
        # Action buttons
        actions_frame = Frame(sidebar_frame, bg=ModernTheme.BG_PRIMARY)
        actions_frame.grid(row=2, column=0, sticky=E+W+S, pady=(10, 0))
        actions_frame.grid_columnconfigure(0, weight=1)
        actions_frame.grid_columnconfigure(1, weight=1)
        
        # Open File and Stop buttons (primary actions)
        self.open_button = ttk.Button(
            actions_frame,
            text="📂 Open File",
            command=self.open_file,
            style="Modern.TButton"
        )
        self.open_button.grid(row=0, column=0, sticky=E+W, padx=(0, 5), pady=3)
        
        self.stop_parsing = False
        self.stop_button = ttk.Button(
            actions_frame,
            text="⏹ Stop",
            command=self.stop,
            state="disabled",
            style="Stop.TButton"
        )
        self.stop_button.grid(row=0, column=1, sticky=E+W, padx=(5, 0), pady=3)
        
        self.bookmark_button = ttk.Button(
            actions_frame,
            text="📌 Add Bookmark",
            command=self.add_bookmark,
            style="Secondary.TButton"
        )
        self.bookmark_button.grid(row=1, column=0, sticky=E+W, padx=(0, 5), pady=3)
        
        self.show_bookmarks_button = ttk.Button(
            actions_frame,
            text="📚 Bookmarks",
            command=self.show_bookmarks,
            style="Secondary.TButton"
        )
        self.show_bookmarks_button.grid(row=1, column=1, sticky=E+W, padx=(5, 0), pady=3)
        
        self.export_button = ttk.Button(
            actions_frame,
            text="📄 Export CSV",
            command=self.export_to_csv,
            style="Secondary.TButton"
        )
        self.export_button.grid(row=2, column=0, sticky=E+W, padx=(0, 5), pady=3)
        
        self.file_info_button = ttk.Button(
            actions_frame,
            text="ℹ️ File Info",
            command=self.show_file_info,
            style="Secondary.TButton"
        )
        self.file_info_button.grid(row=2, column=1, sticky=E+W, padx=(5, 0), pady=3)
        
        self.exit_button = ttk.Button(
            actions_frame,
            text="Exit",
            command=self.exit_app,
            style="Secondary.TButton"
        )
        self.exit_button.grid(row=3, column=0, columnspan=2, sticky=E+W, pady=(10, 0))
        
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
        self._from_hex_click = False  # Flag to prevent scroll loop on hex click
        
        # Don't start in fullscreen by default for better usability
        # self.master.attributes("-fullscreen", True)
        
        # Set a reasonable default window size
        self.master.geometry("1400x900")
        self.master.minsize(1200, 700)

        # Allow toggling fullscreen mode with F11
        self.master.bind("<F11>", self.toggle_fullscreen)
        
        # Bind treeview selection
        self.sequence_treeview.bind("<<TreeviewSelect>>", self.listbox_item_selected)
        
        # Bind scroll/resize events to update treeview highlight border position
        self.sequence_treeview.bind('<Configure>', lambda e: self.master.after_idle(self._update_treeview_border_position))
        self.sequence_treeview.bind('<MouseWheel>', lambda e: self.master.after(10, self._update_treeview_border_position))

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

    def exit_app(self):
        """
        Close the application window and exit the program.
        """
        self.master.quit()
        self.master.destroy()

    def search_sequence(self):
        """
        Search the sequence items based on the search term entered by the user.
        """
        search_term = self.search_var.get().strip().lower()
        matching_items = [item for item in self.sequence_items if item[0][1] and search_term in item[0][1].lower()]
        self.sequence_treeview.delete(*self.sequence_treeview.get_children())
        for values, tags in matching_items:
            item_id = self.sequence_treeview.insert('', 'end', values=values, tags=tags)
            if values and len(values) >= 3:  # Assuming table_value is the 3rd value in the tuple
                self.sequence_treeview.item(item_id, values=(values[0], values[1], values[2]))

    def clear_search(self):
        self.search_var.set('')
        self.sequence_treeview.delete(*self.sequence_treeview.get_children())
        for values, tags in self.sequence_items:
            item_id = self.sequence_treeview.insert('', 'end', values=values, tags=tags)
            if values and len(values) >= 3:  # Assuming table_value is the 3rd value in the tuple
                self.sequence_treeview.item(item_id, values=(values[0], values[1], values[2]))

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
        """Wrapper for treeview yscrollcommand that also updates the highlight border."""
        self.sequence_vscrollbar.set(*args)
        self.master.after_idle(self._update_treeview_border_position)

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
            offset = int(item['values'][0])
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
                    self.popItUp(child.info, tag)
                    
                    # Update status bar with offset info
                    if hasattr(self, 'current_file') and self.current_file:
                        self.status_bar.config(
                            text=f"File: {self.current_file}\t\tOffset Decimal: {offset} \tOffset Hexadecimal: 0x{offset:X}")

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
        self.bookmark_window.geometry("400x300")
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
            self.bookmark_window, columns=('Name', 'Offset'), style="Modern.Treeview", show="headings")
        self.bookmark_treeview.heading('Name', text='Name')
        self.bookmark_treeview.heading('Offset', text='Offset')
        self.bookmark_treeview.column('Name', width=250)
        self.bookmark_treeview.column('Offset', width=100)
        self.bookmark_treeview.pack(fill=BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Populate with existing bookmarks
        for name, offset in self.bookmarks:
            self.bookmark_treeview.insert('', 'end', values=(name, offset))
        
        # Bind the selection event
        self.bookmark_treeview.bind(
            "<<TreeviewSelect>>", self.bookmark_item_selected)
        
        # Delete button
        delete_btn = ttk.Button(
            self.bookmark_window,
            text="Delete Selected",
            command=self.delete_bookmark,
            style="Secondary.TButton"
        )
        delete_btn.pack(pady=(0, 15))
    
    def delete_bookmark(self):
        """Delete the selected bookmark."""
        if self.bookmark_treeview is None:
            return
        selected = self.bookmark_treeview.selection()
        if selected:
            item = self.bookmark_treeview.item(selected)
            name, offset = item['values']
            # Remove from bookmarks list
            self.bookmarks = [(n, o) for n, o in self.bookmarks if not (n == name and o == offset)]
            # Remove from treeview
            self.bookmark_treeview.delete(selected) 
        
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
            offset = values[0]
            name = values[1]
            
            # Check if already bookmarked
            if (name, offset) not in self.bookmarks:
                self.bookmarks.append((name, offset))
                self.update_status(f"Bookmarked: {name} at offset {offset}")
                
                # If bookmark window is open, update it
                if self.bookmark_treeview is not None and self.bookmark_window is not None:
                    try:
                        if self.bookmark_window.winfo_exists():
                            self.bookmark_treeview.insert('', 'end', values=(name, offset))
                    except:
                        pass
            else:
                self.update_status(f"Already bookmarked: {name}")

    def bookmark_item_selected(self, event):
        """
        Handle the bookmark selection event, scrolling to the corresponding position.

        :param event: Event object containing information about the selection event.
        """
        # Get selected index
        selected = self.bookmark_treeview.selection()
        if selected:
            item = self.bookmark_treeview.item(selected)
            # Columns are (Name, Offset)
            offset = int(item['values'][1])

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
        
        close_btn = ttk.Button(
            header_frame,
            text="✕",
            command=self.close_file_info_modal,
            style="Secondary.TButton",
            width=3
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
        import time as time_module
        
        if total == 0:
            return
            
        progress = (current / total) * 100
        current_milestone = int(progress // 10) * 10
        
        # Update progress bar
        self.progress_var.set(progress)
        self.progress_percent_var.set(f"{progress:.0f}%")
        
        # Calculate elapsed and estimated time
        elapsed = time_module.time() - self.loading_start_time
        
        # Update at every 10% milestone or every 5 seconds for long operations
        should_update = (
            current_milestone > self.last_progress_milestone or
            (elapsed - (time_module.time() - self.last_progress_update_time) > 5)
        )
        
        if should_update or current == total:
            self.last_progress_milestone = current_milestone
            self.last_progress_update_time = time_module.time()
            
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
            # reset previous file treeview
            self.sequence_treeview.delete(
                *self.sequence_treeview.get_children())  # Clear previous entries
            # Reset progress bar and show it
            self.progress_var.set(0)
            self.progress_bar.grid(
                row=3, column=0, columnspan=5, sticky=W+E+S, pady=(5, 0))
            self.progress_message.set("Loading...")
            
            # Show loading overlay for better UX
            file_size = os.path.getsize(filename)
            self._show_loading_overlay(f"Loading {os.path.basename(filename)}...")
            self._update_loading_message(
                f"Loading {os.path.basename(filename)}...",
                f"Size: {self._format_file_size(file_size)}"
            )
            
            threading.Thread(target=self.parse_file, args=(filename,)).start()

    def parse_file(self, filename):
        """
        Parse the selected file, displaying the content and controlling the progress.

        :param filename: The path to the file to be parsed.
        """
        self.stop_parsing = False
        self.open_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.current_file = filename
        
        # Reset color generator for new file
        ColorGenerator.reset()
        
        try:
            # Update loading message
            self.master.after(0, lambda: self._update_loading_message(
                "Parsing file structure...",
                "Analyzing binary data"
            ))
            
            with open(filename, "rb") as file:
                parser = get_file_parser(file)
                self.root = parser.parse()  # Store the root node
                self.total_nodes = self.count_nodes(self.root)
                self.processed_nodes = 0
                
                # Update loading message with node count
                self.master.after(0, lambda: self._update_loading_message(
                    "Rendering hex view...",
                    f"Processing {self.total_nodes} fields"
                ))
                
                self.show_parsed_data(self.root)
                # Write parsed content to log file
                self.write_parse_log(filename, self.root)
            if self.stop_parsing:
                self.update_status(f"Parsing of {filename} stopped.")
        except Exception as e:
            self.update_status(f"Could not parse file: {e}")
            # Hide loading on error
            self.master.after(0, self._hide_loading_overlay)

        # Schedule a callback to clear the status after 10 seconds
        self.master.after(10000, self.clear_status)
        self.open_button.config(state="normal")
        self.stop_button.config(state="disabled")

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
        self._hide_treeview_border()
        self._from_hex_click = False
        
        # Collect all node data first (can be done in background thread)
        self.collected_nodes = []
        self._collect_nodes(root)
        
        # Schedule GUI updates on main thread in batches
        self.master.after(0, self._update_gui_batch, 0)
    
    def _collect_nodes(self, node):
        """
        Recursively collect all node data for display.
        This can safely run in a background thread.
        """
        if self.stop_parsing:
            return
        for idx, (key, child) in enumerate(node.children):
            if self.stop_parsing:
                return
            
            # Use actual file offset (key) for display, byte_counter for hex positioning
            offset = key if key is not None else self.byte_counter
            tag = f"color{self.byte_counter}_{idx}"
            table_val = child.table_value or ''
            
            # Store all data needed for GUI update
            self.collected_nodes.append({
                'tag': tag,
                'color': child.color,
                'name': child.name,
                'data': child.data,
                'info': child.info,
                'table_val': table_val,
                'offset': offset,
                'child': child,
                'display_pos': self.byte_counter,  # position in hex widget
            })
            
            self.byte_counter += len(child.data) if child.data else 0
            self._collect_nodes(child)
    
    def _update_gui_batch(self, start_idx):
        """
        Update GUI in batches to prevent freezing.
        Runs on main thread via after().
        Dynamically adjusts batch size based on performance.
        """
        if self.stop_parsing:
            self._hide_loading_overlay()
            return
        
        # Dynamic batch sizing for better responsiveness
        # Start with smaller batches for large files, increase as we go
        total_nodes = len(self.collected_nodes)
        if total_nodes > 1000:
            BATCH_SIZE = 30  # Smaller batches for large files
        elif total_nodes > 500:
            BATCH_SIZE = 50
        else:
            BATCH_SIZE = 100  # Larger batches for smaller files
            
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
            self.text_widget.offsetText.insert('end', '00000000\n')
            
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
        Must run on main thread.
        """
        tag = node_data['tag']
        color = node_data['color']
        offset = node_data['offset']
        child = node_data['child']
        table_val = node_data['table_val']
        
        # Insert into treeview
        item_id = self.sequence_treeview.insert('', 'end', values=(
            offset, node_data['name'], table_val), tags=(tag,))
        
        # Store mappings for click synchronization
        self.tag_to_treeview_item[tag] = item_id
        self.tag_to_child[tag] = child
        self.tag_to_display_pos[tag] = node_data.get('display_pos', offset)
        if offset not in self.offset_to_tag:
            self.offset_to_tag[offset] = tag
        
        # Compute contrast text color for this background
        fg_color = ColorGenerator.get_contrast_text_color(color or '#ffffff')
        
        self.sequence_treeview.tag_configure(tag, background=color, foreground=fg_color)
        self.sequence_items.append(((offset, node_data['name'], table_val), (tag,)))
        
        # Configure tags for text widgets with contrast foreground
        self.text_widget.textWidget.tag_configure(tag, background=color, foreground=fg_color)
        self.text_widget.asciiText.tag_configure(tag, background=color, foreground=fg_color)
        
        # Insert hex and ASCII data
        if node_data['data']:
            for byte in node_data['data']:
                text = f'{byte:02x} '
                self.text_widget.textWidget.insert('end', text, (tag,))
                
                if 32 <= byte < 127:
                    ascii_char = chr(byte)
                else:
                    ascii_char = '.'
                self.text_widget.asciiText.insert('end', ascii_char, (tag,))
                
                self.display_byte_counter += 1
                if self.display_byte_counter % 16 == 0:
                    self.text_widget.textWidget.insert('end', '\n')
                    self.text_widget.asciiText.insert('end', '\n')
                    # Add next offset line
                    self.text_widget.offsetText.insert(
                        'end', f'{self.display_byte_counter:08X}\n')
        
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
        self.popItUp(child.info, tag)
        
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
            text=f"File: {(self.current_file)}\t\tOffset Decimal: {byte_offset} \tOffset Hexadecimal: 0x{byte_offset:X}")
    
    def _highlight_tag(self, tag):
        """
        Highlight a specific tag in the hex and ASCII views.
        Removes highlighting from previously highlighted tag.
        
        :param tag: The tag to highlight
        """
        # Remove previous active highlight
        if self.current_highlight_tag:
            # Restore to original color AND remove border
            try:
                for node_data in self.collected_nodes:
                    if node_data['tag'] == self.current_highlight_tag:
                        original_color = node_data['color']
                        fg = ColorGenerator.get_contrast_text_color(original_color or '#ffffff')
                        self.text_widget.textWidget.tag_configure(
                            self.current_highlight_tag,
                            background=original_color,
                            foreground=fg,
                            borderwidth=0,
                            relief='flat')
                        self.text_widget.asciiText.tag_configure(
                            self.current_highlight_tag,
                            background=original_color,
                            foreground=fg,
                            borderwidth=0,
                            relief='flat')
                        break
            except:
                pass
        
        # Apply new highlight with a distinctive border/outline effect
        self.text_widget.textWidget.tag_configure(
            tag, borderwidth=2, relief='solid')
        self.text_widget.asciiText.tag_configure(
            tag, borderwidth=2, relief='solid')
        
        self.current_highlight_tag = tag


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