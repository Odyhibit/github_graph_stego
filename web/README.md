# GitHub Graph Stego Web

Zero-cost friendly web version of the GitHub contribution graph tools.

## Current MVP

- Static frontend in `public/`
- Cloudflare Pages Function at `/api/profile/:username`
- No database, auth, or always-on server
- Profile analyzer for public GitHub contribution calendars

## Local Development

```bash
npm install
npm run dev
```

Then open the local URL printed by Wrangler.

## Verification

```bash
npm test
```

The tests use Node's built-in test runner and do not call GitHub.
