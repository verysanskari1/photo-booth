# Attendee database (face recognition)

This folder holds the people the booth can recognize. It's a **scaffold** with 3
placeholder rows so the pipeline works end-to-end; replace it with your real
~50 attendees before the event.

## Format

`attendees.csv` has three columns:

| column   | meaning                                   |
|----------|-------------------------------------------|
| image    | filename of the reference headshot (in this folder) |
| name     | full name (first name is used on the strip) |
| company  | company / org (used in the couplet)        |

Then drop one clear, front-facing **reference photo per person** into this
folder, named exactly as in the `image` column. One face per reference photo.

Example:

```
attendees/
  attendees.csv
  aanya.jpg
  rohan.jpg
  ...
```
```csv
image,name,company
aanya.jpg,Aanya Sharma,HackerRank
rohan.jpg,Rohan Mehta,ET HRWorld
```

## Notes

- The sample rows above point at `sample_*.jpg` files that don't exist yet, so
  recognition will simply return "no match" until you add real photos — the
  booth still works (the guest confirms/types their name on screen).
- Embeddings are computed **once at server startup**, so restart the backend
  after changing this folder.
- Matching threshold lives in `faces.py` (`MATCH_THRESHOLD`). Lower it if real
  matches are being missed; raise it if the wrong person is matched.
- Reference photos stay on your machine; nothing is uploaded for recognition.
