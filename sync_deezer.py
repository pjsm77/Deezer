import os
from datetime import datetime, timezone
import requests
from supabase import create_client, Client

USER_ID = os.environ.get("DEEZER_USER_ID")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_all_favorites(user_id):
    tracks = []
    limit = 100
    index = 0
    
    while True:
        url = f"https://api.deezer.com/user/{user_id}/tracks?limit={limit}&index={index}"
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Erro na requisição API Deezer: {response.status_code}")
            break
            
        data = response.json()
        items = data.get("data", [])
        
        if not items:
            break
            
        tracks.extend(items)
        print(f"Buscados {len(tracks)} de {data.get('total', '?')} favoritos...")
        
        # Se a quantidade retornada for menor que o limite, chegamos ao fim da lista
        if len(items) < limit:
            break
            
        index += limit
            
    return tracks

def parse_timestamp(ts):
    """Converte o timestamp Unix da Deezer para formato ISO UTC aceito pelo Postgres"""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None

def sync():
    print("Iniciando busca completa de favoritos no Deezer...")
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
            "time_add": parse_timestamp(item.get("time_add")),
            "raw_data": item,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        records.append(record)

    # 1. Upsert em lotes de 100 registros na tabela física
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        supabase.table("tbl_deezer_favorites").upsert(batch, on_conflict="id").execute()
        print(f"Enviado lote {i // batch_size + 1} ({len(batch)} registros)")
        
    print("Tabela tbl_deezer_favorites atualizada com sucesso!")

    # 2. Atualiza a Materialized View no Supabase
    try:
        print("Atualizando Materialized View (vw_deezer_favorites_scrobbles)...")
        supabase.rpc("refresh_deezer_view").execute()
        print("Materialized View atualizada com sucesso!")
    except Exception as e:
        print(f"Aviso ao atualizar a Materialized View via RPC: {e}")

if __name__ == "__main__":
    sync()
