#!/usr/bin/env python3
import os
import json
import gzip
import requests
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

# -----------------------
# Configuración de salida
# -----------------------
OUTPUT_DIR = "/home/yordi/Documentos/GitHub/Samsung"

# Crear la carpeta si no existe
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)


APP_URL = 'https://i.mjh.nz/SamsungTVPlus/.channels.json.gz'
EPG_URL = 'https://i.mjh.nz/SamsungTVPlus/{region}.xml.gz'
PLAYBACK_URL = 'https://jmp2.uk/{slug}'
TIMEOUT = (10, 30)

DEFAULT_GROUPS = ''
INCLUDE_DRM = True
START_CHNO = 1
SORT_BY = 'chno'
MAX_THREADS = 5

# -----------------------
# Funciones auxiliares
# -----------------------
def download_and_decompress(url):
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
        return gz.read()

def get_channel_data():
    json_data = download_and_decompress(APP_URL)
    return json.loads(json_data)

def get_epg_data(region):
    url = EPG_URL.format(region=region)
    return download_and_decompress(url)

def filter_channels(data, regions, groups):
    channels = {}
    for region in regions:
        if region in data['regions']:
            region_channels = data['regions'][region].get('channels', {})
            channels.update(region_channels)
    if groups:
        filtered = {}
        for cid, ch in channels.items():
            if ch.get('group', '').lower() in [g.lower() for g in groups]:
                filtered[cid] = ch
        channels = filtered
    return channels

def generate_m3u_playlist(data, channels, region_name='all'):
    lines = ['#EXTM3U']
    if SORT_BY == 'name':
        sorted_channels = sorted(channels.items(), key=lambda x: x[1]['name'].strip().lower())
    else:
        sorted_channels = sorted(channels.items(), key=lambda x: x[1].get('chno', 999999))
    
    current_chno = START_CHNO
    for cid, ch in sorted_channels:
        if ch.get('license_url') and not INCLUDE_DRM:
            continue
        name = ch['name']
        logo = ch['logo']
        group = ch['group']
        url = PLAYBACK_URL.format(slug=data['slug'].format(id=cid))
        if ch.get('license_url'):
            name = f"{name} [DRM]"
        chno = ch.get('chno') if START_CHNO == 1 else current_chno
        if START_CHNO != 1:
            current_chno += 1
        extinf_line = f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}" tvg-chno="{chno}"'
        if ch.get('license_url'):
            extinf_line += f' drm="true" license-url="{ch["license_url"]}"'
        extinf_line += f',{name}'
        lines.extend([extinf_line, url])
    return '\n'.join(lines)

def save_m3u(region, m3u_content):
    path = os.path.join(OUTPUT_DIR, f'samsung_{region}.m3u')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    print(f"✔ M3U guardado: {path}")
    return path

def save_epg(region, epg_content):
    path = os.path.join(OUTPUT_DIR, f'samsung_{region}.xml')
    with open(path, 'wb') as f:
        f.write(epg_content)
    print(f"✔ EPG guardado: {path}")
    return path

def merge_all_m3u():
    files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith('samsung_') and f.endswith('.m3u')]
    master_lines = ['#EXTM3U']
    added = set()
    for f in files:
        path = os.path.join(OUTPUT_DIR, f)
        with open(path, encoding='utf-8') as m3u_file:
            for line in m3u_file:
                if line.startswith('#EXTINF'):
                    name = line.split(',')[-1].strip()
                    if name in added:
                        continue
                    added.add(name)
                    master_lines.append(line)
                elif not line.startswith('#EXTM3U') and line.strip():
                    master_lines.append(line)
    master_path = os.path.join(OUTPUT_DIR, 'samsung_all.m3u')
    with open(master_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(master_lines))
    print(f"✔ M3U unificado generado: {master_path}")

def process_region(region, data, groups):
    channels = filter_channels(data, [region], groups)
    if not channels:
        print(f"⚠ No hay canales para la región '{region}', se omite")
        return
    m3u_content = generate_m3u_playlist(data, channels, region)
    save_m3u(region, m3u_content)
    
    # EPG seguro
    try:
        epg_content = get_epg_data(region)
        save_epg(region, epg_content)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"⚠ EPG no disponible para '{region}', se omitirá")
        else:
            raise

# -----------------------
# Selector de regiones
# -----------------------
def select_regions(region_list):
    print("\nRegiones disponibles:\n")
    for i, r in enumerate(region_list, start=1):
        print(f"{i}. {r}")
    print("\n0. Todas\n")
    choice = input("Elige región(es) (ej: 1,3,5): ").strip()
    if choice == "0":
        return region_list, True  # devolvemos flag all=True
    selected = []
    for n in choice.split(","):
        try:
            idx = int(n.strip()) - 1
            if 0 <= idx < len(region_list):
                selected.append(region_list[idx])
        except:
            pass
    return selected, False

# -----------------------
# Main
# -----------------------
def main():
    print("Samsung TV Plus M3U/EPG Generator (Auto-regiones, Safe EPG)")

    groups = [g.strip() for g in DEFAULT_GROUPS.split(',') if g.strip()] if DEFAULT_GROUPS else []

    data = get_channel_data()
    regions = list(data.get('regions', {}).keys())

    print(f"Regiones detectadas: {regions}")
    regions, all_flag = select_regions(regions)

    if not regions:
        print("❌ No se seleccionó ninguna región")
        return

    print(f"Grupos: {groups if groups else 'Todos'}")

    # Ejecutar regiones en paralelo
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(process_region, region, data, groups) for region in regions]
        for f in futures:
            f.result()

    # Generar all.m3u solo si se eligió 0 (todas)
    if all_flag:
        merge_all_m3u()

    print("\n¡Generación completada! Todos los archivos están en:", OUTPUT_DIR)

# -----------------------
# Ejecutar
# -----------------------
if __name__ == '__main__':
    main()