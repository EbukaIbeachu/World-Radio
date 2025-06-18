import requests
import vlc
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import os
from geopy.geocoders import Nominatim
import polyline
from contextlib import closing

class RadioGlobeCore:
    def __init__(self):
        self.api_base = "https://de1.api.radio-browser.info/json"
        self.cache_file = "radio_cache.db"
        self.cache_expiry = timedelta(hours=6)
        
        try:
            self.instance = vlc.Instance("--no-xlib --quiet")
            self.player = self.instance.media_player_new()
        except Exception as e:
            raise RuntimeError(f"VLC initialization failed: {str(e)}")
        
        self.volume = 70
        self._setup_logger()
        self._init_cache_db()
        self.geolocator = Nominatim(user_agent="RadioGlobe/1.0")

    def _setup_logger(self):
        self.logger = logging.getLogger("radioglobe.core")
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('radioglobe.log', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _init_cache_db(self):
        with closing(sqlite3.connect(self.cache_file)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stations (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    url TEXT,
                    country TEXT,
                    code TEXT,
                    tags TEXT,
                    homepage TEXT,
                    lat REAL,
                    lon REAL,
                    last_updated TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_country ON stations(country)")

    def get_countries(self) -> List[Dict]:
        """Get list of available countries from radio-browser.info"""
        try:
            response = requests.get(
                f"{self.api_base}/countries",
                headers={'User-Agent': 'RadioGlobe/3.0'},
                timeout=5
            )
            response.raise_for_status()
            return sorted(response.json(), key=lambda x: x['name'])
        except Exception as e:
            self.logger.error(f"Failed to fetch countries: {str(e)}")
            return []

    def get_stations(self, country: str) -> Tuple[List[Dict], int]:
        """Get radio stations for a specific country"""
        try:
            cached = self._get_cached_stations(country)
            if cached:
                return cached, len(cached)
            
            params = {
                'country': country,
                'hidebroken': 'true',
                'order': 'votes',
                'reverse': 'true',
                'limit': 500
            }
            response = requests.get(
                f"{self.api_base}/stations/search",
                params=params,
                headers={'User-Agent': 'RadioGlobe/3.0'},
                timeout=10
            )
            response.raise_for_status()
            stations = response.json()
            self._cache_stations(stations)
            return stations, len(stations)
        except Exception as e:
            self.logger.error(f"Failed to fetch stations: {str(e)}")
            return [], 0

    def _get_cached_stations(self, country: str) -> List[Dict]:
        """Get cached stations from local database"""
        with closing(sqlite3.connect(self.cache_file)) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM stations 
                WHERE country = ? AND last_updated > ?
            """, (country, datetime.now() - self.cache_expiry))
            return [dict(row) for row in cur.fetchall()]

    def _cache_stations(self, stations: List[Dict]):
        """Cache stations in local database"""
        with closing(sqlite3.connect(self.cache_file)) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO stations VALUES (?,?,?,?,?,?,?,?,?,?)
            """, [
                (
                    s.get('stationuuid'),
                    s.get('name'),
                    s.get('url'),
                    s.get('country'),
                    s.get('countrycode'),
                    s.get('tags'),
                    s.get('homepage'),
                    s.get('geo_lat'),
                    s.get('geo_long'),
                    datetime.now()
                ) for s in stations
            ])

    def get_coordinates(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """Convert address to (lat, lon) coordinates"""
        try:
            location = self.geolocator.geocode(address)
            return (location.latitude, location.longitude) if location else (None, None)
        except Exception as e:
            self.logger.error(f"Geocoding failed: {str(e)}")
            return (None, None)

    def play(self, url: str) -> bool:
        """Play a radio stream"""
        try:
            if self.player.is_playing():
                self.player.stop()
            media = self.instance.media_new(url)
            media.add_option('network-caching=3000')
            self.player.set_media(media)
            self.player.audio_set_volume(self.volume)
            return self.player.play() == 0
        except Exception as e:
            self.logger.error(f"Playback failed: {str(e)}")
            return False

    def set_volume(self, volume: int):
        """Set playback volume (0-100)"""
        if 0 <= volume <= 100:
            self.volume = volume
            if self.player:
                self.player.audio_set_volume(volume)

    def stop(self):
        """Stop playback"""
        try:
            if self.player.is_playing():
                self.player.stop()
        except Exception as e:
            self.logger.error(f"Stop failed: {str(e)}")

    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, 'player'):
            self.player.release()
        if hasattr(self, 'instance'):
            self.instance.release()