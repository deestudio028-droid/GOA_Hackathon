# Phase 3: Face-to-Web/Social Search Integration
**HH Goa 2026 Shortlisting Challenge — Task 3**

---

## 1. Overview & Pipeline Architecture

Phase 3 integrates **Phase 2 (Face Detection & Crop Extraction)** with **Phase 1 (Genuine Google Lens Reverse Image Search)** into an automated end-to-end face discovery pipeline.

### Architectural Flow

```
Input Image (containing human face)
    │
    ▼
Phase 2: MTCNN Multi-Face Detection
    │
    ▼
Face Crop Extraction & Normalization (e.g., face_01.jpg, 160x160 RGB)
    │
    ▼
Phase 1: SerpApi Google Lens Reverse Search (Multimodal Web & Social Index)
    │
    ▼
Live Visual Matches Retrieval
    │
    ▼
Candidate Classification Engine (SOCIAL vs WEB based on domain)
    │
    ▼
Structured & Filtered Candidate Results
```

> [!NOTE]
> **Why Face Crops instead of 512-D Embeddings for Search?**  
> Web reverse-image search engines (Google Lens, Bing Visual Search) require visual image matrices (JPEG/PNG), not numerical vector representations. Phase 2 extracts the precise face crop to send to Google Lens, while simultaneously calculating the 512-D L2-normalized embedding vector for identity validation and downstream blockchain fingerprinting.

---

## 2. Directory Structure

```
phase3/
├── face_web_search.py      # Integrated pipeline & CLI (Phase 2 -> Face Crop -> Phase 1 -> Filter)
├── requirements.txt        # Combined dependencies from Phase 1 and Phase 2
├── README.md               # Architecture, API docs, usage, and verification guide
├── output/
│   └── faces/              # Extracted face crops used for web reverse search
└── test_images/            # Test images
    ├── musician_social.jpg # Real human face with verified live social media presence (X, Instagram)
    ├── person_social.jpg   # Real human face with public news/encyclopedia presence
    ├── real_human.jpg      # Real human portrait (OpenCV benchmark)
    ├── multiple_faces.jpg  # Multi-face test image
    └── no_face.jpg         # Negative control image (0 faces)
```

---

## 3. Setup & Environment

Ensure `.env` in the workspace root or `phase1/` contains your valid API credentials:
```env
SERPAPI_API_KEY=your_serpapi_key_here
```

Install requirements:
```bash
pip install -r phase3/requirements.txt
```

---

## 4. Programmatic API Usage

Import and call `search_face_on_web()` directly in Python:

```python
from phase3.face_web_search import search_face_on_web

# Run end-to-end face to web search
results = search_face_on_web(
    image_path="phase3/test_images/musician_social.jpg",
    face_index=0,
    social_only=True,
    max_results=5
)

print(f"Faces Detected: {results['faces_detected']}")
print(f"Selected Face: {results['selected_face']['face_id']}")
print(f"Social Candidates: {results['social_candidates']}")

for candidate in results["candidates"]:
    print(f"Rank {candidate['rank']}: [{candidate['type']}] {candidate['title']}")
    print(f"Platform: {candidate['source']}")
    print(f"Live URL: {candidate['url']}")
```

---

## 5. CLI Usage & Verification Examples

### Example 1: Full Pipeline with Social Match Discovery
```bash
python phase3/face_web_search.py --image phase3/test_images/musician_social.jpg
```
**Terminal Output:**
```text
========================================
PHASE 3 - FACE TO WEB SEARCH
========================================

Input image:
phase3/test_images/musician_social.jpg

✓ Face detection completed
✓ Selected face: face_01
✓ Face crop prepared
✓ Google Lens search started
✓ Genuine web search completed

CANDIDATE 1
Title: So is emin watching gree and böcü or #Arafta #EmSu
Platform/Source: x.com
Type: SOCIAL
URL: https://x.com/lorrainevc/status/2083252779527852252

CANDIDATE 2
Title: Gr8 Dogs - Bald Eagle/Boxing Day // Live at Big Nice Studio ...
Platform/Source: YouTube
Type: SOCIAL
URL: https://www.youtube.com/watch?v=yBtK0bsx9QM

CANDIDATE 3
Title: Dylan McDermott Can't Give His House Away
Platform/Source: TMZ
Type: WEB
URL: https://www.tmz.com/2009/04/18/dylan-mcdermott-cant-give-his-house-away/

========================================
Faces detected: 1
Candidates found: 5
Social candidates: 2
========================================
```

---

### Example 2: Social-Only Filter Mode (`--social-only`)
```bash
python phase3/face_web_search.py --image phase3/test_images/musician_social.jpg --social-only
```
**Terminal Output:**
```text
========================================
PHASE 3 - FACE TO WEB SEARCH
========================================

Input image:
phase3/test_images/musician_social.jpg

✓ Face detection completed
✓ Selected face: face_01
✓ Face crop prepared
✓ Google Lens search started
✓ Genuine web search completed

CANDIDATE 1
Title: So is emin watching gree and böcü or #Arafta #EmSu
Platform/Source: x.com
Type: SOCIAL
URL: https://x.com/lorrainevc/status/2083252779527852252

CANDIDATE 2
Title: Gr8 Dogs - Bald Eagle/Boxing Day // Live at Big Nice Studio ...
Platform/Source: YouTube
Type: SOCIAL
URL: https://www.youtube.com/watch?v=yBtK0bsx9QM

CANDIDATE 3
Title: Founder of Deciem (owner of The Ordinary) Has Died [News ...
Platform/Source: Reddit
Type: SOCIAL
URL: https://www.reddit.com/r/AsianBeauty/comments/aik1ss/founder_of_deciem_owner_of_the_ordinary_has_died/

========================================
Faces detected: 1
Candidates found: 3
Social candidates: 3
========================================
```

---

### Example 3: General Web Matches Only (No Fake Social Matches)
```bash
python phase3/face_web_search.py --image phase3/test_images/real_human.jpg
```
**Terminal Output:**
```text
========================================
PHASE 3 - FACE TO WEB SEARCH
========================================

Input image:
phase3/test_images/real_human.jpg

✓ Face detection completed
✓ Selected face: face_01
✓ Face crop prepared
✓ Google Lens search started
✓ Genuine web search completed

CANDIDATE 1
Title: Your VAE Sucks
Platform/Source: theadamcolton.github.io
Type: WEB
URL: https://theadamcolton.github.io/your-vae-sucks.html

[NOTICE] SEARCH WORKS, SOCIAL MATCH NOT FOUND

========================================
Faces detected: 1
Candidates found: 5
Social candidates: 0
========================================
```

---

### Example 4: Multi-Face Image with Index Selection (`--face-index 1`)
```bash
python phase3/face_web_search.py --image phase3/test_images/multiple_faces.jpg --face-index 1 --max-results 3
```

---

### Example 5: Negative Control (No Face Detected)
```bash
python phase3/face_web_search.py --image phase3/test_images/no_face.jpg
```
**Output:**
```text
[ERROR: NO FACE DETECTED] No human faces were detected in image: 'phase3/test_images/no_face.jpg'. Reverse face search requires at least one visible human face.
```

---

## 6. Social Domain Classification Rules

A candidate is strictly classified as `SOCIAL` based on its registered domain:
- **Microblogging / Social**: `x.com`, `twitter.com`, `instagram.com`, `facebook.com`, `linkedin.com`, `reddit.com`, `threads.net`, `tiktok.com`, `mastodon.social`, `bsky.app`
- **Video & Media**: `youtube.com`, `pinterest.com`, `flickr.com`, `tumblr.com`
- **Developer / Blogging**: `medium.com`, `github.com`

All other domains (news outlets, encyclopedias, art galleries, commercial websites) are classified as `WEB`. The pipeline **never** classifies a result as social media based on keywords in titles.

---

## 7. Error Handling

| Scenario | Exception | Handling & CLI Behavior |
| :--- | :--- | :--- |
| Missing Image | `ImageNotFoundError` | Exits cleanly with path error (exit code 2) |
| No Faces in Image | `NoFaceDetectedError` | Exits cleanly indicating no faces found (exit code 3) |
| Invalid `--face-index` | `IndexError` | Reports available face indices (exit code 4) |
| Missing API Key | `MissingApiKeyError` | Displays setup instructions (exit code 5) |
| Rate Limit (429) | `ApiRateLimitError` | Informs user and attempts fallback (exit code 6) |
| Network Timeout | `ApiNetworkError` | Catches timeout cleanly (exit code 8) |
| Zero Search Results | `NoResultsFoundError` | Explains 0 matches returned on web (exit code 9) |
