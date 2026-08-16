import os
import requests
from supabase import create_client, Client

USER_ID = os.environ.get("DEEZER_USER_ID")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_all_favorites(user_id):
    tracks = []
    url = f"https://api.deezer.com/user/{user_id}/tracks?limit=100"
    
    while url:
        response = requests.get(url)
        data = response.json()
        
        if "data" in data:
            tracks.extend(data["data"])
            url = data.get("paging", {}).get("next")
        else:
            break
            
    return tracks

def sync():
    print("Buscando favoritos no Deezer...")
    raw_tracks = fetch_all_favorites(USER_ID)
    print(f"Total de músicas encontradas: {len(raw_tracks)}")
    
    records = []
    for item in raw_tracks:
        record = {
            "id": item.get("id"),
            "title": item.get("title"),
            "title_short": item.get("title_short"),
            "title_version": item.get("title_version"),
            "link": item.get("link"),
            "duration": item.get("duration"),
            "rank": item.get("rank"),
            "explicit_lyrics": item.get("explicit_lyrics"),
            "preview": item.get("preview"),
            "artist_id": item.get("artist", {}).get("id"),
            "artist_name": item.get("artist", {}).get("name"),
            "artist_picture": item.get("artist", {}).get("picture_medium"),
            "album_id": item.get("album", {}).get("id"),
            "album_title": item.get("album", {}).get("title"),
            "album_cover": item.get("album", {}).get("cover_medium"),
            "time_add": item.get("time_add"),
            "raw_data": item,
            "updated_at": "now()"
        }
        records.append(record)

    # Upsert em lotes de 100
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        supabase.table("deezer_favorites").upsert(batch, on_conflict="id").execute()
        
    print("Sincronização concluída com sucesso!")

if __name__ == "__main__":
    sync()
