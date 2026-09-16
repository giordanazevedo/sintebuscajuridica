import os
import glob
import io
import json
import re
import sys
import threading
import time
from datetime import datetime
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, jsonify, request, send_from_directory, send_file
from werkzeug.utils import secure_filename

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

app = Flask(__name__, static_folder=".")

# Senha de acesso restrito às planilhas (padrão: sinte@juridico10)
SENHA_ACESSO = os.environ.get("SENHA_ACESSO", "sinte@juridico10")

# Intervalo da sincronização automática em minutos (padrão: 30 minutos)
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "30"))

banco_dados = []
ultima_sincronizacao = None
sincronizando = False
sync_lock = threading.Lock()

# ----------------------------------------------------------------------
# 1. MAPEAMENTO DAS PLANILHAS DO GOOGLE DRIVE
# ----------------------------------------------------------------------
PLANILHAS_GOOGLE = [
    {"nome_acao": "AUTORIZAÇÕES ASSINADAS - MÃO SANTA 99", "id": "1T7riNd-ksnhfWkuR4iQUW8_mYfx8u07O"},
    {"nome_acao": "MAO SANTA II", "id": "1z9tGbxd1BrezQwfnI0gTA9UDnA1CWYxG"},
    {"nome_acao": "MÃO SANTA III", "id": "1GMHtlfXB3bRzknUZh2ILzfEeSny4etkj"},
    {"nome_acao": "MÃO SANTA IV A VII", "id": "1LLxcb-STxF8Y2qhzsmMYTy-n-L9-lu33"},
    {"nome_acao": "Ação Guilherme Melo COMPLETO", "id": "1-3xLtKtDB4VdSIC9C-HAyTdCZ_aQOPNkQcy9fvMG9-c"},
    {"nome_acao": "SEGUNDA AÇÃO", "id": "1_tfg7-uoslZaVJCDDpOyiNXh_LVxvWak"},
    {"nome_acao": "HERDEIROS CONCLUIDOS GUILHERME MELO E MÃO SANTA", "id": "1CxixmGKhtV-MdF6xM3h6RhfxKqzbiyIQ"},
    {"nome_acao": "SEGUNDA AÇÃO - HERDEIROS CONCLUÍDOS", "id": "1eF_NFwNhbR7PeJJmQXLK27z69O3cqhXq"}
]

MAPA_IDS_ACOES = {p["nome_acao"]: p["id"] for p in PLANILHAS_GOOGLE}
MAPA_IDS_ACOES["FUNDEF"] = "1-3xLtKtDB4VdSIC9C-HAyTdCZ_aQOPNkQcy9fvMG9-c"
MAPA_IDS_ACOES["GUILHERME MELO"] = "1-3xLtKtDB4VdSIC9C-HAyTdCZ_aQOPNkQcy9fvMG9-c"
MAPA_IDS_ACOES["FILIAÇÕES"] = "1-3xLtKtDB4VdSIC9C-HAyTdCZ_aQOPNkQcy9fvMG9-c"

ARQUIVO_CADASTROS_MANUAIS = "novos_cadastros_sinte.xlsx"

# ----------------------------------------------------------------------
# CONSTANTES E PERSISTÊNCIA ATÔMICA DO MÓDULO DE HERDEIROS
# ----------------------------------------------------------------------
ARQUIVO_HERDEIROS = "dados_herdeiros.json"
ARQUIVO_HERDEIROS_EXCEL = "herdeiros_cadastros.xlsx"
DIR_UPLOADS_HERDEIROS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads_herdeiros")
os.makedirs(DIR_UPLOADS_HERDEIROS, exist_ok=True)
herdeiros_lock = threading.Lock()

STATUS_HERDEIROS_MAP = {
    "fila_espera": "Fila de Espera",
    "em_producao": "Em Produção",
    "enviado_assinatura": "Enviado p/ Assinatura",
    "concluido": "Concluído & Arquivado"
}

def carregar_herdeiros():
    with herdeiros_lock:
        if not os.path.exists(ARQUIVO_HERDEIROS):
            return []
        try:
            with open(ARQUIVO_HERDEIROS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return dados if isinstance(dados, list) else []
        except Exception as e:
            print(f"⚠️ Erro ao carregar {ARQUIVO_HERDEIROS}: {e}")
            return []

def salvar_herdeiros(dados):
    with herdeiros_lock:
        temp_file = f"{ARQUIVO_HERDEIROS}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            if os.path.exists(ARQUIVO_HERDEIROS):
                os.replace(temp_file, ARQUIVO_HERDEIROS)
            else:
                os.rename(temp_file, ARQUIVO_HERDEIROS)
        except Exception as e:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except Exception: pass
            raise e

        try:
            linhas_excel = []
            for item in dados:
                fal = item.get("falecido", {})
                herds = item.get("herdeiros", [])
                nomes_herdeiros = ", ".join(h.get("nome", "") for h in herds if h.get("nome"))
                contatos_herdeiros = ", ".join(f"{h.get('nome')}: {h.get('telefone') or h.get('email') or 'S/C'}" for h in herds if h.get("nome"))
                processos_str = " / ".join(item.get("processos", [])) or fal.get("acao_juridica", "")
                
                linhas_excel.append({
                    "ID": item.get("id"),
                    "STATUS": STATUS_HERDEIROS_MAP.get(item.get("status"), item.get("status")),
                    "FALECIDO": fal.get("nome"),
                    "CPF FALECIDO": fal.get("cpf"),
                    "MATRÍCULA": fal.get("matricula"),
                    "REGIONAL": fal.get("regional"),
                    "AÇÕES / PROCESSOS": processos_str,
                    "DATA ÓBITO": fal.get("data_obito"),
                    "QTD HERDEIROS": len(herds),
                    "NOMES HERDEIROS": nomes_herdeiros,
                    "CONTATOS HERDEIROS": contatos_herdeiros,
                    "LOCAL PROVISÓRIO": item.get("localizacao_provisoria"),
                    "CAIXA CONCLUÍDO": item.get("caixa_concluido"),
                    "DATA CADASTRO": item.get("data_cadastro"),
                    "ÚLTIMA ATUALIZAÇÃO": item.get("ultima_atualizacao"),
                    "OBSERVAÇÕES": item.get("observacoes")
                })
            df_herd = pd.DataFrame(linhas_excel)
            df_herd.to_excel(ARQUIVO_HERDEIROS_EXCEL, index=False)
        except Exception as e_xl:
            print(f"⚠️ Aviso ao salvar backup Excel de herdeiros: {e_xl}")

def gerar_proximo_id_herdeiro(dados):
    maior_num = 0
    for item in dados:
        item_id = str(item.get("id", ""))
        m = re.search(r'HERD-(\d+)', item_id)
        if m:
            num = int(m.group(1))
            if num > maior_num:
                maior_num = num
    return f"HERD-{maior_num + 1:04d}"

# ----------------------------------------------------------------------
# 2. ESCRITA NO GOOGLE SHEETS
# ----------------------------------------------------------------------
def salvar_no_google_sheets(nome, matricula, cpf, acao, detalhes):
    if not os.path.exists("credentials.json"):
        raise FileNotFoundError("Arquivo 'credentials.json' não encontrado na pasta do projeto.")

    sheet_id = MAPA_IDS_ACOES.get(acao) or PLANILHAS_GOOGLE[0]["id"]
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    sheet = spreadsheet.get_worksheet(0)
    sheet.append_row([nome, matricula, cpf, detalhes])

# ----------------------------------------------------------------------
# 3. LEITURA E PROCESSAMENTO GERAL
# ----------------------------------------------------------------------
def normalizar_cpf(val):
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2].strip()
    if s.upper() in ["NAN", "NONE", "N/I", "-", "NULL", "UNDEFINED", "0", "00", "000", ""]:
        return ""
    apenas_digitos = re.sub(r"\D", "", s)
    if not apenas_digitos or set(apenas_digitos) == {"0"}:
        return ""
    if len(apenas_digitos) <= 11:
        return apenas_digitos.zfill(11)
    return s

def processar_dataframe(df, arquivo_nome, aba_nome, destino_lista=None):
    if df.empty:
        return

    HEADER_KEYWORDS = ['NOME', 'SERVIDOR', 'FUNCIONARIO', 'FUNCIONÁRIO', 'PESSOA', 'FILIADO', 'CPF', 'MATR', 'MTR', 'MAT', 'REGIONAL', 'CIDADE', 'MUNICIPIO', 'MUNICÍPIO', 'NUCLEO', 'NÚCLEO']
    NAME_KEYWORDS = ['NOME', 'SERVIDOR', 'FUNCIONARIO', 'FUNCIONÁRIO', 'PESSOA', 'FILIADO']

    def eh_cabecalho_valido(lista_valores):
        lista_up = [str(v).strip().upper() for v in lista_valores]
        tem_nome = any(any(nk in val for nk in NAME_KEYWORDS) for val in lista_up)
        kw_encontrados = sum(1 for val in lista_up if any(kw in val for kw in HEADER_KEYWORDS))
        return (tem_nome and kw_encontrados >= 1) or (kw_encontrados >= 2)

    if not eh_cabecalho_valido(df.columns):
        max_linhas = min(10, len(df))
        for idx in range(max_linhas):
            linha_valores = list(df.iloc[idx])
            if eh_cabecalho_valido(linha_valores):
                novas_colunas = [str(val).strip() for val in df.iloc[idx]]
                df = df.iloc[idx+1:].copy()
                df.columns = novas_colunas
                break

    colunas_originais = [str(c).strip() for c in df.columns]
    REGIONAL_KEYWORDS = ['REGIONAL', 'CIDADE', 'MUNICIPIO', 'MUNICÍPIO', 'NUCLEO', 'NÚCLEO', 'LOCAL', 'LOCALIDADE', 'LOTACAO', 'LOTAÇÃO', 'SEDE', 'POLO', 'PÓLO']
    MATRICULA_KEYWORDS = ['MATR', 'MTR', 'MATRICULA', 'MATRÍCULA', 'CODIGO', 'CÓDIGO']
    NOME_KEYWORDS = ['NOME', 'SERVIDOR', 'FUNCIONARIO', 'FUNCIONÁRIO', 'PESSOA', 'FILIADO']
    CPF_KEYWORDS = ['CPF']

    TITULOS_E_SEPARADORES = ['NOVAS FILIAÇÕES', 'NOVAS FILIACOES', 'FILIAÇÕES', 'FILIACOES', 'RELAÇÃO', 'RELACAO', 'LISTA DE', 'TOTAL', 'SUBTOTAL', 'DEMONSTRATIVO', 'CADASTROS MANUAIS']
    VALORES_CABECALHO_INVALIDOS = {'NOME', 'NOME DO SERVIDOR', 'SERVIDOR', 'MATRÍCULA', 'MATRICULA', 'CPF', 'REGIONAL', 'CIDADE'}

    for _, linha in df.iterrows():
        matricula, col_mat_idx = "", -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if any(kw in col_upper for kw in MATRICULA_KEYWORDS) or 'MAT' in col_upper:
                val = str(linha.iloc[idx]).strip() if not pd.isna(linha.iloc[idx]) else ''
                if val and val.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL', '0']:
                    matricula = val
                    col_mat_idx = idx
                    break
        if not matricula and len(colunas_originais) > 0:
            val_col1 = str(linha.iloc[0]).strip() if not pd.isna(linha.iloc[0]) else ''
            if val_col1 and val_col1.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                matricula, col_mat_idx = val_col1, 0

        nome, col_nome_idx = "", -1
        for idx, col in enumerate(colunas_originais):
            if any(kw in col.upper() for kw in NOME_KEYWORDS):
                val = str(linha.iloc[idx]).strip().upper() if not pd.isna(linha.iloc[idx]) else ''
                if val and val not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                    nome, col_nome_idx = val, idx
                    break
        if not nome and len(colunas_originais) > 1:
            val_col2 = str(linha.iloc[1]).strip() if not pd.isna(linha.iloc[1]) else ''
            if val_col2 and val_col2.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                nome, col_nome_idx = val_col2.upper(), 1

        cpf, col_cpf_idx = "", -1
        for idx, col in enumerate(colunas_originais):
            if any(kw in col.upper() for kw in CPF_KEYWORDS):
                val = str(linha.iloc[idx]).strip() if not pd.isna(linha.iloc[idx]) else ''
                if val and val.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                    cpf, col_cpf_idx = val, idx
                    break
        if not cpf and len(colunas_originais) > 2:
            val_col3 = str(linha.iloc[2]).strip() if not pd.isna(linha.iloc[2]) else ''
            if val_col3 and val_col3.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                cpf, col_cpf_idx = val_col3, 2

        if cpf.endswith('.0'): cpf = cpf[:-2]
        if matricula.endswith('.0'): matricula = matricula[:-2]

        regional, col_reg_idx = "", -1
        for idx, col in enumerate(colunas_originais):
            if any(kw in col.upper() for kw in REGIONAL_KEYWORDS):
                val_reg = str(linha.iloc[idx]).strip() if not pd.isna(linha.iloc[idx]) else ''
                if val_reg and val_reg.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL', 'UNDEFINED', '0']:
                    regional, col_reg_idx = val_reg.upper(), idx
                    break

        if nome in VALORES_CABECALHO_INVALIDOS or matricula.upper() in VALORES_CABECALHO_INVALIDOS:
            continue

        if any(tit in nome or tit in matricula.upper() for tit in TITULOS_E_SEPARADORES):
            continue

        cpf = normalizar_cpf(cpf)
        detalhes_extras = []
        indices_principais = {col_mat_idx, col_nome_idx, col_cpf_idx, col_reg_idx}
        
        for idx, val in enumerate(linha):
            if idx in indices_principais: continue
            if pd.notna(val):
                valor_str = str(val).strip()
                if valor_str and valor_str.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                    nome_col = colunas_originais[idx]
                    if 'UNNAMED' in nome_col.upper() or not nome_col:
                        detalhes_extras.append(valor_str)
                    else:
                        detalhes_extras.append(f"{nome_col}: {valor_str}")
        
        texto_detalhes = " • ".join(detalhes_extras) if detalhes_extras else "Nenhum detalhe adicional informado."
        alvo = destino_lista if destino_lista is not None else banco_dados
        if (nome and nome != 'NAN') or (cpf and cpf != 'NAN') or (matricula and matricula != 'NAN'):
            alvo.append({
                "arquivo": arquivo_nome,
                "aba": aba_nome,
                "matricula": matricula if matricula != 'NAN' else '',
                "cpf": cpf if cpf != 'NAN' else '',
                "nome": nome if nome != 'NAN' else '',
                "regional": regional,
                "detalhes": texto_detalhes
            })

def carregar_dados():
    global banco_dados, ultima_sincronizacao, sincronizando
    with sync_lock:
        sincronizando = True
        novos_dados = []
        print(f"\n🔄 [{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Sincronizando bases...")
        
        try:
            for item in PLANILHAS_GOOGLE:
                sheet_id, nome_acao = item["id"], item["nome_acao"]
                url_xlsx = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
                try:
                    res = requests.get(url_xlsx, timeout=30)
                    if res.status_code == 200:
                        xls = pd.ExcelFile(io.BytesIO(res.content))
                        for nome_aba in xls.sheet_names:
                            try:
                                df = pd.read_excel(xls, sheet_name=nome_aba)
                                nome_acao_efetivo = nome_acao
                                if nome_acao == "Ação Guilherme Melo COMPLETO":
                                    if "FUNDEF" in nome_aba.upper(): nome_acao_efetivo = "FUNDEF"
                                    elif "FILIA" in nome_aba.upper(): nome_acao_efetivo = "FILIAÇÕES"
                                    elif "GUILHERME" in nome_aba.upper(): nome_acao_efetivo = "Ação Guilherme Melo"
                                processar_dataframe(df, arquivo_nome=nome_acao_efetivo, aba_nome=nome_aba, destino_lista=novos_dados)
                            except Exception as e_aba:
                                print(f"  ⚠️ Erro na aba {nome_aba}: {e_aba}")
                        print(f"  ✅ {nome_acao} sincronizada!")
                except Exception as e:
                    print(f"  ❌ Erro ao conectar com {nome_acao}: {e}")

            if os.path.exists(ARQUIVO_CADASTROS_MANUAIS):
                try:
                    xls_man = pd.ExcelFile(ARQUIVO_CADASTROS_MANUAIS)
                    for nome_aba in xls_man.sheet_names:
                        df_man = pd.read_excel(xls_man, sheet_name=nome_aba)
                        processar_dataframe(df_man, arquivo_nome="Cadastros Manuais (Sistema)", aba_nome=nome_aba, destino_lista=novos_dados)
                except Exception as e:
                    print(f"  ⚠️ Erro cadastros manuais: {e}")

            banco_dados = novos_dados
            ultima_sincronizacao = datetime.now()
            print(f"🟢 Sincronização concluída! {len(banco_dados)} registros ativos.\n")
            return len(banco_dados)
        finally:
            sincronizando = False

def background_sync_worker():
    intervalo_segundos = max(60, SYNC_INTERVAL_MINUTES * 60)
    while True:
        try:
            time.sleep(intervalo_segundos)
            carregar_dados()
        except Exception as e:
            print(f"⚠️ [Auto-Sync] Erro: {e}")
            time.sleep(60)

# ----------------------------------------------------------------------
# 4. ROTAS DA API GERAL
# ----------------------------------------------------------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/api/planilhas")
def listar_planilhas():
    senha = request.headers.get("Authorization") or request.args.get("senha")
    if senha != SENHA_ACESSO:
        return jsonify({"success": False, "error": "Senha incorreta."}), 401

    planilhas = []
    for item in PLANILHAS_GOOGLE:
        planilhas.append({
            "nome": item["nome_acao"],
            "tipo": "Google Sheets",
            "url": f"https://docs.google.com/spreadsheets/d/{item['id']}/edit?usp=drivesdk",
            "local": False
        })
    for arquivo in glob.glob("*.xlsx") + glob.glob("*.xls"):
        planilhas.append({
            "nome": "Cadastros Manuais" if arquivo == ARQUIVO_CADASTROS_MANUAIS else arquivo,
            "tipo": "Arquivo Local Excel",
            "url": f"/planilhas/{arquivo}",
            "local": True
        })
    return jsonify({"success": True, "planilhas": planilhas})

@app.route("/planilhas/<path:filename>")
def baixar_planilha(filename):
    senha = request.args.get("senha")
    if senha != SENHA_ACESSO:
        return "Senha incorreta.", 401
    filename_safe = os.path.basename(filename)
    if os.path.exists(filename_safe):
        return send_from_directory(".", filename_safe, as_attachment=True)
    return "Não encontrada", 404

@app.route("/api/search")
def search():
    query = request.args.get("q", "").strip().upper()
    if not query or len(query) < 2:
        return jsonify({"results": []})
        
    termos = [t.strip() for t in query.split(",") if len(t.strip()) >= 2] if "," in query else [query]
    termos_processados = []
    for t in termos:
        t_limpa = t.replace(".", "").replace("-", "").replace("/", "")
        termos_processados.append({
            "original": t,
            "limpa": t_limpa,
            "eh_numerico": t_limpa.isdigit() or (t_limpa[:-1].isdigit() and t_limpa[-1] in 'XkXK')
        })

    encontrados_diretos = []
    matriculas_validas, nomes_validos, cpfs_validos = set(), set(), set()

    for reg in banco_dados:
        cpf_limpo = reg["cpf"].replace(".", "").replace("-", "").replace("/", "")
        mat_limpa = reg["matricula"].replace(".", "").replace("-", "").replace("/", "").upper()
        nome_reg = reg["nome"].upper()
        
        match = False
        for tp in termos_processados:
            t_num = tp["limpa"]
            if tp["eh_numerico"]:
                if mat_limpa and (mat_limpa == t_num or mat_limpa.lstrip("0") == t_num.lstrip("0") or mat_limpa.startswith(t_num)):
                    match = True
                    break
                if cpf_limpo:
                    if cpf_limpo == t_num or cpf_limpo.startswith(t_num):
                        match = True; break
                    if t_num.isdigit() and cpf_limpo.zfill(11) == t_num.zfill(11):
                        match = True; break
            else:
                if tp["original"] in nome_reg and len(nome_reg) > 0:
                    match = True; break

        if match:
            encontrados_diretos.append(reg)
            if mat_limpa and mat_limpa not in ['NAN', 'NONE', '0', '-']:
                matriculas_validas.add(mat_limpa)
                matriculas_validas.add(mat_limpa.lstrip("0"))
            if cpf_limpo and len(cpf_limpo) >= 8:
                cpfs_validos.add(cpf_limpo.zfill(11))
                cpfs_validos.add(cpf_limpo.lstrip("0"))
            if nome_reg and len(nome_reg) >= 5:
                nomes_validos.add(nome_reg)

    if not encontrados_diretos:
        return jsonify({"results": []})

    resultados_finais = list(encontrados_diretos)
    chaves_ja_incluidas = set((r["arquivo"], r["aba"], r["nome"], r["matricula"]) for r in resultados_finais)

    for reg in banco_dados:
        chave_reg = (reg["arquivo"], reg["aba"], reg["nome"], reg["matricula"])
        if chave_reg in chaves_ja_incluidas: continue
        mat_r = reg["matricula"].replace(".", "").replace("-", "").replace("/", "").upper()
        cpf_r = reg["cpf"].replace(".", "").replace("-", "").replace("/", "")
        nome_r = reg["nome"].upper()
        
        if (mat_r and (mat_r in matriculas_validas or mat_r.lstrip("0") in matriculas_validas)) or \
           (cpf_r and (cpf_r in cpfs_validos or cpf_r.zfill(11) in cpfs_validos or cpf_r.lstrip("0") in cpfs_validos)) or \
           (nome_r and nome_r in nomes_validos):
            resultados_finais.append(reg)
            chaves_ja_incluidas.add(chave_reg)

    # Anexa dados de herdeiros se houver
    try:
        herdeiros_lista = carregar_herdeiros()
        if herdeiros_lista:
            mapa_falecidos = {}
            for h in herdeiros_lista:
                f = h.get("falecido", {})
                h_cpf = str(f.get("cpf", "")).replace(".", "").replace("-", "").replace("/", "").strip()
                h_mat = str(f.get("matricula", "")).replace(".", "").replace("-", "").replace("/", "").strip().upper()
                h_nome = str(f.get("nome", "")).strip().upper()
                info = {
                    "id": h.get("id"),
                    "status": h.get("status"),
                    "status_label": STATUS_HERDEIROS_MAP.get(h.get("status"), h.get("status")),
                    "caixa": h.get("caixa_concluido", ""),
                    "data_cadastro": h.get("data_cadastro", "")
                }
                if h_cpf: mapa_falecidos[f"CPF_{h_cpf.zfill(11)}"] = info; mapa_falecidos[f"CPF_{h_cpf.lstrip('0')}"] = info
                if h_mat: mapa_falecidos[f"MAT_{h_mat}"] = info; mapa_falecidos[f"MAT_{h_mat.lstrip('0')}"] = info
                if h_nome: mapa_falecidos[f"NOME_{h_nome}"] = info

            for r in resultados_finais:
                r_cpf = str(r.get("cpf", "")).replace(".", "").replace("-", "").replace("/", "").strip()
                r_mat = str(r.get("matricula", "")).replace(".", "").replace("-", "").replace("/", "").strip().upper()
                r_nome = str(r.get("nome", "")).strip().upper()
                h_info = mapa_falecidos.get(f"CPF_{r_cpf.zfill(11)}") or mapa_falecidos.get(f"MAT_{r_mat}") or mapa_falecidos.get(f"NOME_{r_nome}")
                if h_info: r["herdeiro_info"] = h_info
    except Exception as e:
        print(f"⚠️ Erro ao cruzar herdeiros com busca: {e}")

    return jsonify({"results": resultados_finais})

@app.route("/api/status")
def status():
    return jsonify({
        "success": True,
        "total_registros": len(banco_dados),
        "ultima_sincronizacao": ultima_sincronizacao.strftime("%d/%m/%Y às %H:%M:%S") if ultima_sincronizacao else None,
        "intervalo_minutos": SYNC_INTERVAL_MINUTES,
        "sincronizando": sincronizando
    })

@app.route("/api/sync")
def sync():
    try:
        total = carregar_dados()
        return jsonify({"success": True, "total_records": total})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/regionais")
def listar_regionais():
    regionais = sorted(list(set(
        reg["regional"].strip().upper() 
        for reg in banco_dados 
        if reg.get("regional") and reg["regional"].strip().upper() not in ['NAN', '', '-', 'NONE', 'N/I']
    )))
    return jsonify({"success": True, "regionais": regionais})

@app.route("/api/regional/stats")
def regional_stats():
    regional_query = request.args.get("q", "").strip().upper()
    if not regional_query:
        return jsonify({"success": False, "error": "Informe a regional."}), 400
    pessoas = [r for r in banco_dados if r.get("regional", "").strip().upper() == regional_query]
    total_por_acao = {}
    for r in pessoas:
        total_por_acao[r["arquivo"]] = total_por_acao.get(r["arquivo"], 0) + 1
    return jsonify({
        "success": True,
        "regional": regional_query,
        "total": len(pessoas),
        "por_acao": total_por_acao,
        "pessoas": pessoas
    })

@app.route("/api/stats/guilherme-fundef")
def stats_guilherme_fundef():
    regional_filtro = request.args.get("regional", "").strip().upper()
    mats_gm, mats_fu = {}, {}

    for reg in banco_dados:
        if regional_filtro and reg.get("regional", "").strip().upper() != regional_filtro:
            continue
        mat = reg.get("matricula", "").replace(".", "").replace("-", "").replace("/", "").strip().upper()
        cpf = normalizar_cpf(reg.get("cpf", ""))
        nome = reg.get("nome", "").strip().upper()
        chave = mat if mat and mat not in ["NAN", "0"] else (f"CPF:{cpf}" if cpf else f"NOME:{nome}")
        if not chave: continue

        if reg.get("arquivo") == "Ação Guilherme Melo": mats_gm[chave] = reg
        elif reg.get("arquivo") == "FUNDEF": mats_fu[chave] = reg

    set_gm, set_fu = set(mats_gm.keys()), set(mats_fu.keys())
    return jsonify({
        "success": True,
        "regional": regional_filtro or None,
        "total_guilherme_melo": len(set_gm),
        "total_fundef": len(set_fu),
        "total_em_ambos": len(set_gm & set_fu),
        "total_unico_conjunto": len(set_gm | set_fu),
        "so_guilherme_melo": len(set_gm - set_fu),
        "so_fundef": len(set_fu - set_gm)
    })

# ----------------------------------------------------------------------
# 5. GESTÃO DE HERDEIROS (COM MÚLTIPLOS PROCESSOS E AUTO-IMPORTAÇÃO)
# ----------------------------------------------------------------------

def executar_importacao_planilhas_herdeiros():
    """Importa e cruza dados das planilhas Google de herdeiros."""
    import csv
    from io import StringIO

    def gerar_chave(nome, matricula, cpf):
        mat = re.sub(r"[^\w]", "", str(matricula or "")).lstrip("0").upper()
        cpf_d = re.sub(r"\D", "", str(cpf or "")).lstrip("0")
        nome_n = re.sub(r"\s+", " ", str(nome or "").strip().upper())
        if mat and mat not in ["", "NAN", "NONE", "0"]: return f"MAT:{mat}"
        if cpf_d and len(cpf_d) >= 8: return f"CPF:{cpf_d}"
        if nome_n and nome_n not in ["", "NAN", "NONE"]: return f"NOME:{nome_n}"
        return None

    def mapear_status_andamento(andamento):
        a = (andamento or "").strip().upper()
        if "AGUARD" in a: return "enviado_assinatura"
        if "ASSIN" in a or "ASSSIN" in a or "CONCLU" in a: return "concluido"
        if "PRODU" in a or "MINUTA" in a: return "em_producao"
        if a in ["", "NAN", "NONE", "-"]: return "fila_espera"
        return "em_producao"

    def extrair_contato(contato_txt):
        email, telefone = "", ""
        if not contato_txt: return email, telefone
        m_email = re.search(r"[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}", contato_txt)
        if m_email: email = m_email.group(0)
        m_tel = re.search(r"\(?\d{2,3}\)?[\s.\-]?\d{4,5}[\s.\-]?\d{4}", contato_txt)
        if m_tel: telefone = m_tel.group(0).strip()
        return email, telefone

    agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dados_existentes = carregar_herdeiros()
    indice_chaves = {}

    for idx, item in enumerate(dados_existentes):
        fal = item.get("falecido", {})
        chave = gerar_chave(fal.get("nome"), fal.get("matricula"), fal.get("cpf"))
        if chave: indice_chaves[chave] = idx

    novos, atualizados, erros = 0, 0, []

    # 1. ABA HERDEIROS GUILHERME MELO (gid=1430431385)
    URL_GM = "https://docs.google.com/spreadsheets/d/1-3xLtKtDB4VdSIC9C-HAyTdCZ_aQOPNkQcy9fvMG9-c/export?format=csv&gid=1430431385"
    try:
        res_gm = requests.get(URL_GM, timeout=25)
        res_gm.encoding = "utf-8"
        if res_gm.status_code == 200:
            reader_gm = csv.DictReader(StringIO(res_gm.text))
            for row in reader_gm:
                row_upper = {k.strip().upper(): (v or "").strip() for k, v in row.items()}
                nome = row_upper.get("NOME", "").upper()
                if not nome or nome in ["NAN", "NONE", "", "NOME"]: continue

                matricula = str(row_upper.get("MATRÍCULA") or row_upper.get("MATRICULA") or "").strip().rstrip(".0")
                cpf = normalizar_cpf(row_upper.get("CPF", ""))
                herdeiros_txt = row_upper.get("HERDEIROS", "")
                contato_txt = row_upper.get("CONTATO", "")
                data_ing = row_upper.get("DATA DE ING") or row_upper.get("DATA DE INGRESSO") or ""
                docs_prod = row_upper.get("DOCS PRODUZIDOS", "")
                andamento = row_upper.get("ANDAMENTO", "")
                data_entrega = row_upper.get("DATA ENTREGA", "")

                status = mapear_status_andamento(andamento)
                chave = gerar_chave(nome, matricula, cpf)

                herd_list = []
                if herdeiros_txt:
                    for i, p in enumerate(re.split(r"[;/\n]+", herdeiros_txt)):
                        p = p.strip().upper()
                        if p and p not in ["NAN", "NONE"]:
                            email_h, tel_h = extrair_contato(contato_txt) if i == 0 else ("", "")
                            herd_list.append({
                                "id": i + 1, "nome": p, "parentesco": "Herdeiro(a)",
                                "cpf": "", "telefone": tel_h, "email": email_h, "is_principal": i == 0
                            })

                obs = f"Andamento: {andamento}. Docs: {docs_prod}. Entrega: {data_entrega}.".strip(". ")

                if chave and chave in indice_chaves:
                    idx_exist = indice_chaves[chave]
                    caso = dados_existentes[idx_exist]
                    if caso.get("origem") == "planilha_gm": caso["status"] = status
                    if herd_list and not caso.get("herdeiros"): caso["herdeiros"] = herd_list
                    if "Ação Guilherme Melo" not in caso.get("processos", []):
                        caso.setdefault("processos", []).append("Ação Guilherme Melo")
                    atualizados += 1
                else:
                    novo_id = gerar_proximo_id_herdeiro(dados_existentes)
                    novo_caso = {
                        "id": novo_id, "data_cadastro": data_ing or agora_iso, "ultima_atualizacao": agora_iso,
                        "status": status, "origem": "planilha_gm", "processos": ["Ação Guilherme Melo"],
                        "falecido": {
                            "nome": nome, "cpf": cpf, "matricula": matricula,
                            "regional": "", "acao_juridica": "Ação Guilherme Melo", "data_obito": ""
                        },
                        "herdeiros": herd_list,
                        "documentos_checklist": {
                            "certidao_obito": False, "rg_cpf_falecido": False, "rg_cpf_herdeiros": False,
                            "comprovante_residencia": False,
                            "certidao_casamento_nascimento": False, "procuracao": bool(docs_prod), "outros": docs_prod
                        },
                        "localizacao_provisoria": "Recepção / Entrada Jurídico",
                        "caixa_concluido": "Caixa GM Herdeiros" if status == "concluido" else "",
                        "observacoes": obs,
                        "historico": [{
                            "data": agora_iso, "acao": "Importação Automática (Guilherme Melo)",
                            "usuario": "Sistema", "detalhes": f"Importado da planilha GM. Andamento: {andamento}"
                        }],
                        "notificacoes": [], "anexos": []
                    }
                    dados_existentes.append(novo_caso)
                    if chave: indice_chaves[chave] = len(dados_existentes) - 1
                    novos += 1
    except Exception as e:
        erros.append(f"Aba Herdeiros GM: {e}")

    # 2. PLANILHA DE CONCLUÍDOS (1eF_...)
    URL_CONC = "https://docs.google.com/spreadsheets/d/1eF_NFwNhbR7PeJJmQXLK27z69O3cqhXq/export?format=xlsx"
    try:
        res_conc = requests.get(URL_CONC, timeout=30)
        if res_conc.status_code == 200:
            xls_conc = pd.ExcelFile(io.BytesIO(res_conc.content))
            for nome_aba in xls_conc.sheet_names:
                try:
                    df_c = pd.read_excel(xls_conc, sheet_name=nome_aba, dtype=str)
                    df_c.columns = [str(c).strip().upper() for c in df_c.columns]

                    for _, row in df_c.iterrows():
                        nome = ""
                        for col in df_c.columns:
                            if "NOME" in col:
                                v = str(row.get(col, "")).strip().upper()
                                if v and v not in ["NAN", "NONE", "", "NOME"]:
                                    nome = v; break
                        if not nome: continue

                        matricula = ""
                        if len(df_c.columns) > 0 and "NOME" not in df_c.columns[0]:
                            v_m = str(row.get(df_c.columns[0], "")).strip()
                            if v_m and v_m.upper() not in ["NAN", "NONE"]: matricula = v_m.rstrip(".0")

                        cpf, caixa = "", ""
                        for col in df_c.columns:
                            if "CPF" in col: cpf = normalizar_cpf(row.get(col, ""))
                            if "CAIXA" in col or "BOX" in col: caixa = str(row.get(col, "")).strip().upper()

                        chave = gerar_chave(nome, matricula, cpf)
                        caixa_final = caixa or f"Caixa Concluídos - {nome_aba}"

                        if chave and chave in indice_chaves:
                            idx_exist = indice_chaves[chave]
                            caso = dados_existentes[idx_exist]
                            caso["status"] = "concluido"
                            if caixa_final: caso["caixa_concluido"] = caixa_final
                            if "SEGUNDA AÇÃO" not in caso.get("processos", []):
                                caso.setdefault("processos", []).append("SEGUNDA AÇÃO")
                            atualizados += 1
                        else:
                            novo_id = gerar_proximo_id_herdeiro(dados_existentes)
                            novo_caso = {
                                "id": novo_id, "data_cadastro": agora_iso, "ultima_atualizacao": agora_iso,
                                "status": "concluido", "origem": "planilha_concluidos", "processos": ["SEGUNDA AÇÃO"],
                                "falecido": {
                                    "nome": nome, "cpf": cpf, "matricula": matricula,
                                    "regional": "", "acao_juridica": "SEGUNDA AÇÃO", "data_obito": ""
                                },
                                "herdeiros": [],
                                "documentos_checklist": {
                                    "certidao_obito": True, "rg_cpf_falecido": True, "rg_cpf_herdeiros": True,
                                    "comprovante_residencia": True, "declaracao_dependentes": False,
                                    "certidao_casamento_nascimento": False, "procuracao": True, "outros": ""
                                },
                                "localizacao_provisoria": "", "caixa_concluido": caixa_final,
                                "observacoes": f"Importado como Concluído ({nome_aba}).",
                                "historico": [{
                                    "data": agora_iso, "acao": f"Importação ({nome_aba})",
                                    "usuario": "Sistema", "detalhes": f"Importado da planilha de concluídos ({nome_aba})."
                                }],
                                "notificacoes": [], "anexos": []
                            }
                            dados_existentes.append(novo_caso)
                            if chave: indice_chaves[chave] = len(dados_existentes) - 1
                            novos += 1
                except Exception as e_aba:
                    erros.append(f"Aba {nome_aba}: {e_aba}")
    except Exception as e:
        erros.append(f"Planilha Concluídos: {e}")

    salvar_herdeiros(dados_existentes)
    return novos, atualizados, len(dados_existentes), erros

@app.route("/api/herdeiros/importar-planilhas", methods=["POST"])
def api_importar_herdeiros_planilhas():
    try:
        novos, atualizados, total, erros = executar_importacao_planilhas_herdeiros()
        return jsonify({
            "success": True,
            "novos": novos,
            "atualizados": atualizados,
            "total": total,
            "erros": erros,
            "mensagem": f"{novos} novos processos adicionados, {atualizados} atualizados."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros", methods=["GET"])
def api_listar_herdeiros():
    try:
        dados = carregar_herdeiros()
        q = request.args.get("q", "").strip().upper()
        status_filtro = request.args.get("status", "").strip().lower()
        caixa_filtro = request.args.get("caixa", "").strip().upper()
        acao_filtro = request.args.get("acao", "").strip().upper()
        
        filtrados = []
        for caso in dados:
            if status_filtro and caso.get("status", "").lower() != status_filtro:
                continue
            if caixa_filtro and caixa_filtro != "TODAS":
                if caixa_filtro not in str(caso.get("caixa_concluido", "")).strip().upper():
                    continue
            if acao_filtro and acao_filtro != "TODAS":
                processos_caso = [p.upper() for p in caso.get("processos", [])]
                acao_primaria = caso.get("falecido", {}).get("acao_juridica", "").upper()
                if acao_filtro not in processos_caso and acao_filtro not in acao_primaria:
                    continue
            if q:
                fal = caso.get("falecido", {})
                texto = f"{caso.get('id', '')} {fal.get('nome', '')} {fal.get('cpf', '')} {fal.get('matricula', '')} {caso.get('caixa_concluido', '')}".upper()
                for h in caso.get("herdeiros", []):
                    texto += f" {h.get('nome', '')} {h.get('cpf', '')} {h.get('telefone', '')}".upper()
                q_limpa = q.replace(".", "").replace("-", "").replace("/", "")
                if q not in texto and (not q_limpa or q_limpa not in texto.replace(".", "").replace("-", "").replace("/", "")):
                    continue
            filtrados.append(caso)
            
        filtrados.sort(key=lambda x: x.get("ultima_atualizacao") or x.get("data_cadastro") or "", reverse=True)
        return jsonify({"success": True, "total": len(filtrados), "herdeiros": filtrados})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros", methods=["POST"])
def api_criar_herdeiro():
    try:
        payload = request.get_json(force=True) or {}
        falecido = payload.get("falecido", {})
        nome_falecido = falecido.get("nome", "").strip().upper()
        if not nome_falecido:
            return jsonify({"success": False, "error": "Informe o nome do titular falecido."}), 400
            
        # Suporte a múltiplos processos
        processos = payload.get("processos") or []
        if not processos and falecido.get("acao_juridica"):
            processos = [falecido.get("acao_juridica")]
        if not processos:
            processos = ["Ação Guilherme Melo"]

        acao_juridica_primaria = processos[0] if processos else "Ação Guilherme Melo"
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dados = carregar_herdeiros()
        novo_id = gerar_proximo_id_herdeiro(dados)

        novo_caso = {
            "id": novo_id,
            "data_cadastro": agora_iso,
            "ultima_atualizacao": agora_iso,
            "status": payload.get("status", "fila_espera").strip().lower(),
            "origem": "manual",
            "processos": processos,
            "falecido": {
                "nome": nome_falecido,
                "cpf": normalizar_cpf(falecido.get("cpf", "")),
                "matricula": str(falecido.get("matricula", "")).strip(),
                "regional": falecido.get("regional", "").strip().upper(),
                "acao_juridica": acao_juridica_primaria,
                "data_obito": falecido.get("data_obito", "").strip()
            },
            "herdeiros": payload.get("herdeiros", []),
            "documentos_checklist": payload.get("documentos_checklist", {}),
            "localizacao_provisoria": payload.get("localizacao_provisoria", "Recepção / Entrada Jurídico").strip(),
            "caixa_concluido": payload.get("caixa_concluido", "").strip().upper(),
            "observacoes": payload.get("observacoes", "").strip(),
            "historico": [{
                "data": agora_iso, "acao": "Recepção e Cadastro Manual",
                "usuario": "Atendimento Jurídico",
                "detalhes": f"Processo registrado com {len(processos)} processo(s) vinculado(s)."
            }],
            "notificacoes": [], "anexos": []
        }
        
        dados.append(novo_caso)
        salvar_herdeiros(dados)
        return jsonify({"success": True, "id": novo_id, "caso": novo_caso})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros/<id>", methods=["GET"])
def api_obter_herdeiro(id):
    try:
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        for c in dados:
            if c.get("id", "").upper() == id_upper:
                return jsonify({"success": True, "caso": c})
        return jsonify({"success": False, "error": "Não encontrado."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros/<id>", methods=["PUT"])
def api_atualizar_herdeiro(id):
    try:
        payload = request.get_json(force=True) or {}
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        caso = next((c for c in dados if c.get("id", "").upper() == id_upper), None)
        if not caso:
            return jsonify({"success": False, "error": "Não encontrado."}), 404

        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "processos" in payload:
            caso["processos"] = payload["processos"]
        if "falecido" in payload:
            fal = payload["falecido"]
            for k in ["nome", "cpf", "matricula", "regional", "acao_juridica", "data_obito"]:
                if k in fal: caso["falecido"][k] = fal[k]
        if "herdeiros" in payload:
            caso["herdeiros"] = payload["herdeiros"]
        if "documentos_checklist" in payload:
            caso["documentos_checklist"] = payload["documentos_checklist"]
        if "localizacao_provisoria" in payload:
            caso["localizacao_provisoria"] = payload["localizacao_provisoria"]
        if "caixa_concluido" in payload:
            caso["caixa_concluido"] = payload["caixa_concluido"]
        if "observacoes" in payload:
            caso["observacoes"] = payload["observacoes"]

        caso["ultima_atualizacao"] = agora_iso
        caso.setdefault("historico", []).append({
            "data": agora_iso, "acao": "Atualização Cadastral",
            "usuario": "Jurídico", "detalhes": "Dados atualizados pelo operador."
        })
        salvar_herdeiros(dados)
        return jsonify({"success": True, "caso": caso})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros/<id>/mover-status", methods=["POST"])
def api_mover_status_herdeiro(id):
    try:
        payload = request.get_json(force=True) or {}
        novo_status = payload.get("novo_status", "").strip().lower()
        if novo_status not in STATUS_HERDEIROS_MAP:
            return jsonify({"success": False, "error": "Status inválido."}), 400

        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        caso = next((c for c in dados if c.get("id", "").upper() == id_upper), None)
        if not caso:
            return jsonify({"success": False, "error": "Não encontrado."}), 404

        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_ant = caso.get("status", "fila_espera")
        caso["status"] = novo_status
        caso["ultima_atualizacao"] = agora_iso
        
        caixa = payload.get("caixa_concluido", "").strip().upper()
        if caixa: caso["caixa_concluido"] = caixa

        caso.setdefault("historico", []).append({
            "data": agora_iso, "acao": f"Transição: {STATUS_HERDEIROS_MAP.get(novo_status)}",
            "usuario": "Equipe Jurídica", "detalhes": f"De {status_ant} para {novo_status}. {caixa}"
        })
        salvar_herdeiros(dados)
        return jsonify({"success": True, "caso": caso})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros/<id>/notificar", methods=["POST"])
def api_notificar_herdeiro(id):
    try:
        payload = request.get_json(force=True) or {}
        dados = carregar_herdeiros()
        caso = next((c for c in dados if c.get("id", "").upper() == id.strip().upper()), None)
        if not caso: return jsonify({"success": False, "error": "Não encontrado."}), 404

        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notif = {
            "data": agora_iso, "canal": payload.get("canal", "whatsapp"),
            "destinatario": payload.get("destinatario", ""), "texto": payload.get("texto", "")
        }
        caso.setdefault("notificacoes", []).append(notif)
        salvar_herdeiros(dados)
        return jsonify({"success": True, "notificacao": notif, "caso": caso})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros/<id>/anexos", methods=["POST"])
def api_upload_anexo_herdeiro(id):
    try:
        if "file" not in request.files or not request.files["file"].filename:
            return jsonify({"success": False, "error": "Arquivo inválido."}), 400
        file = request.files["file"]
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        caso = next((c for c in dados if c.get("id", "").upper() == id_upper), None)
        if not caso: return jsonify({"success": False, "error": "Não encontrado."}), 404

        pasta_caso = os.path.join(DIR_UPLOADS_HERDEIROS, id_upper)
        os.makedirs(pasta_caso, exist_ok=True)
        safe_name = secure_filename(file.filename) or f"doc_{int(time.time())}"
        filename_final = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
        destino = os.path.join(pasta_caso, filename_final)
        file.save(destino)

        novo_anexo = {
            "filename": filename_final, "original_name": file.filename,
            "tipo": request.form.get("tipo", "Documento Digitalizado"),
            "data_upload": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": f"/api/herdeiros/anexos/{id_upper}/{filename_final}"
        }
        caso.setdefault("anexos", []).append(novo_anexo)
        salvar_herdeiros(dados)
        return jsonify({"success": True, "anexo": novo_anexo, "caso": caso})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros/anexos/<id>/<path:filename>")
def api_download_anexo_herdeiro(id, filename):
    return send_from_directory(os.path.join(DIR_UPLOADS_HERDEIROS, id.strip().upper()), os.path.basename(filename))

@app.route("/api/herdeiros/<id>", methods=["DELETE"])
def api_deletar_herdeiro(id):
    try:
        dados = carregar_herdeiros()
        novos = [c for c in dados if c.get("id", "").upper() != id.strip().upper()]
        salvar_herdeiros(novos)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/herdeiros/caixas")
def api_caixas_herdeiros():
    dados = carregar_herdeiros()
    caixas_map = {}
    for c in dados:
        cx = str(c.get("caixa_concluido", "")).strip().upper() or ("CAIXA GERAL" if c.get("status") == "concluido" else "")
        if not cx: continue
        if cx not in caixas_map:
            caixas_map[cx] = {"nome": cx, "total": 0, "casos": []}
        caixas_map[cx]["total"] += 1
        fal = c.get("falecido", {})
        caixas_map[cx]["casos"].append({
            "id": c.get("id"), "falecido_nome": fal.get("nome"),
            "cpf": fal.get("cpf"), "matricula": fal.get("matricula"),
            "acao": " / ".join(c.get("processos", [])) or fal.get("acao_juridica", ""),
            "status": c.get("status")
        })
    return jsonify({"success": True, "caixas": sorted(list(caixas_map.values()), key=lambda x: x["nome"])})

@app.route("/api/herdeiros/stats")
def api_stats_herdeiros():
    dados = carregar_herdeiros()
    stats = {"fila_espera": 0, "em_producao": 0, "enviado_assinatura": 0, "concluido": 0, "total": len(dados)}
    for c in dados:
        st = c.get("status", "fila_espera").lower()
        stats[st] = stats.get(st, 0) + 1
    return jsonify({"success": True, "stats": stats})

@app.route("/api/herdeiros/exportar")
def api_exportar_herdeiros():
    try:
        dados = carregar_herdeiros()
        linhas = []
        for item in dados:
            fal = item.get("falecido", {})
            herds = item.get("herdeiros", [])
            linhas.append({
                "ID": item.get("id"),
                "STATUS": STATUS_HERDEIROS_MAP.get(item.get("status"), item.get("status")),
                "FALECIDO": fal.get("nome"),
                "CPF": fal.get("cpf"),
                "MATRÍCULA": fal.get("matricula"),
                "PROCESSOS": " / ".join(item.get("processos", [])) or fal.get("acao_juridica", ""),
                "HERDEIROS": ", ".join(h.get("nome", "") for h in herds),
                "CAIXA": item.get("caixa_concluido"),
                "LOCAL PROVISÓRIO": item.get("localizacao_provisoria")
            })
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(linhas).to_excel(writer, index=False)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"herdeiros_{datetime.now().strftime('%Y%m%d')}.xlsx")
    except Exception as e:
        return str(e), 500

# ----------------------------------------------------------------------
# 6. INICIALIZAÇÃO DOS DADOS (AUTO-IMPORTAÇÃO CASO BANCO VAZIO)
# ----------------------------------------------------------------------
if not os.environ.get("TESTING"):
    carregar_dados()
    
    # Auto-importa as planilhas de herdeiros se o banco ainda estiver zerado
    if not os.path.exists(ARQUIVO_HERDEIROS) or len(carregar_herdeiros()) == 0:
        print("📥 Base de herdeiros vazia. Iniciando primeira importação automática...")
        threading.Thread(target=executar_importacao_planilhas_herdeiros, daemon=True).start()

    sync_thread = threading.Thread(target=background_sync_worker, daemon=True)
    sync_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 Servidor do SINTE-PI no ar na porta {port}!")
    app.run(host="0.0.0.0", port=port, debug=False)