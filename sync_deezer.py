import os
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
DEEZER_ARL_COOKIE = os.environ.get("DEEZER_ARL_COOKIE")

PLAYLIST_ID = "15652964743"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_fresh_token():
    """Gera um token novo usando a sessão do ARL sem expirar"""
    if not DEEZER_ARL_COOKIE:
        print("ERRO: DEEZER_ARL_COOKIE não configurado nas Secrets.")
        return None

    session = requests.Session()
    session.cookies.set("arl", DEEZER_ARL_COOKIE.strip(), domain=".deezer.com")

    # Requisita a permissão usando o App ID 164115
    url = "https://connect.deezer.com/oauth/auth.php?app_id=164115&redirect_uri=https://developers.deezer.com/api/explorer&perms=basic_access,manage_library,delete_library&response_type=token"
    
    # POST direto força a emissão do token no parâmetro do redirecionamento
    res = session.post(url, allow_redirects=False)

    location = res.headers.get("Location", "")
    if "access_token=" in location:
        token = location.split("access_token=")[1].split("&")[0]
        print("Token gerado automaticamente com sucesso!")
        return token

    # Fallback caso siga o redirecionamento
    if res.status_code == 200:
        res_get = session.get(url)
        if "access_token=" in res_get.url:
            return res_get.url.split("access_token=")[1].split("&")[0]

    print(f"Falha ao obter token. Status: {res.status_code}")
    return None

def update_deezer_playlist():
    print("1. Atualizando View Materializada no Supabase...")
    try:
        supabase.rpc("refresh_deezer_view").execute()
    except Exception as e:
        print(f"Aviso ao atualizar View: {e}")

    print("2. Lendo as 200 músicas mais atrasadas da View...")
    res = supabase.from_("vw_deezer_top100_outdated").select("id").execute()
    
    if not res.data:
        print("Nenhuma faixa encontrada na View.")
        return

    track_ids = [str(item["id"]) for item in res.data]
    print(f"Total de faixas recuperadas: {len(track_ids)}")

    token = get_fresh_token()
    if not token:
        print("Não foi possível continuar sem um token válido.")
        return

    # 3. Limpa a playlist existente (limite ajustado para buscar até 250 faixas)
    url_get = f"https://api.deezer.com/playlist/{PLAYLIST_ID}/tracks?access_token={token}&limit=250"
    res_atuais = requests.get(url_get).json()
    
    if "error" in res_atuais:
        print(f"Erro ao acessar playlist no Deezer: {res_atuais['error']}")
        return

    faixas_atuais = [str(t['id']) for t in res_atuais.get('data', [])]

    if faixas_atuais:
        url_del = f"https://api.deezer.com/playlist/{PLAYLIST_ID}/tracks?access_token={token}&songs={','.join(faixas_atuais)}"
        requests.delete(url_del)
        print("Faixas antigas removidas da playlist.")

    # 4. Insere as 200 novas faixas
    url_add = f"https://api.deezer.com/playlist/{PLAYLIST_ID}/tracks?access_token={token}&songs={','.join(track_ids)}"
    res_add = requests.post(url_add).json()

    print(f"Resultado da atualização no Deezer: {res_add}")

if __name__ == "__main__":
    update_deezer_playlist()
