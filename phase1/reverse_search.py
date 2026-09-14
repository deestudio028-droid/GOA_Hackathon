#!/usr/bin/env python3
"""
==============================================================================
Task 3 - Phase 1: Reverse Image Search Proof of Concept (POC)
HH Goa 2026 Shortlisting Challenge

This module implements a production-grade, genuine reverse-image-search
pipeline that accepts an image file, submits it to a real-time web search
engine (Google Lens via SerpApi or Google Cloud Vision Web Detection), and
retrieves verified live web pages, social media posts, and visual matches.

Supported Engines:
- Primary: SerpApi Google Lens ("google_lens")
- Backup 1: Google Cloud Vision API Web Detection ("google_vision")
- Backup 2: Microsoft Bing Visual Search API ("bing_visual")

NO hardcoded URLs, NO mock results, NO fake output.
==============================================================================
"""

import os
import sys
import io

# Ensure UTF-8 output encoding for cross-platform terminals (Windows CMD/PowerShell, Linux, macOS)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import json
import base64
import argparse
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import requests
from PIL import Image
from dotenv import load_dotenv

# Load environment variables from .env file (check script directory and cwd)
script_dir_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(script_dir_env):
    load_dotenv(dotenv_path=script_dir_env)
load_dotenv()


# ==============================================================================
# Data Models & Custom Exceptions
# ==============================================================================

@dataclass
class SearchResult:
    """Represents a single standardized reverse-image-search result."""
    title: str
    source: str
    url: str
    image_url: str
    similarity_info: Optional[str] = None
    engine: str = "Google Lens"


class ReverseSearchError(Exception):
    """Base exception for all reverse search errors."""
    pass


class InvalidImageError(ReverseSearchError):
    """Raised when the input image is invalid, missing, corrupted, or unreadable."""
    pass


class MissingApiKeyError(ReverseSearchError):
    """Raised when the required API credentials are missing from environment variables."""
    pass


class ApiNetworkError(ReverseSearchError):
    """Raised when network, connection, or timeout errors occur during API calls."""
    pass


class ApiRateLimitError(ReverseSearchError):
    """Raised when search API quotas or rate limits are exceeded (HTTP 429)."""
    pass


class AuthenticationError(ReverseSearchError):
    """Raised when API credentials are rejected or unauthorized (HTTP 401/403)."""
    pass


class NoResultsFoundError(ReverseSearchError):
    """Raised when a genuine search completes successfully but finds zero matches."""
    pass


class MalformedResponseError(ReverseSearchError):
    """Raised when the API returns an unexpected or corrupted payload structure."""
    pass


# ==============================================================================
# Image Validation & Preprocessing Helpers
# ==============================================================================

def validate_and_prepare_image(image_path: str, max_size_kb: int = 450) -> bytes:
    """
    Validates that the file exists, is a valid image, and optimizes its size if necessary
    to ensure smooth programmatic upload to search endpoints (e.g. SerpApi 500KB limit).

    Returns:
        bytes: Raw image bytes ready for upload.
    """
    if not os.path.exists(image_path):
        raise InvalidImageError(f"Image file does not exist at path: '{image_path}'")

    if not os.path.isfile(image_path):
        raise InvalidImageError(f"Specified path is not a file: '{image_path}'")

    try:
        with open(image_path, "rb") as f:
            raw_data = f.read()
    except Exception as e:
        raise InvalidImageError(f"Could not read image file '{image_path}': {str(e)}")

    if len(raw_data) == 0:
        raise InvalidImageError(f"Image file is empty (0 bytes): '{image_path}'")

    # Validate image integrity with PIL
    try:
        image = Image.open(io.BytesIO(raw_data))
        image.verify()  # Verify file header integrity
        image = Image.open(io.BytesIO(raw_data))  # Re-open after verify
    except Exception as e:
        raise InvalidImageError(f"File '{image_path}' is not a valid or supported image: {str(e)}")

    # Check if compression/resizing is needed for upload limits
    file_size_kb = len(raw_data) / 1024.0
    if file_size_kb <= max_size_kb and image.format in ("JPEG", "PNG", "WEBP"):
        return raw_data

    # Optimize/resize image in-memory to fit within upload size limits
    try:
        img_copy = image.copy()
        if img_copy.mode in ("RGBA", "P"):
            img_copy = img_copy.convert("RGB")
        
        # Scale down if dimensions are excessively large (> 1200px)
        max_dim = 1200
        if max(img_copy.size) > max_dim:
            img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img_copy.save(buffer, format="JPEG", quality=85, optimize=True)
        compressed_bytes = buffer.getvalue()
        
        # If still over limit, reduce quality further
        if len(compressed_bytes) / 1024.0 > max_size_kb:
            buffer = io.BytesIO()
            img_copy.save(buffer, format="JPEG", quality=70, optimize=True)
            compressed_bytes = buffer.getvalue()

        return compressed_bytes
    except Exception as e:
        # Fallback to raw data if optimization fails
        return raw_data


def extract_domain(url: str) -> str:
    """Extract clean domain/platform name from a given URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return "web"


# ==============================================================================
# Search Engines Implementations
# ==============================================================================

class SerpApiGoogleLensEngine:
    """
    PRIMARY SEARCH ENGINE: SerpApi Google Lens
    - Submits local image binary via SerpApi Image API.
    - Executes Google Lens visual search across indexed web and social platforms.
    - Extracts structured visual matches (title, source URL, domain, thumbnail).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")
        self.name = "SerpApi (Google Lens)"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_serpapi_api_key_here")

    def search(self, image_bytes: bytes, max_results: int = 5) -> List[SearchResult]:
        if not self.is_configured():
            raise MissingApiKeyError(
                "SERPAPI_API_KEY is missing or unconfigured.\n"
                "To fix:\n"
                "  1. Get a free API key (100 free searches/month) at: https://serpapi.com/\n"
                "  2. Add 'SERPAPI_API_KEY=your_key' to your .env file or set environment variable."
            )

        # Step 1: Upload image to SerpApi Image API
        upload_url = "https://serpapi.com/image"
        headers = {"User-Agent": "ReverseImageSearchPOC/1.0"}
        files = {"image": ("query_image.jpg", image_bytes, "image/jpeg")}
        data = {"api_key": self.api_key}

        try:
            upload_resp = requests.post(
                upload_url,
                files=files,
                data=data,
                headers=headers,
                timeout=25
            )
        except requests.exceptions.Timeout:
            raise ApiNetworkError("Upload to SerpApi timed out after 25 seconds.")
        except requests.exceptions.RequestException as e:
            raise ApiNetworkError(f"Network error during image upload to SerpApi: {str(e)}")

        if upload_resp.status_code in (401, 403):
            raise AuthenticationError(f"SerpApi authentication failed ({upload_resp.status_code}): Invalid SERPAPI_API_KEY.")
        elif upload_resp.status_code == 429:
            raise ApiRateLimitError("SerpApi monthly quota exceeded or rate limit reached (HTTP 429).")
        elif upload_resp.status_code != 200:
            # Fallback check if alternative endpoint is used
            raise ApiNetworkError(f"SerpApi image upload failed with status {upload_resp.status_code}: {upload_resp.text}")

        try:
            upload_json = upload_resp.json()
            image_id = upload_json.get("image_id")
            if not image_id:
                raise MalformedResponseError(f"SerpApi upload response missing 'image_id': {upload_json}")
        except json.JSONDecodeError:
            raise MalformedResponseError("Failed to parse JSON response from SerpApi upload.")

        # Step 2: Query Google Lens with image_id
        search_url = "https://serpapi.com/search"
        search_params = {
            "engine": "google_lens",
            "image_id": image_id,
            "api_key": self.api_key,
            "no_cache": "false"
        }

        try:
            search_resp = requests.get(
                search_url,
                params=search_params,
                headers=headers,
                timeout=30
            )
        except requests.exceptions.Timeout:
            raise ApiNetworkError("Google Lens search request timed out after 30 seconds.")
        except requests.exceptions.RequestException as e:
            raise ApiNetworkError(f"Network error during Google Lens search: {str(e)}")

        if search_resp.status_code in (401, 403):
            raise AuthenticationError("SerpApi authentication failed: Invalid API key.")
        elif search_resp.status_code == 429:
            raise ApiRateLimitError("SerpApi rate limit exceeded during search query (HTTP 429).")
        elif search_resp.status_code != 200:
            raise ApiNetworkError(f"SerpApi search request failed with status {search_resp.status_code}: {search_resp.text}")

        try:
            results_data = search_resp.json()
        except json.JSONDecodeError:
            raise MalformedResponseError("Failed to decode JSON from Google Lens search results.")

        # Check for API-level errors
        if "error" in results_data:
            raise ApiNetworkError(f"SerpApi returned an error: {results_data['error']}")

        # Step 3: Parse visual and exact matches
        exact_matches = results_data.get("exact_matches", [])
        visual_matches = results_data.get("visual_matches", [])
        if not visual_matches and not exact_matches and "reverse_image_search" in results_data:
            visual_matches = results_data["reverse_image_search"].get("inline_images", [])

        # Combine exact matches first, then visual matches (deduping by link)
        combined_matches = list(exact_matches)
        seen_links = {m.get("link") or m.get("source_url") for m in exact_matches if (m.get("link") or m.get("source_url"))}
        for vm in visual_matches:
            link = vm.get("link") or vm.get("source_url")
            if link and link in seen_links:
                continue
            if link:
                seen_links.add(link)
            combined_matches.append(vm)

        if not combined_matches:
            raise NoResultsFoundError(
                "Genuine search executed successfully, but no visual matches were found for this image in Google Lens."
            )

        parsed_results: List[SearchResult] = []
        for idx, match in enumerate(combined_matches[:max_results]):
            title = match.get("title") or match.get("text") or "Untitled Web Match"
            link = match.get("link") or match.get("source_url") or "N/A"
            source = match.get("source") or extract_domain(link)
            thumbnail = match.get("thumbnail") or match.get("original") or "N/A"
            
            # Additional context like price or rating if available
            similarity_info = None
            if "price" in match:
                similarity_info = f"Price: {match['price'].get('extracted_value', '')}"
            elif "rating" in match:
                similarity_info = f"Rating: {match.get('rating')}"

            parsed_results.append(
                SearchResult(
                    title=title,
                    source=source,
                    url=link,
                    image_url=thumbnail,
                    similarity_info=similarity_info,
                    engine="Google Lens (via SerpApi)"
                )
            )

        return parsed_results


class GoogleVisionWebEngine:
    """
    BACKUP SEARCH ENGINE 1: Google Cloud Vision API (Web Detection)
    - Directly sends base64 image binary to official Google Cloud Vision endpoint.
    - Performs Web Detection across Google index.
    - Extracts matching web pages ('pagesWithMatchingImages') and similar images.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_VISION_API_KEY")
        self.name = "Google Cloud Vision (Web Detection)"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_google_vision_api_key_here")

    def search(self, image_bytes: bytes, max_results: int = 5) -> List[SearchResult]:
        if not self.is_configured():
            raise MissingApiKeyError(
                "GOOGLE_VISION_API_KEY is missing or unconfigured.\n"
                "To fix:\n"
                "  1. Enable Cloud Vision API in Google Cloud Console.\n"
                "  2. Create an API Key in Credentials.\n"
                "  3. Add 'GOOGLE_VISION_API_KEY=your_key' to your .env file."
            )

        endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={self.api_key}"
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "requests": [
                {
                    "image": {"content": b64_image},
                    "features": [
                        {
                            "type": "WEB_DETECTION",
                            "maxResults": max_results * 2
                        }
                    ]
                }
            ]
        }

        try:
            resp = requests.post(
                endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=25
            )
        except requests.exceptions.Timeout:
            raise ApiNetworkError("Google Cloud Vision request timed out after 25 seconds.")
        except requests.exceptions.RequestException as e:
            raise ApiNetworkError(f"Network error during Google Cloud Vision call: {str(e)}")

        if resp.status_code in (401, 403):
            raise AuthenticationError(f"Google Cloud Vision authentication failed ({resp.status_code}): Invalid GOOGLE_VISION_API_KEY.")
        elif resp.status_code == 429:
            raise ApiRateLimitError("Google Cloud Vision quota exceeded (HTTP 429).")
        elif resp.status_code != 200:
            raise ApiNetworkError(f"Google Cloud Vision returned error status {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
            responses = data.get("responses", [])
            if not responses:
                raise MalformedResponseError("Empty responses list from Google Cloud Vision API.")
            
            first_response = responses[0]
            if "error" in first_response:
                err_msg = first_response["error"].get("message", "Unknown Vision error")
                raise ApiNetworkError(f"Google Vision API error: {err_msg}")

            web_detection = first_response.get("webDetection", {})
        except json.JSONDecodeError:
            raise MalformedResponseError("Failed to parse JSON response from Google Cloud Vision API.")

        pages_with_matches = web_detection.get("pagesWithMatchingImages", [])
        similar_images = web_detection.get("visuallySimilarImages", [])
        full_matches = web_detection.get("fullMatchingImages", [])
        web_entities = web_detection.get("webEntities", [])

        if not pages_with_matches and not similar_images and not full_matches:
            raise NoResultsFoundError(
                "Genuine search executed successfully, but no matching web pages were found in Google Vision index."
            )

        parsed_results: List[SearchResult] = []

        # Parse pages with matching images
        for page in pages_with_matches[:max_results]:
            url = page.get("url", "N/A")
            title = page.get("pageTitle") or f"Web Match on {extract_domain(url)}"
            source = extract_domain(url)
            
            # Find image thumbnail if present
            matching_imgs = page.get("fullMatchingImages") or page.get("partialMatchingImages") or []
            img_url = matching_imgs[0].get("url") if matching_imgs else "N/A"

            parsed_results.append(
                SearchResult(
                    title=title,
                    source=source,
                    url=url,
                    image_url=img_url,
                    similarity_info="Page with Matching Image",
                    engine="Google Cloud Vision Web Detection"
                )
            )

        # Fallback to visually similar images if no full pages
        if len(parsed_results) < max_results and similar_images:
            for sim in similar_images[:(max_results - len(parsed_results))]:
                img_url = sim.get("url", "N/A")
                parsed_results.append(
                    SearchResult(
                        title=f"Visually Similar Image on {extract_domain(img_url)}",
                        source=extract_domain(img_url),
                        url=img_url,
                        image_url=img_url,
                        similarity_info="Visually Similar Web Image",
                        engine="Google Cloud Vision Web Detection"
                    )
                )

        return parsed_results


class BingVisualSearchEngine:
    """
    BACKUP SEARCH ENGINE 2: Microsoft Bing Visual Search API
    - Sends multipart binary image to Azure Bing Visual Search endpoint.
    - Extracts 'PagesIncluding' and 'VisualSearch' actions with URLs.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BING_SEARCH_API_KEY")
        self.name = "Microsoft Bing Visual Search"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your_bing_search_api_key_here")

    def search(self, image_bytes: bytes, max_results: int = 5) -> List[SearchResult]:
        if not self.is_configured():
            raise MissingApiKeyError(
                "BING_SEARCH_API_KEY is missing or unconfigured.\n"
                "To fix:\n"
                "  1. Create a Bing Search resource on Microsoft Azure Portal.\n"
                "  2. Add 'BING_SEARCH_API_KEY=your_key' to your .env file."
            )

        endpoint = "https://api.bing.microsoft.com/v7.0/images/visualsearch"
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "User-Agent": "ReverseImageSearchPOC/1.0"
        }
        files = {"image": ("query.jpg", image_bytes, "image/jpeg")}

        try:
            resp = requests.post(endpoint, headers=headers, files=files, timeout=25)
        except requests.exceptions.Timeout:
            raise ApiNetworkError("Bing Visual Search request timed out after 25 seconds.")
        except requests.exceptions.RequestException as e:
            raise ApiNetworkError(f"Network error during Bing Visual Search: {str(e)}")

        if resp.status_code in (401, 403):
            raise AuthenticationError("Bing Visual Search authentication failed: Invalid subscription key.")
        elif resp.status_code == 429:
            raise ApiRateLimitError("Bing Visual Search rate limit exceeded (HTTP 429).")
        elif resp.status_code != 200:
            raise ApiNetworkError(f"Bing Visual Search returned status {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
            tags = data.get("tags", [])
            if not tags:
                raise NoResultsFoundError("No visual tags or matches found in Bing Visual Search.")
            
            actions = tags[0].get("actions", [])
        except (json.JSONDecodeError, IndexError):
            raise MalformedResponseError("Malformed response structure from Bing Visual Search.")

        parsed_results: List[SearchResult] = []
        for action in actions:
            action_type = action.get("actionType", "")
            if action_type in ("PagesIncluding", "VisualSearch"):
                items = action.get("data", {}).get("value", [])
                for item in items:
                    url = item.get("hostPageUrl") or item.get("webSearchUrl") or "N/A"
                    title = item.get("name") or f"Bing Visual Match on {extract_domain(url)}"
                    source = extract_domain(url)
                    img_url = item.get("contentUrl") or item.get("thumbnailUrl") or "N/A"

                    parsed_results.append(
                        SearchResult(
                            title=title,
                            source=source,
                            url=url,
                            image_url=img_url,
                            similarity_info=f"Bing Action: {action_type}",
                            engine="Microsoft Bing Visual Search"
                        )
                    )
                    if len(parsed_results) >= max_results:
                        break
            if len(parsed_results) >= max_results:
                break

        if not parsed_results:
            raise NoResultsFoundError("Bing Visual Search completed but found zero matching pages.")

        return parsed_results


# ==============================================================================
# Pipeline & Orchestration
# ==============================================================================

def perform_reverse_search(
    image_path: str,
    engine_name: str = "google_lens",
    max_results: int = 5,
    enable_fallback: bool = True
) -> List[SearchResult]:
    """
    Executes an end-to-end reverse image search pipeline:
    1. Validates and prepares image binary.
    2. Selects the primary engine or specified engine.
    3. Executes genuine web reverse search.
    4. Automatically falls back to backup engine if primary fails or is unconfigured.
    """
    # 1. Validate & prepare image
    image_bytes = validate_and_prepare_image(image_path)

    # Initialize available engines
    engines = {
        "google_lens": SerpApiGoogleLensEngine(),
        "google_vision": GoogleVisionWebEngine(),
        "bing_visual": BingVisualSearchEngine()
    }

    selected_engine = engines.get(engine_name.lower())
    if not selected_engine:
        raise ValueError(f"Unknown engine '{engine_name}'. Supported options: {list(engines.keys())}")

    # Execution with automatic fallback if enabled
    try:
        return selected_engine.search(image_bytes, max_results=max_results)
    except (MissingApiKeyError, ApiRateLimitError, AuthenticationError, ApiNetworkError) as primary_err:
        if not enable_fallback:
            raise primary_err

        # Determine backup engines
        fallback_candidates = [
            e for name, e in engines.items() 
            if name != engine_name.lower() and e.is_configured()
        ]

        if not fallback_candidates:
            # Re-raise original error if no configured backup exists
            raise primary_err

        # Try first available backup engine
        backup_engine = fallback_candidates[0]
        print(f"\n[!] Primary engine ({selected_engine.name}) error: {primary_err}")
        print(f"[*] Automatically falling back to backup engine: {backup_engine.name}...")
        return backup_engine.search(image_bytes, max_results=max_results)


def search_google_social(
    query_entity: str,
    api_key: Optional[str] = None,
    max_results: int = 5
) -> List[SearchResult]:
    """
    Executes a genuine Google Web search via SerpApi targeting major social media platforms
    dynamically for a given query entity derived from reverse image search.
    """
    api_key = api_key or os.getenv("SERPAPI_API_KEY")
    if not api_key or not api_key.strip() or api_key == "your_serpapi_api_key_here":
        return []

    # Target recognized social media platforms dynamically
    social_query = f'{query_entity} (site:instagram.com OR site:facebook.com OR site:x.com OR site:twitter.com OR site:youtube.com OR site:threads.net OR site:tiktok.com OR site:reddit.com)'

    search_url = "https://serpapi.com/search"
    search_params = {
        "engine": "google",
        "q": social_query,
        "api_key": api_key,
        "num": max_results * 2,
        "no_cache": "false"
    }
    headers = {"User-Agent": "ReverseImageSearchPOC/1.0"}

    try:
        resp = requests.get(search_url, params=search_params, headers=headers, timeout=25)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    organic_results = data.get("organic_results", [])
    results: List[SearchResult] = []

    for item in organic_results:
        link = item.get("link")
        if not link or link == "N/A":
            continue
        title = item.get("title") or f"Social Match for {query_entity}"
        source = extract_domain(link)
        thumbnail = item.get("thumbnail") or "N/A"
        snippet = item.get("snippet")

        results.append(
            SearchResult(
                title=title,
                source=source,
                url=link,
                image_url=thumbnail,
                similarity_info=snippet or f"Live Google Social Search: {query_entity}",
                engine="Google Search (via SerpApi)"
            )
        )

    return results


# ==============================================================================
# CLI Formatting & Terminal Display
# ==============================================================================

def display_results(image_path: str, results: List[SearchResult]) -> None:
    """Prints the formatted output strictly following the required project template."""
    print("========================================")
    print("PHASE 1 - REVERSE IMAGE SEARCH")
    print("========================================")
    print()
    print("Input image:")
    print(image_path)
    print()
    print("Searching...")
    print("✓ Image submitted")
    print("✓ Genuine reverse search completed")
    print()

    for idx, res in enumerate(results, 1):
        print(f"RESULT {idx}")
        print(f"Title: {res.title}")
        print(f"Source: {res.source}")
        print(f"URL: {res.url}")
        if res.image_url and res.image_url != "N/A":
            print(f"Image URL: {res.image_url}")
        print()

    print("========================================")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 1: Reverse Image Search Proof of Concept",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python reverse_search.py --image test_images/sample_face.jpg
  python reverse_search.py test_images/sample_face.jpg --engine google_vision
  python reverse_search.py --image test_images/sample_face.jpg --json
        """
    )
    parser.add_argument(
        "positional_image",
        nargs="?",
        default=None,
        help="Path to the query image (optional if --image is specified)"
    )
    parser.add_argument(
        "--image", "-i",
        dest="image_path",
        default=None,
        help="Path to the input image file (JPEG, PNG, WebP)"
    )
    parser.add_argument(
        "--engine", "-e",
        default=os.getenv("DEFAULT_SEARCH_ENGINE", "google_lens"),
        choices=["google_lens", "google_vision", "bing_visual"],
        help="Reverse image search engine to use (default: google_lens)"
    )
    parser.add_argument(
        "--max-results", "-n",
        type=int,
        default=int(os.getenv("MAX_RESULTS", "5")),
        help="Maximum number of search results to return (default: 5)"
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable automatic fallback to backup engine on failure"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted terminal text"
    )

    args = parser.parse_args()
    image_path = args.image_path or args.positional_image

    if not image_path:
        # Default test image if available
        default_test = os.path.join(os.path.dirname(__file__), "test_images", "sample_face.jpg")
        if os.path.exists(default_test):
            image_path = default_test
        else:
            parser.print_help()
            print("\nError: Please specify an input image path via --image or positional argument.")
            sys.exit(1)

    try:
        results = perform_reverse_search(
            image_path=image_path,
            engine_name=args.engine,
            max_results=args.max_results,
            enable_fallback=not args.no_fallback
        )

        if args.json:
            json_output = [
                {
                    "rank": idx + 1,
                    "title": r.title,
                    "source": r.source,
                    "url": r.url,
                    "image_url": r.image_url,
                    "similarity_info": r.similarity_info,
                    "engine": r.engine
                }
                for idx, r in enumerate(results)
            ]
            print(json.dumps({"status": "success", "image": image_path, "results": json_output}, indent=2))
        else:
            display_results(image_path, results)

    except InvalidImageError as e:
        print(f"\n[ERROR: INVALID IMAGE] {e}", file=sys.stderr)
        sys.exit(2)
    except MissingApiKeyError as e:
        print(f"\n[ERROR: MISSING API KEY] {e}", file=sys.stderr)
        sys.exit(3)
    except AuthenticationError as e:
        print(f"\n[ERROR: AUTHENTICATION FAILED] {e}", file=sys.stderr)
        sys.exit(4)
    except ApiRateLimitError as e:
        print(f"\n[ERROR: RATE LIMIT EXCEEDED] {e}", file=sys.stderr)
        sys.exit(5)
    except NoResultsFoundError as e:
        print(f"\n[NOTICE: NO RESULTS FOUND] {e}", file=sys.stderr)
        sys.exit(6)
    except ApiNetworkError as e:
        print(f"\n[ERROR: API NETWORK ERROR] {e}", file=sys.stderr)
        sys.exit(7)
    except MalformedResponseError as e:
        print(f"\n[ERROR: MALFORMED API RESPONSE] {e}", file=sys.stderr)
        sys.exit(8)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        sys.exit(9)


if __name__ == "__main__":
    main()
