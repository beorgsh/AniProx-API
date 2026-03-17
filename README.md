# 🎌 Anime API Proxy

A fast, production-ready REST API proxy that aggregates anime data from multiple upstream sources — including **HiAnime**, **AnimePahe**, **AniList**, and more — into a single, unified interface.

Built with **FastAPI** and deployable to **Vercel** or **Docker**.

---

## 📑 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Upstream Sources](#upstream-sources)
- [Getting Started](#getting-started)
  - [Local Development](#local-development)
  - [Docker](#docker)
  - [Deploy to Vercel](#deploy-to-vercel)
- [API Reference](#api-reference)
  - [GET /](#get-)
  - [GET /home](#get-home)
  - [GET /search](#get-search)
  - [GET /info](#get-info)
  - [GET /stream/{id}/{index}](#get-streamidindex)
- [Response Schemas](#response-schemas)
- [Error Handling](#error-handling)
- [Environment & Configuration](#environment--configuration)
- [Project Structure](#project-structure)
- [Known Limitations](#known-limitations)

---

## Overview

Anime API Proxy is a backend service that wraps several anime data and streaming sources under one clean API. Instead of calling multiple third-party APIs from your frontend, you call this proxy once and receive a fully merged response containing:

- Anime metadata (title, synopsis, genres, score, etc.)
- High-resolution poster and banner images from AniList
- Related anime entries (sequels, prequels, side stories)
- Season groupings
- Merged episode lists from both AnimePahe and HiAnime
- Multi-server, multi-type (sub/dub) streaming links

---

## Architecture

```
Client
  │
  ▼
Anime API Proxy  (this project)
  ├── /search      →  anime-api (HiAnime wrapper)
  ├── /home        →  anime-api (HiAnime wrapper)
  ├── /info        →  anime-api  +  AniList GraphQL  +  AniList Mapper  +  AniScrap Seasons
  └── /stream      →  anime-api (HiAnime streams, 3 servers × sub/dub in parallel)
                   →  AniScrap (AnimePahe resolve)
                   →  AniList Mapper (episode ID mapping)
```

The `/info` and `/stream` endpoints perform **parallel upstream requests** using `ThreadPoolExecutor` to minimize response latency.

---

## Upstream Sources

| Source                   | URL                                              | Used For                         |
| ------------------------ | ------------------------------------------------ | -------------------------------- |
| anime-api                | `https://anime-api-iota-six.vercel.app/api`      | Core anime data, HiAnime streams |
| AniList GraphQL          | `https://graphql.anilist.co`                     | Posters, banners, related anime  |
| AniList Mapper (Pahe)    | `https://anilistmapper.vercel.app/animepahe/map` | AnimePahe episode ID mapping     |
| AniList Mapper (HiAnime) | `https://anilistmapper.vercel.app/hianime`       | HiAnime episode ID mapping       |
| AniScrap Seasons         | `https://catapang1989-aniscrap.hf.space/seasons` | Season grouping data             |
| AniScrap Resolve         | `https://catapang1989-aniscrap.hf.space/resolve` | AnimePahe stream resolution      |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip
- (Optional) Docker

---

### Local Development

**1. Clone the repository**

```bash
git clone https://github.com/your-username/anime-api-proxy.git
cd anime-api-proxy
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Run the development server**

```bash
uvicorn main:app --reload
```

The API will be live at `http://localhost:8000`.

Interactive API docs (Swagger UI) are available at `http://localhost:8000/docs`.

---

### Docker

**Build the image**

```bash
docker build -t anime-proxy .
```

**Run the container**

```bash
docker run -p 8000:8000 anime-proxy
```

The API will be available at `http://localhost:8000`.

**Run in detached mode**

```bash
docker run -d -p 8000:8000 --name anime-proxy anime-proxy
```

---

### Deploy to Vercel

> ⚠️ Vercel's free (Hobby) tier has a **10-second function timeout**. The `/stream` endpoint runs 6+ parallel upstream requests and may approach this limit. Upgrade to Pro (60s timeout) if you encounter timeouts.

**1. Add a `vercel.json` to the project root**

```json
{
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "main.py"
    }
  ]
}
```

**2. Install the Vercel CLI and deploy**

```bash
npm i -g vercel
vercel
```

**3. Follow the prompts.** Your API will be deployed to a URL like `https://your-project.vercel.app`.

---

## API Reference

### GET `/`

Health check. Returns the running status of the proxy.

**Response**

```json
{
  "status": "ok",
  "message": "Anime API Proxy is running."
}
```

---

### GET `/home`

Returns the homepage data from the upstream anime API — typically trending, popular, and recently updated anime.

**Response**

Returns the raw upstream homepage payload.

---

### GET `/search`

Search for anime by title keyword.

**Query Parameters**

| Parameter | Type   | Required | Description                   |
| --------- | ------ | -------- | ----------------------------- |
| `keyword` | string | ✅       | The anime title to search for |

**Example Request**

```
GET /search?keyword=jujutsu+kaisen
```

**Example Response**

```json
{
  "success": true,
  "results": [
    {
      "id": "jujutsu-kaisen-20401",
      "title": "Jujutsu Kaisen",
      "poster": "https://...",
      "type": "TV",
      "episodes": { "sub": 47, "dub": 47 }
    }
  ]
}
```

---

### GET `/info`

Returns full anime details including metadata, poster/banner from AniList, related anime, seasons, and a merged episode list from both AnimePahe and HiAnime.

**Query Parameters**

| Parameter | Type   | Required | Description                                     |
| --------- | ------ | -------- | ----------------------------------------------- |
| `id`      | string | ✅       | The anime slug ID (e.g. `jujutsu-kaisen-20401`) |

**Example Request**

```
GET /info?id=jujutsu-kaisen-20401
```

**Example Response**

```json
{
  "success": true,
  "results": {
    "data": {
      "id": "jujutsu-kaisen-20401",
      "title": "Jujutsu Kaisen",
      "anilistId": 113415,
      "poster": "https://s4.anilist.co/file/...",
      "banner": "https://s4.anilist.co/file/...",
      "coverColor": "#e4835d",
      "animeInfo": {
        "Status": "Finished Airing",
        "Aired": "Oct 3, 2020 to Mar 27, 2021",
        "Duration": "23 min per ep",
        "Score": "8.71",
        "Genres": ["Action", "Fantasy", "School"]
      }
    },
    "related_data": [
      {
        "relationType": "SEQUEL",
        "id": 166871,
        "title": { "romaji": "Jujutsu Kaisen 2nd Season", "english": "Jujutsu Kaisen Season 2" },
        "format": "TV",
        "status": "FINISHED",
        "episodes": 23,
        "averageScore": 87
      }
    ],
    "seasons": {
      "total": 2,
      "seasons": [...]
    }
  },
  "episodes": {
    "anilistId": 113415,
    "total": 24,
    "data": [
      {
        "index": 1,
        "pahe": { "episodeId": "abc123.../def456...", "number": 1 },
        "hianime": { "episodeId": "jujutsu-kaisen-20401?ep=168082", "number": 1, "title": "Ryomen Sukuna" }
      }
    ]
  }
}
```

---

### GET `/stream/{id}/{index}`

Fetches all available streaming links for a specific episode. Returns AnimePahe (direct download + stream) and HiAnime (3 servers × sub/dub) links in one response.

**Path Parameters**

| Parameter | Type    | Required | Description                                     |
| --------- | ------- | -------- | ----------------------------------------------- |
| `id`      | string  | ✅       | The anime slug ID (e.g. `jujutsu-kaisen-20401`) |
| `index`   | integer | ✅       | 1-based episode number                          |

**Example Request**

```
GET /stream/jujutsu-kaisen-20401/1
```

**Example Response**

```json
{
  "success": true,
  "animeId": "jujutsu-kaisen-20401",
  "episode": 1,
  "streams": {
    "pahe": {
      "anime_name": "Jujutsu Kaisen",
      "filename": "Jujutsu_Kaisen_-_Episode_01.mp4",
      "sub": {
        "stream": "https://...",
        "download": "https://...?file=Jujutsu_Kaisen_EP01_1080P.mp4",
        "resolution": "1080"
      },
      "dub": null
    },
    "hianime": {
      "sub": {
        "hd-1": {
          "error": false,
          "server": "hd-1",
          "serverName": "MegaCloud",
          "file": "https://...m3u8",
          "type": "hls",
          "tracks": [
            { "file": "https://...en.vtt", "label": "English", "kind": "captions", "default": true }
          ],
          "intro": { "start": 0, "end": 88 },
          "outro": { "start": 1320, "end": 1380 }
        },
        "hd-2": { "error": false, ... },
        "hd-3": { "error": true, "message": "Server hd-3 (sub) returned no stream data" }
      },
      "dub": {
        "hd-1": { "error": false, ... },
        "hd-2": { "error": true, ... },
        "hd-3": { "error": true, ... }
      }
    }
  }
}
```

#### Stream Notes

- **HiAnime streams** use HLS (`.m3u8`) format and require an HLS-compatible player (e.g. `hls.js`, `Video.js`, `Plyr`).
- **AnimePahe streams** provide a direct download URL and a stream URL.
- `intro` and `outro` fields contain timestamps (in seconds) for skip-intro/skip-outro features.
- `tracks` contains subtitle/caption track URLs in WebVTT format.
- If a server fails, it returns `{ "error": true, "message": "..." }` — it will never be `null`, so clients can safely iterate all servers.

---

## Response Schemas

### Error Response

All errors follow this structure:

```json
{
  "detail": "Human-readable error message here."
}
```

| HTTP Status | Meaning                                                           |
| ----------- | ----------------------------------------------------------------- |
| `400`       | Bad request / missing required parameter                          |
| `404`       | Resource not found (anime ID invalid, episode index out of range) |
| `502`       | Upstream API returned an error or invalid response                |
| `504`       | Upstream API request timed out                                    |

---

## Error Handling

The proxy handles upstream failures gracefully:

- **Connection errors** → `502 Bad Gateway`
- **Upstream timeouts** → `504 Gateway Timeout`
- **Upstream HTTP errors** → `502` with the upstream status code in the detail
- **Invalid upstream JSON** → `502`
- **HiAnime server failures** → included inline in the response as `{ "error": true }` objects rather than crashing the entire request. This means a partial response is always returned even if some servers are unavailable.
- **AnimePahe resolve failure** → `pahe` key in the stream response will be `null`. The HiAnime streams will still be returned.

---

## Environment & Configuration

No environment variables are required for basic operation. All upstream URLs are hardcoded constants in `main.py`:

```python
BASE_URL       = "https://anime-api-iota-six.vercel.app/api"
PAHE_MAP_URL   = "https://anilistmapper.vercel.app/animepahe/map"
HIANIME_MAP_URL= "https://anilistmapper.vercel.app/hianime"
ANILIST_URL    = "https://graphql.anilist.co"
SEASONS_URL    = "https://catapang1989-aniscrap.hf.space/seasons"
PAHE_RESOLVE   = "https://catapang1989-aniscrap.hf.space/resolve"
```

If you want to override these (e.g., to point to your own upstream forks), you can refactor them to read from environment variables using `os.getenv()`.

---

## Project Structure

```
anime-api-proxy/
├── main.py            # FastAPI application — all routes and helpers
├── requirements.txt   # Python dependencies
├── Dockerfile         # Container build definition
├── vercel.json        # Vercel deployment config (add manually, see deploy section)
└── README.md          # This file
```

---

## Known Limitations

| Limitation                 | Detail                                                                                                                       |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Vercel 10s timeout**     | Free tier may timeout on `/stream` due to 6 parallel upstream calls. Use Vercel Pro or self-host via Docker for reliability. |
| **HiAnime stream expiry**  | HLS `.m3u8` links are time-limited. Do not cache stream responses — always fetch fresh.                                      |
| **AnimePahe availability** | AnimePahe episode coverage varies per anime. The `pahe` key in `/stream` may be `null` for some titles.                      |
| **No auth layer**          | The API is fully open. If deploying publicly, consider adding an API key middleware.                                         |
| **Upstream dependency**    | All data depends on third-party upstream services. If any upstream goes down, related endpoints will degrade or fail.        |

---

## License

This project is for personal/educational use. Respect the terms of service of all upstream APIs used.
