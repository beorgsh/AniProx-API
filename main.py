"""
Anime API Proxy
Wraps: https://anime-api-iota-six.vercel.app/api
Run locally: uvicorn main:app --reload
"""

import requests
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_URL = "https://anime-api-iota-six.vercel.app/api"
PAHE_MAP_URL = "https://anilistmapper.vercel.app/animepahe/map"
HIANIME_MAP_URL = "https://anilistmapper.vercel.app/hianime"
ANILIST_URL = "https://graphql.anilist.co"
SEASONS_URL = "https://catapang1989-aniscrap.hf.space/seasons"
PAHE_RESOLVE = "https://catapang1989-aniscrap.hf.space/resolve"

app = FastAPI(
    title="Anime API Proxy",
    description="Proxy API for anime data",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch(url: str) -> dict:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=502, detail=f"Could not connect to upstream: {url}"
        )
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Upstream request timed out.")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {e}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Failed to parse upstream JSON.")


def fetch_silent(url: str):
    try:
        # Use a prepared request so the URL is sent exactly as-is (no re-encoding)
        req = requests.Request("GET", url)
        prepared = req.prepare()
        prepared.url = url  # override to preserve ?ep= inside the id param
        session = requests.Session()
        response = session.send(prepared, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def get_anilist_media(anilist_id: str) -> dict:
    query = """
    query ($id: Int) {
      Media(id: $id, type: ANIME) {
        coverImage { extraLarge large color }
        bannerImage
        relations {
          edges {
            relationType(version: 2)
            node {
              id type
              title { romaji english }
              format status episodes
              coverImage { large medium }
              averageScore season seasonYear
            }
          }
        }
      }
    }
    """
    try:
        response = requests.post(
            ANILIST_URL,
            json={"query": query, "variables": {"id": int(anilist_id)}},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        media = response.json().get("data", {}).get("Media", {})
        edges = media.get("relations", {}).get("edges", [])
        related = [
            {
                "relationType": e.get("relationType"),
                "id": e["node"].get("id"),
                "type": e["node"].get("type"),
                "format": e["node"].get("format"),
                "status": e["node"].get("status"),
                "episodes": e["node"].get("episodes"),
                "averageScore": e["node"].get("averageScore"),
                "season": e["node"].get("season"),
                "seasonYear": e["node"].get("seasonYear"),
                "title": e["node"].get("title", {}),
                "coverImage": e["node"].get("coverImage", {}),
            }
            for e in edges
            if e.get("node", {}).get("type") == "ANIME"
        ]
        return {
            "poster": media.get("coverImage", {}).get("extraLarge")
            or media.get("coverImage", {}).get("large"),
            "banner": media.get("bannerImage"),
            "coverColor": media.get("coverImage", {}).get("color"),
            "related": related,
        }
    except Exception:
        return {"poster": None, "banner": None, "coverColor": None, "related": []}


def get_seasons(anime_id: str) -> dict:
    try:
        r = requests.get(f"{SEASONS_URL}/{anime_id}", timeout=10)
        r.raise_for_status()
        data = r.json()
        return {"total": data.get("total", 0), "seasons": data.get("seasons", [])}
    except Exception:
        return {"total": 0, "seasons": []}


def get_merged_episodes(anilist_id: str) -> list:
    pahe_raw = fetch(f"{PAHE_MAP_URL}/{anilist_id}")
    hianime_raw = fetch(f"{HIANIME_MAP_URL}/{anilist_id}")

    pahe_episodes = (
        pahe_raw.get("animepahe", {}).get("episodes", [])
        if isinstance(pahe_raw, dict)
        else []
    )
    if isinstance(hianime_raw, list):
        hianime_episodes = hianime_raw
    elif isinstance(hianime_raw, dict):
        hianime_episodes = hianime_raw.get("episodes", hianime_raw.get("data", []))
    else:
        hianime_episodes = []

    max_len = max(len(pahe_episodes), len(hianime_episodes), 0)
    return [
        {
            "index": i + 1,
            "pahe": pahe_episodes[i] if i < len(pahe_episodes) else None,
            "hianime": hianime_episodes[i] if i < len(hianime_episodes) else None,
        }
        for i in range(max_len)
    ]


def fetch_hianime_server(episode_id: str, server: str, type_: str):
    """Fetch one hianime server for a given type.
    Returns stream data on success, or an error object on failure.
    episode_id form: slug?ep=NUMBER  (e.g. frieren-...-18542?ep=107257)
    """
    url = f"{BASE_URL}/stream?id={episode_id}&server={server}&type={type_}"
    try:
        req = requests.Request("GET", url)
        prepared = req.prepare()
        prepared.url = url
        session = requests.Session()
        response = session.send(prepared, timeout=30)

        # Catch HTTP error status codes and return descriptive error
        if response.status_code != 200:
            return {
                "error": True,
                "server": server,
                "type": type_,
                "statusCode": response.status_code,
                "message": f"Server {server} ({type_}) returned HTTP {response.status_code}",
            }

        data = response.json()
        streaming = data.get("results", {}).get("streamingLink")

        if (
            not data.get("success")
            or not streaming
            or not streaming.get("link", {}).get("file")
        ):
            return {
                "error": True,
                "server": server,
                "type": type_,
                "message": f"Server {server} ({type_}) returned no stream data",
            }

        return {
            "error": False,
            "server": server,
            "serverName": streaming.get("server"),
            "file": streaming["link"]["file"],
            "type": streaming["link"].get("type", "hls"),
            "tracks": streaming.get("tracks", []),
            "intro": streaming.get("intro"),
            "outro": streaming.get("outro"),
        }

    except requests.exceptions.Timeout:
        return {
            "error": True,
            "server": server,
            "type": type_,
            "message": f"Server {server} ({type_}) timed out",
        }
    except requests.exceptions.ConnectionError:
        return {
            "error": True,
            "server": server,
            "type": type_,
            "message": f"Server {server} ({type_}) connection failed",
        }
    except Exception as e:
        return {
            "error": True,
            "server": server,
            "type": type_,
            "message": f"Server {server} ({type_}) unexpected error: {str(e)}",
        }


def fetch_hianime_all(episode_id: str) -> dict:
    """
    Fetch sub and dub streams for all 3 servers in parallel.
    Returns:
    {
      "sub":  { "hd-1": {...}|null, "hd-2": {...}|null, "hd-3": {...}|null },
      "dub":  { "hd-1": {...}|null, "hd-2": {...}|null, "hd-3": {...}|null }
    }
    """
    servers = ("hd-1", "hd-2", "hd-3")
    types = ("sub", "dub")
    tasks = [(server, t) for t in types for server in servers]  # 6 total

    results = {"sub": {}, "dub": {}}

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            (server, t): pool.submit(fetch_hianime_server, episode_id, server, t)
            for server, t in tasks
        }
        for (server, t), future in futures.items():
            try:
                results[t][server] = future.result(timeout=35)
            except Exception:
                results[t][server] = {
                    "error": True,
                    "server": server,
                    "type": t,
                    "message": f"Server {server} ({t}) timed out waiting for response",
                }

    return results


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def root():
    return {"status": "ok", "message": "Anime API Proxy is running."}


@app.get("/home")
def home():
    return fetch(BASE_URL)


@app.get("/search")
def search(keyword: str = Query(..., description="Anime title to search for")):
    url = f"{BASE_URL}/search?keyword={requests.utils.quote(keyword)}"
    return fetch(url)


@app.get("/info")
def info(id: str = Query(..., description="Anime ID")):
    """
    Full anime info: poster/banner from AniList, seasons, related (anime-only),
    merged pahe + hianime episode list.
    """
    info_data = fetch(f"{BASE_URL}/info?id={requests.utils.quote(id)}")
    results = info_data.get("results", {})
    anime_data = results.get("data", {})
    anime_info = anime_data.get("animeInfo", {})
    anilist_id = anime_data.get("anilistId")

    anilist = (
        get_anilist_media(anilist_id)
        if anilist_id
        else {"poster": None, "banner": None, "coverColor": None, "related": []}
    )

    for key in ("japanese_title", "synonyms", "charactersVoiceActors"):
        anime_data.pop(key, None)
    for key in ("Japanese", "Synonyms", "Studios", "Producers", "trailers"):
        anime_info.pop(key, None)

    if anilist["poster"]:
        anime_data["poster"] = anilist["poster"]
    anime_data["banner"] = anilist["banner"]
    anime_data["coverColor"] = anilist["coverColor"]

    results.pop("charactersVoiceActors", None)
    results["related_data"] = anilist["related"]
    results["seasons"] = get_seasons(id)

    episodes = []
    if anilist_id:
        try:
            episodes = get_merged_episodes(anilist_id)
        except HTTPException:
            episodes = []

    anime_data["animeInfo"] = anime_info
    results["data"] = anime_data
    info_data["results"] = results
    info_data["episodes"] = {
        "anilistId": anilist_id,
        "total": len(episodes),
        "data": episodes,
    }

    return info_data


@app.get("/stream/{id}/{index}")
def stream(
    id: str,
    index: int,
):
    """
    Get streaming links for an episode by anime ID and episode index.

    Logic:
      1. Fetch the merged episode list (pahe + hianime) using the anilistId
      2. Pick the episode at the given index (1-based)
      3. Use pahe episodeId  → GET /resolve/:episodeId
      4. Use hianime episodeId → GET /stream?id=<episodeId>&server=hd-1/2/3&type=sub/dub
      5. Return all streams merged in one response

    Example: /stream/one-piece-100/1
    """
    # ── Step 1: get anilistId and anime title from info ──────────────────
    info_data = fetch(f"{BASE_URL}/info?id={requests.utils.quote(id)}")
    anime_data = info_data.get("results", {}).get("data", {})
    anilist_id = anime_data.get("anilistId")
    anime_title = anime_data.get("title", id)  # fallback to id slug if no title

    if not anilist_id:
        raise HTTPException(
            status_code=404, detail="anilistId not found for this anime."
        )

    # ── Step 2: get merged episode list ───────────────────────────────────
    try:
        episodes = get_merged_episodes(anilist_id)
    except HTTPException:
        raise HTTPException(status_code=502, detail="Failed to fetch episode list.")

    if index < 1 or index > len(episodes):
        raise HTTPException(
            status_code=404,
            detail=f"Episode index {index} out of range (1–{len(episodes)}).",
        )

    episode = episodes[index - 1]  # index is 1-based
    pahe_ep = episode.get("pahe")
    hianime_ep = episode.get("hianime")

    # ── Step 3: pahe stream using pahe episodeId ──────────────────────────
    # episodeId example: "ef55466b-bfaf.../02c3b02d..."
    # calls: https://catapang1989-aniscrap.hf.space/resolve/<episodeId>
    pahe_stream = None
    if pahe_ep and pahe_ep.get("episodeId"):
        pahe_stream = fetch_silent(f"{PAHE_RESOLVE}/{pahe_ep['episodeId']}")
        # Inject real anime title into pahe stream response
        if pahe_stream and isinstance(pahe_stream, dict):
            ep_number = pahe_ep.get("number", index)
            # Clean title: only alphanumeric + single spaces, no leading/trailing spaces
            clean_title = " ".join(
                "".join(c if c.isalnum() else " " for c in anime_title).split()
            )
            # Underscore version for filenames
            file_title = clean_title.replace(" ", "_")
            ep_str = str(ep_number).zfill(2)
            filename = f"{file_title}_-_Episode_{ep_str}.mp4"

            # Replace anime_name with clean spaced title
            pahe_stream["anime_name"] = clean_title

            # Update download URL filename param in sub and dub if present
            for track in ("sub", "dub"):
                if track in pahe_stream and isinstance(pahe_stream[track], dict):
                    dl = pahe_stream[track].get("download", "")
                    if dl and "?file=" in dl:
                        base, _ = dl.split("?file=", 1)
                        resolution = pahe_stream[track].get("resolution", "1080")
                        pahe_stream[track]["download"] = (
                            f"{base}?file={file_title}_EP{ep_str}_{resolution}P.mp4"
                        )

            # Set top-level filename field
            pahe_stream["filename"] = filename

    # ── Step 4: hianime streams using hianime episodeId ───────────────────
    # episodeId example: "jujutsu-kaisen-...-20401?ep=168082"
    # calls: BASE_URL/stream?id=<episodeId>&server=hd-1&type=sub  etc.
    hianime_streams = {
        "sub": {"hd-1": None, "hd-2": None, "hd-3": None},
        "dub": {"hd-1": None, "hd-2": None, "hd-3": None},
    }
    if hianime_ep and hianime_ep.get("episodeId"):
        hianime_streams = fetch_hianime_all(hianime_ep["episodeId"])

    # ── Step 5: return merged result ──────────────────────────────────────
    return {
        "success": True,
        "animeId": id,
        "episode": index,
        "streams": {
            "pahe": pahe_stream,
            "hianime": hianime_streams,
        },
    }


# ---------------------------------------------------------------------------
# Local dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
