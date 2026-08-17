import os
from datetime import datetime, timezone
import requests
from supabase import create_client, Client

USER_ID = os.environ.get("DEEZER_USER_ID")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
DEEZER_ACCESS_TOKEN = os.environ.get("DEEZER_ACCESS_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
PLAYLIST_NAME = "!! Favoritas mais atrasadas"

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
        if len(items) < limit:
            break
            
        index += limit
            
    return tracks

def parse_timestamp(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None

def update_outdated_playlist():
    """Busca as 50 faixas mais atrasadas no Supabase e atualiza a playlist fixa no Deezer"""
    if not DEEZER_ACCESS_TOKEN:
        print("DEEZER_ACCESS_TOKEN não configurado. Pulando atualização da playlist.")
        return

    print(f"Buscando as 50 faixas mais atrasadas no Supabase...")
    res = supabase.from_("vw_deezer_favorites_scrobbles") \
        .select("id, dias_ouvida") \
        .neq("dias_ouvida", 999999) \
        .order("dias_ouvida", ascending=False) \
        .limit(50) \
        .execute()

    if not res.data:
        print("Nenhuma faixa válida encontrada para atualizar a playlist.")
        return

    track_ids = [str(item["id"]) for item in res.data]
    songs_param = ",".join(track_ids)

    # 1. Verifica se a playlist já existe no perfil
    playlists_url = f"https://api.deezer.com/user/me/playlists?access_token={DEEZER_ACCESS_TOKEN}"
    playlists_res = requests.get(playlists_url).json()
    
    playlist_id = None
    if "data" in playlists_res:
        for pl in playlists_res["data"]:
            if pl.get("title") == PLAYLIST_NAME:
                playlist_id = pl.get("id")
                break

    # 2. Se não existir, cria a playlist
    if not playlist_id:
        create_url = f"https://api.deezer.com/user/me/playlists?access_token={DEEZER_ACCESS_TOKEN}&title={requests.utils.quote(PLAYLIST_NAME)}"
        create_res = requests.post(create_url).json()
        playlist_id = create_res.get("id")
        print(f"Playlist '{PLAYLIST_NAME}' criada com ID: {playlist_id}")

    # 3. Sobrescreve as faixas da mesma playlist
    if playlist_id:
        # Substitui a lista de faixas existentes pelas 50 novas
        update_url = f"https://api.deezer.com/playlist/{playlist_id}/tracks?access_token={DEEZER_ACCESS_TOKEN}&songs={songs_param}"
        requests.post(update_url)
        print(f"Playlist '{PLAYLIST_NAME}' (ID: {playlist_id}) atualizada com {len(track_ids)} faixas!")

def sync():
    print("Iniciando busca de favoritos no Deezer...")
    raw_tracks = fetch_all_favorites(USER_ID)
    
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

    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        supabase.table("tbl_deezer_favorites").upsert(batch, on_conflict="id").execute()
        
    print("Tabela tbl_deezer_favorites atualizada!")

    # Refresh na Materialized View do Supabase
    try:
        supabase.rpc("refresh_deezer_view").execute()
        print("Materialized View atualizada com sucesso!")
    except Exception as e:
        print(f"Aviso ao atualizar View: {e}")

    # Atualiza a playlist no Deezer
    try:
        update_outdated_playlist()
    except Exception as e:
        print(f"Erro ao atualizar playlist no Deezer: {e}")

if __name__ == "__main__":
    sync()
