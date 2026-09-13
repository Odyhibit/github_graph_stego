# Encoding Format

GitHub contribution graph steganography uses one calendar cell per 2-bit payload chunk.

## Markers

- Start marker: 20 commits, darkest green
- End marker: 20 commits, darkest green

The decoder reads payload cells between the first and last darkest-green marker in the selected date range.

## Payload Mapping

| Bits | Contribution State | Commit Count |
|------|--------------------|--------------|
| `00` | Empty/gray | 0 |
| `01` | Light green | 1 |
| `10` | Medium-light green | 5 |
| `11` | Medium-dark green | 10 |

The darkest green level is reserved for markers and is not used for payload data.
