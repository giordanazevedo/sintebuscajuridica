import pandas as pd
import math
import os

# Importa o módulo de banco de dados que criamos
import database as db

def limpar_nan(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.endswith(".0") and s[:-2].isdigit(): s = s[:-2]
    if s.upper() in ["NAN", "NONE", "NULL", "NAT"]: return ""
    return s

STATUS_REVERSE_MAP = {
    "Fila de Espera": "fila_espera",
    "Em Produção": "em_producao",
    "Enviado p/ Assinatura": "enviado_assinatura",
    "Concluído & Arquivado": "concluido"
}

def restaurar():
    print("Iniciando restauração direta no banco de dados...")
    
    if not db.usar_postgres():
        print("❌ ERRO: DATABASE_URL não configurada no ambiente. Crie um arquivo .env ou defina a variável DATABASE_URL.")
        return

    db.init_db()
    
    print("Lendo a planilha Excel...")
    df = pd.read_excel("herdeiros_sinte_20260929_1758.xlsx")
    dados = []

    for idx, row in df.iterrows():
        try:
            caso_id = limpar_nan(row.get("ID"))
            if not caso_id: continue
            
            status_label = limpar_nan(row.get("STATUS"))
            status = STATUS_REVERSE_MAP.get(status_label, "fila_espera")
            
            # Parse Herdeiros
            herdeiros_nomes = limpar_nan(row.get("HERDEIROS (NOMES)")).split(",")
            telefones = limpar_nan(row.get("CONTATO / TELEFONE")).split("|")
            emails = limpar_nan(row.get("EMAIL")).split("|")
            
            lista_herdeiros = []
            for i, nome_h in enumerate(herdeiros_nomes):
                nome_h = nome_h.strip()
                if not nome_h: continue
                
                tel = telefones[i].strip() if i < len(telefones) else ""
                if ":" in tel: tel = tel.split(":", 1)[1].strip()
                
                email = emails[i].strip() if i < len(emails) else ""
                if ":" in email: email = email.split(":", 1)[1].strip()
                
                lista_herdeiros.append({
                    "id": i + 1,
                    "nome": nome_h,
                    "parentesco": "Herdeiro(a)",
                    "cpf": "",
                    "telefone": tel,
                    "email": email,
                    "is_principal": (i == 0),
                    "observacao": ""
                })
                
            if not lista_herdeiros:
                lista_herdeiros = [{
                    "id": 1,
                    "nome": "HERDEIRO NÃO INFORMADO",
                    "parentesco": "Herdeiro(a)",
                    "cpf": "", "telefone": "", "email": "",
                    "is_principal": True, "observacao": ""
                }]
                
            caso = {
                "id": caso_id,
                "data_cadastro": limpar_nan(row.get("DATA CADASTRO")),
                "ultima_atualizacao": limpar_nan(row.get("ÚLTIMA ATUALIZAÇÃO")),
                "status": status,
                "falecido": {
                    "nome": limpar_nan(row.get("FALECIDO")),
                    "cpf": limpar_nan(row.get("CPF FALECIDO")),
                    "matricula": limpar_nan(row.get("MATRÍCULA")),
                    "regional": limpar_nan(row.get("REGIONAL")),
                    "acao_juridica": limpar_nan(row.get("AÇÃO JURÍDICA")),
                    "data_obito": limpar_nan(row.get("DATA ÓBITO"))
                },
                "herdeiros": lista_herdeiros,
                "documentos_checklist": {
                    "certidao_obito": False, "rg_cpf_falecido": False, "rg_cpf_herdeiros": False,
                    "comprovante_residencia": False, "declaracao_dependentes": False,
                    "certidao_casamento_nascimento": False, "procuracao": False, "outros": "Recuperado do Excel de backup"
                },
                "localizacao_provisoria": limpar_nan(row.get("LOCAL PROVISÓRIO")),
                "caixa_concluido": limpar_nan(row.get("CAIXA CONCLUÍDO")),
                "observacoes": limpar_nan(row.get("OBSERVAÇÕES")),
                "historico": [],
                "notificacoes": [],
                "anexos": []
            }
            dados.append(caso)
        except Exception as e:
            print(f"Erro na linha {idx}: {e}")

    print(f"Processado! {len(dados)} casos extraídos. Inserindo no banco de dados...")
    db.migrar_de_json(dados)
    print("✅ RESTAURAÇÃO CONCLUÍDA COM SUCESSO!")

if __name__ == "__main__":
    restaurar()
