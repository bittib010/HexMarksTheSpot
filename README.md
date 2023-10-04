# HexMarksTheSpot: Advanced Hex File Analysis and Annotation

## Overview

HexMarksTheSpot is a Python-based application engineered to offer an intuitive yet sophisticated environment for hex-level file analysis and annotation. The platform is designed for both novice and experienced users, serving as a facilitative tool for manual file validation and educational exploration.

## Objectives

- Facilitate manual validation of files at the hex level.
- Provide an educational platform for understanding file structures and sequences.
- Enhance visual recognition of distinct data sequences.
- Encourage community contributions to expand artifact recognition capabilities.

## Features

### Core Functionalities

- **Comprehensive Parsing**: Decode and interpret file content, offering detailed information about parsed sequences.
- **Syntax Highlighting**: Utilize color-coded hex sequences and corresponding ASCII translations for easier data recognition.
- **Mirrored Behavior**: Ensure consistent user experience between hex and ASCII views.
- **Selective Parsing**: Option to halt parsing, useful when investigating specific segments of a file.
- **Searching**: Search for findings in the listview to filter down and faster compare similar values across the file.
- **Export csv**: Based on what is left before (everything) or after a search (limited) export it out to csv. (Feature under development/improvement - might be buggy).

### Known Limitations

- Performance issues - large files may take a long time to parse. Multi-threading implemented to maintain GUI responsiveness.
- Search functionality may exhibit unexpected behavior during active parsing.
- Limited artifact support, with ongoing development for SQLite and LNK file types.

### Future Enhancements

- Plan to introduce a 'diff' feature to compare the original file against parsed segments, aiding in the identification of parsing errors or omissions.

## Workflow Diagrams

### General Workflow


```mermaid
graph TD
  A[Start] --> B{Open File}
  B --> |Success| C{Check File Type}
  B --> |Failure| J[Throw Cannot open file]
  C --> |SQLite| D[Create SQLiteFileParser]
  C --> |PNG| E[Create PNGFileParser]
  C --> |Other| K[Throw Unknown file type]
  D --> F{Parse Chunk of File into Node}
  E --> F
  F --> |Success| G{Add Node to Children}
  F --> |Failure| L[Throw Error parsing file]
  G --> H{Print Node Info}
  H --> I{Print Node Data if Full Chunk}
  I --> M{File End?}
  M --> |No| F
  M --> |Yes| N[End]
```

### SQLite Workflow

```mermaid
graph TD;
    A[Start] --> B[Read SQLite Page];
    B --> C{Is it the first page?};
    
    C -->|Yes| D1[Parse Header Fields];
    D1 --> B;

    C -->|No| E{Is autovacuum != 0 and page_counter == 2?};
    E -->|Yes| B;
    
    E -->|No| F{Check page type};
    F -->|btree| G[Parse b-tree];
    F -->|lockbyte| H[Process lockbyte];
    F -->|overflow| I[Process overflow];
    F -->|freelist| J[Process freelist];
    F -->|ptrmap| K[Process ptrmap];
    
    G --> B;
    H --> B;
    I --> B;
    J --> B;
    K --> B;
```