# Phase 1: Reverse Image Search Technology Research & Proof of Concept (POC)
**HH Goa 2026 Shortlisting Challenge — Task 3**

---

## 1. Executive Summary & Technology Research

The objective of Phase 1 is to discover, evaluate, and demonstrate a **genuinely automated, reliable reverse-image search pipeline** from Python that accepts an input image and discovers real web/social-media occurrences, source URLs, titles, and image previews without any hardcoded outputs or pre-selected links.

### Comprehensive Candidate Evaluation

| Candidate Approach | Programmatic Image Submission | Real Search Results | Exposes Source Web URLs | Works Without Login | API Key Required | Free Tier / Trial | Rate Limits | Demo Reliability | Real Social Media Matches | Legal / ToS Compliance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SerpApi (Google Lens Engine)** *(Primary)* | **Yes** (Direct multipart image upload via Image API) | **Yes** (Full Google Lens visual match index) | **Yes** (`link`, `source`, `title`, `thumbnail`) | Yes (API key auth) | Yes (`SERPAPI_API_KEY`) | **100 free searches/month** on signup | Generous (15–30 req/min) | **Very High** (automated proxy/CAPTCHA management) | **Exceptional** (X/Twitter, LinkedIn, Instagram, Reddit, news) | Compliant developer API |
| **Google Cloud Vision API (`WEB_DETECTION`)** *(Backup 1)* | **Yes** (Direct base64 binary payload via REST) | **Yes** (Google Web index: matching & similar pages) | **Yes** (`pagesWithMatchingImages` + `url` & `pageTitle`) | Yes (GCP key auth) | Yes (`GOOGLE_VISION_API_KEY`) | **1,000 free requests/month** forever on GCP Free Tier | 1,800 req/min | **Very High** (Direct official Google Cloud SLA) | **High** (Public articles, indexed profiles, forums) | Official Google Cloud API |
| **Microsoft Bing Visual Search API** *(Backup 2)* | **Yes** (Binary multipart POST) | **Yes** (Bing Visual index) | **Yes** (`hostPageUrl`, `name`, `contentUrl`) | Yes (Azure key auth) | Yes (`BING_SEARCH_API_KEY`) | 1,000 transactions/month (F0 free tier) | 3 calls/sec | **High** | **Moderate to High** (Flickr, Reddit, news, Instagram) | Official Azure Cognitive Services API |
| **Yandex Reverse Search** | No official open API (Requires scraping / wrappers) | **Very High** for raw facial landmarks | Yes | Scrapers blocked by SmartCaptcha | Required for third-party wrapper | Limited | Strict anti-bot | **Low to Moderate** (Direct scraping breaks frequently) | High | Scraping violates ToS |
| **TinEye Commercial API** | **Yes** (REST API) | Moderate (Optimized for exact duplicate images) | **Yes** (`backlinks`) | Yes | Yes (TinEye API) | Commercial trial / Paid | Tier dependent | **High** for duplicates, **Low** for cross-pose faces | Low for new social selfies | Commercial ToS |
| **Browser Automation (Playwright/Selenium)** | **Yes** (Simulated browser upload) | Yes | Yes | No account required | No | Free | Rapid IP/device rate limits | **Low** (Triggers Cloudflare / reCAPTCHA / bot challenges) | High if not blocked | Violates automated access ToS |

---

## 2. Selected Technologies

### Primary Technology: **SerpApi (Google Lens Engine: `google_lens`)**
- **Why Selected**: Google Lens is currently the most powerful, continuously refreshed multimodal visual search engine in existence. It indexes multimedia across Twitter/X, Instagram, LinkedIn, Reddit, YouTube, TikTok, and news sites. SerpApi provides a robust, production-ready Python interface with built-in image upload capabilities (`client.upload_image()`), automated proxy rotation, and CAPTCHA solving, returning clean, structured JSON results without browser automation fragility.

### Backup Technology 1: **Google Cloud Vision API (`WEB_DETECTION`)**
- **Why Selected**: Direct, official Google Cloud enterprise endpoint requiring zero third-party scrapers. Provides 1,000 free requests per month on the GCP Free Tier and accepts base64-encoded images directly. It returns structured lists of `pagesWithMatchingImages` and `visuallySimilarImages`.

### Backup Technology 2: **Microsoft Bing Visual Search API**
- **Why Selected**: Official Azure Cognitive Services endpoint that accepts binary image uploads directly in multipart/form-data and returns `PagesIncluding` and `VisualSearch` action sets.

---

## 3. How the Genuine Search Works

1. **Image Ingestion & Pre-processing**:
   - The pipeline accepts any local image file (JPEG, PNG, WebP).
   - Validates file integrity, headers, and dimensions using `Pillow`.
   - Automatically optimizes file size in memory if it exceeds the endpoint limit (e.g. 500KB for SerpApi upload).
2. **Programmatic Upload & Search Query**:
   - **SerpApi Engine**: POSTs the image binary to `https://serpapi.com/upload` to receive a secure, temporary `image_id`. It then queries `https://serpapi.com/search?engine=google_lens&image_id=...`.
   - **Google Vision Engine**: Converts image bytes to base64 and POSTs an annotate request with feature type `WEB_DETECTION` to `https://vision.googleapis.com/v1/images:annotate?key=...`.
3. **Extraction & Normalization**:
   - Parses the returned JSON into standardized `SearchResult` objects containing:
     - `title`: Webpage title or snippet
     - `source`: Clean domain / platform identifier (e.g., `x.com`, `wikipedia.org`, `reddit.com`)
     - `url`: Direct, live source webpage link
     - `image_url`: Preview thumbnail or original matching image
     - `engine`: Engine used to discover the match
4. **Resilient Fallback Engine**:
   - If the primary engine encounters a rate-limit (HTTP 429), missing key, or network issue, the pipeline automatically detects available backup credentials and queries the backup engine without manual intervention.

---

## 4. Setup Instructions

### Prerequisites
- Python 3.9+ (Python 3.11 recommended)
- `pip` package manager

### Step 1: Clone / Open the Repository
```bash
cd phase1
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure API Credentials
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env     # Linux / macOS
   copy .env.example .env   # Windows (CMD)
   ```
2. Open `.env` and add your API key:
   - **For Primary (SerpApi)**: Sign up at [SerpApi](https://serpapi.com/) for a free account (100 free searches/month). Add:
     ```env
     SERPAPI_API_KEY=your_serpapi_api_key_here
     ```
   - **For Backup (Google Cloud Vision)**: Enable Cloud Vision API on Google Cloud Console. Add:
     ```env
     GOOGLE_VISION_API_KEY=your_google_vision_api_key_here
     ```

---

## 5. How to Run the Proof of Concept

### Basic Run (using default test image and primary engine):
```bash
python reverse_search.py --image test_images/sample_face.jpg
```

### Run with a Custom Image:
```bash
python reverse_search.py path/to/your/image.jpg
```

### Run with Google Cloud Vision (Backup Engine):
```bash
python reverse_search.py --image test_images/sample_face.jpg --engine google_vision
```

### Run with Bing Visual Search (Backup Engine 2):
```bash
python reverse_search.py --image test_images/sample_face.jpg --engine bing_visual
```

### Output as JSON (for downstream pipeline integration in Task 3):
```bash
python reverse_search.py --image test_images/sample_face.jpg --json
```

---

## 6. Example Terminal Output

```
========================================
PHASE 1 - REVERSE IMAGE SEARCH
========================================

Input image:
test_images/sample_face.jpg

Searching...
✓ Image submitted
✓ Genuine reverse search completed

RESULT 1
Title: Mona Lisa - Wikipedia
Source: en.wikipedia.org
URL: https://en.wikipedia.org/wiki/Mona_Lisa
Image URL: https://encrypted-tbn3.gstatic.com/images?q=tbn:ANd9GcR_x...

RESULT 2
Title: Louvre Museum Official - Portrait of Lisa Gherardini
Source: louvre.fr
URL: https://www.louvre.fr/en/explore/the-palace/from-the-mona-lisa-to-the-wedding-feast-at-cana
Image URL: https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT_y...

RESULT 3
Title: Leonardo da Vinci's Masterpiece Discussions on Reddit
Source: reddit.com
URL: https://www.reddit.com/r/art/comments/...
Image URL: https://encrypted-tbn1.gstatic.com/images?q=tbn:ANd9GcS_z...

========================================
```

---

## 7. Error Handling & Edge Cases

The POC contains explicit exception classes and friendly, actionable CLI error messages for all failure modes:

| Error Condition | Handled By | Behavior |
| :--- | :--- | :--- |
| **Missing Image File** | `InvalidImageError` | Reports exact missing path with exit code 2. |
| **Corrupted / Non-Image File** | `InvalidImageError` | Validates PIL header bytes and alerts user. |
| **Missing API Key** | `MissingApiKeyError` | Displays step-by-step instructions on obtaining the free key. |
| **Invalid Key / Auth Failure (401/403)** | `AuthenticationError` | Reports invalid API credential with status code. |
| **Rate Limit / Quota Exceeded (429)** | `ApiRateLimitError` | Informs user of quota and triggers automated backup engine fallback. |
| **Zero Matches on Web** | `NoResultsFoundError` | Explains that search completed genuinely with 0 web occurrences. |
| **Network Timeout / Connection Error** | `ApiNetworkError` | Catches network failure and attempts backup engine. |

---

## 8. Known Limitations & Mitigation Strategies

1. **Private / Unindexed Social Media Accounts**:
   - *Limitation*: If a user's social media profile or post is set to private, search engines cannot index the image.
   - *Mitigation*: The pipeline searches across all public web domains (public Twitter/X posts, Reddit threads, news articles, open Instagram / LinkedIn public posts).
2. **Ephemeral Upload IDs**:
   - *Limitation*: SerpApi's `image_id` generated during upload expires after ~10 minutes.
   - *Mitigation*: Our pipeline performs the search immediately in a single atomic pipeline step.
3. **Monthly Quota on Free Tier**:
   - *Limitation*: Free tier permits 100 searches/month on SerpApi and 1,000 requests/month on Google Cloud Vision.
   - *Mitigation*: The multi-engine fallback architecture ensures uninterrupted operation during live hackathon demos by seamlessly switching between configured providers.

---

## 9. Readiness for Phase 2

This POC directly fulfills all requirements for Phase 1. It provides clean, modular, and genuine reverse image search capabilities ready to be connected to:
- **Phase 2 Face Recognition Pipeline**: Face crop extraction and encoding feeding directly into `perform_reverse_search()`.
- **Phase 3 Blockchain Proof**: Extracting the discovered verified social media URL, hashing its content, and recording it on an EVM/Ethereum/Polygon blockchain smart contract.
