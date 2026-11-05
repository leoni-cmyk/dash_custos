"""
Lógica de dados do Dashboard de Custos (sem dependência de Streamlit).
"""
import re
import unicodedata
import pandas as pd
import numpy as np

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
ORDEM_CLASSIF = ["Administrativo", "Apoio", "Produtivo", "Neutro"]

# Ordem exata das contas para o Relatório Gerencial
ORDEM_CONTAS = [
    "Despesas com Pessoal", "Pessoal Terceirizado", "Outras Despesas de Pessoal com/sem Vínculo", 
    "Material de Uso na Saúde", "Material de Uso e Consumo", "Materiais de Uso Educacional",
    "Manutenção", "Serviços Terceirizados", "Propaganda e Publicidade", "Tecnologia da Informação",
    "Serviços Essenciais", "Apoio Discente", "Bolsa Residencia", "Demais Despesas", "Seguros",
    "Despesas Financeiras", "Impostos, Taxas e Multas", "Aluguéis", "Depreciação"
]

# ----------------------------------------------------------------------
# Campos esperados
# ----------------------------------------------------------------------
CAMPOS_DIRETO = [
    ("periodo", "Período", True, ["periodo", "competencia", "mes", "ano mes", "anomes", "cdperiodocompetencia"]),
    ("cc_nome", "Centro de custo (nome)", True, ["centro de custo", "nome centro de custo", "cc", "descricao", "nocentrocusto"]),
    ("classificacao", "Classificação", True, ["classificacao", "classificacao cc", "tipo", "classificacaocc"]),
    ("segmento", "Segmento", True, ["segmento", "unidade", "seguimento"]),
    ("valor", "Valor", True, ["valor", "valor rs", "vlr", "total", "vllancamentocentrocusto total"]),
    ("cc_codigo", "Centro de custo (código)", False, ["codigo", "cod", "codigo centro de custo", "codigo cc", "cdcentrocusto"]),
    ("grupo", "Grupo de conta", False, ["grupo de conta", "grupo", "conta", "nogrupoconta"]),
]

CAMPOS_INDIRETO = [
    ("periodo", "Período", True, ["periodo", "competencia", "mes", "anomes", "periodo_competencia"]),
    ("destino_nome", "Centro de custo DESTINO (nome)", True, ["destino", "nome_centrocusto_destino"]),
    ("valor", "Valor", True, ["valor", "valor rs", "vlr", "total", "valor_rateio total"]),
    ("origem_nome", "Centro de custo ORIGEM (nome)", False, ["origem", "nome_centrocusto_origem"]),
    ("destino_codigo", "Destino (código)", False, ["cod destino", "codigo", "cod_centrocusto_destino"]),
    ("origem_codigo", "Origem (código)", False, ["cod origem", "cod_centrocusto_origem"]),
    ("destino_classificacao", "Classificação do destino", False, ["classificacao destino", "classificacao_destino"]),
    ("destino_segmento", "Segmento do destino", False, ["segmento destino", "noseguimento_destino"]),
    ("origem_classificacao", "Classificação da origem", False, ["classificacao origem", "classificacao_origem"]),
    ("origem_segmento", "Segmento da origem", False, ["segmento origem", "noseguimento_origem"]),
]

# ----------------------------------------------------------------------
# Formatação e Datas
# ----------------------------------------------------------------------
def brl(v) -> str:
    if pd.isna(v): return "–"
    n = round(float(v or 0))
    s = f"{abs(n):,.0f}".replace(",", ".")
    return ("-" if n < 0 else "") + "R$ " + s

def pct(a, b) -> str:
    return f"{a / b * 100:.1f}".replace(".", ",") + "%" if b else "–"

def ano_mes_dict(periodos) -> dict:
    res = {}
    for p in periodos:
        p = str(p)
        if len(p) >= 6:
            a, m = p[:4], p[4:6]
            if a not in res: res[a] = []
            if m not in res[a]: res[a].append(m)
    for a in res: res[a].sort()
    return res

def rotulo_mes(m: str) -> str:
    try: return MESES[int(m) - 1]
    except: return m

def rotulo_periodo(p: str) -> str:
    try: return f"{MESES[int(p[4:6]) - 1]}/{p[2:4]}"
    except: return str(p)

def formatar_periodo(a, m) -> str:
    return f"{a}{m}"

def _norm_txt(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def auto_mapear(colunas, campos) -> dict:
    por_norm = {_norm_txt(c): c for c in colunas}
    usadas, mapa = set(), {}
    for chave, _rot, _obr, apelidos in campos:
        mapa[chave] = None
        for a in apelidos:
            col = por_norm.get(_norm_txt(a))
            if col is not None and col not in usadas:
                mapa[chave] = col
                usadas.add(col)
                break
    return mapa

def _periodo(v) -> str | None:
    if pd.isna(v): return None
    if hasattr(v, "strftime"): return v.strftime("%Y%m")
    s = str(v).strip()
    if re.fullmatch(r"\d{6}", s): return s
    if re.fullmatch(r"\d{6}\.0", s): return s[:6]
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?(?:\s.*)?", s)
    if m: return f"{m.group(1)}{int(m.group(2)):02d}"
    m = re.fullmatch(r"(\d{1,2})[-/](\d{4})", s)
    if m: return f"{m.group(2)}{int(m.group(1)):02d}"
    return s

def _valor(serie: pd.Series) -> pd.Series:
    if serie.dtype == object:
        serie = (serie.astype(str).str.replace("R$", "", regex=False).str.strip()
                 .str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(serie, errors="coerce")

def normalizar_direto(raw: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    c = lambda ch: raw[mapa[ch]].astype("string").str.strip().mask(raw[mapa[ch]].isin(["", "nan", "None", "<NA>"])) if mapa.get(ch) else pd.Series(pd.NA, index=raw.index)
    nome, cod = c("cc_nome"), c("cc_codigo")
    df = pd.DataFrame({
        "periodo": raw[mapa["periodo"]].map(_periodo), "cc_id": cod.fillna(nome), "cc_nome": nome,
        "classificacao": c("classificacao"), "segmento": c("segmento"), "grupo": c("grupo"), "valor": _valor(raw[mapa["valor"]])
    })
    return df.dropna(subset=["periodo", "cc_id", "valor"]).reset_index(drop=True)

def normalizar_indireto(raw: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    c = lambda ch: raw[mapa[ch]].astype("string").str.strip().mask(raw[mapa[ch]].isin(["", "nan", "None", "<NA>"])) if mapa.get(ch) else pd.Series(pd.NA, index=raw.index)
    dn, dc, on, oc = c("destino_nome"), c("destino_codigo"), c("origem_nome"), c("origem_codigo")
    df = pd.DataFrame({
        "periodo": raw[mapa["periodo"]].map(_periodo), "destino_id": dc.fillna(dn), "destino_nome": dn,
        "destino_classificacao": c("destino_classificacao"), "destino_segmento": c("destino_segmento"),
        "origem_id": oc.fillna(on), "origem_nome": on, "origem_classificacao": c("origem_classificacao"),
        "origem_segmento": c("origem_segmento"), "valor": _valor(raw[mapa["valor"]])
    })
    return df.dropna(subset=["periodo", "destino_id", "valor"]).reset_index(drop=True)

# ----------------------------------------------------------------------
# Agregações Analíticas
# ----------------------------------------------------------------------
def tem_origem(ind: pd.DataFrame) -> bool: return ind is not None and ind["origem_id"].notna().any()

def montar_cadastro(direto: pd.DataFrame, indireto: pd.DataFrame) -> pd.DataFrame:
    cols = ["cc_id", "cc_nome", "classificacao", "segmento"]
    partes = [direto[cols]]
    for lado in ("destino", "origem"):
        p = indireto[[f"{lado}_id", f"{lado}_nome", f"{lado}_classificacao", f"{lado}_segmento"]]
        p.columns = cols; partes.append(p.dropna(subset=["cc_id"]))
    cad = pd.concat(partes, ignore_index=True).groupby("cc_id", as_index=False).first()
    cad["cc_nome"] = cad["cc_nome"].fillna(cad["cc_id"])
    cad["classificacao"] = cad["classificacao"].fillna("Sem classificação")
    cad["segmento"] = cad["segmento"].fillna("Sem segmento")
    return cad.astype(str)

def diagnostico(direto, indireto, cad) -> list[str]:
    avisos, ids_cad = [], set(direto["cc_id"])
    for lado in ("destino", "origem"):
        ids = set(indireto[f"{lado}_id"].dropna())
        fora = ids - ids_cad
        if ids and len(fora) / len(ids) > 0.5: avisos.append(f"{len(fora)} centros de {lado} não estão na base direta.")
    if not tem_origem(indireto): avisos.append("A base indireta não tem centro de ORIGEM.")
    return avisos

def periodos_disponiveis(direto, indireto) -> list[str]:
    return sorted(set(direto["periodo"]) | set(indireto["periodo"]))

def resumo_centros(direto, indireto, cad, periodos) -> pd.DataFrame:
    dd = direto[direto["periodo"].isin(periodos)]
    ii = indireto[indireto["periodo"].isin(periodos)]
    out = cad.set_index("cc_id")[["cc_nome", "classificacao", "segmento"]].copy()
    out["direto"] = dd.groupby("cc_id")["valor"].sum()
    out["recebido"] = ii.groupby("destino_id")["valor"].sum()
    out["rateado"] = ii.groupby("origem_id")["valor"].sum()
    out[["direto", "recebido", "rateado"]] = out[["direto", "recebido", "rateado"]].fillna(0.0)
    out.loc[out["classificacao"] == "Produtivo", "rateado"] = 0.0
    out["total"] = out["direto"] + out["recebido"]
    return out.reset_index()

def filtrar_centros(res, classificacoes=None, segmentos=None, busca="") -> pd.DataFrame:
    m = pd.Series(True, index=res.index)
    if classificacoes: m &= res["classificacao"].isin(classificacoes)
    if segmentos: m &= res["segmento"].isin(segmentos)
    if busca:
        q = busca.lower().strip()
        m &= res["cc_nome"].str.lower().str.contains(q, regex=False) | res["cc_id"].str.contains(q, regex=False)
    res = res[m]
    return res[(res[["direto", "recebido", "rateado"]] != 0).any(axis=1)]

def kpis(res: pd.DataFrame) -> dict:
    d, r, o = res["direto"].sum(), res["recebido"].sum(), res["rateado"].sum()
    return {"direto": d, "recebido": r, "total": d + r, "pct_indireto": (r / (d + r) * 100) if (d + r) else 0.0, "rateado": o}

def resumo_segmentos(res: pd.DataFrame) -> pd.DataFrame:
    g = res.groupby("segmento")[["direto", "recebido", "rateado"]].sum()
    g["total"] = g["direto"] + g["recebido"]
    return g.sort_values("total", ascending=False).reset_index()

def matriz_segmentos(indireto, cad, ids_origem, periodos) -> pd.DataFrame:
    ii = indireto[indireto["periodo"].isin(periodos) & indireto["origem_id"].isin(ids_origem)]
    seg = cad.set_index("cc_id")["segmento"]
    ii = ii.assign(o=ii["origem_id"].map(seg), d=ii["destino_id"].map(seg))
    if ii.empty: return pd.DataFrame()
    pv = ii.pivot_table(index="o", columns="d", values="valor", aggfunc="sum", fill_value=0.0)
    pv = pv.loc[(pv != 0).any(axis=1), (pv != 0).any(axis=0)]
    return pv.sort_index().sort_index(axis=1)

def serie_mensal(direto, indireto, cc_id, todos_periodos) -> pd.DataFrame:
    s = pd.DataFrame(index=pd.Index(todos_periodos, name="periodo"))
    s["direto"] = direto[direto["cc_id"] == cc_id].groupby("periodo")["valor"].sum()
    s["recebido"] = indireto[indireto["destino_id"] == cc_id].groupby("periodo")["valor"].sum()
    s["rateado"] = indireto[indireto["origem_id"] == cc_id].groupby("periodo")["valor"].sum()
    return s.fillna(0.0).reset_index()

def direto_por_grupo(direto, cc_id, periodos) -> pd.DataFrame:
    d = direto[(direto["cc_id"] == cc_id) & direto["periodo"].isin(periodos) & direto["grupo"].notna()]
    g = d.groupby("grupo")["valor"].sum()
    return g[g != 0].sort_values(ascending=False).reset_index()

def fluxo_do_centro(indireto, cad, cc_id, periodos, sentido: str) -> pd.DataFrame:
    ii = indireto[indireto["periodo"].isin(periodos)]
    if sentido == "destino": ii, outro = ii[ii["origem_id"] == cc_id], "destino_id"
    else: ii, outro = ii[ii["destino_id"] == cc_id], "origem_id"
    g = ii.groupby(outro)["valor"].sum()
    g = g[g != 0].sort_values(ascending=False).rename("valor").reset_index().rename(columns={outro: "cc_id"})
    return g.merge(cad, on="cc_id", how="left")

def total_rateado_pela_origem(indireto, periodos) -> pd.Series:
    ii = indireto[indireto["periodo"].isin(periodos)]
    return ii.groupby("origem_id")["valor"].sum()

# ----------------------------------------------------------------------
# NOVIDADE: Funções para a aba de Relatório Consolidado (Estilo Excel)
# ----------------------------------------------------------------------
def relatorio_direto_pivot(direto, cc_id, ano_selecionado):
    d = direto[(direto["cc_id"] == cc_id) & (direto["periodo"].str.startswith(str(ano_selecionado))) & (direto["grupo"].notna())]
    if d.empty: return pd.DataFrame()
    d = d.copy()
    d["mes"] = d["periodo"].str[-2:]
    
    # Criar a pivot table (linhas = grupo, colunas = mes)
    pv = d.pivot_table(index="grupo", columns="mes", values="valor", aggfunc="sum", fill_value=0.0)
    pv["TOTAL"] = pv.sum(axis=1)
    
    # Ordenar conforme o Excel (ORDEM_CONTAS)
    ordem_dict = {c: i for i, c in enumerate(ORDEM_CONTAS)}
    pv = pv.reset_index()
    pv["_ordem"] = pv["grupo"].map(lambda x: ordem_dict.get(x, 999))
    pv = pv.sort_values("_ordem").drop(columns=["_ordem"])
    
    pv.loc["TOTAL DIRETO"] = pv.sum(numeric_only=True)
    pv.at["TOTAL DIRETO", "grupo"] = "TOTAL DO CUSTO DIRETO"
    return pv.set_index("grupo")

def relatorio_indireto_drilldown(indireto, cc_id, ano_selecionado):
    ii = indireto[(indireto["destino_id"] == cc_id) & (indireto["periodo"].str.startswith(str(ano_selecionado)))]
    if ii.empty: return pd.DataFrame()
    # Retorna o detalhamento completo para fazer o drill-down na tela
    return ii.groupby(["origem_segmento", "origem_nome", "origem_id"])["valor"].sum().reset_index()
