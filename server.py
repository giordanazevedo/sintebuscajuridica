import os
import glob
import io
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=".")

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
    
    for item in PLANILHAS_GOOGLE:
        sheet_id = item["id"]
        nome_acao = item["nome_acao"]
        url_xlsx = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        
        try:
            res = requests.get(url_xlsx)
            if res.status_code == 200:
                xls = pd.ExcelFile(io.BytesIO(res.content))
                for nome_aba in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=nome_aba)
                    processar_dataframe(df, arquivo_nome=nome_acao, aba_nome=nome_aba)
                print(f"  ✅ {nome_acao} (todas as abas) sincronizada!")
        except Exception as e:
            print(f"  ❌ Erro ao conectar com {nome_acao}: {e}")

    if os.path.exists(ARQUIVO_CADASTROS_MANUAIS):
        try:
            df_man = pd.read_excel(ARQUIVO_CADASTROS_MANUAIS)
            processar_dataframe(df_man, arquivo_nome="Cadastros Manuais (Sistema)", aba_nome="Entradas Recentes")
            print(f"  ✅ {ARQUIVO_CADASTROS_MANUAIS} carregado!")
        except Exception as e:
            print(f"  ⚠️ Erro ao ler cadastros manuais: {e}")

    arquivos_locais = glob.glob("*.xlsx") + glob.glob("*.xls")
    for arquivo in arquivos_locais:
        if arquivo == ARQUIVO_CADASTROS_MANUAIS:
            continue
        try:
            xls = pd.ExcelFile(arquivo)
            for nome_aba in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=nome_aba)
                processar_dataframe(df, arquivo_nome=f"Local: {arquivo}", aba_nome=nome_aba)
        except Exception as e:
            print(f"Erro ao ler arquivo local {arquivo}: {e}")
            
    print(f"\n🟢 Sincronização concluída! Total de {len(banco_dados)} registros ativos.\n")
    return len(banco_dados)


def processar_dataframe(df, arquivo_nome, aba_nome):
    if df.empty:
        return

    colunas_originais = [str(c).strip() for c in df.columns]
    df.columns = colunas_originais
    
    for _, linha in df.iterrows():
        matricula = ""
        col_mat_idx = -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if 'MATR' in col_upper or 'MTR' in col_upper or 'MAT' in col_upper:
                matricula = str(linha.get(col, '')).strip()
                col_mat_idx = idx
                break
        if not matricula or matricula.upper() == 'NAN':
            if len(colunas_originais) > 0:
                val_col1 = str(linha.iloc[0]).strip() if not pd.isna(linha.iloc[0]) else ''
                if val_col1 and val_col1.upper() != 'NAN':
                    matricula = val_col1
                    col_mat_idx = 0

        nome = ""
        col_nome_idx = -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if 'NOME' in col_upper or 'SERVIDOR' in col_upper:
                nome = str(linha.get(col, '')).strip().upper()
                col_nome_idx = idx
                break
        if (not nome or nome == 'NAN') and len(colunas_originais) > 1:
            val_col2 = str(linha.iloc[1]).strip() if not pd.isna(linha.iloc[1]) else ''
            if val_col2 and val_col2.upper() != 'NAN':
                nome = val_col2.upper()
                col_nome_idx = 1

        cpf = ""
        col_cpf_idx = -1
        for idx, col in enumerate(colunas_originais):
            col_upper = col.upper()
            if 'CPF' in col_upper:
                cpf = str(linha.get(col, '')).strip()
                col_cpf_idx = idx
                break
        if (not cpf or cpf == 'NAN') and len(colunas_originais) > 2:
            val_col3 = str(linha.iloc[2]).strip() if not pd.isna(linha.iloc[2]) else ''
            if val_col3 and val_col3.upper() != 'NAN':
                cpf = val_col3
                col_cpf_idx = 2

        if cpf.endswith('.0'): cpf = cpf[:-2]
        if matricula.endswith('.0'): matricula = matricula[:-2]

        detalhes_extras = []
        indices_principais = {col_mat_idx, col_nome_idx, col_cpf_idx}
        
        for idx, val in enumerate(linha):
            if idx in indices_principais:
                continue
                
            if pd.notna(val):
                valor_str = str(val).strip()
                if valor_str and valor_str.upper() != 'NAN' and valor_str != '-':
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
            "detalhes": f"Observações: {detalhes}"
        })

        return jsonify({"success": True, "message": f"Servidor cadastrado com sucesso{msg_drive}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    carregar_dados()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 Servidor do SINTE-PI no ar na porta {port}!")
    
    app.run(host="0.0.0.0", port=port, debug=False)
