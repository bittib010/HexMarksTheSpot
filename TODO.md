

MIDI's inner message parsing relies on variable-length quantities (VLQ) and running status — features not supported by the JSON parser engine. The right approach is to fully parse the header and track chunk boundaries, then capture track data as raw bytes with thorough documentation.

- Add possibility to parse variable-length quantities (VLQ). An example of this is the delta time field in MIDI events, which can be 1 to 4 bytes long depending on the value. The parser should read bytes until it encounters a byte with the most significant bit (MSB) set to 0, indicating the end of the VLQ.
- Pages content on SQLite3 database. This is necessary to handle large databases without consuming excessive memory. Implement a mechanism to fetch and display results in chunks, allowing users to navigate through pages of results.
- Consider outsourcing the parsing and reading the finished parsed file,  to avoid the app crashing.???
- Rounded corners on buttons and input fields for a more modern look.
- precedence logic to look at extension first, then magic bytes, then alternative magic bytes.
  - This forces us to also add file protocol versioning, so we can add new fields in the future without breaking old configs. We can also add a "deprecated" field to mark fields that should no longer be used but are still supported for backward compatibility.
- Add a "deprecated" field to mark fields that should no longer be used but are still supported for backward compatibility. This allows us to phase out old fields gracefully while maintaining support for existing configurations.
- 