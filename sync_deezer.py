import os
from datetime import datetime, timezone
import requests
from supabase import create_client, Client

USER_ID = os.environ.get("DEEZER_USER_ID")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
DEEZER_ARL_COOKIE = os.environ.get("DEEZER_ARL_COOKIE")

# COLOQUE O ID NUMÉRICO DA SUA PLAYLIST AQUI
PLAYLIST_ID_FIXA = "SEU_ID_DA_PLAYLIST_AQUI"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_fresh_token():
    """Gera um token com permissão de escrita usando o ARL Cookie"""
    if not DEEZER_ARL_COOKIE:
        print("ERRO: DEEZER_ARL_COOKIE não encontrado nas Secrets.")
        return None
    
    session = requests.Session()
    session.cookies.set('arl', DEEZER_ARL_COOKIE.strip(), domain='.deezer.com')
    
    # App ID 164115 (API Explorer Oficial do Deezer)
    auth_url = "https://connect.deezer.com/oauth/auth.php?app_id=164115&redirect_uri=https://developers.deezer.com/api/explorer&perms=basic_access,manage_library,delete_library&response_type=token"
    
    response = session.get(auth_url, allow_redirects=False)
    
    if response.status_code in (301, 302):
        location = response.headers.get('Location', '')
        if 'access_token=' in location:
            token = location.split('access_token=')[1].split('&')[0]
            print("Token temporário do Deezer gerado com sucesso!")
            return token
            
    print(f"Erro ao gerar token. Status HTTP: {response.status_code}. Verifique o ARL Cookie.")
    return None

def fetch_all_favorites(user_id):
    tracks = []
    limit = 100
    index = 0
    
    while True:
        url = f"https://api.deezer.com/user/{user_id}/tracks?limit={limit}&index={index}"
        response = requests.get(url)
        if response.status_code != 200:
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

def update_outdated_playlist(token):
    print(f"Buscando as 50 faixas mais atrasadas do Supabase para a playlist {PLAYLIST_ID_FIXA}...")
    res = supabase.from_("vw_deezer_favorites_scrobbles") \
        .select("id, dias_ouvida") \
        .neq("dias_ouvida", 999999) \
        .order("dias_ouvida", ascending=False) \
        .limit(50) \
        .execute()

    if not res.data:
        print("Nenhuma faixa válida encontrada no Supabase.")
        return

    novas_faixas = [str(item["id"]) for item in res.data]

    # 1. Pega os IDs das faixas que já estão na playlist
    url_get = f"https://api.deezer.com/playlist/{PLAYLIST_ID_FIXA}/tracks?access_token={token}&limit=100"
    res_atuais = requests.get(url_get).json()
    
    if "error" in res_atuais:
        print(f"Erro ao acessar playlist no Deezer: {res_atuais['error']}")
        return

    faixas_atuais = [str(t['id']) for t in res_atuais.get('data', [])]

    # 2. Apaga faixas antigas (se houver)
    if faixas_atuais:
        del_url = f"https://api.deezer.com/playlist/{PLAYLIST_ID_FIXA}/tracks?access_token={token}&songs={','.join(faixas_atuais)}"
        res_del = requests.delete(del_url).json()
        print(f"Remoção de faixas antigas: {res_del}")

    # 3. Adiciona as 50 faixas novas
    add_url = f"https://api.deezer.com/playlist/{PLAYLIST_ID_FIXA}/tracks?access_token={token}&songs={','.join(novas_faixas)}"
    res_add = requests.post(add_url).json()
    print(f"Adição de 50 novas faixas: {res_add}")

def parse_timestamp(ts):
    if not ts: return None
    try: return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except: return None

def sync():
    print("Sincronizando favoritos com Supabase...")
    raw_tracks = fetch_all_favorites(USER_ID)
    records = []
    for item in raw_tracks:
        records.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "artist_id": item.get("artist", {}).get("id"),
            "artist_name": item.get("artist", {}).get("name"),
            "artist_picture": item.get("artist", {}).get("picture_medium"),
            "album_id": item.get("album", {}).get("id"),
            "album_title": item.get("album", {}).get("title"),
            "album_cover": item.get("album", {}).get("cover_medium"),
            "link": item.get("link"),
            "time_add": parse_timestamp(item.get("time_add")),
            "raw_data": item,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    for i in range(0, len(records), 100):
        supabase.table("tbl_deezer_favorites").upsert(records[i:i+100], on_conflict="id").execute()
    print("Base do Supabase atualizada!")

    try:
        supabase.rpc("refresh_deezer_view").execute()
        print("View Materializada recalculada!")
    except Exception as e:
        print(f"Aviso ao recalcular View: {e}")

    token = get_fresh_token()
    if token:
        update_outdated_playlist(token)

if __name__ == "__main__":
    sync()
