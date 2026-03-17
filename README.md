# 🎌 Anime API Proxy

> A production-ready FastAPI proxy that unifies anime metadata and multi-source streaming — HiAnime, AnimePahe, AniList — into one clean API.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-Personal%20Use-e84393?style=flat-square)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/your-username/anime-api-proxy)

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Upstream Sources](#-upstream-sources)
- [Getting Started](#-getting-started)
- [API Reference](#-api-reference)
- [Error Handling](#-error-handling)
- [Project Structure](#-project-structure)
- [Known Limitations](#-known-limitations)

---

## ✨ Overview

Anime API Proxy sits between your frontend and several third-party anime data sources. Instead of juggling multiple APIs and CORS issues from the client, you call this proxy once and receive a fully merged, normalized response.

| Feature | Detail |
| :--- | :--- |
| 🎨 **Enriched Metadata** | High-res posters, banners, and cover colors from AniList GraphQL |
| 🔀 **Merged Episode Lists** | AnimePahe and HiAnime episode IDs aligned by index into one list |
| 📡 **Multi-Server Streams** | 3 HiAnime servers × sub + dub fetched in parallel via `ThreadPoolExecutor` |
| 📼 **AnimePahe Downloads** | Direct download URLs with properly formatted filenames injected server-side |
| 🔗 **Related Anime** | Sequels, prequels, side stories, and spin-offs from AniList relations |
| 🛡️ **Graceful Degradation** | Partial upstream failures return inline error objects — never a crash |
| 🌐 **CORS Ready** | Open CORS headers on all routes — callable from any browser frontend |

---

## 🏗️ Architecture

```
                     ┌──────────────────────────────┐
                     │       Anime API Proxy         │
                     │   (this project — FastAPI)    │
                     └──────────────┬───────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
  ┌──────▼──────┐          ┌────────▼────────┐       ┌────────▼────────┐
  │  /search    │          │  /info          │       │  /stream/{id}/  │
  │  /home      │          │                 │       │  {index}        │
  └──────┬──────┘          └────────┬────────┘       └────────┬────────┘
         │                          │                          │
  anime-api.vercel         anime-api + AniList          AniList Mapper
                           + AniList Mapper             + AniScrap resolve
                           + AniScrap seasons           + HiAnime x6 parallel
```

> `/info` and `/stream` run multiple upstream calls **concurrently** to minimize response latency.

---

## 🔗 Upstream Sources

| Source | Base URL | Used For |
| :--- | :--- | :--- |
| `anime-api` | `anime-api-iota-six.vercel.app/api` | Core anime data, HiAnime streams |
| `AniList GraphQL` | `graphql.anilist.co` | Posters, banners, cover colors, related anime |
| `AniList Mapper — Pahe` | `anilistmapper.vercel.app/animepahe/map` | AnimePahe episode ID mapping |
| `AniList Mapper — HiAnime` | `anilistmapper.vercel.app/hianime` | HiAnime episode ID mapping |
| `AniScrap Seasons` | `catapang1989-aniscrap.hf.space/seasons` | Season grouping data |
| `AniScrap Resolve` | `catapang1989-aniscrap.hf.space/resolve` | AnimePahe stream resolution & download URLs |

> All upstream calls are server-side — zero CORS leakage to the client.

---

## 🚀 Getting Started

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

**3. Start the server**

```bash
uvicorn main:app --reload
```

| Interface | URL |
| :--- | :--- |
| API Root | `http://localhost:8000` |
| Swagger UI | `http://localhost:8000/docs` |
| ReDoc | `http://localhost:8000/redoc` |

---

### Docker

```bash
# Build the image
docker build -t anime-proxy .

# Run
docker run -p 8000:8000 anime-proxy

# Run in detached mode
docker run -d -p 8000:8000 --name anime-proxy anime-proxy
```

---

### Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/your-username/anime-api-proxy)

> [!WARNING]
> Vercel's free Hobby tier enforces a **10-second function timeout**. The `/stream` endpoint runs 6+ parallel upstream requests and may hit this limit. Upgrade to **Pro** (60s timeout) for reliable stream serving.

**1. Add `vercel.json` to your project root**

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

**2. Deploy via CLI**

```bash
npm i -g vercel
vercel
```

---

## 📖 API Reference

### `GET /`

Health check. Confirms the proxy is running.

**Response**

```json
{
  "status": "ok",
  "message": "Anime API Proxy is running."
}
```

---

### `GET /home`

Returns homepage data from the upstream anime API — trending, recently updated, and top-airing anime. Response is proxied directly with no transformation.

---

### `GET /search`

Search for anime by title keyword.

**Query Parameters**

| Parameter | Type | Required | Description |
| :--- | :---: | :---: | :--- |
| `keyword` | `string` | ✅ | Anime title to search for |

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
      "episodes": {
        "sub": 47,
        "dub": 47
      }
    }
  ]
}
```

---

### `GET /info`

Returns full anime details — metadata, AniList poster/banner/color, related anime, seasons, and a merged episode list from AnimePahe and HiAnime.

**Query Parameters**

| Parameter | Type | Required | Description |
| :--- | :---: | :---: | :--- |
| `id` | `string` | ✅ | Anime slug ID e.g. `jujutsu-kaisen-20401` |

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
        "title": {
          "romaji": "Jujutsu Kaisen 2nd Season",
          "english": "Jujutsu Kaisen Season 2"
        },
        "format": "TV",
        "status": "FINISHED",
        "episodes": 23,
        "averageScore": 87
      }
    ],
    "seasons": {
      "total": 2,
      "seasons": ["..."]
    }
  },
  "episodes": {
    "anilistId": 113415,
    "total": 24,
    "data": [
      {
        "index": 1,
        "pahe": {
          "episodeId": "abc123.../def456...",
          "number": 1
        },
        "hianime": {
          "episodeId": "jujutsu-kaisen-20401?ep=168082",
          "number": 1,
          "title": "Ryomen Sukuna"
        }
      }
    ]
  }
}
```

---

### `GET /stream/{id}/{index}`

Fetches all streaming links for a specific episode. Returns AnimePahe (stream + download) and HiAnime (3 servers × sub/dub = 6 total) merged in one response. All HiAnime calls are made **in parallel**.

**Path Parameters**

| Parameter | Type | Required | Description |
| :--- | :---: | :---: | :--- |
| `id` | `string` | ✅ | Anime slug ID e.g. `jujutsu-kaisen-20401` |
| `index` | `integer` | ✅ | 1-based episode number |

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
          "file": "https://...master.m3u8",
          "type": "hls",
          "tracks": [
            {
              "file": "https://...en.vtt",
              "label": "English",
              "kind": "captions",
              "default": true
            }
          ],
          "intro": { "start": 0, "end": 88 },
          "outro": { "start": 1320, "end": 1380 }
        },
        "hd-2": { "error": false },
        "hd-3": {
          "error": true,
          "message": "Server hd-3 (sub) returned no stream data"
        }
      },
      "dub": {
        "hd-1": { "error": false },
        "hd-2": { "error": true },
        "hd-3": { "error": true }
      }
    }
  }
}
```

**Stream Notes**

> [!NOTE]
> - HiAnime streams use **HLS (`.m3u8`)** — requires `hls.js`, `Video.js`, or `Plyr` on the client
> - `intro` / `outro` contain timestamps in **seconds** — use these for skip intro/outro UI
> - `tracks` contains **WebVTT** subtitle URLs — pass directly to your player's track API
> - HLS links are **time-limited** — never cache stream responses, always fetch fresh
> - A failed server always returns `{ "error": true, "message": "..." }` — never `null` — safe to iterate all keys
> - Fall through servers `hd-1 → hd-2 → hd-3` until one returns `error: false`

---

## ⚠️ Error Handling

All errors follow FastAPI's standard structure:

```json
{
  "detail": "Human-readable error message."
}
```

**HTTP Status Codes**

| Status | Meaning | Cause |
| :---: | :--- | :--- |
| `400` | Bad Request | Missing required query parameter |
| `404` | Not Found | Invalid anime ID or episode index out of range |
| `502` | Bad Gateway | Upstream returned an error, invalid JSON, or refused connection |
| `504` | Gateway Timeout | Upstream request exceeded the 10-second timeout |

**Partial Failure Behavior**

| Layer | Behavior |
| :--- | :--- |
| Connection error | Raises `502 Bad Gateway` |
| Upstream timeout | Raises `504 Gateway Timeout` |
| HiAnime server failure | Returns `{ "error": true }` inline — overall response stays `200 OK` |
| AnimePahe resolve failure | Sets `streams.pahe` to `null` — HiAnime streams still returned |
| AniList failure | Falls back to `null` for poster/banner/related — core data still returned |

---

## 🗂️ Project Structure

```
anime-api-proxy/
│
├── main.py              # FastAPI app — all routes, helpers, upstream logic
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container build definition
├── vercel.json          # Vercel deployment config (add manually)
└── README.md            # This file
```

**`requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
requests==2.32.3
```

> No environment variables required. All upstream URLs are constants in `main.py`. Swap them to `os.getenv()` if you need to override per environment.

---

## 🚧 Known Limitations

| # | Limitation | Detail |
| :---: | :--- | :--- |
| 1 | **Vercel 10s Timeout** | Free tier may timeout on `/stream` (6 parallel calls). Use Vercel Pro or Docker. |
| 2 | **HLS Link Expiry** | HiAnime `.m3u8` links are short-lived. Never cache stream responses. |
| 3 | **AnimePahe Coverage** | Not all anime have Pahe episodes. `streams.pahe` may be `null`. |
| 4 | **No Auth Layer** | API is fully open. Add API key middleware before public deployment. |
| 5 | **Upstream Dependency** | Relies on 6 third-party services. No local caching included by default. |

> [!CAUTION]
> If deploying publicly without authentication, your proxy can be abused to hammer upstream services. Add rate limiting or an API key check before going live.

---

*For personal and educational use — respect the Terms of Service of all upstream APIs consumed by this proxy.*
