import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime, timedelta
from supabase import create_client

st.set_page_config(
    page_title="Portal da Oficina | YESHUA RASTREAMENTO",
    page_icon="🏢",
    layout="wide",
)

OFICINA_PORTAL = "YESHUA RASTREAMENTO"
CACHE_TTL_SEGUNDOS = 60

def obter_cliente_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        st.error(
            "O portal ainda não está conectado ao Supabase. "
            "Configure SUPABASE_URL e SUPABASE_KEY nos Secrets do Streamlit."
        )
        st.stop()
    return create_client(url, key)

cliente = obter_cliente_supabase()

def buscar_todos(tabela: str, ordem: str | None = None, desc: bool = False):
    consulta = cliente.table(tabela).select("*")
    if ordem:
        consulta = consulta.order(ordem, desc=desc)
    resposta = consulta.execute()
    return resposta.data or []



import html

import io

import re

import unicodedata

import uuid

from datetime import date, datetime

from typing import Any

from urllib.parse import quote, urlsplit, urlunsplit

from zoneinfo import ZoneInfo

import pandas as pd

import plotly.express as px

import streamlit as st

from supabase import Client, create_client

TABELA_POR_TIPO = {
    "planejado": "atividades_planejadas",
    "resultado": "atividades_resultado",
}

DATA_CORTE_NOVA_REGRA = "2026-08-08"

CACHE_TTL_SEGUNDOS = 60

def buscar_todos(
    tabela: str,
    colunas: str = "*",
    filtros: dict[str, Any] | None = None,
    ordem: str | None = None,
    desc: bool = False,
    tamanho_pagina: int = 1000,
) -> list[dict]:
    """Busca todos os registros, inclusive quando houver mais de 1.000 linhas."""
    cliente = exigir_supabase()
    registros: list[dict] = []
    inicio = 0

    while True:
        consulta = cliente.table(tabela).select(colunas)

        for coluna, valor in (filtros or {}).items():
            consulta = consulta.eq(coluna, valor)

        if ordem:
            consulta = consulta.order(ordem, desc=desc)

        resposta = consulta.range(
            inicio,
            inicio + tamanho_pagina - 1,
        ).execute()

        lote = resposta.data or []
        registros.extend(lote)

        if len(lote) < tamanho_pagina:
            break

        inicio += tamanho_pagina

    return registros

def carregar_base(
    tipo: str,
    data_operacional: str,
) -> pd.DataFrame:
    tabela = TABELA_POR_TIPO[tipo]
    registros = buscar_todos(
        tabela,
        filtros={"data_operacional": data_operacional},
        ordem="id",
    )

    linhas = []

    for registro in registros:
        dados = dict(registro.get("dados") or {})

        padrao = {
            "Ticket Jira": registro.get("ticket_jira", ""),
            "OS": registro.get("os", ""),
            "Placa": registro.get("placa", ""),
            "Oficina": registro.get("oficina", ""),
            "Cliente": registro.get("cliente", ""),
            "Estado": registro.get("estado", ""),
            "Cidade": registro.get("cidade", ""),
            "Tipo de Atividade": registro.get("tipo_atividade", ""),
            "Status da Atividade": registro.get(
                "status_atividade",
                "",
            ),
            "Recurso": registro.get("recurso", ""),
            "__Data Operacional": registro.get(
                "data_operacional",
                data_operacional,
            ),
        }

        if tipo == "planejado":
            padrao.update(
                {
                    "__Primeira Aparição": registro.get(
                        "primeira_aparicao",
                        "",
                    ),
                    "__Primeira Aparição Data": registro.get(
                        "primeira_aparicao_data",
                        "",
                    ),
                    "__Última Aparição": registro.get(
                        "ultima_aparicao",
                        "",
                    ),
                    "__Ativa no Planejamento": bool(
                        registro.get(
                            "ativa_no_planejamento",
                            True,
                        )
                    ),
                    "__Arquivo Primeira Aparição": registro.get(
                        "nome_arquivo_primeira_aparicao",
                        "",
                    ),
                }
            )

        dados.update(padrao)
        linhas.append(dados)

    return pd.DataFrame(linhas)

def carregar_consolidado(datas: list[str]) -> pd.DataFrame:
    """Concilia todas as datas completas e cria a visão histórica geral."""
    partes = []

    for data_operacional in datas:
        planejado = carregar_base("planejado", data_operacional)
        resultado = carregar_base("resultado", data_operacional)

        if planejado.empty and resultado.empty:
            continue

        conciliacao_data = conciliar_bases(
            planejado,
            resultado,
        )
        conciliacao_data.insert(
            0,
            "Data Operacional",
            data_operacional,
        )
        partes.append(conciliacao_data)

    if not partes:
        return pd.DataFrame()

    return pd.concat(
        partes,
        ignore_index=True,
        sort=False,
    )

def carregar_oficinas() -> pd.DataFrame:
    registros = buscar_todos(
        "oficinas",
        ordem="nome_oficina",
    )

    if not registros:
        return pd.DataFrame()

    return pd.DataFrame(
        {
            "ID": [r.get("codigo_oficina", "") for r in registros],
            "Oficina": [r.get("nome_oficina", "") for r in registros],
            "Cidade-base": [r.get("cidade", "") for r in registros],
            "UF-base": [r.get("uf", "") for r in registros],
            "Consultor": [r.get("consultor", "Não definido") for r in registros],
            "WhatsApp": [r.get("whatsapp", "") for r in registros],
            "Prioridade": [r.get("prioridade", "Normal") for r in registros],
            "Ativa": ["Sim" if r.get("ativa", True) else "Não" for r in registros],
            "Observações": [r.get("observacoes", "") for r in registros],
            "Chave Oficina": [r.get("chave_oficina", "") for r in registros],
        }
    )

def conciliar_bases(
    planejado: pd.DataFrame,
    resultado: pd.DataFrame,
) -> pd.DataFrame:
    """
    Regra híbrida:
    - datas anteriores a DATA_CORTE_NOVA_REGRA usam a lógica histórica;
    - a partir da data de corte, usa primeira aparição da OS para
      classificar Agendada x Extra/Encaixe.
    """
    planejado = filtrar_somente_manutencoes(planejado)
    resultado = filtrar_somente_manutencoes(resultado)

    planejado = criar_chaves(planejado)
    resultado = criar_chaves(resultado)

    if "Status da Atividade" not in resultado.columns:
        resultado["Status da Atividade"] = ""

    if "Status da Atividade" not in planejado.columns:
        planejado["Status da Atividade"] = ""

    # Compatibilidade com todo o histórico já salvo:
    # se uma importação antiga não tiver estes campos, o painel continua
    # funcionando e exibe o detalhe como vazio, sem alterar os indicadores.
    if "Razão da Improdutiva" not in resultado.columns:
        resultado["Razão da Improdutiva"] = ""

    if "Observação do Técnico (Improdutiva)" not in resultado.columns:
        resultado["Observação do Técnico (Improdutiva)"] = ""

    if "__Ativa no Planejamento" not in planejado.columns:
        planejado["__Ativa no Planejamento"] = True

    if "__Primeira Aparição Data" not in planejado.columns:
        planejado["__Primeira Aparição Data"] = ""

    if "__Data Operacional" not in planejado.columns:
        planejado["__Data Operacional"] = ""

    resumo_resultado = (
        resultado
        .groupby("Chave Atendimento", dropna=False)
        .agg(
            Ticket_resultado=("Ticket Jira", "first"),
            Placa_resultado=("Placa", "first"),
            OS_resultado=("OS", juntar_unicos),
            Oficina_resultado=("Oficina", "first"),
            Status_resultado=("Status da Atividade", juntar_unicos),
            Razao_improdutiva=(
                "Razão da Improdutiva",
                juntar_unicos,
            ),
            Observacao_tecnico_improdutiva=(
                "Observação do Técnico (Improdutiva)",
                juntar_unicos,
            ),
            Qtd_resultado=("Chave Atendimento", "size"),
        )
        .reset_index()
    )

    resumo_planejado = (
        planejado
        .groupby("Chave Atendimento", dropna=False)
        .agg(
            Ticket_planejado=("Ticket Jira", "first"),
            Placa_planejada=("Placa", "first"),
            OS_planejada=("OS", juntar_unicos),
            Oficina_planejada=("Oficina", "first"),
            Status_planejado=("Status da Atividade", juntar_unicos),
            Primeira_aparicao_data=(
                "__Primeira Aparição Data",
                "first",
            ),
            Data_operacional_planejada=(
                "__Data Operacional",
                "first",
            ),
            Ativa_planejamento=(
                "__Ativa no Planejamento",
                "max",
            ),
            Qtd_planejada=("Chave Atendimento", "size"),
        )
        .reset_index()
    )

    conciliacao = resumo_planejado.merge(
        resumo_resultado,
        on="Chave Atendimento",
        how="outer",
        indicator=True,
    )

    # Auditoria de substituição de OS:
    # se a OS planejada não aparece pelo mesmo atendimento, procuramos
    # outra OS no resultado com o MESMO Ticket Jira + MESMA placa.
    # Nessa situação, não declaramos no-show automaticamente.
    def chave_ticket_placa(ticket, placa) -> str:
        ticket_norm = normalizar_texto(ticket)
        placa_norm = normalizar_texto(placa)

        if not ticket_norm or not placa_norm:
            return ""

        return f"{ticket_norm}||{placa_norm}"

    chaves_resultado_ticket_placa = set()

    for _, item in resumo_resultado.iterrows():
        chave = chave_ticket_placa(
            item.get("Ticket_resultado", ""),
            item.get("Placa_resultado", ""),
        )
        if chave:
            chaves_resultado_ticket_placa.add(chave)

    def encontrou_substituicao_ticket_placa(linha) -> bool:
        if linha.get("_merge") != "left_only":
            return False

        chave = chave_ticket_placa(
            linha.get("Ticket_planejado", ""),
            linha.get("Placa_planejada", ""),
        )

        return bool(
            chave
            and chave in chaves_resultado_ticket_placa
        )

    conciliacao["Possível substituição de OS"] = conciliacao.apply(
        encontrou_substituicao_ticket_placa,
        axis=1,
    )

    def data_referencia_linha(linha) -> str | None:
        data_operacional = converter_data_operacional(
            linha.get("Data_operacional_planejada", "")
        )
        return data_operacional

    def usar_regra_nova(linha) -> bool:
        data_operacional = data_referencia_linha(linha)

        if not data_operacional:
            return False

        return data_operacional >= DATA_CORTE_NOVA_REGRA

    def eh_agendada_nova(linha) -> bool:
        if linha.get("_merge") == "right_only":
            return False

        if not bool(linha.get("Ativa_planejamento", False)):
            return False

        primeira = converter_data_operacional(
            linha.get("Primeira_aparicao_data", "")
        )
        data_operacional = data_referencia_linha(linha)

        if not primeira or not data_operacional:
            return False

        return primeira < data_operacional

    def eh_agendada_historica(linha) -> bool:
        # Na regra antiga, toda manutenção válida presente no planejado
        # era considerada agendada, independentemente de primeira aparição.
        if linha.get("_merge") == "right_only":
            return False

        status_planejado = linha.get("Status_planejado", "")

        if status_cancelado(status_planejado):
            return False

        return True

    def eh_agendada(linha) -> bool:
        if usar_regra_nova(linha):
            return eh_agendada_nova(linha)

        return eh_agendada_historica(linha)

    conciliacao["Origem Agendamento"] = conciliacao.apply(
        lambda linha: (
            "Agendada"
            if eh_agendada(linha)
            else "Extra / encaixe"
        ),
        axis=1,
    )

    def classificar(linha) -> str:
        origem_merge = linha["_merge"]
        status_resultado = linha.get("Status_resultado", "")
        status_planejado = linha.get("Status_planejado", "")
        agendada = linha["Origem Agendamento"] == "Agendada"
        ativa = bool(linha.get("Ativa_planejamento", False))
        nova_regra = usar_regra_nova(linha)

        # Histórico antigo preserva a lógica anterior.
        if not nova_regra:
            if origem_merge == "left_only":
                if status_cancelado(status_planejado):
                    return "Cancelada no agendamento"
                if bool(
                    linha.get(
                        "Possível substituição de OS",
                        False,
                    )
                ):
                    return "Possível substituição de OS"
                return "No-show"

            if origem_merge == "right_only":
                if status_improdutivo(status_resultado):
                    return "Improdutiva extra"
                if status_cancelado(status_resultado):
                    return "Cancelada extra"
                if status_executado(status_resultado):
                    return "Executada extra"
                return "Evento extra"

            if status_cancelado(status_planejado):
                return "Cancelada no agendamento"

            if status_improdutivo(status_resultado):
                return "Improdutiva agendada"

            if status_cancelado(status_resultado):
                return "Cancelada"

            if status_executado(status_resultado):
                return "Executada agendada"

            return "Status intermediário agendado"

        # Nova regra, a partir da data de corte.
        if origem_merge == "left_only" and not ativa:
            return "Retirada do agendamento"

        if (
            origem_merge in {"left_only", "both"}
            and ativa
            and status_cancelado(status_planejado)
        ):
            return "Cancelada no agendamento"

        if origem_merge == "left_only":
            if agendada:
                if bool(
                    linha.get(
                        "Possível substituição de OS",
                        False,
                    )
                ):
                    return "Possível substituição de OS"
                return "No-show"
            return "Encaixe não realizado"

        if origem_merge == "right_only":
            if status_improdutivo(status_resultado):
                return "Improdutiva extra"
            if status_cancelado(status_resultado):
                return "Cancelada extra"
            if status_executado(status_resultado):
                return "Executada extra"
            return "Evento extra"

        if status_improdutivo(status_resultado):
            return (
                "Improdutiva agendada"
                if agendada
                else "Improdutiva extra"
            )

        if status_cancelado(status_resultado):
            return (
                "Cancelada"
                if agendada
                else "Cancelada extra"
            )

        if status_executado(status_resultado):
            return (
                "Executada agendada"
                if agendada
                else "Executada extra"
            )

        return (
            "Status intermediário agendado"
            if agendada
            else "Status intermediário extra"
        )

    conciliacao["Classificação"] = conciliacao.apply(
        classificar,
        axis=1,
    )

    def explicar_classificacao(linha) -> str:
        classificacao = linha.get("Classificação", "")
        status_planejado = texto_limpo(
            linha.get("Status_planejado", "")
        )
        status_resultado = texto_limpo(
            linha.get("Status_resultado", "")
        )
        primeira = texto_limpo(
            linha.get("Primeira_aparicao_data", "")
        )
        data_operacional = texto_limpo(
            linha.get("Data_operacional_planejada", "")
        )
        nova_regra = usar_regra_nova(linha)

        if not nova_regra:
            return (
                "Histórico anterior à data de corte: classificação "
                "preservada pela lógica antiga do painel."
            )

        if classificacao == "Executada agendada":
            return (
                f"Manutenção já estava agendada antes de {data_operacional} "
                f"(primeira aparição: {primeira}) e foi executada."
            )
        if classificacao == "Executada extra":
            return (
                "Manutenção não tinha prova de agendamento para essa data "
                "antes do início do dia e foi executada como extra/encaixe."
            )
        if classificacao == "Improdutiva agendada":
            return (
                "Manutenção já estava agendada antes do dia e terminou "
                f"improdutiva/não concluída: {status_resultado}"
            )
        if classificacao == "Improdutiva extra":
            return (
                "Manutenção extra/encaixe terminou improdutiva/não concluída: "
                f"{status_resultado}"
            )
        if classificacao == "Cancelada":
            return (
                "Manutenção estava agendada válida e apareceu cancelada "
                f"posteriormente no resultado: {status_resultado}"
            )
        if classificacao == "Cancelada extra":
            return (
                "Cancelamento de manutenção sem prova de agendamento "
                "anterior para essa mesma data."
            )
        if classificacao == "Cancelada no agendamento":
            return (
                "A manutenção já estava cancelada na fotografia vigente "
                f"do agendamento: {status_planejado}"
            )
        if classificacao == "Possível substituição de OS":
            return (
                "A OS agendada não apareceu pelo mesmo atendimento, mas "
                "foi localizada outra OS no resultado com o mesmo Ticket "
                "Jira + mesma placa. O caso foi retirado do no-show para "
                "auditoria de possível troca/substituição de OS."
            )
        if classificacao == "No-show":
            return (
                "Manutenção estava agendada antes do dia, a própria OS não "
                "apareceu no resultado e nenhuma outra OS com o mesmo Ticket "
                "Jira + mesma placa foi localizada. Classificada como "
                "no-show provável."
            )
        if classificacao == "Encaixe não realizado":
            return (
                "A manutenção surgiu no próprio dia como extra/encaixe "
                "e não apareceu no resultado; não conta como no-show."
            )
        if classificacao == "Retirada do agendamento":
            return (
                "A OS apareceu em fotografia anterior, mas não está mais "
                "no agendamento vigente dessa data."
            )

        return (
            "Status não reconhecido pelas regras principais. "
            f"Planejado: {status_planejado}; resultado: {status_resultado}."
        )

    conciliacao["Motivo da Classificação"] = conciliacao.apply(
        explicar_classificacao,
        axis=1,
    )

    conciliacao["Regra Aplicada"] = conciliacao.apply(
        lambda linha: (
            "Nova regra"
            if usar_regra_nova(linha)
            else "Regra histórica"
        ),
        axis=1,
    )

    conciliacao["Troca de OS"] = conciliacao.apply(
        lambda linha: (
            "Sim"
            if (
                linha["_merge"] == "both"
                and texto_limpo(
                    linha.get("OS_planejada", "")
                )
                != texto_limpo(
                    linha.get("OS_resultado", "")
                )
            )
            else "Não"
        ),
        axis=1,
    )

    conciliacao["Oficina"] = conciliacao[
        "Oficina_planejada"
    ].fillna(conciliacao["Oficina_resultado"])

    conciliacao["Ticket"] = conciliacao[
        "Ticket_planejado"
    ].fillna(conciliacao["Ticket_resultado"])

    conciliacao["Placa"] = conciliacao[
        "Placa_planejada"
    ].fillna(conciliacao["Placa_resultado"])

    return conciliacao

def converter_data_operacional(valor) -> str | None:
    texto = texto_limpo(valor)

    if not texto:
        return None

    for dayfirst in (True, False):
        try:
            data_convertida = pd.to_datetime(
                texto,
                dayfirst=dayfirst,
                errors="raise",
            )
            return data_convertida.date().isoformat()
        except Exception:
            pass

    return None

def criar_chaves(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for coluna in ["Ticket Jira", "Placa", "OS"]:
        if coluna not in df.columns:
            df[coluna] = ""

        df[coluna] = df[coluna].apply(texto_limpo)

    df["Chave Ticket"] = df["Ticket Jira"].apply(normalizar_texto)
    df["Chave Placa"] = df["Placa"].apply(normalizar_texto)
    df["Chave OS"] = df["OS"].apply(normalizar_texto)

    # Os indicadores do painel são baseados em OS.
    # Quando houver OS, ela será a chave principal. A regra anterior
    # usava Ticket + Placa e podia agrupar OS diferentes.
    possui_os = df["Chave OS"] != ""

    df["Chave Atendimento"] = ""

    df.loc[possui_os, "Chave Atendimento"] = (
        "OS|"
        + df.loc[possui_os, "Chave OS"]
        + "|"
        + df.loc[possui_os, "Chave Placa"]
    )

    sem_os = ~possui_os

    df.loc[sem_os, "Chave Atendimento"] = (
        "TICKET|"
        + df.loc[sem_os, "Chave Ticket"]
        + "|"
        + df.loc[sem_os, "Chave Placa"]
    )

    sem_identificador = (
        (df["Chave Ticket"] == "")
        & (df["Chave OS"] == "")
        & (df["Chave Placa"] == "")
    )

    df.loc[sem_identificador, "Chave Atendimento"] = (
        "LINHA|" + df.index[sem_identificador].astype(str)
    )

    return df

def enriquecer_com_cadastro(
    base: pd.DataFrame,
    cadastro: pd.DataFrame,
) -> pd.DataFrame:
    resultado = base.copy()

    if "Oficina" not in resultado.columns:
        resultado["Oficina"] = ""

    resultado["Chave Oficina"] = resultado["Oficina"].apply(
        normalizar_texto
    )

    colunas = [
        "Chave Oficina",
        "Cidade-base",
        "UF-base",
        "Consultor",
        "WhatsApp",
        "Prioridade",
    ]

    resultado = resultado.merge(
        cadastro[colunas].drop_duplicates(
            subset=["Chave Oficina"]
        ),
        on="Chave Oficina",
        how="left",
    )

    resultado["Consultor"] = resultado["Consultor"].fillna(
        "Não definido"
    )
    resultado["Cidade-base"] = resultado["Cidade-base"].fillna("")
    resultado["UF-base"] = resultado["UF-base"].fillna("")
    resultado["WhatsApp"] = resultado["WhatsApp"].fillna("")
    resultado["Prioridade"] = resultado["Prioridade"].fillna("Normal")

    return resultado

def exigir_supabase() -> Client:
    if SUPABASE is None:
        st.error(ERRO_SUPABASE or "Supabase não conectado.")
        st.stop()

    return SUPABASE

def filtrar_somente_manutencoes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mantém somente atividades cujo Tipo de Atividade contenha
    a palavra MANUTEN, cobrindo manutenção, manutenções,
    manutenção corretiva, preventiva e demais variações.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else [])

    if "Tipo de Atividade" not in df.columns:
        raise ValueError(
            "A base não possui a coluna 'Tipo de Atividade'. "
            "Não foi possível filtrar somente manutenções."
        )

    base = df.copy()

    mascara = base["Tipo de Atividade"].apply(
        lambda valor: "MANUTEN" in normalizar_texto(valor)
    )

    return base[mascara].copy().reset_index(drop=True)

def juntar_unicos(valores) -> str:
    itens = sorted(
        {
            texto_limpo(valor)
            for valor in valores
            if texto_limpo(valor)
        }
    )
    return " | ".join(itens)

def listar_bases() -> pd.DataFrame:
    registros = buscar_todos(
        "bases_importadas",
        ordem="data_operacional",
        desc=True,
    )
    return pd.DataFrame(registros)

def normalizar_texto(valor) -> str:
    texto = texto_limpo(valor).upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()

def status_cancelado(valor) -> bool:
    return "CANCEL" in status_normalizado(valor)

def status_executado(valor) -> bool:
    status = status_normalizado(valor)
    return any(
        termo in status
        for termo in [
            "CONCLUID",
            "EXECUTAD",
            "FINALIZAD",
            "COMPLET",
            "REALIZAD",
        ]
    )

def status_improdutivo(valor) -> bool:
    status = status_normalizado(valor)
    return any(
        termo in status
        for termo in [
            "NAO CONCLUIDO",
            "NAO CONCLUIDA",
            "IMPRODUTIVO",
            "IMPRODUTIVA",
            "SEM SUCESSO",
        ]
    )

def status_normalizado(valor) -> str:
    return normalizar_texto(valor)

def texto_limpo(valor) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass

    texto = str(valor).strip()

    if texto.lower() in {"nan", "none", "null", "nat"}:
        return ""

    return texto


# =========================================================
# PORTAL YESHUA — MVP 1.0 (SOMENTE LEITURA)
# =========================================================

st.title("🏢 YESHUA RASTREAMENTO")
st.caption("Portal de Desempenho Operacional • Oficina parceira PS")

st.info(
    "Versão piloto somente leitura. Os indicadores abaixo usam a mesma "
    "base operacional do PS Field Operations."
)

try:
    bases = listar_bases()
except Exception as exc:
    st.error(f"Não foi possível consultar as bases operacionais: {exc}")
    st.stop()

if bases is None or bases.empty:
    st.warning("Ainda não existem bases operacionais disponíveis.")
    st.stop()

datas_planejado = set(
    bases.loc[bases["tipo"] == "planejado", "data_operacional"].astype(str)
)
datas_resultado = set(
    bases.loc[bases["tipo"] == "resultado", "data_operacional"].astype(str)
)
datas_completas = sorted(datas_planejado & datas_resultado)

if not datas_completas:
    st.warning("Ainda não há datas com Planejado + Resultado disponíveis.")
    st.stop()

datas_dt = pd.to_datetime(pd.Series(datas_completas), errors="coerce").dropna()
data_max = datas_dt.max().date()
data_min = datas_dt.min().date()

inicio_padrao = max(data_min, data_max.replace(day=1))

with st.sidebar:
    st.header("Meu desempenho")
    periodo = st.date_input(
        "Período",
        value=(inicio_padrao, data_max),
        min_value=data_min,
        max_value=data_max,
        key="portal_periodo",
    )
    st.caption("Oficina vinculada")
    st.success(OFICINA_PORTAL)
    st.divider()
    st.caption("Portal da Oficina • MVP 1.0")

if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
    inicio, fim = periodo
else:
    inicio = fim = periodo[0] if isinstance(periodo, (tuple, list)) else periodo

datas_periodo = [
    d for d in datas_completas
    if inicio <= pd.to_datetime(d).date() <= fim
]

if not datas_periodo:
    st.info("Não existem bases completas no período selecionado.")
    st.stop()

with st.spinner("Atualizando indicadores da oficina..."):
    consolidado = carregar_consolidado(datas_periodo)
    cadastro = carregar_oficinas()
    if not cadastro.empty:
        consolidado = enriquecer_com_cadastro(consolidado, cadastro)

if consolidado.empty:
    st.info("Não há atendimentos consolidados nesse período.")
    st.stop()

col_oficina = "Oficina"
if col_oficina not in consolidado.columns:
    st.error("A base consolidada não contém a coluna de Oficina.")
    st.stop()

dados = consolidado[
    consolidado[col_oficina].fillna("").astype(str).str.strip().str.upper()
    == OFICINA_PORTAL.upper()
].copy()

if dados.empty:
    st.warning(
        "Nenhum atendimento da YESHUA RASTREAMENTO foi localizado no período. "
        "Confira se o nome da oficina no cadastro/base está exatamente vinculado."
    )
    st.stop()

# Uma linha consolidada representa o atendimento operacional já classificado
# pelo mesmo motor do painel interno.
classes = dados["Classificação"].fillna("").astype(str)

agendadas = int(
    classes.isin([
        "Executada agendada",
        "Improdutiva agendada",
        "Cancelada",
        "No-show",
        "Possível substituição de OS",
    ]).sum()
)
executadas_ag = int((classes == "Executada agendada").sum())
executadas_extra = int((classes == "Executada extra").sum())
executadas = executadas_ag + executadas_extra

improd_ag = int((classes == "Improdutiva agendada").sum())
improd_extra = int((classes == "Improdutiva extra").sum())
improdutivas = improd_ag + improd_extra

no_show = int((classes == "No-show").sum())
canceladas = int(classes.isin(["Cancelada", "Cancelada extra", "Cancelada no agendamento"]).sum())

# Mesmas leituras operacionais usadas no painel: MCI sobre planejadas;
# MD de improdutividade sobre execuções/desfechos de campo.
mci = (executadas_ag / agendadas * 100) if agendadas else 0.0
base_md = executadas + improdutivas
md = (improdutivas / base_md * 100) if base_md else 0.0

st.subheader(f"Visão do período • {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Planejadas", agendadas)
c2.metric("Executadas", executadas)
c3.metric("Improdutivas", improdutivas)
c4.metric("No-show", no_show)

c5, c6, c7 = st.columns(3)
c5.metric("Canceladas", canceladas)
c6.metric("MCI", f"{mci:.1f}%")
c7.metric("MD • Improdutividade", f"{md:.1f}%")

st.divider()

aba_resumo, aba_improd, aba_noshow, aba_os = st.tabs([
    "📈 Desempenho",
    "🔴 Improdutivas",
    "🚫 No-show",
    "🔎 Minhas OS",
])

with aba_resumo:
    st.markdown("### Evolução diária")
    diario = (
        dados.groupby(["Data Operacional", "Classificação"])
        .size()
        .reset_index(name="Quantidade")
    )
    fig = px.bar(
        diario,
        x="Data Operacional",
        y="Quantidade",
        color="Classificação",
        barmode="stack",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Distribuição dos resultados")
    resumo = (
        classes.value_counts()
        .rename_axis("Classificação")
        .reset_index(name="Quantidade")
    )
    st.dataframe(resumo, use_container_width=True, hide_index=True)

with aba_improd:
    imp = dados[
        classes.isin(["Improdutiva agendada", "Improdutiva extra"])
    ].copy()

    st.markdown(
        f"### {len(imp)} improdutiva(s) no período "
        f"• {improd_ag} agendada(s) • {improd_extra} extra(s)"
    )

    if imp.empty:
        st.success("Nenhuma improdutiva encontrada no período.")
    else:
        motivo_col = "Razao_improdutiva"
        obs_col = "Observacao_tecnico_improdutiva"

        if motivo_col in imp.columns:
            motivos = (
                imp[motivo_col]
                .fillna("Não informado")
                .astype(str)
                .value_counts()
                .rename_axis("Motivo")
                .reset_index(name="Quantidade")
            )
            fig_m = px.bar(
                motivos.head(10),
                x="Quantidade",
                y="Motivo",
                orientation="h",
                text="Quantidade",
            )
            st.plotly_chart(fig_m, use_container_width=True)

        cols = [
            c for c in [
                "Data Operacional", "Classificação", "Ticket", "Placa",
                "OS_planejada", "OS_resultado", motivo_col, obs_col
            ] if c in imp.columns
        ]
        st.dataframe(imp[cols], use_container_width=True, hide_index=True)

with aba_noshow:
    ns = dados[classes == "No-show"].copy()
    st.markdown(f"### {len(ns)} no-show(s) no período")

    if ns.empty:
        st.success("Nenhum no-show encontrado no período.")
    else:
        cols = [
            c for c in [
                "Data Operacional", "Ticket", "Placa",
                "OS_planejada", "OS_resultado", "Consultor", "UF-base"
            ] if c in ns.columns
        ]
        st.dataframe(ns[cols], use_container_width=True, hide_index=True)

with aba_os:
    st.markdown("### Detalhamento operacional")
    tipos = sorted(classes.dropna().unique().tolist())
    filtro_tipo = st.multiselect(
        "Classificação",
        tipos,
        key="portal_filtro_classificacao",
    )

    detalhe = dados.copy()
    if filtro_tipo:
        detalhe = detalhe[detalhe["Classificação"].isin(filtro_tipo)]

    cols = [
        c for c in [
            "Data Operacional", "Classificação", "Ticket", "Placa",
            "OS_planejada", "OS_resultado", "Troca de OS",
            "Razao_improdutiva", "Observacao_tecnico_improdutiva"
        ] if c in detalhe.columns
    ]
    st.dataframe(
        detalhe[cols].sort_values("Data Operacional", ascending=False),
        use_container_width=True,
        hide_index=True,
        height=560,
    )

st.divider()
st.caption(
    "Piloto YESHUA RASTREAMENTO • Dados provenientes da base operacional PS. "
    "Portal somente leitura."
)
