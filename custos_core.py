"""
Lógica de dados do Dashboard de Custos (sem dependência de Streamlit).
"""
import re
import unicodedata
import pandas as pd

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
ORDEM_CLASSIF = ["Administrativo", "Apoio", "Produtivo", "Neutro"]

# ----------------------------------------------------------------------
# Campos esperados em cada planilha (com os nomes reais do ERP Feso mapeados)
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
# Formatação e Detecção de colunas
# ----------------------------------------------------------------------
def brl(v) -> str:
    n = round(float(v or 0))
    s = f"{abs(n):,.0f}".replace(",", ".")
    return ("-" if n < 0 else "") + "R$ " + s

def pct(a, b) -> str:
    return f"{a / b * 100:.1f}".replace(".", ",") + "%" if b else "–"

def rotulo_periodo(p: str) -> str:
    try:
        return f"{MESES[int(p[4:6]) - 1]}/{p[2:4]}"
    except (ValueError, IndexError):
        return str(p)

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

def _txt(serie: pd.Series) -> pd.Series:
    s = serie.astype("string").str.strip()
    return s.mask(s.isin(["", "nan", "None", "<NA>"]))

def _col(raw, mapa, chave):
    c = mapa.get(chave)
    return _txt(raw[c]) if c else pd.Series(pd.NA, index=raw.index, dtype="string")

def normalizar_direto(raw: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    nome = _col(raw, mapa, "cc_nome")
    cod = _col(raw, mapa, "cc_codigo")
    df = pd.DataFrame({
        "periodo": raw[mapa["periodo"]].map(_periodo),
        "cc_id": cod.fillna(nome),
        "cc_nome": nome,
        "classificacao": _col(raw, mapa, "classificacao"),
        "segmento": _col(raw, mapa, "segmento"),
        "grupo": _col(raw, mapa, "grupo"),
        "valor": _valor(raw[mapa["valor"]]),
    })
    return df.dropna(subset=["periodo", "cc_id", "valor"]).reset_index(drop=True)

def normalizar_indireto(raw: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    d_nome, d_cod = _col(raw, mapa, "destino_nome"), _col(raw, mapa, "destino_codigo")
    o_nome, o_cod = _col(raw, mapa, "origem_nome"), _col(raw, mapa, "origem_codigo")
    df = pd.DataFrame({
        "periodo": raw[mapa["periodo"]].map(_periodo),
        "destino_id": d_cod.fillna(d_nome),
        "destino_nome": d_nome,
        "destino_classificacao": _col(raw, mapa, "destino_classificacao"),
        "destino_segmento": _col(raw, mapa, "destino_segmento"),
        "origem_id": o_cod.fillna(o_nome),
        "origem_nome": o_nome,
        "origem_classificacao": _col(raw, mapa, "origem_classificacao"),
        "origem_segmento": _col(raw, mapa, "origem_segmento"),
        "valor": _valor(raw[mapa["valor"]]),
    })
    return df.dropna(subset=["periodo", "destino_id", "valor"]).reset_index(drop=True)

def tem_origem(ind: pd.DataFrame) -> bool:
    return ind is not None and ind["origem_id"].notna().any()

# ----------------------------------------------------------------------
# Cadastro e Agregações
# ----------------------------------------------------------------------
def montar_cadastro(direto: pd.DataFrame, indireto: pd.DataFrame) -> pd.DataFrame:
    cols = ["cc_id", "cc_nome", "classificacao", "segmento"]
    partes = [direto[cols]]
    for lado in ("destino", "origem"):
        p = indireto[[f"{lado}_id", f"{lado}_nome", f"{lado}_classificacao", f"{lado}_segmento"]]
        p.columns = cols
        partes.append(p.dropna(subset=["cc_id"]))
    cad = pd.concat(partes, ignore_index=True).groupby("cc_id", as_index=False).first()
    cad["cc_nome"] = cad["cc_nome"].fillna(cad["cc_id"])
    cad["classificacao"] = cad["classificacao"].fillna("Sem classificação")
    cad["segmento"] = cad["segmento"].fillna("Sem segmento")
    return cad.astype(str)

def diagnostico(direto, indireto, cad) -> list[str]:
    avisos = []
    ids_cad = set(direto["cc_id"])
    for lado in ("destino", "origem"):
        ids = set(indireto[f"{lado}_id"].dropna())
        fora = ids - ids_cad
        if ids and len(fora) / len(ids) > 0.5:
            avisos.append(f"{len(fora)} de {len(ids)} centros de {lado} do rateio não aparecem na base direta.")
    if not tem_origem(indireto):
        avisos.append("A base indireta não tem centro de ORIGEM.")
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
    if classificacoes: 
        m &= res["classificacao"].isin(classificacoes)
    if segmentos: 
        m &= res["segmento"].isin(segmentos)
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
    if sentido == "destino":
        ii, outro = ii[ii["origem_id"] == cc_id], "destino_id"
    else:
        ii, outro = ii[ii["destino_id"] == cc_id], "origem_id"
    g = ii.groupby(outro)["valor"].sum()
    g = g[g != 0].sort_values(ascending=False).rename("valor").reset_index().rename(columns={outro: "cc_id"})
    return g.merge(cad, on="cc_id", how="left")

def total_rateado_pela_origem(indireto, periodos) -> pd.Series:
    ii = indireto[indireto["periodo"].isin(periodos)]
    return ii.groupby("origem_id")["valor"].sum()
