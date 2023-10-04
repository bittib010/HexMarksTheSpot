# Standard Libraries
import os
import threading
import time
import csv
import hashlib

# Third-Party Libraries
from tkinter import Tk, Text, N, S, E, W
from tkinter import filedialog, Button, Scrollbar, Label
from tkinter import SEL, SEL_LAST, SEL_FIRST, END
from tkinter import TclError, Entry, Listbox, ttk
from tkinter import StringVar, DoubleVar, NO, Toplevel, BOTH
from tkhtmlview import HTMLText

# Application-specific
from main import get_file_parser




class TextWidget:
    """
    A class to create and manage text widgets for displaying hex and ASCII data.
    """

    def __init__(self, master):
        """
        Initialize the TextWidget with scrollbars and other configurations.

        :param master: The parent widget for this TextWidget.
        """
        self.textWidget = Text(master, exportselection=False, width=49, height=43, font=(
            'Courier 10 bold'), padx=5, bg='black', fg='green', relief='flat', bd=2)

        self.scrollbar = Scrollbar(master, command=self.yscroll)

        #self.popupText = Text(master, width=35, height=38, font=(
        #    'Courier 12 bold'), padx=5, bg='white', relief='sunken', bd=2)
        
        self.popupText = HTMLText(master, width=35, height=38, font=('Courier 12 bold'), padx=5, bg='white', relief='sunken', bd=2)
        
        self.asciiText = Text(master, exportselection=False, width=16, height=43, font=(
            'Courier 10 bold'), padx=5, bg='black', fg='green', relief='flat', bd=2)

        self.textWidget.configure(yscrollcommand=self.scrollbar.set)
        self.asciiText.configure(yscrollcommand=self.scrollbar.set)

        self.textWidget.grid(row=1, column=0, pady=15,
                             padx=(20, 0), sticky=W+E+N+S)
        self.scrollbar.grid(row=1, column=1, pady=15, sticky=N+S+W)
        self.asciiText.grid(row=1, column=2, pady=15, sticky=W)
        self.popupText.grid(row=1, column=3, pady=15, padx=(0, 10), sticky=E)

        self.textWidget.tag_configure(
            "sel", background="#c3c3c3", foreground="black")
        self.asciiText.tag_configure(
            "sel", background="#c3c3c3", foreground="black")

        # Link the scrollbars
        self.textWidget.bind("<MouseWheel>", self.scrollBoth)
        self.asciiText.bind("<MouseWheel>", self.scrollBoth)

    def yscroll(self, *args):
        """
        Scroll both the hex and ASCII text widgets vertically.

        :param args: Scrolling arguments passed by the scrollbar.
        """
        self.textWidget.yview(*args)
        self.asciiText.yview(*args)

    def scrollBoth(self, event):
        """
        Handle mouse wheel scrolling in both text widgets.

        :param event: Event object containing information about the scrolling event.
        """
        adjusted_delta = int(-(event.delta / 10))

        self.textWidget.yview("scroll", adjusted_delta, "units")
        self.asciiText.yview("scroll", adjusted_delta, "units")
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
    """

    def __init__(self, master):
        """
        Initialize the main application window with widgets and layout configurations.

        :param master: The parent widget for this application.
        """
        self.master = master
        self.bookmark_treeview = None
        self.bookmark_window = None

        # Stop parsing button
        self.stop_parsing = False
        self.stop_button = Button(
            master, text="Stop", command=self.stop, state="disabled")
        self.stop_button.grid(row=3, column=6, padx=10, pady=10, sticky=W+E)

        # Configure rows and columns in the master frame
        master.grid_rowconfigure(0, weight=0)  # Top padding row
        master.grid_rowconfigure(1, weight=1)  # TextWidget row
        master.grid_rowconfigure(2, weight=0)  # Status bar row
        master.grid_rowconfigure(3, weight=0)  # Buttons row
        master.grid_rowconfigure(4, weight=0)  # Progress bar row
        master.grid_rowconfigure(5, weight=0)  # Progress label row

        # TextWidget column (hex view)
        master.grid_columnconfigure(0, weight=1, minsize=420)
        master.grid_columnconfigure(1, weight=0)  # Scrollbar column
        # TextWidget column (ASCII view)
        master.grid_columnconfigure(2, weight=1, minsize=150)
        master.grid_columnconfigure(
            3, weight=0, minsize=150)  # PopupText column
        master.grid_columnconfigure(4, weight=1)  # Sequence treeview column
        master.grid_columnconfigure(5, weight=0)  # Buttons column
        master.grid_columnconfigure(6, weight=0)  # Buttons column
        # Sequence treeview scrollbar column
        master.grid_columnconfigure(7, weight=0)

        self.text_widget = TextWidget(master)

        # Open file button
        self.open_button = Button(
            master, text="Open File", command=self.open_file)
        self.open_button.grid(row=2, column=6, padx=10, pady=(40,10), sticky=W+E)

        # Exit button
        self.exit_button = Button(master, text="Exit", command=self.exit_app)
        self.exit_button.grid(row=4, column=6, padx=10, pady=10, sticky=W+E)

        # Export to CSV treeview
        self.export_button = Button(master, text="Export to CSV", command=self.export_to_csv)
        self.export_button.grid(row=4, column=5, padx=10, pady=10, sticky=W+E)

        # Set bookmark button
        self.bookmark_button = Button(
            master, text="Add Bookmark", command=self.add_bookmark)
        self.bookmark_button.grid(
            row=3, column=5, padx=10, pady=10, sticky=W+E)

        # Show bookmarks button
        self.show_bookmarks_button = Button(
            master, text="Show Bookmarks", command=self.show_bookmarks)
        self.show_bookmarks_button.grid(
            row=2, column=5, padx=10, pady=(40,10), sticky=W+E)

        self.last_clicked = None

        # File info button
        self.file_info_button = Button(master, text="File Info", command=self.show_file_info)
        self.file_info_button.grid(row=5, column=6, padx=10, pady=10, sticky=W+E)

        # Start in fullscreen mode
        self.master.attributes("-fullscreen", True)

        # Allow toggling fullscreen mode with F11
        self.master.bind("<F11>", self.toggle_fullscreen)

        self.sequence_treeview = ttk.Treeview(
            self.master, columns=('Offset', 'Name', "Value"), height=43)
        # Heading for the first implicit column
        self.sequence_treeview.heading('#0', text='')
        self.sequence_treeview.heading('Offset', text='Offset')
        self.sequence_treeview.heading('Name', text='Name')
        self.sequence_treeview.heading('Value', text='Value')

        # Hide the first implicit column
        self.sequence_treeview.column('#0', stretch=NO, width=0)
        self.sequence_treeview.column("Offset", width=39)
        self.sequence_treeview.column("Name", width=70)
        self.sequence_treeview.column("Value", width=150)

        self.sequence_treeview.grid(
            row=1, column=4, columnspan=3, padx=10, pady=15, sticky=W+E+N+S)

        # status bar
        self.status_bar = Label(
            self.master, text="Offset: 0", bd=1, relief="sunken", anchor=W)
        self.status_bar.grid(row=2, column=0, columnspan=5,
                             sticky=W+E+S, pady=(0, 0))

        # Add a search entry
        self.search_var = StringVar()
        self.search_entry = Entry(master, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=4, padx=10, pady=10, sticky=W+E)
        self.search_button = Button(
            master, text="Search", command=self.search_sequence)
        self.search_button.grid(row=0, column=6, padx=10, pady=10, sticky=W+E)
        self.clear_button = Button(
            master, text="Clear", command=self.clear_search)
        self.clear_button.grid(row=0, column=5, padx=10, pady=10, sticky=W+E)

        # Store original sequence items
        self.sequence_items = []

        # Bind the search entry to update the list on every key press
        # self.search_entry.bind("<KeyRelease>", self.search_sequence)

        # Progress bar
        self.progress_var = DoubleVar()  # Variable to track progress bar value
        self.progress_bar = ttk.Progressbar(
            self.master, variable=self.progress_var, orient="horizontal", length=200, mode="determinate")
        self.progress_bar.grid(
            row=4, column=0, columnspan=5, sticky=W+E+S, pady=(0, 0))
        self.progress_message = StringVar()
        self.progress_label = Label(
            self.master, textvariable=self.progress_message, bd=1, relief="sunken", anchor=W)
        self.progress_label.grid(
            row=5, column=0, columnspan=5, sticky=W+E+S, pady=(0, 0))

        # Vertical Scrollbar
        self.sequence_vscrollbar = Scrollbar(self.master, orient="vertical")
        self.sequence_vscrollbar.grid(row=1, column=7, sticky=E+N+S)
        self.sequence_treeview.configure(
            yscrollcommand=self.sequence_vscrollbar.set)
        self.sequence_vscrollbar.config(command=self.sequence_treeview.yview)

        # Horizontal Scrollbar
        self.sequence_hscrollbar = Scrollbar(self.master, orient="horizontal")
        self.sequence_hscrollbar.grid(
            row=2, column=4, columnspan=3, sticky=N+E+W)
        self.sequence_treeview.configure(
            xscrollcommand=self.sequence_hscrollbar.set)
        self.sequence_hscrollbar.config(command=self.sequence_treeview.xview)

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

    def listbox_item_selected(self, event):
        """
        Handle the selection event in the sequence treeview, scrolling to the corresponding position.

        :param event: Event object containing information about the selection event.
        """
        # Get selected index
        selected = self.sequence_treeview.selection()
        if selected:
            item = self.sequence_treeview.item(selected)
            offset = int(item['values'][0])

            # Calculate the corresponding row and column in the Text widget
            row = offset // 16 + 1  # Adding 1 because Text widget indices start from 1
            # Every byte in hex view is 3 characters (e.g., "FF ")
            col_hex = (offset % 16) * 3
            col_ascii = offset % 16
            # Scroll both views to the selected position
            self.text_widget.textWidget.see(f"{row}.{col_hex}")
            self.text_widget.asciiText.see(f"{row}.{col_ascii}")

    def show_bookmarks(self):
        """
        Display the bookmarks window containing the saved bookmarks.
        """
        self.bookmark_window = Toplevel(self.master)
        self.bookmark_window.title("Bookmarks")
        self.bookmark_treeview = ttk.Treeview(
            self.bookmark_window, columns=('Offset', 'Name'))
        # Heading for the first implicit column
        self.bookmark_treeview.heading('#0', text='')
        self.bookmark_treeview.heading('Name', text='Name')
        self.bookmark_treeview.heading('Offset', text='Offset')
        # Hide the first implicit column
        self.bookmark_treeview.column('#0', stretch=NO, width=0)
        self.bookmark_treeview.pack(fill=BOTH, expand=True)
        # Bind the selection event
        self.bookmark_treeview.bind(
            "<<TreeviewSelect>>", self.bookmark_item_selected) 
        
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
        if self.bookmark_treeview is not None:
            selected = self.sequence_treeview.selection()
            if selected:
                item = self.sequence_treeview.item(selected)
                name, offset, *_ = item['values']
                # Add to the bookmarks if it doesn't exist already
                bookmarks = [self.bookmark_treeview.item(
                    bookmark)['values'] for bookmark in self.bookmark_treeview.get_children()]
                if (name, offset) not in bookmarks:
                    self.bookmark_treeview.insert(
                        '', 'end', values=(name, offset))

    def bookmark_item_selected(self, event):
        """
        Handle the bookmark selection event, scrolling to the corresponding position.

        :param event: Event object containing information about the selection event.
        """
        # Get selected index
        selected = self.bookmark_treeview.selection()
        if selected:
            item = self.bookmark_treeview.item(selected)
            offset = int(item['values'][0])

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
        # Create a popup to show file info
        file_info_window = Toplevel(self.master)
        file_info_window.title("File Info")
        Label(file_info_window, text=f"File: {self.current_file}").pack()
        Label(file_info_window, text=f"Size: {os.path.getsize(self.current_file)} bytes").pack()
        Label(file_info_window, text=f"Hash: {self.generate_file_hash()}").pack()


    def open_file(self):
        """
        Open a file dialog and initiate the parsing of the selected file.
        """
        current_directory = os.getcwd()  # Get current working directory
        filename = filedialog.askopenfilename(initialdir=current_directory,
                                              title="Select File",
                                              filetypes=(("All Files", "*.*"),
                                                         ("SQLite Files",
                                                          "*.sqlite"),
                                                         ("PNG Files", "*.png"),
                                                         ("JPG Files", "*.jpg"),
                                                         ("JPEG Files", "*.jpeg"),
                                                         ("MFT Files", "$MFT"),
                                                         ("LNK Files", "*.lnk")))
        if filename:
            # reset previous file treeview
            self.sequence_treeview.delete(
                *self.sequence_treeview.get_children())  # Clear previous entries
            # Reset progress bar and show it
            self.progress_var.set(0)
            self.progress_bar.grid(
                row=3, column=0, columnspan=5, sticky=W+E+S, pady=(5, 0))
            self.progress_message.set("Loading...")
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
        try:
            with open(filename, "rb") as file:
                parser = get_file_parser(file)
                self.root = parser.parse()  # Store the root node
                self.total_nodes = self.count_nodes(self.root)
                self.processed_nodes = 0
                self.show_parsed_data(self.root)
            if self.stop_parsing:
                self.update_status(f"Parsing of {filename} stopped.")
            else:
                self.update_status(f"{filename} completed successfully.")
        except Exception as e:
            self.update_status(f"Could not parse file: {e}")

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

    def update_progress(self, progress):
        """
        Update the progress bar with the given progress value.

        :param progress: The progress value to be set (0 to 100).
        """
        self.progress_var.set(progress)
        if progress >= 100:
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

        :param root: The root node of the parsed data.
        """
        self.sequence_items = []  # Initialize the sequence items list
        self.text_widget.textWidget.configure(
            state='normal')  # Temporarily enable the widget
        self.text_widget.asciiText.configure(
            state='normal')  # Temporarily enable the widget

        self.text_widget.textWidget.delete('1.0', 'end')
        self.text_widget.asciiText.delete('1.0', 'end')

        # Mark text mirror
        self.text_widget.textWidget.bind(
            "<ButtonRelease-1>", lambda e: self.mirror_highlight(self.text_widget.textWidget))
        self.text_widget.asciiText.bind(
            "<ButtonRelease-1>", lambda e: self.mirror_highlight(self.text_widget.asciiText))
        self.text_widget.textWidget.bind(
            "<Button-1>", lambda e: self.clear_mirror_highlight())
        self.text_widget.asciiText.bind(
            "<Button-1>", lambda e: self.clear_mirror_highlight())

        self.iterNode(root)

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

        except TclError as e:
            # This exception is raised when there's no selection.
            print(e)

    def clear_mirror_highlight(self):
        for widget in [self.text_widget.textWidget, self.text_widget.asciiText]:
            widget.tag_remove("mirror_highlight", "1.0", END)

    def iterNode(self, node):
        """
        Iterate through the node tree, displaying the content and handling the user interactions.

        :param node: The current node in the iteration.
        """
        if self.stop_parsing:
            return
        byte_counter = 0
        for idx, (key, child) in enumerate(node.children):
            if self.stop_parsing:
                return
            tag = f"color{idx}"  # Create a unique tag for each item
            color = child.color  # Use the color from the Node
            table_val = child.table_value
            offset = byte_counter

            if table_val:
                text_from_popup_text = table_val
            else:
                text_from_popup_text = ''

            item_id = self.sequence_treeview.insert('', 'end', values=(
                offset, child.name, text_from_popup_text), tags=(tag,))
            
            # Update the Value column if needed
            if text_from_popup_text:
                self.sequence_treeview.item(
                    item_id, values=(offset, child.name, text_from_popup_text))

            self.sequence_treeview.tag_configure(tag, background=child.color)


            # Search in treeview and place it after search
            self.sequence_items.append(((offset, child.name, text_from_popup_text), (tag,)))


            self.text_widget.textWidget.tag_configure(tag, background=color)
            self.text_widget.asciiText.tag_configure(tag, background=color)
            self.text_widget.textWidget.configure(
                state='normal')  # Temporarily enable the widget
            self.text_widget.asciiText.configure(
                state='normal')  # Temporarily enable the widget
            for byte in child.data:
                text = f'{byte:02x} '
                self.text_widget.textWidget.insert('end', text, (tag,))
                # Insert ASCII representation into the asciiText widget
                if 32 <= byte < 127:
                    ascii_char = chr(byte)
                else:
                    ascii_char = '.'
                self.text_widget.asciiText.insert('end', ascii_char, (tag,))
                byte_counter += 1
                if byte_counter % 16 == 0:
                    self.text_widget.textWidget.insert('end', '\n')
                    self.text_widget.asciiText.insert('end', '\n')

            self.text_widget.textWidget.configure(
                state='disabled')  # Make the widget read-only
            self.text_widget.asciiText.configure(
                state='disabled')  # Make the widget read-only

            self.text_widget.textWidget.tag_bind(tag, "<Button-1>",
                                                 lambda event, currentTag=tag, child=child: self.handle_click(event, currentTag, child))
            self.text_widget.asciiText.tag_bind(tag, "<Button-1>",
                                                lambda event, currentTag=tag, child=child: self.handle_click(event, currentTag, child))
            # Bind the selection event
            self.sequence_treeview.bind(
                "<<TreeviewSelect>>", self.listbox_item_selected)

            self.iterNode(child)

            self.processed_nodes += 1
            progress = (self.processed_nodes / self.total_nodes) * 100
            self.master.after(0, self.update_progress, progress)

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

        :param event: Event object containing information about the click event.
        :param tag: The tag associated with the clicked text.
        :param child: The child node associated with the clicked text.
        """
        self.last_clicked = child
        self.popItUp(child.info, tag)

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

        self.status_bar.config(
            text=f"File: {(self.current_file)}\t\tOffset Decimal: {byte_offset} \tOffset Hexadecimal: 0x{byte_offset:X}")


if __name__ == "__main__":
    root = Tk()
    app = Main(root)
    root.title("Poppetypop")
    root.configure(bg='#F0F0F0')  # Change to a light background color
    root.mainloop()

# TODO: Consider adding menu: File
# TODO: Add information showing related info for the current file chosen as a questionmark button in a corner to represent the file in its birdseye view.
# TODO: Add fucntionality to export as CSV the bookmarks and the complete treeview
# TODO: Add funcitonality to import CSV bookmarks?? Should be the same file - hash check? Import a full parsed file instead?