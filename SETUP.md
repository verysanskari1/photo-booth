# SETUP — Innovator Awards Photobooth (from scratch on a Mac)

Run everything on **one Mac at the booth**. The iPad just opens a web page.
(Do NOT use Vercel/serverless — this needs a persistent Python server plus a
local Google Drive folder and, optionally, a local printer.)

---

## 1. Install prerequisites

```bash
# Homebrew (if you don't have it)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Tools
brew install python git ngrok
```

Also install:
- **Google Drive for Desktop** — https://www.google.com/drive/download/ (sign in with the account that owns the upload folder)
- An **ngrok account** (free) — then run `ngrok config add-authtoken <your-token>` (token from the ngrok dashboard)

---

## 2. Get the code

Easiest is **GitHub Desktop** (GUI login): install it, sign in, Clone
`verysanskari1/photo-booth`, and in the branch dropdown pick
**`claude/affectionate-feynman-3H9gp`**.

Or with git + a Personal Access Token:
```bash
cd ~
git clone https://github.com/verysanskari1/photo-booth.git
cd photo-booth
git checkout claude/affectionate-feynman-3H9gp
```

> Everything except secrets travels with the repo: the **logo, both strip
> templates, the Kalice/Satoshi fonts, and the sample attendees** are already in
> it. You only add your real attendees + create the `.env`.

---

## 3. Connect the Google Drive folder

1. In Finder, open your sync folder (e.g. `My Drive / Photobooth Uploads /
   Innovator Awards 2026`).
2. **Drag that folder into a Terminal window** to copy its exact local path.
   It looks like:
   `/Users/you/Library/CloudStorage/GoogleDrive-you@co.com/My Drive/Photobooth Uploads/Innovator Awards 2026`
3. You'll paste it into `.env` in the next step (keep the quotes — there are spaces).

---

## 4. Configure keys (.env)

```bash
cd ~/photo-booth/backend
cp .env.example .env
open -e .env
```
Fill in:
```ini
FAL_KEY=your-fal-key                       # REQUIRED
OPENROUTER_API_KEY=sk-or-your-key          # optional (nice couplets; else templates)
OPENROUTER_MODEL=openai/gpt-4o-mini
DRIVE_FOLDER="/Users/you/Library/CloudStorage/GoogleDrive-.../My Drive/Photobooth Uploads/Innovator Awards 2026"
PUBLIC_HOST=http://localhost:8000          # update to the ngrok URL in step 7
# Leave PRINTER_* blank if printing is offsite via the Drive folder.
```

---

## 5. Add the attendees (face recognition)

Put the reference photos + a CSV in **`backend/attendees/`**:

- One clear, **front-facing photo per person**, one face each. JPG/PNG.
- Filenames: lowercase, underscores, no spaces (e.g. `jane_doe.png`). The
  filename is just a key — the displayed name comes from the CSV.
- Edit **`backend/attendees/attendees.csv`** — columns `image,name,company`:
  ```csv
  image,name,company
  jane_doe.png,"Jane Doe","HackerRank"
  arjun_kumar_mehta.png,"Arjun Kumar Mehta","ET HRWorld"
  ```
  Always wrap `name` and `company` in double quotes (handles commas/middle
  names/multi-word companies automatically). Each `image` must exactly match a
  real file in this folder.
- Embeddings build at startup, so **restart the server after changing this folder.**
  Watch the log for `[faces] loaded N attendee reference face(s).`

If a guest isn't recognized, they just type their name on screen — nothing breaks.

---

## 6. Run the server

```bash
cd ~/photo-booth/backend
./start.sh
```
First run builds the venv + installs deps (a few minutes). It serves on
http://localhost:8000.

---

## 7. Expose it for the iPad (https)

In a second terminal:
```bash
ngrok http 8000
```
Copy the `https://….ngrok-free.app` URL. Put it in `.env` as `PUBLIC_HOST`, then
restart `./start.sh`.

On the **iPad**, open the ngrok URL in **Chrome**, allow the camera, and take one
warm-up shot (loads the face model so the first guest is instant).

---

## 8. Verify

```bash
curl -s http://localhost:8000/health           # {"status":"ok",...}
curl -s http://localhost:8000/printers          # see configured printer (if any)
# server log should show: [faces] loaded N attendee reference face(s).
```
Run a full capture → confirm the 4x6 appears, and a file named
`N - Name - Company.png` lands in your Drive folder.

---

## 9. Printing

- **Offsite (recommended):** the print station prints the `N - Name - Company.png`
  files from the same shared Drive folder. Nothing else to configure here.
- **Local DS620A:** install the DNP driver, add the printer, then set
  `PRINTER_NAME` (from `lpstat -p`) and `PRINT_MEDIA` (from
  `lpoptions -p <name> -l`) in `.env`. See the main README.

---

## 10. If something fails

- Guests see a friendly "ask the host" screen; details are in the browser console
  (Cmd+Option+J).
- The usual culprit is **internet** (fal needs it). Keep a **phone hotspot** ready.
- Every photo is saved in `backend/uploads/` with a `<job_id>.json` (name/company).
  Re-run any guest once back online:
  ```bash
  python app.py --restrip uploads/<job_id>.jpg --name "Full Name" --company "Company"
  ```

---

## Reminders each session
- New terminal → `cd backend && ./start.sh` (re-activates venv + reads `.env`).
- Keep `ngrok` running in its own terminal; if it restarts, the URL changes —
  update `PUBLIC_HOST` and reopen on the iPad.
