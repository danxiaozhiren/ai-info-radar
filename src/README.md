# Source Code

Implementation will live here.

Suggested modules:

```text
src/
|-- fetchers/       # RSS, API, GitHub, Hugging Face, browser fetchers
|-- normalizers/    # Convert source-specific data into common items
|-- scoring/        # World, learning, practice, and focus scores
|-- verification/   # Source checks and confidence labels
|-- reporters/      # Daily radar and weekly learning map generation
`-- storage/        # Local cache or database
```

Keep the first implementation boring, observable, and easy to verify.
