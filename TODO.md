- Add a template for: 
  - ~~WAL~~ (done — `wal.json`)
  - 
  - We have a lot of `*.bt` files in the Artefacts folder, which are the template files belonging to 010 Editor. These files needs to be converted into our wanted format by looking at the structure and converting to our format specifications json. 
    - ~~BMP.bt~~ (done — `bmp.json`)
    - ~~GIF.bt~~ (done — `gif.json`, header/LSD parsed; block dispatch needs engine features)
    - Remaining: 7ZIP, ASF, AVI, BPlist, CAB, DOC, DS_Store, FLV, H264, IconCache, JPG (already have jpeg.json), MBR, MP4, MXF, ONE, PB, RegistryDhcpInterfaceOptions, RegistryPolicyFile, ThumbCache, Torrent

- Add current filename/path to be visible in gui: "Currently investigating: {filename}" (can be added to the top of the left pane, or as a header above the hex viewer). This provides context to the user about which file they are currently analyzing, especially when working with multiple files in a session. 
- Add an additional Bookmark possibility that build no the existing function to mark a section in the hexviewer. The existing functionality for makring a section simply by clicking a place and draging to select multiple bytes in the viewer is reflected with a background change in color as well as the selected border change in the opposite viewer (hex vs ascii). This functionality should be both be improved with realtime update to the color change as well as happen on the click+drag on the selected viewer (if clcik on drag on hexviewer it should reflect there too, not just on the opposite) - furthermore, if selection has been made we should enable a right-click option to save that sequence to bookmark, which would then be added to the bookmark list with the offset range and a user-provided name/description. This allows for more flexible bookmarking of arbitrary byte ranges, not just predefined fields.
- Close the gap between hexviewer and ASCII viewer. A fat border or simply both borders side by side is enough. 

PS! Remember to update Copilot instructions if necessary on new implementations. 

---

## Proposed Improvements — Forensic Investigation Suite

### Parser Engine Enhancements (`config_parser.py`)

1. **Section-level endianness inheritance** — Allow `struct`/`section` to set `"endianness"` that propagates to all children, overriding the global default. Currently each child must individually specify its own `"endianness"`, making mixed-endian formats (Exif TIFF, ELF with different section byte orders) verbose. The parent endianness would act as a scoped override between global and field-level.

2. **Offset-based seeking / computed field positions** — Add an `"offset"` property on fields that positions the read cursor at a **computed offset** (absolute or relative to a base like segment start) before reading. This enables parsing formats where data positions are stored as pointer fields (TIFF IFD value offsets, PE section RVAs, LNK extra data blocks). Example: `"offset": "$IFD0_Offset + $ExifStartOffset"`.

3. **Checksum / hash verification fields** — A new field type or property (`"checksum"`) that computes CRC32/Adler32/SHA-256 over a byte range and compares against a stored value. Useful for detecting silent corruption in PNG chunks, ZIP central directories, EVTX records, and PE section integrity.

4. **Bit-level field parsing** — Support fields smaller than 1 byte for formats that pack data at the bit level (JPEG quantization table precision nibble + table ID nibble in a single byte, GIF packed fields, TCP flags). Could use `"size": "4b"` syntax for bit-width fields.

5. **String encoding auto-detection** — A `"string_auto"` type that tries UTF-8 → UTF-16LE → UTF-16BE → Latin-1 decoding with a confidence score. Useful for carving text from unallocated space or unknown record formats. I think this might best fit as some parsing specific changes to the description, like: "The sequence corresponds to this bit pattern, which could be interpreted into different flags being set. The different flags available for this sequence in specific corresponds to these <insert the list of possible encodings and their confidence scores>.". This approach aligns with the possibility to do logic in the engine/template, allowing for more dynamic and context-aware parsing AND (most importantly) findings and learnings for the user. 

6. **Multi-segment / virtual file parsing** — Support parsing a logical structure that spans non-contiguous byte ranges (e.g., fragmented NTFS $MFT records, SQLite overflow chains, multi-extent files). Could use `"segments": [{"offset": X, "size": Y}, ...]` to define the byte ranges.

### Detection & Analysis Features

7. **Entropy analysis per field/region** — Calculate Shannon entropy (0.0–8.0) for each parsed field and display as a color-coded bar or column in the treeview. High entropy (>7.5) suggests encryption/compression; low entropy (<1.0) suggests padding/zeroes; medium entropy with specific patterns can fingerprint file types. Add a whole-file entropy heatmap overlay on the hex viewer.

8. **Byte frequency histogram** — Show a 256-bar histogram of byte value distribution for selected regions or the entire file. Uniform distribution = encrypted/compressed; spikes at specific values = text encoding patterns; large 0x00 spike = sparse/padded file. Display as a sidebar widget or popup.

9. **Pattern / signature scanning** — Automated scanning for known byte patterns beyond magic bytes: credit card numbers (Luhn-validated), email addresses, URLs, file signatures embedded within files (ZIP inside JPEG, PE inside document), cryptocurrency wallet addresses, Base64-encoded blobs, GPS coordinate patterns. Results shown as a "Findings" panel with severity classification.

10. **String extraction and display** — Dedicated "Strings" tab/panel showing all printable ASCII and Unicode strings above a configurable minimum length (default 4 chars), with their offsets. Similar to the Unix `strings` command but integrated with the hex viewer — clicking a string highlights its bytes. Filter by encoding (ASCII/UTF-8/UTF-16), minimum length, and regex pattern.

11. **Timestamp timeline view** — Collect all parsed timestamp fields (filetime, unix_time, dos_datetime) from the current file and display them on a visual timeline. Useful for establishing a chronology: file creation → modification → access times, email sent/received, photo taken/edited. Highlight temporal anomalies (timestamps in the future, timestamps before the file format was invented, timestamps that violate causal order).

12. **Cross-field consistency checks** — Beyond `antiforensic` and `expected_values`, add a `"consistency"` property that validates relationships between fields. Examples: `"consistency": "$FileSize == $HeaderSize + $DataSize"`, `"consistency": "$Checksum == crc32($Data)"`. Violations shown as warnings (yellow) vs. anti-forensic violations (red+black).

### GUI Enhancements

13. **File comparison / diff view** — Side-by-side hex comparison of two files with highlighted differences. Essential for: comparing clean vs. tampered files, before/after analysis, identifying what a tool changed. Color-code: green=added, red=removed, yellow=modified. Show a summary: N bytes differ, first diff at offset X.

14. **Findings / anomaly summary panel** — A dedicated panel that aggregates all noteworthy findings: anti-forensic detections, expected_value violations, unusual entropy regions, timestamps, and forensic-flagged fields. Sortable by severity (critical/warning/info) and type. One-click navigation to any finding in the hex viewer. This gives investigators a quick triage view without scrolling through every field.

15. **Export to forensic report** — Generate a structured forensic report (PDF/HTML) with: file metadata (name, path, hash, size), key findings summary, all parsed fields with values, hex dump of flagged regions, bookmarks with annotations, and examiner notes. Include chain-of-custody metadata (examiner name, case ID, date). Suitable for court submission.

16. **Multi-file / batch analysis** — Open multiple files in tabs or a project view. Run parsers across all files and aggregate findings. Useful for analyzing a directory of recovered files, comparing multiple versions of a database, or processing a forensic image extraction.

17. **Data interpreter panel** — A floating panel that shows the bytes at the current cursor position interpreted as multiple types simultaneously: uint8/16/32/64 (LE+BE), int8/16/32/64 (LE+BE), float32/64, FILETIME, Unix time, ASCII, UTF-16, hex. Updates live as the user moves the cursor. Similar to 010 Editor's "Inspector" panel. Invaluable for unknown format reverse engineering.

18. **Hex editor mode** — Allow editing hex values directly with undo/redo, save-as, and change tracking. Show a diff of modifications before saving. Useful for: patching headers to repair damaged files, testing parser behavior with modified values, and preparing test files for parser development.

19. **Annotation / tagging system** — Let investigators add free-text annotations to arbitrary byte ranges (not just bookmarked fields). Support tags (e.g., "suspicious", "evidence", "timestamp", "encrypted") with color coding. Annotations persist per-file via the cache system and are included in report exports.

### Color & Visual Improvements

20. **Entropy-based hex byte coloring** — Color each hex byte in the viewer by its local entropy contribution: blue for low-entropy (repetitive/padding), white for normal, red for high-entropy (random/encrypted). Provides instant visual identification of encrypted blocks, compressed data, padding regions, and plaintext within binary files.

21. **Data type coloring mode** — Alternative color mode where bytes are colored by their data type category rather than field ownership: blue for integers, green for strings/text, purple for timestamps, orange for pointers/offsets, gray for padding/skip, red for suspect/anti-forensic. Helps identify structure in unparsed regions.

22. **Minimap / file overview bar** — A narrow vertical bar alongside the scrollbar showing a color-coded miniature view of the entire file. Each pixel row represents a byte range colored by field type, entropy, or parser coverage. Click to jump. Shows the "shape" of the file at a glance — where headers end, where data regions are, where gaps exist.

## Future Parser Enhancements

### JPEG (jpeg.json)
The current JPEG parser handles all marker segments and provides full forensic documentation. The following enhancements would require **new config_parser.py engine features** (recursive structures, endian switching within a file, offset-based seeking):
- ~~**Deep Exif IFD/TIFF tag parsing**~~ (partially done — TIFF header, IFD0 entry-level parsing with tag value_map, Exif sub-IFD and GPS sub-IFD conditional parsing using the declarative JSON config; individual IFD entries parsed with tag ID, type, count, and value fields)
- **JFXX extension thumbnails** — Parse JFIF extension (JFXX) thumbnails in APP0 segments including JPEG-compressed thumbnails (extension_code 0x10), palette thumbnails (0x11), and RGB thumbnails (0x13). Requires sub-file JPEG parsing.
- **Canon CIFF structure** — Parse Canon Camera Image File Format (CIFF) heap structures embedded in APP0 segments. Requires recursive directory/entry parsing with heap-based storage.
- **Casio MakerNote parsing** — Parse camera-specific MakerNote IFD entries (e.g., Casio QV-R62) within Exif data. Requires camera model detection and model-specific tag dictionaries.
- **Photoshop IRB deep parsing** — Parse individual 8BIM Image Resource Blocks within APP13 (IPTC, thumbnails, ICC profiles, XMP). Currently parsed as a single blob after the identifier.
- **XMP metadata parsing** — Extract and parse XMP metadata embedded in JPEG files, including Dublin Core, Photoshop, and custom namespaces. Requires XML parsing and namespace handling.
- ~~**DQT individual table parsing**~~ (done — precision/ID byte parsed separately, 64 QT values as bytes blob with forensic fingerprinting documentation)
- ~~**SOF component parsing**~~ (done — individual color component entries parsed as repeated structs: component ID with value_map, sampling factors with subsampling ratio display, quantization table selector with expected_values)