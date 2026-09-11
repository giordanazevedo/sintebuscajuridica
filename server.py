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
    """Lê atomicamente a lista de processos de herdeiros do arquivo JSON persistente."""
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
    """Salva com segurança atômica e atualiza planilha Excel de backup."""
    with herdeiros_lock:
        # Gravação atômica em arquivo temporário
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

        # Exportação / Backup em Excel
        try:
            linhas_excel = []
            for item in dados:
                fal = item.get("falecido", {})
                herds = item.get("herdeiros", [])
                nomes_herdeiros = ", ".join(h.get("nome", "") for h in herds if h.get("nome"))
                contatos_herdeiros = ", ".join(f"{h.get('nome')}: {h.get('telefone') or h.get('email') or 'S/C'}" for h in herds if h.get("nome"))
                linhas_excel.append({
                    "ID": item.get("id"),
                    "STATUS": STATUS_HERDEIROS_MAP.get(item.get("status"), item.get("status")),
                    "FALECIDO": fal.get("nome"),
                    "CPF FALECIDO": fal.get("cpf"),
                    "MATRÍCULA": fal.get("matricula"),
                    "REGIONAL": fal.get("regional"),
                    "AÇÃO": fal.get("acao_juridica"),
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
    """Gera o próximo ID sequencial HERD-XXXX."""
    maior_num = 0
    for item in dados:
        item_id = str(item.get("id", ""))
        m = re.search(r'HERD-(\d+)', item_id)
        if m:
            num = int(m.group(1))
            if num > maior_num:
                maior_num = num
    novo_num = maior_num + 1
    return f"HERD-{novo_num:04d}"

# ----------------------------------------------------------------------
# 2. ESCRITA NA PLANILHA CORRESPONDENTE VIA CREDENTIALS.JSON
# ----------------------------------------------------------------------
def salvar_no_google_sheets(nome, matricula, cpf, acao, detalhes):
    """Identifica a planilha da ação e insere na primeira linha em branco da primeira aba."""
    if not os.path.exists("credentials.json"):
        raise FileNotFoundError("Arquivo 'credentials.json' não encontrado na pasta do projeto.")

    sheet_id = MAPA_IDS_ACOES.get(acao)
    if not sheet_id:
        sheet_id = PLANILHAS_GOOGLE[0]["id"]

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    
    # Abre a planilha pelo ID
    spreadsheet = client.open_by_key(sheet_id)
    
    # Seleciona a primeira aba/guia da planilha (independente do nome dela)
    sheet = spreadsheet.get_worksheet(0)
    
    # Adiciona a nova linha na próxima posição disponível
    nova_linha = [nome, matricula, cpf, detalhes]
    sheet.append_row(nova_linha)


# ----------------------------------------------------------------------
# 3. LEITURA E SINCRONIZAÇÃO DAS BASES (THREAD-SAFE / ATOMIC SWAP)
# ----------------------------------------------------------------------
def carregar_dados():
    global banco_dados, ultima_sincronizacao, sincronizando
    with sync_lock:
        sincronizando = True
        novos_dados = []
        hora_inicio = datetime.now()
        print(f"\n🔄 [{hora_inicio.strftime('%d/%m/%Y %H:%M:%S')}] Sincronizando planilhas do Google Drive e Cadastros Manuais...")
        
        try:
            # 1. Planilhas do Google Drive (processando todas as abas)
            for item in PLANILHAS_GOOGLE:
                sheet_id = item["id"]
                nome_acao = item["nome_acao"]
                url_xlsx = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
                
                try:
                    res = requests.get(url_xlsx, timeout=30)
                    if res.status_code == 200:
                        xls = pd.ExcelFile(io.BytesIO(res.content))
                        for nome_aba in xls.sheet_names:
                            try:
                                df = pd.read_excel(xls, sheet_name=nome_aba)
                                nome_acao_efetivo = nome_acao
                                
                                # Separação especial da planilha Guilherme Melo / FUNDEF
                                if nome_acao == "Ação Guilherme Melo COMPLETO":
                                    if "FUNDEF" in nome_aba.upper():
                                        nome_acao_efetivo = "FUNDEF"
                                    elif "FILIA" in nome_aba.upper():
                                        nome_acao_efetivo = "FILIAÇÕES"
                                    elif "GUILHERME" in nome_aba.upper():
                                        nome_acao_efetivo = "Ação Guilherme Melo"

                                processar_dataframe(df, arquivo_nome=nome_acao_efetivo, aba_nome=nome_aba, destino_lista=novos_dados)
                            except Exception as e_aba:
                                print(f"  ⚠️ Erro ao processar aba '{nome_aba}' de {nome_acao}: {e_aba}")
                        print(f"  ✅ {nome_acao} sincronizada!")
                    else:
                        print(f"  ⚠️ HTTP {res.status_code} ao baixar {nome_acao}")
                except Exception as e:
                    print(f"  ❌ Erro ao conectar com {nome_acao}: {e}")

            # 2. Cadastros Manuais (processando todas as abas)
            if os.path.exists(ARQUIVO_CADASTROS_MANUAIS):
                try:
                    xls_man = pd.ExcelFile(ARQUIVO_CADASTROS_MANUAIS)
                    for nome_aba in xls_man.sheet_names:
                        try:
                            df_man = pd.read_excel(xls_man, sheet_name=nome_aba)
                            processar_dataframe(df_man, arquivo_nome="Cadastros Manuais (Sistema)", aba_nome=nome_aba, destino_lista=novos_dados)
                        except Exception as e_aba:
                            print(f"  ⚠️ Erro ao processar aba '{nome_aba}' em {ARQUIVO_CADASTROS_MANUAIS}: {e_aba}")
                    print(f"  ✅ {ARQUIVO_CADASTROS_MANUAIS} carregado!")
                except Exception as e:
                    print(f"  ⚠️ Erro ao ler cadastros manuais: {e}")

            # 3. Demais arquivos Excel locais (processando todas as abas)
            arquivos_locais = sorted(list(set(glob.glob("*.xlsx") + glob.glob("*.xls") + glob.glob("*.XLSX") + glob.glob("*.XLS"))))
            for arquivo in arquivos_locais:
                if os.path.basename(arquivo) == ARQUIVO_CADASTROS_MANUAIS:
                    continue
                try:
                    xls = pd.ExcelFile(arquivo)
                    for nome_aba in xls.sheet_names:
                        try:
                            df = pd.read_excel(xls, sheet_name=nome_aba)
                            processar_dataframe(df, arquivo_nome=f"Local: {arquivo}", aba_nome=nome_aba, destino_lista=novos_dados)
                        except Exception as e_aba:
                            print(f"  ⚠️ Erro ao processar aba '{nome_aba}' de {arquivo}: {e_aba}")
                except Exception as e:
                    print(f"Erro ao ler arquivo local {arquivo}: {e}")
                    
            # Substituição atômica na memória: buscas nunca sofrem com banco vazio
            banco_dados = novos_dados
            ultima_sincronizacao = datetime.now()
            print(f"\n🟢 Sincronização concluída! Total de {len(banco_dados)} registros ativos.\n")
            return len(banco_dados)
        finally:
            sincronizando = False


def background_sync_worker():
    """Thread em segundo plano que executa a sincronização automática em intervalos regulares."""
    intervalo_segundos = max(60, SYNC_INTERVAL_MINUTES * 60)
    print(f"⏱️ Sincronização automática em segundo plano ativada (a cada {SYNC_INTERVAL_MINUTES} minutos).")
    while True:
        try:
            time.sleep(intervalo_segundos)
            print(f"\n⏰ [Auto-Sync] Iniciando atualização periódica automática dos dados...")
            carregar_dados()
        except Exception as e:
            print(f"⚠️ [Auto-Sync] Erro na sincronização automática: {e}")
            time.sleep(60)


def normalizar_cpf(val):
    """
    Normaliza CPF para exatamente 11 dígitos se for numérico.
    Preenche zeros à esquerda caso o Excel/planilha tenha removido (ex: 3567931334 vira 03567931334).
    Descarta valores inválidos como '0', '0.0', 'NAN', etc.
    """
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2].strip()
    s_upper = s.upper()
    if s_upper in ["NAN", "NONE", "N/I", "-", "NULL", "UNDEFINED", "0", "00", "000", ""]:
        return ""
    
    apenas_digitos = re.sub(r"\D", "", s)
    if not apenas_digitos or set(apenas_digitos) == {"0"}:
        return ""
    
    # Se tiver até 11 dígitos, completa com zeros à esquerda (padrão CPF brasileiro)
    if len(apenas_digitos) <= 11:
        return apenas_digitos.zfill(11)
        
    return s


def processar_dataframe(df, arquivo_nome, aba_nome, destino_lista=None):
    if df.empty:
        return

    HEADER_KEYWORDS = ['NOME', 'SERVIDOR', 'FUNCIONARIO', 'FUNCIONÁRIO', 'PESSOA', 'FILIADO', 'CPF', 'MATR', 'MTR', 'MAT', 'REGIONAL', 'CIDADE', 'MUNICIPIO', 'MUNICÍPIO', 'NUCLEO', 'NÚCLEO']
    NAME_KEYWORDS = ['NOME', 'SERVIDOR', 'FUNCIONARIO', 'FUNCIONÁRIO', 'PESSOA', 'FILIADO']

    def eh_cabecalho_valido(lista_valores):
        """Verifica se a lista de valores possui termos característicos de cabeçalho real."""
        lista_up = [str(v).strip().upper() for v in lista_valores]
        tem_nome = any(any(nk in val for nk in NAME_KEYWORDS) for val in lista_up)
        kw_encontrados = sum(1 for val in lista_up if any(kw in val for kw in HEADER_KEYWORDS))
        
        if tem_nome and kw_encontrados >= 1:
            return True
        if kw_encontrados >= 2:
            return True
        return False

    # 1. Busca dinâmica de cabeçalhos até 10 linhas (Requisito 1)
    possui_cabecalho = eh_cabecalho_valido(df.columns)

    if not possui_cabecalho:
        max_linhas = min(10, len(df))
        for idx in range(max_linhas):
            linha_valores = list(df.iloc[idx])
            if eh_cabecalho_valido(linha_valores):
                novas_colunas = [str(val).strip() for val in df.iloc[idx]]
                df = df.iloc[idx+1:].copy()
                df.columns = novas_colunas
                break

    colunas_originais = [str(c).strip() for c in df.columns]
    
    # Mapeamento expandido (Requisito 2)
    REGIONAL_KEYWORDS = [
        'REGIONAL', 'CIDADE', 'MUNICIPIO', 'MUNICÍPIO',
        'NUCLEO', 'NÚCLEO', 'LOCAL', 'LOCALIDADE',
        'LOTACAO', 'LOTAÇÃO', 'SEDE', 'POLO', 'PÓLO',
        'MUNICIPALIDADE', 'SECRETARIA'
    ]
    MATRICULA_KEYWORDS = ['MATR', 'MTR', 'MATRICULA', 'MATRÍCULA', 'CODIGO', 'CÓDIGO']
    NOME_KEYWORDS = ['NOME', 'SERVIDOR', 'FUNCIONARIO', 'FUNCIONÁRIO', 'PESSOA', 'FILIADO']
    CPF_KEYWORDS = ['CPF']

    # Palavras-chave e valores para filtrar títulos e separadores no meio da tabela (Requisito 3)
    TITULOS_E_SEPARADORES = [
        'NOVAS FILIAÇÕES', 'NOVAS FILIACOES', 'FILIAÇÕES', 'FILIACOES', 'RELAÇÃO', 'RELACAO',
        'LISTA DE', 'TOTAL', 'SUBTOTAL', 'DEMONSTRATIVO', 'CADASTROS MANUAIS', 'SERVIDORES ADMITIDOS',
        'SECRETARIA DE EDUCACAO', 'GOVERNO DO ESTADO', 'SINTE', 'SINDICATO', 'TERMO DE', 'ALTERAÇÕES', 'ALTERACOES'
    ]

    VALORES_CABECALHO_INVALIDOS = {
        'NOME', 'NOME DO SERVIDOR', 'SERVIDOR', 'NOME COMPLETO', 'FUNCIONARIO', 'NOME DO FUNCIONARIO', 'FILIADO', 'NOME DO FILIADO',
        'MATRÍCULA', 'MATRICULA', 'MATR', 'MTR', 'CODIGO', 'CÓDIGO', 'ORDEM', 'Nº', 'NR', 'Nº.',
        'CPF', 'CPF/MF', 'C.P.F.', 'DOC', 'DOCUMENTO',
        'REGIONAL', 'CIDADE', 'MUNICIPIO', 'MUNICÍPIO', 'NÚCLEO', 'NUCLEO'
    }

    for _, linha in df.iterrows():
        # Extração de Matrícula
        matricula = ""
        col_mat_idx = -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if any(kw in col_upper for kw in MATRICULA_KEYWORDS) or 'MAT' in col_upper:
                val = str(linha.iloc[idx]).strip() if not pd.isna(linha.iloc[idx]) else ''
                if val and val.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL', '0']:
                    matricula = val
                    col_mat_idx = idx
                    break
        if not matricula or matricula.upper() == 'NAN':
            if len(colunas_originais) > 0:
                val_col1 = str(linha.iloc[0]).strip() if not pd.isna(linha.iloc[0]) else ''
                if val_col1 and val_col1.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                    matricula = val_col1
                    col_mat_idx = 0

        # Extração de Nome
        nome = ""
        col_nome_idx = -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if any(kw in col_upper for kw in NOME_KEYWORDS):
                val = str(linha.iloc[idx]).strip().upper() if not pd.isna(linha.iloc[idx]) else ''
                if val and val not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                    nome = val
                    col_nome_idx = idx
                    break
        if (not nome or nome == 'NAN') and len(colunas_originais) > 1:
            val_col2 = str(linha.iloc[1]).strip() if not pd.isna(linha.iloc[1]) else ''
            if val_col2 and val_col2.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                nome = val_col2.upper()
                col_nome_idx = 1

        # Extração de CPF
        cpf = ""
        col_cpf_idx = -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if any(kw in col_upper for kw in CPF_KEYWORDS):
                val = str(linha.iloc[idx]).strip() if not pd.isna(linha.iloc[idx]) else ''
                if val and val.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                    cpf = val
                    col_cpf_idx = idx
                    break
        if (not cpf or cpf == 'NAN') and len(colunas_originais) > 2:
            val_col3 = str(linha.iloc[2]).strip() if not pd.isna(linha.iloc[2]) else ''
            if val_col3 and val_col3.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                cpf = val_col3
                col_cpf_idx = 2

        if cpf.endswith('.0'): cpf = cpf[:-2]
        if matricula.endswith('.0'): matricula = matricula[:-2]

        # Extração da Regional / Cidade / Município (Requisito 2)
        regional = ""
        col_reg_idx = -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if any(kw in col_upper for kw in REGIONAL_KEYWORDS):
                val_reg = str(linha.iloc[idx]).strip() if not pd.isna(linha.iloc[idx]) else ''
                if val_reg and val_reg.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL', 'UNDEFINED', '0']:
                    regional = val_reg.upper()
                    col_reg_idx = idx
                    break

        # Requisito 3: Filtrar linhas de títulos, separadores de datas e cabeçalhos repetidos
        if nome in VALORES_CABECALHO_INVALIDOS or matricula.upper() in VALORES_CABECALHO_INVALIDOS or cpf.upper() in VALORES_CABECALHO_INVALIDOS:
            continue

        texto_linha_combinado = f"{nome} {matricula} {regional}".upper()

        eh_titulo_ou_divisor = False
        for tit in TITULOS_E_SEPARADORES:
            if tit in nome or tit in matricula.upper():
                eh_titulo_ou_divisor = True
                break

        if not eh_titulo_ou_divisor:
            if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', nome) or re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', matricula):
                if any(w in texto_linha_combinado for w in ['FILIA', 'CADASTRO', 'LOTE', 'NOVA', 'NOVO', 'RELA', 'LISTA', 'ALTERA', 'DATA', 'TOTAL', 'SEMANA', 'MES', 'MÊS']):
                    eh_titulo_ou_divisor = True

        if eh_titulo_ou_divisor:
            continue

        # Normaliza CPF com 11 dígitos (preenchendo zeros à esquerda perdidos no Excel)
        cpf = normalizar_cpf(cpf)

        detalhes_extras = []
        indices_principais = {col_mat_idx, col_nome_idx, col_cpf_idx, col_reg_idx}
        
        for idx, val in enumerate(linha):
            if idx in indices_principais:
                continue
                
            if pd.notna(val):
                valor_str = str(val).strip()
                if valor_str and valor_str.upper() not in ['NAN', 'NONE', 'N/I', '-', 'NULL']:
                    nome_col = colunas_originais[idx]
                    if 'UNNAMED' in nome_col.upper() or nome_col == '':
                        detalhes_extras.append(f"{valor_str}")
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

# ----------------------------------------------------------------------
# 4. ROTAS DA API (BUSCA RIGOROSA E DE ALTA PERFORMANCE)
# ----------------------------------------------------------------------
@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/api/planilhas")
def listar_planilhas():
    try:
        # Verifica a senha enviada no cabeçalho ou como parâmetro de consulta
        senha = request.headers.get("Authorization") or request.args.get("senha")
        if senha != SENHA_ACESSO:
            return jsonify({"success": False, "error": "Acesso não autorizado. Senha incorreta."}), 401

        planilhas = []
        # Google spreadsheets
        for item in PLANILHAS_GOOGLE:
            planilhas.append({
                "nome": item["nome_acao"],
                "tipo": "Google Sheets",
                "url": f"https://docs.google.com/spreadsheets/d/{item['id']}/edit?usp=drivesdk",
                "local": False
            })
        
        # Local files
        arquivos_locais = glob.glob("*.xlsx") + glob.glob("*.xls")
        for arquivo in arquivos_locais:
            nome_exibir = "Cadastros Manuais (Sistema)" if arquivo == ARQUIVO_CADASTROS_MANUAIS else arquivo
            planilhas.append({
                "nome": nome_exibir,
                "tipo": "Arquivo Local Excel",
                "url": f"/planilhas/{arquivo}",
                "local": True
            })
            
        return jsonify({"success": True, "planilhas": planilhas})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/planilhas/<path:filename>")
def baixar_planilha(filename):
    # Verifica a senha como parâmetro de consulta
    senha = request.args.get("senha")
    if senha != SENHA_ACESSO:
        return "Acesso não autorizado. Senha incorreta.", 401

    filename_safe = os.path.basename(filename)
    if filename_safe.endswith(".xlsx") or filename_safe.endswith(".xls"):
        if os.path.exists(filename_safe):
            return send_from_directory(".", filename_safe, as_attachment=True)
    return "Planilha não encontrada", 404


@app.route("/api/search")
def search():
    query = request.args.get("q", "").strip().upper()
    if not query or len(query) < 2:
        return jsonify({"results": []})
        
    # Divide a busca por vírgula para suportar múltiplos termos
    if "," in query:
        termos = [t.strip() for t in query.split(",") if len(t.strip()) >= 2]
    else:
        termos = [query]
        
    if not termos:
        return jsonify({"results": []})
        
    termos_processados = []
    for t in termos:
        t_limpa = t.replace(".", "").replace("-", "").replace("/", "")
        t_eh_numerico = t_limpa.isdigit() or (t_limpa[:-1].isdigit() and t_limpa[-1] in 'XkXK')
        termos_processados.append({
            "original": t,
            "limpa": t_limpa,
            "eh_numerico": t_eh_numerico
        })
    
    encontrados_diretos = []
    matriculas_validas = set()
    nomes_validos = set()
    cpfs_validos = set()
    
    # 1º Passo: Localiza correspondências DIRETAS e PRECISAS
    for reg in banco_dados:
        cpf_limpo = reg["cpf"].replace(".", "").replace("-", "").replace("/", "")
        mat_limpa = reg["matricula"].replace(".", "").replace("-", "").replace("/", "").upper()
        nome_reg = reg["nome"].upper()
        
        match = False
        for tp in termos_processados:
            t_num = tp["limpa"]
            if tp["eh_numerico"]:
                # Match de Matrícula flexível (com ou sem zeros à esquerda)
                match_mat = False
                if mat_limpa:
                    if mat_limpa == t_num or mat_limpa.startswith(t_num):
                        match_mat = True
                    else:
                        mat_sem_zero = mat_limpa.lstrip("0")
                        t_sem_zero = t_num.lstrip("0")
                        if t_sem_zero and len(t_sem_zero) >= 2:
                            if mat_sem_zero == t_sem_zero or mat_sem_zero.startswith(t_sem_zero):
                                match_mat = True

                # Match de CPF flexível (com zero, sem zero, prefixo e zfill 11)
                match_cpf = False
                if cpf_limpo:
                    if cpf_limpo == t_num or cpf_limpo.startswith(t_num):
                        match_cpf = True
                    elif t_num.isdigit():
                        if len(t_num) <= 11 and len(cpf_limpo) <= 11 and cpf_limpo.zfill(11) == t_num.zfill(11):
                            match_cpf = True
                        else:
                            cpf_sem_zero = cpf_limpo.lstrip("0")
                            t_sem_zero = t_num.lstrip("0")
                            if t_sem_zero and len(t_sem_zero) >= 2:
                                if cpf_sem_zero == t_sem_zero or cpf_sem_zero.startswith(t_sem_zero):
                                    match_cpf = True

                if match_mat or match_cpf:
                    match = True
                    break
            else:
                # Se tiver letras, busca por substring no Nome
                if tp["original"] in nome_reg and len(nome_reg) > 0:
                    match = True
                    break
        
        if match:
            encontrados_diretos.append(reg)
            
            # Só coleta dados para consolidação se o termo buscado for consistente
            if mat_limpa and mat_limpa not in ['NAN', 'NONE', 'N/I', '0', '-'] and len(mat_limpa) >= 3:
                matriculas_validas.add(mat_limpa)
                mat_sz = mat_limpa.lstrip("0")
                if mat_sz:
                    matriculas_validas.add(mat_sz)

            if cpf_limpo and len(cpf_limpo) >= 8:
                cpfs_validos.add(cpf_limpo.zfill(11))
                cpf_sz = cpf_limpo.lstrip("0")
                if cpf_sz:
                    cpfs_validos.add(cpf_sz)
                
            if nome_reg and nome_reg not in ['NAN', 'NONE', 'SEM NOME'] and len(nome_reg) >= 5:
                nomes_validos.add(nome_reg)

    if not encontrados_diretos:
        return jsonify({"results": []})

    # 2º Passo: Consolidação — Busca apenas os outros processos dos servidores que realmente bateram com a pesquisa
    resultados_finais = list(encontrados_diretos)
    chaves_ja_incluidas = set((r["arquivo"], r["aba"], r["nome"], r["matricula"]) for r in resultados_finais)
    
    if matriculas_validas or nomes_validos or cpfs_validos:
        for reg in banco_dados:
            chave_reg = (reg["arquivo"], reg["aba"], reg["nome"], reg["matricula"])
            if chave_reg in chaves_ja_incluidas:
                continue
                
            mat_reg_limpa = reg["matricula"].replace(".", "").replace("-", "").replace("/", "").upper()
            cpf_reg_limpo = reg["cpf"].replace(".", "").replace("-", "").replace("/", "")
            nome_reg = reg["nome"].upper()
            
            mat_match = (mat_reg_limpa and (mat_reg_limpa in matriculas_validas or mat_reg_limpa.lstrip("0") in matriculas_validas))
            cpf_match = (cpf_reg_limpo and (cpf_reg_limpo in cpfs_validos or cpf_reg_limpo.zfill(11) in cpfs_validos or cpf_reg_limpo.lstrip("0") in cpfs_validos))
            nome_match = (nome_reg and nome_reg in nomes_validos)

            if mat_match or cpf_match or nome_match:
                resultados_finais.append(reg)
                chaves_ja_incluidas.add(chave_reg)
            
    # Anexa informação de herdeiros se houver caso cadastrado para o servidor
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
                if h_cpf and len(h_cpf) >= 8:
                    mapa_falecidos[f"CPF_{h_cpf.zfill(11)}"] = info
                    mapa_falecidos[f"CPF_{h_cpf.lstrip('0')}"] = info
                if h_mat and h_mat not in ['NAN', '0', '']:
                    mapa_falecidos[f"MAT_{h_mat}"] = info
                    mapa_falecidos[f"MAT_{h_mat.lstrip('0')}"] = info
                if h_nome and len(h_nome) >= 4:
                    mapa_falecidos[f"NOME_{h_nome}"] = info

            for r in resultados_finais:
                r_cpf = str(r.get("cpf", "")).replace(".", "").replace("-", "").replace("/", "").strip()
                r_mat = str(r.get("matricula", "")).replace(".", "").replace("-", "").replace("/", "").strip().upper()
                r_nome = str(r.get("nome", "")).strip().upper()
                
                h_info = None
                if r_cpf:
                    h_info = mapa_falecidos.get(f"CPF_{r_cpf.zfill(11)}") or mapa_falecidos.get(f"CPF_{r_cpf.lstrip('0')}")
                if not h_info and r_mat:
                    h_info = mapa_falecidos.get(f"MAT_{r_mat}") or mapa_falecidos.get(f"MAT_{r_mat.lstrip('0')}")
                if not h_info and r_nome:
                    h_info = mapa_falecidos.get(f"NOME_{r_nome}")

                if h_info:
                    r["herdeiro_info"] = h_info
    except Exception as e_herd:
        print(f"⚠️ Erro ao enriquecer busca com dados de herdeiros: {e_herd}")

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
        return jsonify({
            "success": True, 
            "total_records": total,
            "ultima_sincronizacao": ultima_sincronizacao.strftime("%d/%m/%Y às %H:%M:%S") if ultima_sincronizacao else None
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/cadastrar", methods=["POST"])
def cadastrar():
    try:
        dados = request.json
        nome = dados.get("nome", "").strip().upper()
        matricula = dados.get("matricula", "").strip()
        cpf = normalizar_cpf(dados.get("cpf", ""))
        regional = dados.get("regional", "").strip().upper()
        acao = dados.get("acao", "AUTORIZAÇÕES ASSINADAS - MÃO SANTA 99").strip()
        detalhes = dados.get("detalhes", "Sem detalhes").strip()

        if not nome and not matricula and not cpf:
            return jsonify({"success": False, "error": "Informe ao menos Nome, Matrícula ou CPF."}), 400

        msg_drive = ""
        try:
            salvar_no_google_sheets(nome, matricula, cpf, acao, detalhes)
            msg_drive = f" e inserido na planilha '{acao}' do Google Drive!"
            print(f"✅ {nome} salvo na planilha '{acao}' do Google Drive!")
        except Exception as e_drive:
            print(f"⚠️ Aviso ao salvar no Google Drive: {e_drive}")

        novo_registro = {
            "NOME": nome,
            "MATRÍCULA": matricula,
            "CPF": cpf,
            "REGIONAL": regional,
            "AÇÃO JURÍDICA": acao,
            "OBSERVAÇÕES": detalhes
        }

        if os.path.exists(ARQUIVO_CADASTROS_MANUAIS):
            df_existente = pd.read_excel(ARQUIVO_CADASTROS_MANUAIS)
            df_novo = pd.concat([df_existente, pd.DataFrame([novo_registro])], ignore_index=True)
        else:
            df_novo = pd.DataFrame([novo_registro])

        df_novo.to_excel(ARQUIVO_CADASTROS_MANUAIS, index=False)

        banco_dados.append({
            "arquivo": acao,
            "aba": "Novo Cadastro",
            "matricula": matricula,
            "cpf": cpf,
            "nome": nome,
            "regional": regional,
            "detalhes": f"Observações: {detalhes}"
        })

        return jsonify({"success": True, "message": f"Servidor cadastrado com sucesso{msg_drive}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/regionais")
def listar_regionais():
    try:
        # Coleta todas as regionais únicas, ignorando valores vazios e de erro
        regionais = sorted(list(set(
            reg["regional"].strip().upper() 
            for reg in banco_dados 
            if reg.get("regional") and reg["regional"].strip().upper() not in ['NAN', '', '-', 'NONE', 'N/I']
        )))
        return jsonify({"success": True, "regionais": regionais})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/regional/stats")
def regional_stats():
    try:
        regional_query = request.args.get("q", "").strip().upper()
        if not regional_query:
            return jsonify({"success": False, "error": "Informe a regional."}), 400
            
        pessoas_na_regional = []
        total_por_acao = {}
        
        for reg in banco_dados:
            reg_val = reg.get("regional", "").strip().upper()
            if reg_val == regional_query:
                pessoas_na_regional.append(reg)
                acao = reg["arquivo"]
                total_por_acao[acao] = total_por_acao.get(acao, 0) + 1
                
        # Formata a resposta com as estatísticas e as pessoas
        return jsonify({
            "success": True,
            "regional": regional_query,
            "total": len(pessoas_na_regional),
            "por_acao": total_por_acao,
            "pessoas": pessoas_na_regional
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/diagnostico")
def diagnostico():
    """Mostra por planilha/aba: total registros, quantos tem regional preenchida, e quais acoes aparecem."""
    try:
        resumo = {}
        for reg in banco_dados:
            chave = f"{reg['arquivo']} | {reg['aba']}"
            if chave not in resumo:
                resumo[chave] = {"total": 0, "com_regional": 0, "sem_regional": 0, "acao": reg["arquivo"]}
            resumo[chave]["total"] += 1
            if reg.get("regional", "").strip():
                resumo[chave]["com_regional"] += 1
            else:
                resumo[chave]["sem_regional"] += 1

        resultado = []
        for chave, v in sorted(resumo.items(), key=lambda x: x[1]["sem_regional"], reverse=True):
            resultado.append({
                "planilha_aba": chave,
                "acao": v["acao"],
                "total": v["total"],
                "com_regional": v["com_regional"],
                "sem_regional": v["sem_regional"],
                "pct_com_regional": round(v["com_regional"] / v["total"] * 100, 1) if v["total"] else 0
            })

        return jsonify({"success": True, "resumo": resultado})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats/guilherme-fundef")
def stats_guilherme_fundef():
    """
    Retorna estatísticas de pessoas únicas entre 'Ação Guilherme Melo' e 'FUNDEF'.
    A deduplicação é feita por matrícula (normalizada: sem pontos, traços, espaços).
    Pessoas sem matrícula são contadas individualmente pelo nome.
    Aceita parâmetro opcional ?regional=NOME para filtrar por cidade/regional.
    """
    try:
        ACAO_GM = "Ação Guilherme Melo"
        ACAO_FU = "FUNDEF"

        # Filtro opcional por regional
        regional_filtro = request.args.get("regional", "").strip().upper()

        def normalizar_mat(m):
            return m.replace(".", "").replace("-", "").replace("/", "").replace(" ", "").upper().strip()

        # Coleta matrículas e nomes por ação
        mats_gm = {}   # matricula_normalizada -> registro representativo
        mats_fu = {}

        for reg in banco_dados:
            arq = reg.get("arquivo", "")
            mat_raw = reg.get("matricula", "").strip()
            cpf_raw = reg.get("cpf", "").strip()
            nome = reg.get("nome", "").strip().upper()
            reg_regional = reg.get("regional", "").strip().upper()
            mat = normalizar_mat(mat_raw) if mat_raw else ""
            cpf_norm = normalizar_cpf(cpf_raw) if cpf_raw else ""

            # Aplica filtro de regional se informado
            if regional_filtro and reg_regional != regional_filtro:
                continue

            # Chave de identificação: matrícula se existir, senão CPF, senão nome
            if mat and mat not in ["NAN", "NONE", "0", "N/I", "-"]:
                chave = mat
            elif cpf_norm:
                chave = f"CPF:{cpf_norm}"
            elif nome:
                chave = f"NOME:{nome}"
            else:
                continue
            if not chave:
                continue

            if arq == ACAO_GM:
                if chave not in mats_gm:
                    mats_gm[chave] = reg
            elif arq == ACAO_FU:
                if chave not in mats_fu:
                    mats_fu[chave] = reg

        set_gm = set(mats_gm.keys())
        set_fu = set(mats_fu.keys())

        so_gm = set_gm - set_fu
        so_fu = set_fu - set_gm
        em_ambos = set_gm & set_fu
        total_unico = set_gm | set_fu

        return jsonify({
            "success": True,
            "regional": regional_filtro or None,
            "total_guilherme_melo": len(set_gm),
            "total_fundef": len(set_fu),
            "total_em_ambos": len(em_ambos),
            "total_unico_conjunto": len(total_unico),
            "so_guilherme_melo": len(so_gm),
            "so_fundef": len(so_fu),
            "pessoas_em_ambos": [mats_gm[k] for k in sorted(em_ambos)],
            "pessoas_so_guilherme_melo": [mats_gm[k] for k in sorted(so_gm)],
            "pessoas_so_fundef": [mats_fu[k] for k in sorted(so_fu)],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------------
# 5. ROTAS REST DO MÓDULO DE GESTÃO DE HERDEIROS
# ----------------------------------------------------------------------

@app.route("/api/herdeiros", methods=["GET"])
def api_listar_herdeiros():
    """Retorna lista de processos de herdeiros com suporte a filtros."""
    try:
        dados = carregar_herdeiros()
        
        q = request.args.get("q", "").strip().upper()
        status_filtro = request.args.get("status", "").strip().lower()
        caixa_filtro = request.args.get("caixa", "").strip().upper()
        acao_filtro = request.args.get("acao", "").strip().upper()
        
        filtrados = []
        for caso in dados:
            # Filtro por status
            if status_filtro and caso.get("status", "").lower() != status_filtro:
                continue
                
            # Filtro por caixa de arquivamento
            if caixa_filtro and caixa_filtro != "TODAS":
                caso_caixa = str(caso.get("caixa_concluido", "")).strip().upper()
                if caixa_filtro not in caso_caixa:
                    continue
                    
            # Filtro por ação jurídica
            fal = caso.get("falecido", {})
            if acao_filtro and acao_filtro != "TODAS":
                caso_acao = str(fal.get("acao_juridica", "")).strip().upper()
                if acao_filtro not in caso_acao:
                    continue
                    
            # Filtro por termo geral (busca textual em falecido, herdeiros, telefone, matrícula, CPF, caixa)
            if q:
                texto_busca = f"{caso.get('id', '')} {fal.get('nome', '')} {fal.get('cpf', '')} {fal.get('matricula', '')} {caso.get('caixa_concluido', '')} {caso.get('localizacao_provisoria', '')}".upper()
                for h in caso.get("herdeiros", []):
                    texto_busca += f" {h.get('nome', '')} {h.get('cpf', '')} {h.get('telefone', '')} {h.get('email', '')}".upper()
                
                # Suporta busca por CPF sem pontuação ou com pontuação
                q_limpa = q.replace(".", "").replace("-", "").replace("/", "")
                texto_busca_limpa = texto_busca.replace(".", "").replace("-", "").replace("/", "")
                
                if q not in texto_busca and (not q_limpa or q_limpa not in texto_busca_limpa):
                    continue
                    
            filtrados.append(caso)
            
        # Ordenação: mais recentes primeiro
        filtrados.sort(key=lambda x: x.get("ultima_atualizacao") or x.get("data_cadastro") or "", reverse=True)
        
        return jsonify({
            "success": True,
            "total": len(filtrados),
            "herdeiros": filtrados
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros", methods=["POST"])
def api_criar_herdeiro():
    """Cadastra um novo processo de herdeiros com validação e histórico inicial."""
    try:
        payload = request.get_json(force=True) or {}
        
        falecido = payload.get("falecido", {})
        nome_falecido = falecido.get("nome", "").strip().upper()
        if not nome_falecido:
            return jsonify({"success": False, "error": "Informe o nome do titular falecido."}), 400
            
        cpf_falecido = normalizar_cpf(falecido.get("cpf", ""))
        matricula_falecido = str(falecido.get("matricula", "")).strip()
        regional_falecido = falecido.get("regional", "").strip().upper()
        acao_juridica = falecido.get("acao_juridica", "Ação Guilherme Melo").strip()
        data_obito = falecido.get("data_obito", "").strip()
        
        herdeiros_raw = payload.get("herdeiros", [])
        herdeiros_processados = []
        for idx, h in enumerate(herdeiros_raw):
            nome_h = h.get("nome", "").strip().upper()
            if not nome_h:
                continue
            herdeiros_processados.append({
                "id": idx + 1,
                "nome": nome_h,
                "parentesco": h.get("parentesco", "Herdeiro(a)").strip(),
                "cpf": normalizar_cpf(h.get("cpf", "")),
                "telefone": h.get("telefone", "").strip(),
                "email": h.get("email", "").strip(),
                "is_principal": bool(h.get("is_principal", idx == 0)),
                "observacao": h.get("observacao", "").strip()
            })
            
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dados = carregar_herdeiros()
        novo_id = gerar_proximo_id_herdeiro(dados)
        
        status_inicial = payload.get("status", "fila_espera").strip().lower()
        if status_inicial not in STATUS_HERDEIROS_MAP:
            status_inicial = "fila_espera"
            
        novo_caso = {
            "id": novo_id,
            "data_cadastro": agora_iso,
            "ultima_atualizacao": agora_iso,
            "status": status_inicial,
            "falecido": {
                "nome": nome_falecido,
                "cpf": cpf_falecido,
                "matricula": matricula_falecido,
                "regional": regional_falecido,
                "acao_juridica": acao_juridica,
                "data_obito": data_obito
            },
            "herdeiros": herdeiros_processados,
            "documentos_checklist": payload.get("documentos_checklist", {
                "certidao_obito": False,
                "rg_cpf_falecido": False,
                "rg_cpf_herdeiros": False,
                "comprovante_residencia": False,
                "declaracao_dependentes": False,
                "certidao_casamento_nascimento": False,
                "procuracao": False,
                "outros": ""
            }),
            "localizacao_provisoria": payload.get("localizacao_provisoria", "Recepção / Entrada Jurídico").strip(),
            "caixa_concluido": payload.get("caixa_concluido", "").strip().upper(),
            "observacoes": payload.get("observacoes", "").strip(),
            "historico": [
                {
                    "data": agora_iso,
                    "acao": "Recepção e Cadastro de Herdeiros",
                    "usuario": "Atendimento Jurídico",
                    "detalhes": f"Processo registrado na {STATUS_HERDEIROS_MAP.get(status_inicial)} com {len(herdeiros_processados)} herdeiro(s)."
                }
            ],
            "notificacoes": [],
            "anexos": []
        }
        
        dados.append(novo_caso)
        salvar_herdeiros(dados)
        
        return jsonify({"success": True, "id": novo_id, "caso": novo_caso})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/<id>", methods=["GET"])
def api_obter_herdeiro(id):
    """Retorna dados detalhados de um caso de herdeiros pelo ID."""
    try:
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        for c in dados:
            if c.get("id", "").upper() == id_upper:
                return jsonify({"success": True, "caso": c})
        return jsonify({"success": False, "error": f"Caso {id} não encontrado."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/<id>", methods=["PUT"])
def api_atualizar_herdeiro(id):
    """Atualiza dados cadastrais, herdeiros ou checklist de um caso."""
    try:
        payload = request.get_json(force=True) or {}
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        
        caso_encontrado = None
        for c in dados:
            if c.get("id", "").upper() == id_upper:
                caso_encontrado = c
                break
                
        if not caso_encontrado:
            return jsonify({"success": False, "error": f"Caso {id} não encontrado."}), 404
            
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if "falecido" in payload:
            fal = payload["falecido"]
            if fal.get("nome"): caso_encontrado["falecido"]["nome"] = fal.get("nome", "").strip().upper()
            if "cpf" in fal: caso_encontrado["falecido"]["cpf"] = normalizar_cpf(fal.get("cpf", ""))
            if "matricula" in fal: caso_encontrado["falecido"]["matricula"] = str(fal.get("matricula", "")).strip()
            if "regional" in fal: caso_encontrado["falecido"]["regional"] = str(fal.get("regional", "")).strip().upper()
            if "acao_juridica" in fal: caso_encontrado["falecido"]["acao_juridica"] = str(fal.get("acao_juridica", "")).strip()
            if "data_obito" in fal: caso_encontrado["falecido"]["data_obito"] = str(fal.get("data_obito", "")).strip()
            
        if "herdeiros" in payload:
            herdeiros_proc = []
            for idx, h in enumerate(payload["herdeiros"]):
                nome_h = h.get("nome", "").strip().upper()
                if not nome_h: continue
                herdeiros_proc.append({
                    "id": idx + 1,
                    "nome": nome_h,
                    "parentesco": h.get("parentesco", "Herdeiro(a)").strip(),
                    "cpf": normalizar_cpf(h.get("cpf", "")),
                    "telefone": h.get("telefone", "").strip(),
                    "email": h.get("email", "").strip(),
                    "is_principal": bool(h.get("is_principal", False)),
                    "observacao": h.get("observacao", "").strip()
                })
            caso_encontrado["herdeiros"] = herdeiros_proc
            
        if "documentos_checklist" in payload:
            caso_encontrado["documentos_checklist"] = payload["documentos_checklist"]
            
        if "localizacao_provisoria" in payload:
            caso_encontrado["localizacao_provisoria"] = payload["localizacao_provisoria"].strip()
            
        if "caixa_concluido" in payload:
            caso_encontrado["caixa_concluido"] = payload["caixa_concluido"].strip().upper()
            
        if "observacoes" in payload:
            caso_encontrado["observacoes"] = payload["observacoes"].strip()
            
        caso_encontrado["ultima_atualizacao"] = agora_iso
        caso_encontrado["historico"].append({
            "data": agora_iso,
            "acao": "Atualização Cadastral",
            "usuario": "Jurídico",
            "detalhes": payload.get("motivo_edicao", "Dados do processo de herdeiros editados pelo operador.")
        })
        
        salvar_herdeiros(dados)
        return jsonify({"success": True, "caso": caso_encontrado})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/<id>/mover-status", methods=["POST"])
def api_mover_status_herdeiro(id):
    """Altera o estágio do processo no Kanban e registra histórico."""
    try:
        payload = request.get_json(force=True) or {}
        novo_status = payload.get("novo_status", "").strip().lower()
        
        if novo_status not in STATUS_HERDEIROS_MAP:
            return jsonify({"success": False, "error": f"Status '{novo_status}' inválido."}), 400
            
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        
        caso_encontrado = None
        for c in dados:
            if c.get("id", "").upper() == id_upper:
                caso_encontrado = c
                break
                
        if not caso_encontrado:
            return jsonify({"success": False, "error": f"Caso {id} não encontrado."}), 404
            
        status_anterior = caso_encontrado.get("status", "fila_espera")
        caixa_concluido = payload.get("caixa_concluido", "").strip().upper()
        observacao = payload.get("observacao", "").strip()
        
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        caso_encontrado["status"] = novo_status
        caso_encontrado["ultima_atualizacao"] = agora_iso
        
        if caixa_concluido:
            caso_encontrado["caixa_concluido"] = caixa_concluido
            
        detalhes_msg = f"De '{STATUS_HERDEIROS_MAP.get(status_anterior, status_anterior)}' para '{STATUS_HERDEIROS_MAP.get(novo_status, novo_status)}'."
        if caixa_concluido:
            detalhes_msg += f" Arquivado na {caixa_concluido}."
        if observacao:
            detalhes_msg += f" Obs: {observacao}"
            
        caso_encontrado["historico"].append({
            "data": agora_iso,
            "acao": f"Transição: {STATUS_HERDEIROS_MAP.get(novo_status)}",
            "usuario": "Equipe Jurídica",
            "detalhes": detalhes_msg
        })
        
        salvar_herdeiros(dados)
        return jsonify({"success": True, "caso": caso_encontrado})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/<id>/notificar", methods=["POST"])
def api_notificar_herdeiro(id):
    """Registra envio de notificação (WhatsApp, Ligação ou E-mail) para os herdeiros."""
    try:
        payload = request.get_json(force=True) or {}
        canal = payload.get("canal", "whatsapp").strip().lower()
        destinatario = payload.get("destinatario", "").strip()
        texto = payload.get("texto", "").strip()
        
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        caso_encontrado = None
        for c in dados:
            if c.get("id", "").upper() == id_upper:
                caso_encontrado = c
                break
                
        if not caso_encontrado:
            return jsonify({"success": False, "error": f"Caso {id} não encontrado."}), 404
            
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notif_item = {
            "data": agora_iso,
            "canal": canal,
            "destinatario": destinatario,
            "texto": texto
        }
        caso_encontrado.setdefault("notificacoes", []).append(notif_item)
        caso_encontrado["ultima_atualizacao"] = agora_iso
        
        canal_nome = "WhatsApp" if canal == "whatsapp" else ("E-mail" if canal == "email" else "Telefone")
        caso_encontrado["historico"].append({
            "data": agora_iso,
            "acao": f"Notificação via {canal_nome}",
            "usuario": "Atendimento Jurídico",
            "detalhes": f"Contato enviado para {destinatario}."
        })
        
        salvar_herdeiros(dados)
        return jsonify({"success": True, "notificacao": notif_item, "caso": caso_encontrado})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/<id>/anexos", methods=["POST"])
def api_upload_anexo_herdeiro(id):
    """Recebe e armazena arquivo digitalizado anexado ao caso de herdeiros."""
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "Nenhum arquivo enviado."}), 400
            
        file = request.files["file"]
        if not file.filename:
            return jsonify({"success": False, "error": "Nome de arquivo vazio."}), 400
            
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        caso_encontrado = None
        for c in dados:
            if c.get("id", "").upper() == id_upper:
                caso_encontrado = c
                break
                
        if not caso_encontrado:
            return jsonify({"success": False, "error": f"Caso {id} não encontrado."}), 404
            
        # Cria pasta específica para o caso
        pasta_caso = os.path.join(DIR_UPLOADS_HERDEIROS, id_upper)
        os.makedirs(pasta_caso, exist_ok=True)
        
        original_name = file.filename
        safe_name = secure_filename(original_name)
        if not safe_name:
            safe_name = f"documento_{int(time.time())}"
            
        timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_final = f"{timestamp_prefix}_{safe_name}"
        destino_arquivo = os.path.join(pasta_caso, filename_final)
        
        file.save(destino_arquivo)
        tamanho_bytes = os.path.getsize(destino_arquivo)
        
        tipo_anexo = request.form.get("tipo", "Documento Digitalizado").strip()
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        novo_anexo = {
            "filename": filename_final,
            "original_name": original_name,
            "tipo": tipo_anexo,
            "tamanho": tamanho_bytes,
            "data_upload": agora_iso,
            "url": f"/api/herdeiros/anexos/{id_upper}/{filename_final}"
        }
        
        caso_encontrado.setdefault("anexos", []).append(novo_anexo)
        caso_encontrado["ultima_atualizacao"] = agora_iso
        caso_encontrado["historico"].append({
            "data": agora_iso,
            "acao": f"Anexo Adicionado: {tipo_anexo}",
            "usuario": "Jurídico",
            "detalhes": f"Arquivo '{original_name}' anexado com sucesso."
        })
        
        salvar_herdeiros(dados)
        return jsonify({"success": True, "anexo": novo_anexo, "caso": caso_encontrado})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/anexos/<id>/<path:filename>")
def api_download_anexo_herdeiro(id, filename):
    """Permite visualização/download seguro de anexo do processo de herdeiros."""
    try:
        id_upper = id.strip().upper()
        pasta_caso = os.path.join(DIR_UPLOADS_HERDEIROS, id_upper)
        filename_safe = os.path.basename(filename)
        return send_from_directory(pasta_caso, filename_safe, as_attachment=False)
    except Exception as e:
        return f"Arquivo não encontrado ou erro de acesso: {e}", 404


@app.route("/api/herdeiros/<id>", methods=["DELETE"])
def api_deletar_herdeiro(id):
    """Remove um processo de herdeiros do banco de dados persistente."""
    try:
        dados = carregar_herdeiros()
        id_upper = id.strip().upper()
        
        novos_dados = [c for c in dados if c.get("id", "").upper() != id_upper]
        if len(novos_dados) == len(dados):
            return jsonify({"success": False, "error": f"Caso {id} não encontrado."}), 404
            
        salvar_herdeiros(novos_dados)
        return jsonify({"success": True, "message": f"Caso {id} removido com sucesso."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/caixas")
def api_caixas_herdeiros():
    """Retorna agrupamento consolidado de todas as caixas físicas de arquivamento."""
    try:
        dados = carregar_herdeiros()
        caixas_map = {}
        
        for c in dados:
            cx = str(c.get("caixa_concluido", "")).strip().upper()
            if not cx:
                if c.get("status") == "concluido":
                    cx = "CAIXA GERAL / NÃO ESPECIFICADA"
                else:
                    continue
                    
            if cx not in caixas_map:
                caixas_map[cx] = {
                    "nome": cx,
                    "total": 0,
                    "casos": []
                }
                
            caixas_map[cx]["total"] += 1
            fal = c.get("falecido", {})
            caixas_map[cx]["casos"].append({
                "id": c.get("id"),
                "falecido_nome": fal.get("nome"),
                "cpf": fal.get("cpf"),
                "matricula": fal.get("matricula"),
                "acao": fal.get("acao_juridica"),
                "data_cadastro": c.get("data_cadastro"),
                "status": c.get("status")
            })
            
        # Lista ordenada alfabeticamente pelo nome da caixa
        caixas_lista = sorted(list(caixas_map.values()), key=lambda x: x["nome"])
        return jsonify({"success": True, "caixas": caixas_lista, "total_caixas": len(caixas_lista)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/stats")
def api_stats_herdeiros():
    """Retorna métricas da esteira de herdeiros para o dashboard."""
    try:
        dados = carregar_herdeiros()
        stats = {
            "fila_espera": 0,
            "em_producao": 0,
            "enviado_assinatura": 0,
            "concluido": 0,
            "total": len(dados)
        }
        for c in dados:
            st = c.get("status", "fila_espera").lower()
            if st in stats:
                stats[st] += 1
            else:
                stats["fila_espera"] += 1
                
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/herdeiros/exportar")
def api_exportar_herdeiros():
    """Exporta os processos de herdeiros para arquivo Excel com download direto."""
    try:
        dados = carregar_herdeiros()
        linhas = []
        for item in dados:
            fal = item.get("falecido", {})
            herds = item.get("herdeiros", [])
            nomes_h = ", ".join(h.get("nome", "") for h in herds if h.get("nome"))
            contatos_h = ", ".join(f"{h.get('nome')}: {h.get('telefone') or h.get('email') or 'S/C'}" for h in herds if h.get("nome"))
            
            linhas.append({
                "ID": item.get("id"),
                "STATUS": STATUS_HERDEIROS_MAP.get(item.get("status"), item.get("status")),
                "FALECIDO": fal.get("nome"),
                "CPF FALECIDO": fal.get("cpf"),
                "MATRÍCULA": fal.get("matricula"),
                "REGIONAL": fal.get("regional"),
                "AÇÃO JURÍDICA": fal.get("acao_juridica"),
                "DATA ÓBITO": fal.get("data_obito"),
                "QTD HERDEIROS": len(herds),
                "HERDEIROS (NOMES)": nomes_h,
                "HERDEIROS (CONTATOS)": contatos_h,
                "LOCAL PROVISÓRIO": item.get("localizacao_provisoria"),
                "CAIXA CONCLUÍDO": item.get("caixa_concluido"),
                "DATA CADASTRO": item.get("data_cadastro"),
                "ÚLTIMA ATUALIZAÇÃO": item.get("ultima_atualizacao"),
                "OBSERVAÇÕES": item.get("observacoes")
            })
            
        df = pd.DataFrame(linhas)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Herdeiros")
        output.seek(0)
        
        data_str = datetime.now().strftime("%Y%m%d_%H%M")
        nome_arq = f"herdeiros_sinte_{data_str}.xlsx"
        
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=nome_arq
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ----------------------------------------------------------------------
# 6. INICIALIZAÇÃO DOS DADOS E BACKGROUND SYNC DAEMON
# ----------------------------------------------------------------------
if not os.environ.get("TESTING"):
    carregar_dados()
    sync_thread = threading.Thread(target=background_sync_worker, daemon=True)
    sync_thread.start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 Servidor do SINTE-PI no ar na porta {port}!")
    app.run(host="0.0.0.0", port=port, debug=False)

