"""Fetch data from PyPI."""

import asyncio
import hashlib
from typing import List, Optional

import aiohttp
from packaging.version import Version

from django.core.cache import cache

from allianceauth.services.hooks import get_extension_logger

logger = get_extension_logger(__name__)

BASE_URL = "https://pypi.org/pypi"
CACHE_TIMEOUT = 3600 * 24
CACHE_KEY = "package-monitor-pypi-"


async def fetch_pypi_releases(
    session: aiohttp.ClientSession, name: str, releases: List[Version]
) -> List[dict]:
    """Fetch and return data for releases of a pypi project."""
    tasks = [
        asyncio.create_task(
            fetch_release_from_pypi_async(session, name=name, version=str(r))
        )
        for r in releases
    ]
    r = await asyncio.gather(*tasks)
    return r


async def fetch_project_from_pypi_async(
    session: aiohttp.ClientSession, name: str
) -> Optional[dict]:
    """Fetch project data from PyPI and return it.

    Returns None if there was an API error.
    """
    return await _fetch_data_from_pypi_async(session, _make_pypi_url(name))


async def fetch_release_from_pypi_async(
    session: aiohttp.ClientSession, name: str, version: str
) -> Optional[dict]:
    """Fetch release data from PyPI and return it.

    Returns None if there was an API error.
    """
    key = _make_cache_key(name, version)
    if data := await cache.aget(key):
        return data

    r = await _fetch_data_from_pypi_async(session, _make_pypi_url(name, version))
    await cache.aset(key=key, value=r, timeout=CACHE_TIMEOUT)
    return r


def _make_cache_key(name: str, version: str) -> str:
    b = f"{name}-{version}".encode("utf-8")
    key_hash = hashlib.md5(b).hexdigest()
    key = f"{CACHE_KEY}{key_hash}"
    return key


def _make_pypi_url(name: str, version: Optional[str] = None) -> str:
    if not version:
        return f"{BASE_URL}/{name}/json"
    return f"{BASE_URL}/{name}/{version}/json"


async def _fetch_data_from_pypi_async(
    session: aiohttp.ClientSession, url: str
) -> Optional[dict]:
    """Fetch JSON data for a URL and return it.

    Returns None if there was an API error.
    """
    logger.info("Fetching data from PyPI for url: %s", url)

    async with session.get(url) as resp:
        if not resp.ok:
            if resp.status == 404:
                logger.info("PyPI URL not found: %s", url)
            else:
                logger.warning(
                    "Failed to retrieve data from PyPI for "
                    "url '%s'. "
                    "Status code: %d, "
                    "response: %s",
                    url,
                    resp.status,
                    await resp.text(),
                )
            return None

        data = await resp.json()
        return data


def clear_cache():
    """Clear the release cache."""
    keys = cache.iter_keys(f"{CACHE_KEY}*")
    cache.delete_many(keys)
