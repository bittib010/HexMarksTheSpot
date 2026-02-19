- Add a template for: 
  - WAL
  - 
  - We have a lot of `*.bt` files in the Artefacts folder, which are the template files belonging to 010 Editor. These files needs to be converted into our wanted format by looking at the structure and converting to our format specifications json. 

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