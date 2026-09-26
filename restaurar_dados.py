import pandas as pd
import json
import math
import re

excel_path = r"C:\Users\geova\Downloads\ATUALIZAÇÃO SINTE\herdeiros_sinte_20260925_2358.xlsx"
json_path = "dados_herdeiros.json"

df = pd.read_excel(excel_path)
df = df.fillna("")

STATUS_REVERSE_MAP = {
    "Fila de Espera": "fila_espera",
    "Em Produção": "em_producao",
    "Enviado p/ Assinatura": "enviado_assinatura",
    "Concluído & Arquivado": "concluido"
}

def clean_str(s):
    if pd.isna(s) or s == "": return ""
    return str(s).strip()

def extract_herdeiros(nomes_str, contatos_str):
    nomes = [n.strip() for n in clean_str(nomes_str).split(",")]
    contatos_map = {}
    if clean_str(contatos_str):
        for c in clean_str(contatos_str).split(","):
            if ":" in c:
                k, v = c.split(":", 1)
                contatos_map[k.strip()] = v.strip()
    
    herds = []
    for i, n in enumerate(nomes):
        if not n: continue
        contato = contatos_map.get(n, "")
        telefone = contato if contato != "S/C" else ""
        herds.append({
            "id": i + 1,
            "nome": n,
            "parentesco": "Herdeiro(a)",
            "cpf": "",
            "telefone": telefone,
            "email": "",
            "is_principal": (i == 0),
            "observacao": ""
        })
    return herds

registros = []
for idx, row in df.iterrows():
    # Map column names handling encoding issues from pandas if any
    cols = list(df.columns)
    get_col = lambda name: next((row[c] for c in cols if name in c or name.replace(" ", "") in c.replace(" ", "")), "")
    
    status_excel = clean_str(get_col("STATUS"))
    status_json = STATUS_REVERSE_MAP.get(status_excel, "em_producao")
    
    herds = extract_herdeiros(get_col("HERDEIROS (NOMES)") or get_col("NOMES HERDEIROS"), get_col("HERDEIROS (CONTATOS)") or get_col("CONTATOS HERDEIROS"))
    
    cpf_fal = clean_str(get_col("CPF FALECIDO"))
    if cpf_fal and cpf_fal.endswith(".0"):
        cpf_fal = cpf_fal[:-2]
        
    mat = clean_str(get_col("MATRÍCULA") or get_col("MATRCULA"))
    if mat and mat.endswith(".0"):
        mat = mat[:-2]

    reg = {
        "id": clean_str(get_col("ID")),
        "data_cadastro": clean_str(get_col("DATA CADASTRO")),
        "ultima_atualizacao": clean_str(get_col("ÚLTIMA ATUALIZAÇÃO") or get_col("LTIMA ATUALIZAO")),
        "status": status_json,
        "falecido": {
            "nome": clean_str(get_col("FALECIDO")),
            "cpf": cpf_fal,
            "matricula": mat,
            "regional": clean_str(get_col("REGIONAL")),
            "acao_juridica": clean_str(get_col("AÇÃO") or get_col("AO")),
            "data_obito": clean_str(get_col("DATA ÓBITO") or get_col("DATA BITO"))
        },
        "herdeiros": herds,
        "documentos_checklist": {
            "certidao_obito": False,
            "rg_cpf_falecido": False,
            "rg_cpf_herdeiros": False,
            "comprovante_residencia": False,
            "declaracao_dependentes": False,
            "certidao_casamento_nascimento": False,
            "procuracao": False,
            "outros": "Recuperado do backup"
        },
        "localizacao_provisoria": clean_str(get_col("LOCAL PROVISÓRIO") or get_col("LOCAL PROVISRIO")),
        "caixa_concluido": clean_str(get_col("CAIXA CONCLUÍDO") or get_col("CAIXA CONCLUDO")),
        "observacoes": clean_str(get_col("OBSERVAÇÕES") or get_col("OBSERVAES")),
        "historico": [],
        "notificacoes": [],
        "anexos": []
    }
    registros.append(reg)

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(registros, f, ensure_ascii=False, indent=2)

print(f"Sucesso! {len(registros)} herdeiros recuperados e salvos em {json_path}")
