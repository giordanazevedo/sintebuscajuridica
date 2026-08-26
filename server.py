import os
import glob
import io
import re
import sys
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, jsonify, request, send_from_directory

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

app = Flask(__name__, static_folder=".")

# Senha de acesso restrito às planilhas (padrão: sinte@juridico10)
SENHA_ACESSO = os.environ.get("SENHA_ACESSO", "sinte@juridico10")


# ----------------------------------------------------------------------
# 1. MAPEAMENTO DAS 6 PLANILHAS DO GOOGLE DRIVE
# ----------------------------------------------------------------------
PLANILHAS_GOOGLE = [
    {"nome_acao": "AUTORIZAÇÕES ASSINADAS - MÃO SANTA 99", "id": "1T7riNd-ksnhfWkuR4iQUW8_mYfx8u07O"},
    {"nome_acao": "MAO SANTA II", "id": "1z9tGbxd1BrezQwfnI0gTA9UDnA1CWYxG"},
    {"nome_acao": "MÃO SANTA III", "id": "1GMHtlfXB3bRzknUZh2ILzfEeSny4etkj"},
    {"nome_acao": "MÃO SANTA IV A VII", "id": "1LLxcb-STxF8Y2qhzsmMYTy-n-L9-lu33"},
    {"nome_acao": "Ação Guilherme Melo COMPLETO", "id": "1RcO2WxsflWWeTAeZeAaRGhGwbdrZBDJw"},
    {"nome_acao": "SEGUNDA AÇÃO", "id": "1_tfg7-uoslZaVJCDDpOyiNXh_LVxvWak"}
]

MAPA_IDS_ACOES = {p["nome_acao"]: p["id"] for p in PLANILHAS_GOOGLE}

ARQUIVO_CADASTROS_MANUAIS = "novos_cadastros_sinte.xlsx"
banco_dados = []

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
# 3. LEITURA E SINCRONIZAÇÃO DAS BASES
# ----------------------------------------------------------------------
def carregar_dados():
    global banco_dados
    banco_dados = []
    
    print("\n🔄 Sincronizando planilhas do Google Drive e Cadastros Manuais...")
    
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
                        processar_dataframe(df, arquivo_nome=nome_acao, aba_nome=nome_aba)
                    except Exception as e_aba:
                        print(f"  ⚠️ Erro ao processar aba '{nome_aba}' de {nome_acao}: {e_aba}")
                print(f"  ✅ {nome_acao} (todas as abas) sincronizada!")
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
                    processar_dataframe(df_man, arquivo_nome="Cadastros Manuais (Sistema)", aba_nome=nome_aba)
                except Exception as e_aba:
                    print(f"  ⚠️ Erro ao processar aba '{nome_aba}' em {ARQUIVO_CADASTROS_MANUAIS}: {e_aba}")
            print(f"  ✅ {ARQUIVO_CADASTROS_MANUAIS} (todas as abas) carregado!")
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
                    processar_dataframe(df, arquivo_nome=f"Local: {arquivo}", aba_nome=nome_aba)
                except Exception as e_aba:
                    print(f"  ⚠️ Erro ao processar aba '{nome_aba}' de {arquivo}: {e_aba}")
        except Exception as e:
            print(f"Erro ao ler arquivo local {arquivo}: {e}")
            
    print(f"\n🟢 Sincronização concluída! Total de {len(banco_dados)} registros ativos.\n")
    return len(banco_dados)


def processar_dataframe(df, arquivo_nome, aba_nome):
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
    REGIONAL_KEYWORDS = ['REGIONAL', 'CIDADE', 'MUNICIPIO', 'MUNICÍPIO', 'NUCLEO', 'NÚCLEO']
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
                val = str(linha.get(col, '')).strip()
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
                val = str(linha.get(col, '')).strip().upper()
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
                val = str(linha.get(col, '')).strip()
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
                val_reg = str(linha.get(col, '')).strip()
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
        
        if (nome and nome != 'NAN') or (cpf and cpf != 'NAN') or (matricula and matricula != 'NAN'):
            banco_dados.append({
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
        
    query_limpa = query.replace(".", "").replace("-", "").replace("/", "")
    eh_numerico = query_limpa.isdigit() or (query_limpa[:-1].isdigit() and query_limpa[-1] in 'XkXK')
    
    encontrados_diretos = []
    matriculas_validas = set()
    nomes_validos = set()
    
    # 1º Passo: Localiza correspondências DIRETAS e PRECISAS
    for reg in banco_dados:
        cpf_limpo = reg["cpf"].replace(".", "").replace("-", "").replace("/", "")
        mat_limpa = reg["matricula"].replace(".", "").replace("-", "").replace("/", "").upper()
        nome_reg = reg["nome"].upper()
        
        match = False
        
        if eh_numerico:
            # Exige correspondência EXATA ou que o registro comece exatamente com a query
            if (mat_limpa and (mat_limpa == query_limpa or mat_limpa.startswith(query_limpa))) or \
               (cpf_limpo and (cpf_limpo == query_limpa or cpf_limpo.startswith(query_limpa))):
                match = True
        else:
            # Se tiver letras, busca por substring no Nome
            if query in nome_reg and len(nome_reg) > 0:
                match = True

        if match:
            encontrados_diretos.append(reg)
            
            # Só coleta dados para consolidação se o termo buscado for consistente
            if mat_limpa and mat_limpa not in ['NAN', 'NONE', 'N/I', '0', '-'] and len(mat_limpa) >= 3:
                matriculas_validas.add(mat_limpa)
                
            if nome_reg and nome_reg not in ['NAN', 'NONE', 'SEM NOME'] and len(nome_reg) >= 5:
                nomes_validos.add(nome_reg)

    if not encontrados_diretos:
        return jsonify({"results": []})

    # 2º Passo: Consolidação — Busca apenas os outros processos dos servidores que realmente bateram com a pesquisa
    resultados_finais = list(encontrados_diretos)
    chaves_ja_incluidas = set((r["arquivo"], r["aba"], r["nome"], r["matricula"]) for r in resultados_finais)
    
    if matriculas_validas or nomes_validos:
        for reg in banco_dados:
            chave_reg = (reg["arquivo"], reg["aba"], reg["nome"], reg["matricula"])
            if chave_reg in chaves_ja_incluidas:
                continue
                
            mat_reg_limpa = reg["matricula"].replace(".", "").replace("-", "").replace("/", "").upper()
            nome_reg = reg["nome"].upper()
            
            if (mat_reg_limpa and mat_reg_limpa in matriculas_validas) or \
               (nome_reg and nome_reg in nomes_validos):
                resultados_finais.append(reg)
                chaves_ja_incluidas.add(chave_reg)
            
    return jsonify({"results": resultados_finais})


@app.route("/api/sync")
def sync():
    try:
        total = carregar_dados()
        return jsonify({"success": True, "total_records": total})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/cadastrar", methods=["POST"])
def cadastrar():
    try:
        dados = request.json
        nome = dados.get("nome", "").strip().upper()
        matricula = dados.get("matricula", "").strip()
        cpf = dados.get("cpf", "").strip()
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


if __name__ == "__main__":
    carregar_dados()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 Servidor do SINTE-PI no ar na porta {port}!")
    
    app.run(host="0.0.0.0", port=port, debug=False)
