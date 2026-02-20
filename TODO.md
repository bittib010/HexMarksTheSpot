- Add a template for: 
  - We have a lot of `*.bt` files in the Artefacts folder, which are the template files belonging to 010 Editor. These files needs to be converted into our wanted format by looking at the structure and converting to our format specifications json. 
    - Remaining: 7ZIP, ASF, AVI, BPlist, CAB, DOC, DS_Store, FLV, H264, IconCache, JPG (already have jpeg.json), MBR, MP4, MXF, ONE, PB, RegistryDhcpInterfaceOptions, RegistryPolicyFile, ThumbCache, Torrent

- Add an additional Bookmark possibility that build no the existing function to mark a section in the hexviewer. The existing functionality for makring a section simply by clicking a place and draging to select multiple bytes in the viewer is reflected with a background change in color as well as the selected border change in the opposite viewer (hex vs ascii). This functionality should be both be improved with realtime update to the color change as well as happen on the click+drag on the selected viewer (if clcik on drag on hexviewer it should reflect there too, not just on the opposite) - furthermore, if selection has been made we should enable a right-click option to save that sequence to bookmark, which would then be added to the bookmark list with the offset range and a user-provided name/description. This allows for more flexible bookmarking of arbitrary byte ranges, not just predefined fields.

PS! Remember to update Copilot instructions if necessary on new implementations. 

---

## Proposed Improvements — Forensic Investigation Suite

### Parser Engine Enhancements (`config_parser.py`)


1. **Offset-based seeking / computed field positions** — Add an `"offset"` property on fields that positions the read cursor at a **computed offset** (absolute or relative to a base like segment start) before reading. This enables parsing formats where data positions are stored as pointer fields (TIFF IFD value offsets, PE section RVAs, LNK extra data blocks). Example: `"offset": "$IFD0_Offset + $ExifStartOffset"`. Can this be hard to achieve? How do we ensure that the parsing will be complete and that the parsed information is ordered correctly etc? Now the verify functionality becomes much more important.

2. **Checksum / hash verification fields** — A new field type or property (`"checksum"`) that computes CRC32/Adler32/SHA-256 over a byte range and compares against a stored value. Useful for detecting silent corruption in PNG chunks, ZIP central directories, EVTX records, and PE section integrity.

3. **Bit-level field parsing** — Support fields smaller than 1 byte for formats that pack data at the bit level (JPEG quantization table precision nibble + table ID nibble in a single byte, GIF packed fields, TCP flags). Could use `"size": "4b"` syntax for bit-width fields. I think this might best fit as some parsing specific changes to the description, like: "The sequence corresponds to this bit pattern, which could be interpreted into different flags being set. The different flags available for this sequence in specific corresponds to these <insert the list of possible encodings and their confidence scores>.". This approach aligns with the possibility to do logic in the engine/template, allowing for more dynamic and context-aware parsing AND (most importantly) findings and learnings for the user. 

4. **String encoding auto-detection** — A `"string_auto"` type that tries UTF-8 → UTF-16LE → UTF-16BE → Latin-1 decoding with a confidence score. Useful for carving text from unallocated space or unknown record formats. 

5. **Nullify parsed values for long hex sequences of 0x00** — For fields that parse large byte ranges, if the content is all 0x00, display the parsed value as `null`/`nulled out`/`no data besides 0s` instead of dumping a long string of zeroes. This improves readability for sparse files, uninitialized data, and padding regions. But if the sequence has a bunch of 0s but some non-zero bytes, we should strip the edged of those to actually print the hex values. This is ONLY to be used on sequences that are either part of `unallocated` or `uparsed`/`unknown` data. We ALWAYS want to prioritize the real representation of known fields - so consider this as more of a resorting to a more user-friendly display of the content of unknown/unallocated fields.

6. **Multi-segment / virtual file parsing** — Support parsing a logical structure that spans non-contiguous byte ranges (e.g., fragmented NTFS $MFT records, SQLite overflow chains, multi-extent files). Could use `"segments": [{"offset": X, "size": Y}, ...]` to define the byte ranges.

### Detection & Analysis Features

1. **Byte frequency histogram** — Show a 256-bar histogram of byte value distribution for selected regions or the entire file. Uniform distribution = encrypted/compressed; spikes at specific values = text encoding patterns; large 0x00 spike = sparse/padded file. Display as a sidebar widget or popup.

2. **Pattern / signature scanning** — Automated scanning for known byte patterns beyond magic bytes: credit card numbers (Luhn-validated), email addresses, URLs, file signatures embedded within files (ZIP inside JPEG, PE inside document), cryptocurrency wallet addresses, Base64-encoded blobs, GPS coordinate patterns. Results shown as a "Findings" panel with severity classification. This could be an "add-on" triggered by a button click only available after the file has been completely parsed. It should call a separate script that runs in the background and only affect the main application by adding a toast message like: "Initiated scanning of patterns of <filename> - results will be added to <path/filename.md> once completed". This way we can avoid performance issues by running the scanning in a separate thread and only update the main application once the results are ready.

3.  **Cross-field consistency checks** — Beyond `antiforensic` and `expected_values`, add a `"consistency"` property that validates relationships between fields. Examples: `"consistency": "$FileSize == $HeaderSize + $DataSize"`, `"consistency": "$Checksum == crc32($Data)"`. Violations shown as warnings (yellow) vs. anti-forensic violations (red+black).

### GUI Enhancements

1.  **Hex editor mode** — Allow editing hex values directly with undo/redo, save-as, and change tracking. Show a diff of modifications before saving. Useful for: patching headers to repair damaged files, testing parser behavior with modified values, and preparing test files for parser development. Not aiming to be a heavy editor, but mainly for solving issues with possible damaged files. 

2.  **Annotation / tagging system** — Let investigators add free-text annotations to arbitrary byte ranges (not just bookmarked fields). Support tags (e.g., "suspicious", "evidence", "timestamp", "encrypted") with color coding. Annotations persist per-file via the cache system and are included in report exports.

### Color & Visual Improvements

1. Current coloring behavior seem a little incosistent. The color precedence categories for antiforensics, forensic value etc are working really good - but i think that we should default to two varying colors (both background and text) for everything that is uncategorized. This makes it easy to see which fields are less important (per template definition) as well as the next sequence is differentiated by having the inverse of the previous sequences color. So if one field has Grey Background with white text, the next field would have white background with grey text. This makes it easier to visually separate fields and also gives a better visual overview of the file structure. Then, the more important categories (antiforensics, forensic value, expected value, consistency violation) can have their own distinct colors that override the default alternating scheme which will make them pop more out and become MUCH more visible and attractive to the user. 
2. The border of the parents of the selected field marked around the hex and ascii bytes should be more visible. It is currently looking like a thin line where it seem to mimick the engraved cells instead of an actual border around the cells. The selected sequwence has a very good black border around it, and that is exactly what i want for the parent but only with a different color. Currently it should be white - but green or blue might be better. 

## Future Parser Enhancements

### JPEG (jpeg.json)
The current JPEG parser handles all marker segments and provides full forensic documentation. The following enhancements would require **new config_parser.py engine features** (recursive structures, endian switching within a file, offset-based seeking):
- ~~**Deep Exif IFD/TIFF tag parsing**~~ (partially done — TIFF header, IFD0 entry-level parsing with tag value_map, Exif sub-IFD and GPS sub-IFD conditional parsing using the declarative JSON config; individual IFD entries parsed with tag ID, type, count, and value fields)
- **JFXX extension thumbnails** — Parse JFIF extension (JFXX) thumbnails in APP0 segments including JPEG-compressed thumbnails (extension_code 0x10), palette thumbnails (0x11), and RGB thumbnails (0x13). Requires sub-file JPEG parsing.
- **Canon CIFF structure** — Parse Canon Camera Image File Format (CIFF) heap structures embedded in APP0 segments. Requires recursive directory/entry parsing with heap-based storage.
- **Casio MakerNote parsing** — Parse camera-specific MakerNote IFD entries (e.g., Casio QV-R62) within Exif data. Requires camera model detection and model-specific tag dictionaries.
- **Photoshop IRB deep parsing** — Parse individual 8BIM Image Resource Blocks within APP13 (IPTC, thumbnails, ICC profiles, XMP). Currently parsed as a single blob after the identifier.
- **XMP metadata parsing** — Extract and parse XMP metadata embedded in JPEG files, including Dublin Core, Photoshop, and custom namespaces. Requires XML parsing and namespace handling.
