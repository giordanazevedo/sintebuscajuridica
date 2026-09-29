"""
Módulo de persistência PostgreSQL para gestão de herdeiros do SINTE-PI.

Se DATABASE_URL estiver definida no ambiente, o sistema usa PostgreSQL.
Caso contrário, o server.py continua usando o arquivo JSON como antes (fallback).

Cada caso de herdeiro é armazenado como documento JSONB, mantendo a mesma
estrutura de dados usada pelo frontend — zero mudanças na API.
"""
import os
import json
import threading

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway/Heroku usam postgres:// mas psycopg2 requer postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_pool = None
_pool_lock = threading.Lock()


def usar_postgres():
    """Retorna True se o banco PostgreSQL está configurado."""
    return bool(DATABASE_URL)


def get_pool():
    """Retorna o pool de conexões thread-safe (criando na primeira chamada)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                try:
                    from psycopg2 import pool as pg_pool
                    _pool = pg_pool.ThreadedConnectionPool(
                        minconn=1,
                        maxconn=5,
                        dsn=DATABASE_URL
                    )
                    print("✅ Pool de conexões PostgreSQL criado com sucesso!")
                except ImportError:
                    print("❌ psycopg2 não instalado. Execute: pip install psycopg2-binary")
                    raise
                except Exception as e:
                    print(f"❌ Erro ao criar pool PostgreSQL: {e}")
                    raise
    return _pool


def get_conn():
    """Obtém uma conexão do pool."""
    return get_pool().getconn()


def put_conn(conn):
    """Devolve uma conexão ao pool."""
    try:
        get_pool().putconn(conn)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# INICIALIZAÇÃO
# ──────────────────────────────────────────────────────────────
def init_db():
    """Cria a tabela e índices se não existirem."""
    if not usar_postgres():
        return

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS casos_herdeiros (
                    id TEXT PRIMARY KEY,
                    dados JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_casos_status
                    ON casos_herdeiros ((dados->>'status'));

                CREATE INDEX IF NOT EXISTS idx_casos_falecido_cpf
                    ON casos_herdeiros ((dados->'falecido'->>'cpf'));

                CREATE INDEX IF NOT EXISTS idx_casos_atualizacao
                    ON casos_herdeiros ((dados->>'ultima_atualizacao'));
            """)
        conn.commit()
        print("✅ Tabela casos_herdeiros verificada/criada no PostgreSQL.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao inicializar tabelas PostgreSQL: {e}")
        raise
    finally:
        put_conn(conn)


# ──────────────────────────────────────────────────────────────
# LEITURA
# ──────────────────────────────────────────────────────────────
def carregar_todos():
    """Carrega todos os registros do PostgreSQL, retornando lista de dicts."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dados FROM casos_herdeiros
                ORDER BY (dados->>'ultima_atualizacao') DESC NULLS LAST
            """)
            rows = cur.fetchall()
        return [row[0] for row in rows]
    except Exception as e:
        print(f"⚠️ Erro ao carregar herdeiros do PostgreSQL: {e}")
        return []
    finally:
        put_conn(conn)


def carregar_por_id(caso_id):
    """Carrega um caso específico pelo ID."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dados FROM casos_herdeiros WHERE id = %s",
                (caso_id.strip().upper(),)
            )
            row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"⚠️ Erro ao carregar herdeiro {caso_id}: {e}")
        return None
    finally:
        put_conn(conn)


def contar_registros():
    """Retorna a quantidade total de registros no banco."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM casos_herdeiros")
            row = cur.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
    finally:
        put_conn(conn)


# ──────────────────────────────────────────────────────────────
# ESCRITA
# ──────────────────────────────────────────────────────────────
def salvar_todos(dados):
    """
    Sincroniza TODA a lista de herdeiros no PostgreSQL.
    Usa UPSERT para inserir/atualizar e remove registros que saíram da lista.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # IDs que devem existir após a operação
            novos_ids = {caso.get("id", "") for caso in dados if caso.get("id")}

            # IDs atuais no banco
            cur.execute("SELECT id FROM casos_herdeiros")
            ids_existentes = {row[0] for row in cur.fetchall()}

            # Remove registros que não estão mais na lista
            ids_remover = ids_existentes - novos_ids
            if ids_remover:
                cur.execute(
                    "DELETE FROM casos_herdeiros WHERE id = ANY(%s)",
                    (list(ids_remover),)
                )

            # Upsert de cada caso
            for caso in dados:
                caso_id = caso.get("id", "")
                if not caso_id:
                    continue
                cur.execute("""
                    INSERT INTO casos_herdeiros (id, dados)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET dados = EXCLUDED.dados
                """, (caso_id, json.dumps(caso, ensure_ascii=False, default=str)))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao salvar herdeiros no PostgreSQL: {e}")
        raise
    finally:
        put_conn(conn)


def salvar_caso(caso):
    """Salva/atualiza um único caso no PostgreSQL (upsert)."""
    caso_id = caso.get("id", "")
    if not caso_id:
        return

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO casos_herdeiros (id, dados)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET dados = EXCLUDED.dados
            """, (caso_id, json.dumps(caso, ensure_ascii=False, default=str)))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao salvar caso {caso_id} no PostgreSQL: {e}")
        raise
    finally:
        put_conn(conn)


def deletar_caso(caso_id):
    """Remove um caso do PostgreSQL."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM casos_herdeiros WHERE id = %s",
                (caso_id.strip().upper(),)
            )
            removidos = cur.rowcount
        conn.commit()
        return removidos > 0
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao deletar caso {caso_id}: {e}")
        return False
    finally:
        put_conn(conn)


# ──────────────────────────────────────────────────────────────
# ESTATÍSTICAS
# ──────────────────────────────────────────────────────────────
def stats():
    """Retorna estatísticas por status diretamente do banco (eficiente)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COALESCE(dados->>'status', 'fila_espera') AS status,
                    COUNT(*) AS total
                FROM casos_herdeiros
                GROUP BY dados->>'status'
            """)
            rows = cur.fetchall()

        result = {
            "fila_espera": 0,
            "em_producao": 0,
            "enviado_assinatura": 0,
            "concluido": 0,
            "total": 0
        }
        for status, total in rows:
            st = (status or "fila_espera").lower()
            if st in result:
                result[st] = total
            else:
                result["fila_espera"] += total
            result["total"] += total

        return result
    except Exception as e:
        print(f"⚠️ Erro ao calcular stats: {e}")
        return {
            "fila_espera": 0, "em_producao": 0,
            "enviado_assinatura": 0, "concluido": 0, "total": 0
        }
    finally:
        put_conn(conn)


# ──────────────────────────────────────────────────────────────
# MIGRAÇÃO JSON → POSTGRESQL
# ──────────────────────────────────────────────────────────────
def migrar_de_json(dados_json):
    """Importa lista de casos do arquivo JSON para o PostgreSQL (bulk upsert)."""
    if not dados_json:
        return 0

    conn = get_conn()
    try:
        inseridos = 0
        with conn.cursor() as cur:
            for caso in dados_json:
                caso_id = caso.get("id", "")
                if not caso_id:
                    continue
                cur.execute("""
                    INSERT INTO casos_herdeiros (id, dados)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET dados = EXCLUDED.dados
                """, (caso_id, json.dumps(caso, ensure_ascii=False, default=str)))
                inseridos += 1
        conn.commit()
        print(f"✅ Migração concluída: {inseridos} registros importados para o PostgreSQL.")
        return inseridos
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro na migração JSON → PostgreSQL: {e}")
        raise
    finally:
        put_conn(conn)
