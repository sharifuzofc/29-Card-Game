# Twenty-Nine — PyScript Demo

This repo contains a PyScript-powered Twenty-Nine card game demo. The site is static and can be deployed to Netlify or Vercel as-is.

## Quick test (local)

Start a static server in the project root and open the page:

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy to Netlify (one-click)

Click the button below to deploy this repository to Netlify. It will connect your GitHub account and create a new site that serves the static files.

[![Deploy to Netlify](https://www.netlify.com/img/deploy/button.svg)](https://app.netlify.com/start/deploy?repository=sharifuzofc/29-Card-Game)

Netlify will use the project root as the publish directory. `netlify.toml` is included and already configures `publish = "."`.

## Deploy to Vercel

1. Sign in to https://vercel.com and import the GitHub repository `sharifuzofc/29-Card-Game`.
2. Vercel will detect a static site. Set the `Build and Output Settings` to default (no build command) and `Output Directory` to `/` if asked.
3. Deploy — Vercel will serve the repo's static `index.html` and included `.py` files (PyScript runs in the browser).

## Notes and common issues

- PyScript runs entirely in the browser; the server only needs to serve static files. There is no Python execution on the host.
- Make sure `index.html`, `game29.py`, and `game_browser.py` are present in the repository root — they are required for the demo.
- If the live site shows "Loading Python..." but never finishes, open the browser console for network errors (blocked resources, CSP, or 404s). Share the console output if you want me to diagnose further.

If you want, I can (a) open a local server here and verify the demo, or (b) attempt to trigger a Netlify deploy via the API — you will need to provide a Netlify personal access token. Tell me which you'd like.