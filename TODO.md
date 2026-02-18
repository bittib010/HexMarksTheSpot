- Add possibility to parse variable-length quantities (VLQ). An example of this is the delta time field in MIDI events, which can be 1 to 4 bytes long depending on the value. The parser should read bytes until it encounters a byte with the most significant bit (MSB) set to 0, indicating the end of the VLQ.
- Pages content on SQLite3 database. This is necessary to handle large databases without consuming excessive memory. Implement a mechanism to fetch and display results in chunks, allowing users to navigate through pages of results.
- Consider outsourcing the parsing and reading the finished parsed file,  to avoid the app crashing.???
- Rounded corners on buttons and input fields for a more modern look.
- precedence logic to look at extension first, then magic bytes, then alternative magic bytes.
  - This forces us to also add file protocol versioning, so we can add new fields in the future without breaking old configs. We can also add a "deprecated" field to mark fields that should no longer be used but are still supported for backward compatibility.
- Add a "deprecated" field to mark fields that should no longer be used but are still supported for backward compatibility. This allows us to phase out old fields gracefully while maintaining support for existing configurations.
- Parser field column header - left align.
- not change scroll locaton on-click on a segment. the behavior is currently messing up the workflow of sending you backto the top of the sequence clicked on. so for large sequences you get somewhat lost. Clicking n parserfield should however send you to the correct location in the hexviewer by scrolling to it and marking like implemented already, but not when clicking in the viewer itself. This is a bit of a UX issue, but it can be solved by adding a flag to indicate whether the click originated from the parser field or the hex viewer, and only scroll to the location if the click came from the parser field.
- clicking hexviewer marks the location in the parserfield currently, but the mark is hard to see unless you know which color it already had. lets change the mark to be a border change for the item instead. black border would be good.
- Extract file as hex to .txt file.
- Import file as hex text. (remove all whitespace and parse as hex).
- Set size limit? as it keeps crashing on < 3mb files.
- Open files already parsed by the app earlier. This would require saving the parsed structure to a file (e.g., JSON) and implementing a loading mechanism to reconstruct the parser state from that file. This allows users to save their work and resume later without having to re-parse the original file.


## Future Parser Enhancements

### JPEG (jpeg.json)
The current JPEG parser handles all marker segments and provides full forensic documentation. The following enhancements would require **new config_parser.py engine features** (recursive structures, endian switching within a file, offset-based seeking):
- **Deep Exif IFD/TIFF tag parsing** — Extract individual Exif tags (camera make, model, serial number, GPS coordinates, timestamps) from the APP1 payload. Requires parsing a TIFF structure with dynamic endianness (II/MM byte order mark), recursive IFD chains, and offset-based data lookups within the Exif block. Currently documented as raw bytes with forensic tag reference.
- **JFXX extension thumbnails** — Parse JFIF extension (JFXX) thumbnails in APP0 segments including JPEG-compressed thumbnails (extension_code 0x10), palette thumbnails (0x11), and RGB thumbnails (0x13). Requires sub-file JPEG parsing.
- **Canon CIFF structure** — Parse Canon Camera Image File Format (CIFF) heap structures embedded in APP0 segments. Requires recursive directory/entry parsing with heap-based storage.
- **Casio MakerNote parsing** — Parse camera-specific MakerNote IFD entries (e.g., Casio QV-R62) within Exif data. Requires camera model detection and model-specific tag dictionaries.
- **Photoshop IRB deep parsing** — Parse individual 8BIM Image Resource Blocks within APP13 (IPTC, thumbnails, ICC profiles, XMP). Currently parsed as a single blob after the identifier.
- 