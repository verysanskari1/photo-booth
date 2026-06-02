# Fonts

Drop the brand font files here and both the web page and the printed strip will
use them automatically. **Neither is a Google Font**, so download them from the
sources below (free, ~1 minute on your Mac):

| Font     | What for            | Download from                               | File to save here              |
|----------|---------------------|---------------------------------------------|--------------------------------|
| Satoshi  | sans (UI, labels)   | https://www.fontshare.com/fonts/satoshi     | `Satoshi.ttf`, `Satoshi-Bold.ttf` |
| Kalice   | serif (titles, verse)| https://velvetyne.fr/fonts/kalice/         | `Kalice.ttf` (or `Kalice.otf`) |

Steps: open each link → Download → unzip → copy the `.ttf`/`.otf` into this
folder with the names above → restart the backend.

Notes:
- The web page also pulls **Satoshi** from the Fontshare CDN when online, so the
  UI sans already looks right with internet. These local files are what the
  **strip generator** (server-side) and **offline** use.
- If a file is missing, clean system fallbacks (Georgia / a sans) are used, so
  nothing breaks.
- If you prefer Google alternatives that need no download: **Fraunces** (close to
  Kalice) and **Plus Jakarta Sans** (close to Satoshi). Tell me and I'll wire
  those via Google Fonts instead.
