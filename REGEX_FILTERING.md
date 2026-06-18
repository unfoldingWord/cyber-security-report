# Regex Pattern Matching in Filters

The filter system now supports **regex patterns** in addition to plain substring matching.

## Quick Start

Edit `config.yaml` filters to use regex patterns:

```yaml
filters:
  ignore:
    - "job posting"              # Plain string (still works)
    - "CVE-\\d{4}-\\d{5}"        # Regex: any CVE number
    - "(Azure|AWS|Google Cloud)"  # Regex: cloud providers to ignore
  
  include:
    - "Linux"                     # Plain string
    - "critical|high"             # Regex: severity keywords
    - "ransomware|malware"        # Regex: threat types
```

## How It Works

- All patterns are **case-insensitive** (via `re.IGNORECASE`)
- Patterns match anywhere in the article title + summary combined
- Invalid regex raises a `ValueError` at startup (fail-fast)
- Compiled once at config load (no per-article overhead)

## Examples

### Plain Strings (backward-compatible)
```yaml
ignore:
  - "Microsoft Windows"  # Matches: "Microsoft Windows Update", "microsoft windows patch"
  - Azure                # Matches: "Azure Stack", "azure services", "AZURE BLOB"
```

### Regex Metacharacters
```yaml
ignore:
  - "CVE-\\d{4}-\\d{4,5}"        # CVE numbers: CVE-2026-1234, CVE-2026-12345
  - "(Node|npm)\\s+vuln"         # npm/Node vulnerabilities
  - "job\\s+(posting|board)"     # Job postings/boards

include:
  - "critical|high|severe"       # Severity levels
  - "zero[\\s-]?day"             # Zero-day exploits
  - "encryption|TLS|SSH"         # Security protocols
```

### Word Boundaries
```yaml
ignore:
  - "\\bJava\\b"                 # Match "Java" but not "JavaScript"
  
include:
  - "\\b(Linux|Docker|Kubernetes)\\b"  # Exact word matches
```

## Error Handling

Invalid regex patterns are caught at startup:

```
ValueError: Invalid regex in filters.ignore: '[invalid' — unterminated character set at position 0
```

Fix by escaping metacharacters or correcting the pattern syntax.

## Performance

- Patterns are compiled once at startup
- No performance penalty for regex vs. substring matching
- Safe for production use
