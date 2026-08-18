import os
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
DEEZER_ACCESS_TOKEN = os.environ.get("DEEZER_ACCESS_TOKEN")

PLAYLIST_ID = "15652964743"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def update_deezer_playlist():
    print("1. Atualizando View Materializada no Supabase...")
    try:
        supabase.rpc("refresh_deezer_view").execute()
    except Exception as e:
        print(f"Aviso ao atualizar View: {e}")

    print("2. Lendo as 100 músicas mais atrasadas da View...")
    res = supabase.from_("vw_deezer_top100_outdated").select("id").execute()
    
    if not res.data:
        print("Nenhuma faixa encontrada na View.")
        return

    track_ids = [str(item["id"]) for item in res.data]
    print(f"Total de faixas recuperadas: {len(track_ids)}")

    if not DEEZER_ACCESS_TOKEN:
        print("ERRO: DEEZER_ACCESS_TOKEN não configurado nas Secrets.")
        return

    # 3. Limpa a playlist existente no Deezer
    url_get = f"https://api.deezer.com/playlist/{PLAYLIST_ID}/tracks?access_token={DEEZER_ACCESS_TOKEN}&limit=110"
    res_atuais = requests.get(url_get).json()
    
    if "error" in res_atuais:
        print(f"Erro ao acessar playlist no Deezer: {res_atuais['error']}")
        return

    faixas_atuais = [str(t['id']) for t in res_atuais.get('data', [])]

    if faixas_atuais:
        url_del = f"https://api.deezer.com/playlist/{PLAYLIST_ID}/tracks?access_token={DEEZER_ACCESS_TOKEN}&songs={','.join(faixas_atuais)}"
        requests.delete(url_del)
        print("Faixas antigas removidas da playlist.")

    # 4. Adiciona os 100 IDs novos
    url_add = f"https://api.deezer.com/playlist/{PLAYLIST_ID}/tracks?access_token={DEEZER_ACCESS_TOKEN}&songs={','.join(track_ids)}"
    res_add = requests.post(url_add).json()

    print(f"Resultado da atualização no Deezer: {res_add}")

if __name__ == "__main__":
    update_deezer_playlist()
