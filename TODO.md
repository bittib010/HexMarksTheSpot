- Add a template for: 
  - ~~WAL~~ (done — `wal.json`)
  - 
  - We have a lot of `*.bt` files in the Artefacts folder, which are the template files belonging to 010 Editor. These files needs to be converted into our wanted format by looking at the structure and converting to our format specifications json. 
    - ~~BMP.bt~~ (done — `bmp.json`)
    - ~~GIF.bt~~ (done — `gif.json`, header/LSD parsed; block dispatch needs engine features)
    - Remaining: 7ZIP, ASF, AVI, BPlist, CAB, DOC, DS_Store, FLV, H264, IconCache, JPG (already have jpeg.json), MBR, MP4, MXF, ONE, PB, RegistryDhcpInterfaceOptions, RegistryPolicyFile, ThumbCache, Torrent

- Update SQlite with possible learning or forensics values from these sites:
  - https://dfrws.org/sites/default/files/session-files/2018_EU_paper_a_standardized_corpus_for_sqlite_database_forensics.pdf
  - https://imf-conference.org/imf2018/downloads/09_Sven-Schmitt_Introducing-Anti-Forensics.pdf
  - https://www.forensicfocus.com/webinars/a-standardized-corpus-for-sqlite-database-forensics/
  - CellPointerArray should get some children. We should add logic to actually parse out the pointers, if it is possible. At least providing the offsets or whatever is possible to derive from a dead-box forensic analysis of such a file. 
    - This also means that the values derived from the above, if possible, should be used to get sequences of actual rows, and not just the raw bytes of the CellPointerArray. This would be a significant enhancement to the current parser, which only documents the CellPointerArray as a blob of bytes without interpreting its structure or contents.

PS! Remember to update Copilot instructions if necessary on new implementations. 

## Future Parser Enhancements

### JPEG (jpeg.json)
The current JPEG parser handles all marker segments and provides full forensic documentation. The following enhancements would require **new config_parser.py engine features** (recursive structures, endian switching within a file, offset-based seeking):
- **Deep Exif IFD/TIFF tag parsing** — Extract individual Exif tags (camera make, model, serial number, GPS coordinates, timestamps) from the APP1 payload. Requires parsing a TIFF structure with dynamic endianness (II/MM byte order mark), recursive IFD chains, and offset-based data lookups within the Exif block. Currently documented as raw bytes with forensic tag reference.
- **JFXX extension thumbnails** — Parse JFIF extension (JFXX) thumbnails in APP0 segments including JPEG-compressed thumbnails (extension_code 0x10), palette thumbnails (0x11), and RGB thumbnails (0x13). Requires sub-file JPEG parsing.
- **Canon CIFF structure** — Parse Canon Camera Image File Format (CIFF) heap structures embedded in APP0 segments. Requires recursive directory/entry parsing with heap-based storage.
- **Casio MakerNote parsing** — Parse camera-specific MakerNote IFD entries (e.g., Casio QV-R62) within Exif data. Requires camera model detection and model-specific tag dictionaries.
- **Photoshop IRB deep parsing** — Parse individual 8BIM Image Resource Blocks within APP13 (IPTC, thumbnails, ICC profiles, XMP). Currently parsed as a single blob after the identifier.
- **XMP metadata parsing** — Extract and parse XMP metadata embedded in JPEG files, including Dublin Core, Photoshop, and custom namespaces. Requires XML parsing and namespace handling.