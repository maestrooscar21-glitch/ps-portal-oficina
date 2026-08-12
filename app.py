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

        # Usa o mesmo padrão do painel principal.
        if "SUPABASE_SERVICE_KEY" in st.secrets:
            key = st.secrets["SUPABASE_SERVICE_KEY"]
        elif "SUPABASE_KEY" in st.secrets:
            key = st.secrets["SUPABASE_KEY"]
        else:
            raise KeyError("Chave do Supabase não encontrada.")

    except Exception:
        st.error(
            "O portal ainda não está conectado ao Supabase. "
            "Configure SUPABASE_URL e SUPABASE_SERVICE_KEY "
            "(ou SUPABASE_KEY) nos Secrets do Streamlit."
        )
        st.stop()

    return create_client(url, key)

cliente = obter_cliente_supabase()

# Compatibilidade com o motor reaproveitado do painel principal.
# Algumas funções internas usam os nomes SUPABASE / ERRO_SUPABASE.
SUPABASE = cliente
ERRO_SUPABASE = None

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


def carregar_consolidado_portal_todos_servicos(
    datas: list[str],
) -> pd.DataFrame:
    """Concilia todas as atividades da oficina, não apenas manutenções."""
    partes = []

    for data_operacional in datas:
        planejado = carregar_base(
            "planejado",
            data_operacional,
        )
        resultado = carregar_base(
            "resultado",
            data_operacional,
        )

        if planejado.empty and resultado.empty:
            continue

        conciliacao_data = (
            conciliar_bases_portal_todos_servicos(
                planejado,
                resultado,
            )
        )

        conciliacao_data.insert(
            0,
            "Data Operacional",
            data_operacional,
        )

        partes.append(
            conciliacao_data
        )

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


def conciliar_bases_portal_todos_servicos(
    planejado: pd.DataFrame,
    resultado: pd.DataFrame,
) -> pd.DataFrame:
    """
    Regra híbrida:
    - datas anteriores a DATA_CORTE_NOVA_REGRA usam a lógica histórica;
    - a partir da data de corte, usa primeira aparição da OS para
      classificar Agendada x Extra/Encaixe.
    """
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
            Tipo_resultado=("Tipo de Atividade", "first"),
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
            Tipo_planejado=("Tipo de Atividade", "first"),
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

    conciliacao["Tipo de Serviço"] = conciliacao[
        "Tipo_planejado"
    ].fillna(conciliacao["Tipo_resultado"])

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




def calcular_indicadores(conciliacao: pd.DataFrame) -> dict:
    agendadas_validas = {
        "Executada agendada",
        "Improdutiva agendada",
        "Cancelada",
        "No-show",
        "Status intermediário agendado",
    }

    manutencoes_agendadas = int(
        conciliacao["Classificação"].isin(
            agendadas_validas
        ).sum()
    )

    agendadas_executadas = int(
        (
            conciliacao["Classificação"]
            == "Executada agendada"
        ).sum()
    )

    executadas_extras = int(
        (
            conciliacao["Classificação"]
            == "Executada extra"
        ).sum()
    )

    improdutivas_agendadas = int(
        (
            conciliacao["Classificação"]
            == "Improdutiva agendada"
        ).sum()
    )

    improdutivas_extras = int(
        (
            conciliacao["Classificação"]
            == "Improdutiva extra"
        ).sum()
    )

    improdutivas = (
        improdutivas_agendadas
        + improdutivas_extras
    )

    canceladas = int(
        (conciliacao["Classificação"] == "Cancelada").sum()
    )

    no_show = int(
        (conciliacao["Classificação"] == "No-show").sum()
    )

    mci = (
        agendadas_executadas
        / manutencoes_agendadas
        * 100
        if manutencoes_agendadas
        else 0.0
    )

    base_md = (
        agendadas_executadas
        + executadas_extras
        + improdutivas
    )

    md = (
        improdutivas / base_md * 100
        if base_md
        else 0.0
    )

    return {
        "Planejadas": manutencoes_agendadas,
        "Executadas planejadas": agendadas_executadas,
        "Improdutivas": improdutivas,
        "Improdutivas agendadas": improdutivas_agendadas,
        "Improdutivas extras": improdutivas_extras,
        "Canceladas": canceladas,
        "No-show": no_show,
        "Possíveis substituições de OS": int(
            (
                conciliacao["Classificação"]
                == "Possível substituição de OS"
            ).sum()
        ),
        "Executadas extras": executadas_extras,
        "MCI": mci,
        "MD": md,
        "Índice no-show": (
            no_show / manutencoes_agendadas * 100
            if manutencoes_agendadas
            else 0.0
        ),
        "Índice cancelamento": (
            canceladas / manutencoes_agendadas * 100
            if manutencoes_agendadas
            else 0.0
        ),
        "Execução total": (
            (
                agendadas_executadas
                + executadas_extras
            )
            / manutencoes_agendadas
            * 100
            if manutencoes_agendadas
            else 0.0
        ),
    }




def limpar_telefone(valor) -> str:
    numeros = re.sub(r"\D", "", texto_limpo(valor))

    if numeros.startswith("0") and len(numeros) > 10:
        numeros = numeros[1:]

    if numeros and not numeros.startswith("55"):
        numeros = f"55{numeros}"

    return numeros

def carregar_resposta_mais_recente_follow(follow_id: int) -> dict:
    cliente = exigir_supabase()

    resposta = (
        cliente.table("follow_respostas")
        .select("*")
        .eq("follow_id", follow_id)
        .order("respondido_em", desc=True)
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return {}

    return resposta.data[0]


# =========================================================
# FOLLOW INTEGRADO AO PORTAL DA OFICINA
# =========================================================

MOTIVOS_IMPEDIMENTO_PORTAL = [
    "Veículo indisponível",
    "Cliente solicitou alteração da data",
    "Falta de equipamento ou ferramenta",
    "Falta de peça ou insumo",
    "Problema técnico sem solução",
    "Técnico/equipe indisponível",
    "Oficina sem capacidade para a data",
    "Dificuldade de acesso ou deslocamento",
    "Dados/OS insuficientes para executar",
    "Outro",
]


def buscar_follow_pendentes_portal() -> pd.DataFrame:
    registros = buscar_todos(
        "follow_contatos",
        ordem="data_manutencao",
        desc=False,
    )

    if not registros:
        return pd.DataFrame()

    df = pd.DataFrame(registros)

    if df.empty or "oficina" not in df.columns:
        return pd.DataFrame()

    df["oficina_norm"] = (
        df["oficina"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return df[
        df["oficina_norm"] == OFICINA_PORTAL.upper()
    ].copy()


def carregar_resposta_follow_portal(follow_id: int) -> dict:
    resposta = (
        cliente.table("follow_respostas")
        .select("*")
        .eq("follow_id", follow_id)
        .order("respondido_em", desc=True)
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return {}

    return resposta.data[0]


def enviar_resposta_follow_portal(
    follow: dict,
    nome_respondente: str,
    equipamentos: str,
    veiculo: str,
    capacidade: str,
    tem_impedimento: bool,
    motivos: list[str],
    os_afetadas: list[str],
    observacao: str,
    previsao: str,
) -> None:
    agora = datetime.now().astimezone().isoformat()

    cliente.table("follow_respostas").insert(
        {
            "follow_id": int(follow["id"]),
            "token": str(follow["token"]),
            "nome_respondente": nome_respondente,
            "equipamentos_ok": equipamentos == "Sim",
            "veiculo_disponivel": veiculo,
            "capacidade_ok": capacidade == "Sim",
            "tem_impedimento": tem_impedimento,
            "motivos": motivos,
            "os_afetadas": os_afetadas,
            "observacao": observacao,
            "previsao_solucao": previsao,
            "respondido_em": agora,
        }
    ).execute()

    cliente.table("follow_contatos").update(
        {
            "status": "Respondido",
            "respondido_em": agora,
            "tem_impedimento": tem_impedimento,
            "status_resposta": (
                "Com impedimento"
                if tem_impedimento
                else "Sem impedimento"
            ),
            "ultima_atualizacao": agora,
        }
    ).eq(
        "id",
        int(follow["id"]),
    ).execute()



def gerar_follows_automaticos_portal() -> dict:
    """
    Gera o Follow diretamente da tabela atividades_planejadas.

    Esta versão não depende de bases_importadas para descobrir as datas.
    Ela lê o planejamento vigente salvo no Supabase, filtra:
    - somente manutenções;
    - somente a oficina do portal;
    - somente registros ativos;
    - exclui canceladas;
    - somente hoje e datas futuras.
    """
    hoje = date.today()

    registros = buscar_todos(
        "atividades_planejadas",
        ordem="data_operacional",
        desc=False,
    )

    if not registros:
        return {
            "criados": 0,
            "atualizados": 0,
            "pendentes": 0,
            "datas_detectadas": [],
            "os_detectadas": 0,
        }

    linhas = []

    for registro in registros:
        dados = dict(registro.get("dados") or {})

        linha = {
            "data_operacional": str(
                registro.get("data_operacional") or ""
            ),
            "chave_atendimento": texto_limpo(
                registro.get("chave_atendimento", "")
            ),
            "os": texto_limpo(
                registro.get("os", "")
            ),
            "oficina": texto_limpo(
                registro.get("oficina", "")
            ),
            "tipo_atividade": texto_limpo(
                registro.get("tipo_atividade", "")
            ),
            "status_atividade": texto_limpo(
                registro.get("status_atividade", "")
            ),
            "ativa_no_planejamento": bool(
                registro.get(
                    "ativa_no_planejamento",
                    True,
                )
            ),
        }

        # Fallback para dados históricos armazenados no JSON.
        if not linha["oficina"]:
            linha["oficina"] = texto_limpo(
                dados.get("Oficina", "")
            )

        if not linha["tipo_atividade"]:
            linha["tipo_atividade"] = texto_limpo(
                dados.get("Tipo de Atividade", "")
            )

        if not linha["status_atividade"]:
            linha["status_atividade"] = texto_limpo(
                dados.get("Status da Atividade", "")
            )

        if not linha["os"]:
            linha["os"] = texto_limpo(
                dados.get("OS", "")
            )

        linhas.append(linha)

    df = pd.DataFrame(linhas)

    if df.empty:
        return {
            "criados": 0,
            "atualizados": 0,
            "pendentes": 0,
            "datas_detectadas": [],
            "os_detectadas": 0,
        }

    df["data_dt"] = pd.to_datetime(
        df["data_operacional"],
        errors="coerce",
    ).dt.date

    # Somente datas atuais/futuras.
    df = df[
        df["data_dt"].notna()
        & (df["data_dt"] >= hoje)
    ].copy()

    # Somente registros ainda vigentes no planejamento.
    df = df[
        df["ativa_no_planejamento"] == True
    ].copy()

    # Somente manutenções.
    df = df[
        df["tipo_atividade"].apply(
            lambda valor: (
                "MANUTEN" in normalizar_texto(valor)
            )
        )
    ].copy()

    # Exclui canceladas.
    df = df[
        ~df["status_atividade"].apply(
            status_cancelado
        )
    ].copy()

    # Somente a oficina deste portal.
    df = df[
        df["oficina"].apply(
            normalizar_texto
        ) == normalizar_texto(
            OFICINA_PORTAL
        )
    ].copy()

    if df.empty:
        return {
            "criados": 0,
            "atualizados": 0,
            "pendentes": 0,
            "datas_detectadas": [],
            "os_detectadas": 0,
        }

    # Evita duplicidade da mesma atividade.
    df["chave_unica"] = df.apply(
        lambda linha: (
            texto_limpo(
                linha["chave_atendimento"]
            )
            or (
                f"{linha['data_operacional']}|"
                f"{texto_limpo(linha['os'])}"
            )
        ),
        axis=1,
    )

    df = df.drop_duplicates(
        subset=["data_operacional", "chave_unica"],
        keep="last",
    )

    cadastro = carregar_oficinas()

    consultor = "Não definido"
    telefone = ""
    chave_oficina = normalizar_texto(
        OFICINA_PORTAL
    )

    if not cadastro.empty:
        cadastro_oficina = cadastro[
            cadastro["Oficina"].apply(
                normalizar_texto
            ) == normalizar_texto(
                OFICINA_PORTAL
            )
        ]

        if not cadastro_oficina.empty:
            cad = cadastro_oficina.iloc[0]

            consultor = (
                texto_limpo(
                    cad.get("Consultor", "")
                )
                or "Não definido"
            )
            telefone = texto_limpo(
                cad.get("WhatsApp", "")
            )
            chave_oficina = (
                texto_limpo(
                    cad.get("Chave Oficina", "")
                )
                or chave_oficina
            )

    existentes_raw = buscar_todos(
        "follow_contatos",
        ordem="data_manutencao",
        desc=False,
    )
    existentes = pd.DataFrame(
        existentes_raw
    )

    criados = 0
    atualizados = 0

    for data_operacional, grupo in df.groupby(
        "data_operacional"
    ):
        os_lista = sorted(
            {
                texto_limpo(v)
                for v in grupo["os"]
                if texto_limpo(v)
            }
        )

        quantidade = len(grupo)

        existente = None

        if not existentes.empty:
            mascara = (
                existentes["data_manutencao"]
                .astype(str)
                .eq(str(data_operacional))
            )

            if "oficina" in existentes.columns:
                mascara = mascara & (
                    existentes["oficina"]
                    .fillna("")
                    .astype(str)
                    .apply(normalizar_texto)
                    .eq(
                        normalizar_texto(
                            OFICINA_PORTAL
                        )
                    )
                )

            encontrados = existentes[
                mascara
            ]

            if not encontrados.empty:
                existente = (
                    encontrados
                    .sort_values("id")
                    .iloc[-1]
                    .to_dict()
                )

        agora = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        mensagem = (
            f"Olá! A {OFICINA_PORTAL} possui "
            f"{quantidade} manutenção(ões) "
            f"planejada(s) para "
            f"{pd.to_datetime(data_operacional).strftime('%d/%m/%Y')}. "
            "Acesse o Portal da Oficina e confirme o Follow."
        )

        if existente:
            payload = {
                "qtd_agendadas": quantidade,
                "os_agendadas": os_lista,
                "telefone": telefone,
                "mensagem": mensagem,
                "ultima_atualizacao": agora,
            }

            # Só reabre como pendente se ainda não houve resposta.
            if not existente.get(
                "respondido_em"
            ):
                payload["status"] = "Pendente"

            cliente.table(
                "follow_contatos"
            ).update(
                payload
            ).eq(
                "id",
                int(existente["id"]),
            ).execute()

            atualizados += 1

        else:
            cliente.table(
                "follow_contatos"
            ).insert(
                {
                    "token": str(uuid.uuid4()),
                    "data_follow": hoje.isoformat(),
                    "data_manutencao": (
                        data_operacional
                    ),
                    "chave_oficina": chave_oficina,
                    "oficina": OFICINA_PORTAL,
                    "consultor": consultor,
                    "telefone": telefone,
                    "qtd_agendadas": quantidade,
                    "os_agendadas": os_lista,
                    "mensagem": mensagem,
                    "status": "Pendente",
                    "preparado_em": agora,
                    "ultima_atualizacao": agora,
                }
            ).execute()

            criados += 1

    follows = buscar_follow_pendentes_portal()

    pendentes = 0

    if not follows.empty:
        follows["data_dt"] = pd.to_datetime(
            follows["data_manutencao"],
            errors="coerce",
        ).dt.date

        pendentes = int(
            (
                follows["data_dt"].notna()
                & (follows["data_dt"] >= hoje)
                & (follows["respondido_em"].isna() | follows["respondido_em"].astype(str).str.strip().str.lower().isin(["", "nan", "none", "nat"]))
            ).sum()
        )

    return {
        "criados": criados,
        "atualizados": atualizados,
        "pendentes": pendentes,
        "datas_detectadas": sorted(
            df["data_operacional"]
            .astype(str)
            .unique()
            .tolist()
        ),
        "os_detectadas": len(df),
    }


def resumo_alerta_follow_portal() -> tuple[int, int]:
    """
    Retorna:
    (quantidade de datas com Follow pendente,
     quantidade total de manutenções aguardando confirmação)
    """
    follows = buscar_follow_pendentes_portal()

    if follows.empty:
        return 0, 0

    hoje = date.today()

    follows["data_dt"] = pd.to_datetime(
        follows["data_manutencao"],
        errors="coerce",
    ).dt.date

    pendentes = follows[
        follows["data_dt"].notna()
        & (follows["data_dt"] >= hoje)
        & (follows["respondido_em"].isna() | follows["respondido_em"].astype(str).str.strip().str.lower().isin(["", "nan", "none", "nat"]))
    ].copy()

    if pendentes.empty:
        return 0, 0

    return (
        len(pendentes),
        int(
            pendentes["qtd_agendadas"]
            .fillna(0)
            .astype(int)
            .sum()
        ),
    )


def exibir_follow_portal() -> None:
    st.markdown("### 📞 Follow de Manutenções")
    st.caption(
        "As manutenções planejadas aparecem aqui automaticamente. "
        "A oficina deve confirmar se está tudo OK ou informar impedimentos."
    )

    follows = buscar_follow_pendentes_portal()

    if follows.empty:
        st.success("Você não possui Follow disponível no momento.")
        return

    hoje = date.today()

    follows["data_dt"] = pd.to_datetime(
        follows["data_manutencao"],
        errors="coerce",
    ).dt.date

    pendentes = follows[
        follows["data_dt"].notna()
        & (follows["data_dt"] >= hoje)
    ].copy()

    if pendentes.empty:
        st.info("Não há Follow pendente para datas atuais ou futuras.")
    else:
        st.markdown("#### Pendências para confirmação")

        for _, row in pendentes.sort_values("data_dt").iterrows():
            follow = row.to_dict()
            data_txt = pd.to_datetime(
                follow["data_manutencao"]
            ).strftime("%d/%m/%Y")
            qtd = int(follow.get("qtd_agendadas") or 0)

            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"#### {data_txt}")
                c1.caption(
                    f"{qtd} manutenção(ões) prevista(s)"
                )
                c2.metric(
                    "Status",
                    str(follow.get("status") or "Preparado"),
                )
                status_resposta_valor = follow.get("status_resposta")
                status_resposta_txt = (
                    str(status_resposta_valor).strip()
                    if pd.notna(status_resposta_valor)
                    and str(status_resposta_valor).strip().lower()
                    not in ("", "nan", "none", "nat")
                    else "Pendente"
                )

                c3.metric(
                    "Resposta",
                    status_resposta_txt,
                )

                os_lista = [
                    str(x)
                    for x in (follow.get("os_agendadas") or [])
                    if str(x).strip()
                ]

                if os_lista:
                    st.markdown("**OS previstas para confirmação**")

                    # Busca detalhes do planejamento futuro para exibir
                    # cada OS separadamente, preservando o Follow diário.
                    detalhes_os = carregar_planejamento_futuro_portal()

                    if not detalhes_os.empty:
                        detalhes_os = detalhes_os[
                            detalhes_os["OS"]
                            .astype(str)
                            .isin(os_lista)
                        ].copy()

                    if not detalhes_os.empty:
                        colunas_follow = [
                            "OS",
                            "Cliente",
                            "Local",
                            "Tipo de Serviço",
                            "Status",
                        ]
                        colunas_follow = [
                            c
                            for c in colunas_follow
                            if c in detalhes_os.columns
                        ]

                        st.dataframe(
                            detalhes_os[colunas_follow]
                            .drop_duplicates(
                                subset=["OS"]
                            )
                            .sort_values("OS"),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.dataframe(
                            pd.DataFrame(
                                {"OS": os_lista}
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

                respondido_em = follow.get("respondido_em")
                ja_respondido = (
                    pd.notna(respondido_em)
                    and str(respondido_em).strip().lower()
                    not in ("", "nan", "none", "nat")
                )

                if ja_respondido:
                    resposta = carregar_resposta_follow_portal(
                        int(follow["id"])
                    )

                    tem_impedimento_valor = follow.get("tem_impedimento")
                    tem_impedimento_registrado = (
                        pd.notna(tem_impedimento_valor)
                        and bool(tem_impedimento_valor)
                    )

                    if tem_impedimento_registrado:
                        st.warning(
                            "⚠️ Follow respondido com impedimento."
                        )
                    else:
                        st.success(
                            "✅ Follow respondido sem impedimento."
                        )

                    if resposta:
                        nome = str(
                            resposta.get("nome_respondente") or ""
                        )
                        motivos = resposta.get("motivos") or []
                        observacao = str(
                            resposta.get("observacao") or ""
                        )

                        if nome:
                            st.write(
                                f"**Respondente:** {nome}"
                            )
                        if motivos:
                            st.write(
                                "**Motivos:** "
                                + " | ".join(map(str, motivos))
                            )
                        if observacao:
                            st.write(
                                f"**Observação:** {observacao}"
                            )
                    continue

                with st.form(
                    f"follow_portal_{int(follow['id'])}"
                ):
                    nome = st.text_input(
                        "Seu nome",
                        key=f"nome_{follow['id']}",
                    )

                    equipamentos = st.radio(
                        "Todos os equipamentos/ferramentas estão disponíveis?",
                        ["Sim", "Não"],
                        horizontal=True,
                        key=f"equip_{follow['id']}",
                    )

                    veiculo = st.radio(
                        "O(s) veículo(s) estará(ão) disponível(is)?",
                        ["Sim", "Não", "Não sei"],
                        horizontal=True,
                        key=f"veic_{follow['id']}",
                    )

                    capacidade = st.radio(
                        "A oficina possui técnico/capacidade para atender?",
                        ["Sim", "Não"],
                        horizontal=True,
                        key=f"cap_{follow['id']}",
                    )

                    impedimento = st.radio(
                        "Existe algum impedimento para a execução?",
                        [
                            "Não, está tudo OK",
                            "Sim, existe impedimento",
                        ],
                        key=f"imp_{follow['id']}",
                    )

                    tem_impedimento = (
                        impedimento == "Sim, existe impedimento"
                    )

                    motivos = []
                    os_afetadas = []
                    observacao = ""
                    previsao = ""

                    if tem_impedimento:
                        motivos = st.multiselect(
                            "Qual(is) o(s) impedimento(s)?",
                            MOTIVOS_IMPEDIMENTO_PORTAL,
                            key=f"motivos_{follow['id']}",
                        )

                        if os_lista:
                            os_afetadas = st.multiselect(
                                "Quais OS podem ser afetadas?",
                                os_lista,
                                key=f"osafet_{follow['id']}",
                            )

                        observacao = st.text_area(
                            "Explique o impedimento",
                            key=f"obs_{follow['id']}",
                        )

                        previsao = st.text_input(
                            "Previsão de solução (opcional)",
                            key=f"prev_{follow['id']}",
                        )
                    else:
                        observacao = st.text_area(
                            "Observação (opcional)",
                            key=f"obsok_{follow['id']}",
                        )

                    enviar = st.form_submit_button(
                        "Enviar confirmação",
                        type="primary",
                        use_container_width=True,
                    )

                if enviar:
                    if not nome.strip():
                        st.error("Informe seu nome.")
                        return

                    if tem_impedimento and not motivos:
                        st.error(
                            "Selecione ao menos um motivo."
                        )
                        return

                    enviar_resposta_follow_portal(
                        follow=follow,
                        nome_respondente=nome,
                        equipamentos=equipamentos,
                        veiculo=veiculo,
                        capacidade=capacidade,
                        tem_impedimento=tem_impedimento,
                        motivos=motivos,
                        os_afetadas=os_afetadas,
                        observacao=observacao,
                        previsao=previsao,
                    )

                    st.success(
                        "Resposta enviada para a gestão."
                    )
                    st.rerun()

    st.divider()
    st.markdown("#### Histórico recente")

    historico = follows[
        follows["respondido_em"].notna()
        & ~follows["respondido_em"].astype(str).str.strip().str.lower().isin(
            ["", "nan", "none", "nat"]
        )
    ].copy()

    if historico.empty:
        st.caption("Nenhuma resposta registrada ainda.")
    else:
        cols = [
            c
            for c in [
                "data_manutencao",
                "qtd_agendadas",
                "status_resposta",
                "respondido_em",
            ]
            if c in historico.columns
        ]

        st.dataframe(
            historico[cols].sort_values(
                "data_manutencao",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )



def calcular_indicadores_portal_todos_servicos(
    conciliacao: pd.DataFrame,
) -> dict:
    classes = conciliacao[
        "Classificação"
    ].fillna("").astype(str)

    planejadas_validas = {
        "Executada agendada",
        "Improdutiva agendada",
        "Cancelada",
        "No-show",
        "Status intermediário agendado",
    }

    planejadas = int(
        classes.isin(
            planejadas_validas
        ).sum()
    )

    executadas_agendadas = int(
        (
            classes
            == "Executada agendada"
        ).sum()
    )

    executadas_extras = int(
        (
            classes
            == "Executada extra"
        ).sum()
    )

    improdutivas_agendadas = int(
        (
            classes
            == "Improdutiva agendada"
        ).sum()
    )

    improdutivas_extras = int(
        (
            classes
            == "Improdutiva extra"
        ).sum()
    )

    no_show = int(
        (
            classes
            == "No-show"
        ).sum()
    )

    canceladas = int(
        (
            classes
            == "Cancelada"
        ).sum()
    )

    base_executavel = max(
        planejadas - canceladas,
        0,
    )

    indice_execucao = (
        executadas_agendadas
        / base_executavel
        * 100
        if base_executavel
        else 0.0
    )

    perdas_agendadas = (
        improdutivas_agendadas
        + no_show
    )

    indice_perda = (
        perdas_agendadas
        / base_executavel
        * 100
        if base_executavel
        else 0.0
    )

    if (
        indice_execucao >= 90
        and indice_perda <= 10
    ):
        nivel = "Excelente"
        simbolo = "🟢"
        mensagem = (
            "Ótimo aproveitamento do planejamento. "
            "Mantenha o ritmo e continue prevenindo perdas."
        )
    elif (
        indice_execucao >= 75
        and indice_perda <= 20
    ):
        nivel = "Atenção"
        simbolo = "🟡"
        mensagem = (
            "O desempenho está razoável, mas existem perdas "
            "que podem ser reduzidas."
        )
    else:
        nivel = "Crítico"
        simbolo = "🔴"
        mensagem = (
            "Há perda relevante do planejamento. "
            "Priorize No-show, improdutivas e pendências futuras."
        )

    return {
        "Planejadas": planejadas,
        "Executadas agendadas": executadas_agendadas,
        "Executadas extras": executadas_extras,
        "Executadas totais": (
            executadas_agendadas
            + executadas_extras
        ),
        "Improdutivas": (
            improdutivas_agendadas
            + improdutivas_extras
        ),
        "Improdutivas agendadas": improdutivas_agendadas,
        "Improdutivas extras": improdutivas_extras,
        "No-show": no_show,
        "Canceladas": canceladas,
        "Índice de execução": indice_execucao,
        "Índice de perda": indice_perda,
        "Nível": nivel,
        "Símbolo": simbolo,
        "Mensagem": mensagem,
    }


def carregar_planejamento_futuro_portal() -> pd.DataFrame:
    """
    Planejamento futuro de TODOS os tipos de serviço da oficina.
    Follow continua sendo exclusivo para manutenções.
    """
    registros = buscar_todos(
        "atividades_planejadas",
        ordem="data_operacional",
        desc=False,
    )

    if not registros:
        return pd.DataFrame()

    linhas = []

    for registro in registros:
        dados_json = dict(
            registro.get("dados")
            or {}
        )

        cliente_nome = (
            texto_limpo(
                registro.get("cliente", "")
            )
            or texto_limpo(
                dados_json.get("Cliente", "")
            )
        )

        local_servico = (
            texto_limpo(
                registro.get("cidade", "")
            )
            or texto_limpo(
                dados_json.get("Cidade", "")
            )
            or texto_limpo(
                dados_json.get("Local", "")
            )
            or texto_limpo(
                dados_json.get("Localidade", "")
            )
        )

        linha = {
            "Data": str(
                registro.get(
                    "data_operacional"
                )
                or ""
            ),
            "OS": texto_limpo(
                registro.get("os", "")
            )
            or texto_limpo(
                dados_json.get("OS", "")
            ),
            "Cliente": cliente_nome,
            "Local": local_servico,
            "Oficina": texto_limpo(
                registro.get("oficina", "")
            )
            or texto_limpo(
                dados_json.get("Oficina", "")
            ),
            "Tipo de Serviço": texto_limpo(
                registro.get(
                    "tipo_atividade",
                    "",
                )
            )
            or texto_limpo(
                dados_json.get(
                    "Tipo de Atividade",
                    "",
                )
            ),
            "Status": texto_limpo(
                registro.get(
                    "status_atividade",
                    "",
                )
            )
            or texto_limpo(
                dados_json.get(
                    "Status da Atividade",
                    "",
                )
            ),
            "Ativa": bool(
                registro.get(
                    "ativa_no_planejamento",
                    True,
                )
            ),
        }

        linhas.append(linha)

    df = pd.DataFrame(
        linhas
    )

    if df.empty:
        return df

    df["Data_dt"] = pd.to_datetime(
        df["Data"],
        errors="coerce",
    ).dt.date

    hoje = date.today()

    df = df[
        df["Data_dt"].notna()
        & (df["Data_dt"] >= hoje)
        & (df["Ativa"] == True)
    ].copy()

    df = df[
        df["Oficina"].apply(
            normalizar_texto
        )
        == normalizar_texto(
            OFICINA_PORTAL
        )
    ].copy()

    df = df[
        ~df["Status"].apply(
            status_cancelado
        )
    ].copy()

    return df





# =========================================================
# DETALHAMENTO CLICÁVEL DOS INDICADORES DO PORTAL
# =========================================================

def definir_detalhe_portal(filtro: str) -> None:
    st.session_state["portal_detalhe_ativo"] = filtro


def limpar_detalhe_portal() -> None:
    st.session_state["portal_detalhe_ativo"] = None


def filtrar_detalhe_portal(base: pd.DataFrame, filtro: str) -> pd.DataFrame:
    classes = base["Classificação"].fillna("").astype(str)

    mapa = {
        "Planejados": [
            "Executada agendada",
            "Improdutiva agendada",
            "Cancelada",
            "No-show",
            "Status intermediário agendado",
        ],
        "Executados": [
            "Executada agendada",
            "Executada extra",
        ],
        "Não concluídos": [
            "Improdutiva agendada",
            "Improdutiva extra",
        ],
        "No-show": ["No-show"],
        "Cancelados": ["Cancelada"],
        "Execuções extras": ["Executada extra"],
    }

    classes_filtro = mapa.get(filtro, [])
    return base[classes.isin(classes_filtro)].copy()


def exibir_card_portal(coluna, titulo: str, valor, filtro: str | None = None) -> None:
    coluna.metric(titulo, valor)

    if filtro:
        coluna.button(
            "🔎 Ver OS",
            key="portal_ver_" + normalizar_texto(filtro).lower().replace(" ", "_"),
            on_click=definir_detalhe_portal,
            args=(filtro,),
            use_container_width=True,
        )


def exibir_detalhe_portal(base: pd.DataFrame) -> None:
    filtro = st.session_state.get("portal_detalhe_ativo")
    if not filtro:
        return

    detalhe = filtrar_detalhe_portal(base, filtro)

    st.markdown("---")
    st.subheader(f"🔎 Conferência das OS — {filtro}")
    st.caption(
        f"Foram encontrados {len(detalhe)} atendimento(s) "
        "da oficina no período selecionado."
    )

    colunas = [
        "Data Operacional",
        "Tipo de Serviço",
        "Classificação",
        "Ticket",
        "Placa",
        "OS_planejada",
        "OS_resultado",
        "Status_planejado",
        "Status_resultado",
        "Razao_improdutiva",
        "Observacao_tecnico_improdutiva",
        "Motivo da Classificação",
    ]
    colunas = [c for c in colunas if c in detalhe.columns]

    exibicao = detalhe[colunas].copy().rename(
        columns={
            "OS_planejada": "OS planejada",
            "OS_resultado": "OS resultado",
            "Status_planejado": "Status planejado",
            "Status_resultado": "Status resultado",
            "Razao_improdutiva": "Razão da Improdutiva",
            "Observacao_tecnico_improdutiva": "Observação do Técnico",
        }
    )

    st.dataframe(
        exibicao,
        use_container_width=True,
        hide_index=True,
        height=500,
    )

    if st.button(
        "✖ Fechar",
        key="portal_fechar_detalhe",
    ):
        limpar_detalhe_portal()
        st.rerun()


# =========================================================
# PORTAL YESHUA — MVP 1.0 (SOMENTE LEITURA)
# =========================================================

st.title("🏢 YESHUA RASTREAMENTO")
st.caption("Portal Operacional • Planejamento, execução e Follow")

st.info(
    "Portal piloto com Follow automático. As manutenções planejadas importadas "
    "pela gestão aparecem automaticamente para confirmação da oficina."
)

try:
    bases = listar_bases()
except Exception as exc:
    st.error(f"Não foi possível consultar as bases operacionais: {exc}")
    st.stop()

if bases is None or bases.empty:
    st.warning("Ainda não existem bases operacionais disponíveis.")
    st.stop()


# Gera/atualiza automaticamente as pendências de Follow a partir
# das manutenções planejadas da própria oficina.
resultado_follow_automatico = {
    "criados": 0,
    "atualizados": 0,
    "pendentes": 0,
    "datas_detectadas": [],
    "os_detectadas": 0,
}

try:
    resultado_follow_automatico = (
        gerar_follows_automaticos_portal()
    )
except Exception as erro_follow:
    st.warning(
        "Os indicadores estão disponíveis, mas não foi possível "
        f"atualizar o Follow automático neste momento: {erro_follow}"
    )

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
    st.caption("Portal da Oficina • MVP 1.3.2")

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
    consolidado = carregar_consolidado_portal_todos_servicos(datas_periodo)
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

# Série de classificações usada nas análises e abas do portal.
classes = dados["Classificação"].fillna("").astype(str)

if dados.empty:
    st.warning(
        "Nenhum atendimento da YESHUA RASTREAMENTO foi localizado no período. "
        "Confira se o nome da oficina no cadastro/base está exatamente vinculado."
    )
    st.stop()

# Indicadores do Portal: todos os tipos de serviço.
indicadores = calcular_indicadores_portal_todos_servicos(
    dados
)

planejadas = indicadores["Planejadas"]
executadas_ag = indicadores["Executadas agendadas"]
executadas_extra = indicadores["Executadas extras"]
executadas = indicadores["Executadas totais"]
improdutivas = indicadores["Improdutivas"]
improd_ag = indicadores["Improdutivas agendadas"]
improd_extra = indicadores["Improdutivas extras"]
no_show = indicadores["No-show"]
canceladas = indicadores["Canceladas"]
indice_execucao = indicadores["Índice de execução"]
indice_perda = indicadores["Índice de perda"]

st.subheader(
    f"Seu desempenho • "
    f"{inicio.strftime('%d/%m/%Y')} a "
    f"{fim.strftime('%d/%m/%Y')}"
)

st.markdown(
    f"### {indicadores['Símbolo']} "
    f"Termômetro operacional: **{indicadores['Nível']}**"
)
st.caption(
    indicadores["Mensagem"]
)

c1, c2, c3, c4 = st.columns(4)

exibir_card_portal(c1, "Serviços planejados", planejadas, "Planejados")
exibir_card_portal(c2, "Executados", executadas, "Executados")
exibir_card_portal(c3, "Não concluídos", improdutivas, "Não concluídos")
exibir_card_portal(c4, "No-show", no_show, "No-show")

c5, c6, c7, c8 = st.columns(4)

exibir_card_portal(c5, "Cancelados", canceladas, "Cancelados")
exibir_card_portal(c6, "Execuções extras", executadas_extra, "Execuções extras")
exibir_card_portal(c7, "Índice de execução", f"{indice_execucao:.1f}%")
exibir_card_portal(c8, "Índice de perda", f"{indice_perda:.1f}%")

st.caption(
    "Índice de execução = executados do planejamento ÷ "
    "(planejados − cancelados). "
    "Índice de perda = improdutivas agendadas + No-show ÷ "
    "(planejados − cancelados)."
)


exibir_detalhe_portal(dados)

# Planejamento futuro de todos os tipos de atividade.
planejamento_futuro = (
    carregar_planejamento_futuro_portal()
)

if not planejamento_futuro.empty:
    hoje = date.today()
    fim_semana = hoje + timedelta(
        days=6
    )

    proximos_7 = planejamento_futuro[
        planejamento_futuro["Data_dt"]
        <= fim_semana
    ].copy()

    if not proximos_7.empty:
        st.info(
            f"📅 Você possui **{len(proximos_7)} serviço(s)** "
            "planejado(s) para os próximos 7 dias. "
            "O objetivo é converter o máximo possível desse planejamento."
        )

        with st.expander(
            "Ver planejamento dos próximos 7 dias"
        ):
            st.caption(
                "Cada OS aparece separadamente para facilitar "
                "a análise de cada atendimento."
            )

            colunas_planejamento = [
                "Data",
                "OS",
                "Cliente",
                "Local",
                "Tipo de Serviço",
                "Status",
            ]

            colunas_planejamento = [
                coluna
                for coluna in colunas_planejamento
                if coluna in proximos_7.columns
            ]

            st.dataframe(
                proximos_7[
                    colunas_planejamento
                ].sort_values(
                    ["Data", "OS"]
                ),
                use_container_width=True,
                hide_index=True,
                height=420,
            )

st.divider()

qtd_follows_pendentes, qtd_os_follow_pendentes = (
    resumo_alerta_follow_portal()
)

rotulo_follow = (
    f"🔴 Follow ({qtd_follows_pendentes})"
    if qtd_follows_pendentes
    else "✅ Follow"
)

aba_resumo, aba_improd, aba_noshow, aba_os, aba_follow = st.tabs([
    "📊 Resumo",
    "🔴 Não concluídos",
    "🚫 No-show",
    "🔎 Serviços",
    rotulo_follow,
])


if qtd_follows_pendentes:
    st.warning(
        f"⚠️ Você possui {qtd_os_follow_pendentes} manutenção(ões) "
        f"em {qtd_follows_pendentes} data(s) aguardando confirmação "
        "de Follow. Acesse a aba Follow e responda."
    )

datas_planejamento_detectadas = (
    resultado_follow_automatico.get(
        "datas_detectadas",
        [],
    )
)

if datas_planejamento_detectadas:
    datas_formatadas = ", ".join(
        pd.to_datetime(data).strftime("%d/%m/%Y")
        for data in datas_planejamento_detectadas
    )

    st.caption(
        "Planejamento futuro detectado para a oficina: "
        f"**{datas_formatadas}** · "
        f"{resultado_follow_automatico.get('os_detectadas', 0)} "
        "manutenção(ões) vigente(s)."
    )

with aba_resumo:
    st.markdown("### Serviços por tipo")

    if "Tipo de Serviço" in dados.columns:
        tipos_resumo = (
            dados[
                "Tipo de Serviço"
            ]
            .fillna("Não informado")
            .astype(str)
            .value_counts()
            .rename_axis(
                "Tipo de Serviço"
            )
            .reset_index(
                name="Quantidade"
            )
        )

        st.dataframe(
            tipos_resumo,
            use_container_width=True,
            hide_index=True,
        )

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
        f"### {len(imp)} serviço(s) não concluído(s) no período "
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
                "Data Operacional", "Tipo de Serviço", "Classificação",
                "Ticket", "Placa", "OS_planejada", "OS_resultado",
                motivo_col, obs_col
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
                "Data Operacional", "Tipo de Serviço", "Ticket", "Placa",
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
            "Data Operacional", "Tipo de Serviço", "Classificação",
            "Ticket", "Placa", "OS_planejada", "OS_resultado", "Troca de OS",
            "Razao_improdutiva", "Observacao_tecnico_improdutiva"
        ] if c in detalhe.columns
    ]
    st.dataframe(
        detalhe[cols].sort_values("Data Operacional", ascending=False),
        use_container_width=True,
        hide_index=True,
        height=560,
    )

with aba_follow:
    exibir_follow_portal()

st.divider()
st.caption(
    "Piloto YESHUA RASTREAMENTO • Dados provenientes da base operacional PS. "
    "Portal com Follow automático por planejamento."
)
