"""
Lógica de dados do Dashboard de Custos (sem dependência de Streamlit).
"""
import re
import io
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

def kpis(res: pd.DataFrame, indireto=None, periodos=None, segmentos_filtrados=None) -> dict:
    d = res["direto"].sum()
    if segmentos_filtrados and indireto is not None and periodos is not None and len(res) > 1:
        ii = indireto[indireto["periodo"].isin(periodos)]
        r = ii[(ii["destino_segmento"].isin(segmentos_filtrados)) & (~ii["origem_segmento"].isin(segmentos_filtrados))]["valor"].sum()
        o = ii[(ii["origem_segmento"].isin(segmentos_filtrados)) & (~ii["destino_segmento"].isin(segmentos_filtrados))]["valor"].sum()
    else:
        r = res["recebido"].sum()
        o = res["rateado"].sum()
        
    tot = d + r
    return {"direto": d, "recebido": r, "total": tot, "pct_indireto": (r / tot * 100) if tot else 0.0, "rateado": o}

def resumo_segmentos(res: pd.DataFrame, indireto=None, periodos=None) -> pd.DataFrame:
    if indireto is not None and periodos is not None:
        ii = indireto[indireto["periodo"].isin(periodos)]
        segs = sorted(res["segmento"].unique())
        linhas = []
        for s in segs:
            d_val = res[res["segmento"] == s]["direto"].sum()
            rec_inter = ii[(ii["destino_segmento"] == s) & (ii["origem_segmento"] != s)]["valor"].sum()
            rat_inter = ii[(ii["origem_segmento"] == s) & (ii["destino_segmento"] != s)]["valor"].sum()
            linhas.append({
                "segmento": s,
                "direto": d_val,
                "recebido": rec_inter,
                "total": d_val + rec_inter,
                "rateado": rat_inter
            })
        g = pd.DataFrame(linhas)
    else:
        g = res.groupby("segmento")[["direto", "recebido", "rateado"]].sum()
        g["total"] = g["direto"] + g["recebido"]
        g = g.reset_index()
    return g.sort_values("total", ascending=False).reset_index(drop=True)

def detalhe_origens_inter_segmento(indireto, periodos, segmentos_filtrados) -> pd.DataFrame:
    ii = indireto[indireto["periodo"].isin(periodos)].copy()
    ii["destino_segmento"] = ii["destino_segmento"].fillna("Sem Segmento")
    ii["origem_segmento"] = ii["origem_segmento"].fillna("Sem Segmento")
    
    inter = ii[(ii["destino_segmento"].isin(segmentos_filtrados)) & (~ii["origem_segmento"].isin(segmentos_filtrados))]
    if inter.empty:
        return pd.DataFrame()
        
    g = inter.groupby(["destino_segmento", "origem_segmento"])["valor"].sum().reset_index()
    totais = g.groupby("destino_segmento")["valor"].transform("sum")
    g["pct"] = (g["valor"] / totais) * 100
    
    g = g.rename(columns={
        "destino_segmento": "Segmento Destino",
        "origem_segmento": "Segmento de Origem",
        "valor": "Valor Recebido",
        "pct": "% do Recebido Inter"
    }).sort_values(["Segmento Destino", "Valor Recebido"], ascending=[True, False])
    return g

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

def relatorio_direto_pivot(direto, cc_id, ano_selecionado, mes_limite=12):
    d = direto[(direto["cc_id"] == cc_id) & (direto["periodo"].astype(str).str.startswith(str(ano_selecionado))) & (direto["grupo"].notna())].copy()
    cols_meses = [f"{m:02d}" for m in range(1, 13)]
    
    if d.empty:
        df_empty = pd.DataFrame(0.0, index=ORDEM_CONTAS, columns=cols_meses + ["TOTAL", "MÉDIA"])
        df_empty.index.name = "grupo"
        df_empty.loc["TOTAL DO CUSTO DIRETO"] = 0.0
        return df_empty

    d["mes"] = d["periodo"].astype(str).str[-2:]
    pv = d.pivot_table(index="grupo", columns="mes", values="valor", aggfunc="sum", fill_value=0.0)
    pv = pv.reindex(columns=cols_meses, fill_value=0.0)
    
    cols_limite = [f"{m:02d}" for m in range(1, mes_limite + 1)]
    pv["TOTAL"] = pv[cols_limite].sum(axis=1)
    pv["MÉDIA"] = pv["TOTAL"] / max(1, mes_limite)
    
    ordem_dict = {c: i for i, c in enumerate(ORDEM_CONTAS)}
    pv = pv.reset_index()
    pv["_ordem"] = pv["grupo"].map(lambda x: ordem_dict.get(x, 999))
    pv = pv.sort_values("_ordem").drop(columns=["_ordem"]).set_index("grupo")
    
    pv.loc["TOTAL DO CUSTO DIRETO"] = pv.sum(numeric_only=True)
    return pv

def relatorio_indireto_por_segmento(indireto, cc_id, ano_selecionado, mes_limite=12):
    ii = indireto[(indireto["destino_id"] == cc_id) & (indireto["periodo"].astype(str).str.startswith(str(ano_selecionado)))].copy()
    cols_meses = [f"{m:02d}" for m in range(1, 13)]
    
    if ii.empty:
        return pd.DataFrame(), {}

    ii["mes"] = ii["periodo"].astype(str).str[-2:]
    ii["origem_segmento"] = ii["origem_segmento"].fillna("Sem Segmento")
    cols_limite = [f"{m:02d}" for m in range(1, mes_limite + 1)]
    
    # 1. Agrupar por segmento primeiro
    pv_seg = ii.pivot_table(index="origem_segmento", columns="mes", values="valor", aggfunc="sum", fill_value=0.0)
    pv_seg = pv_seg.reindex(columns=cols_meses, fill_value=0.0)
    pv_seg["TOTAL"] = pv_seg[cols_limite].sum(axis=1)
    pv_seg["MÉDIA"] = pv_seg["TOTAL"] / max(1, mes_limite)
    pv_seg = pv_seg.sort_values("TOTAL", ascending=False)
    
    # AJUSTE FINO: Salvar a ordem dos segmentos (do maior rateio pro menor) antes de incluir a linha TOTAL
    segmentos_ordenados = pv_seg.index.tolist()
    
    pv_seg.loc["TOTAL RATEIO RECEBIDO"] = pv_seg.sum(numeric_only=True)
    pv_seg.index.name = "Segmento de Origem"
    
    detalhes_por_seg = {}
    # Iterar seguindo a ordem do maior ofensor pro menor
    for seg in segmentos_ordenados:
        sub = ii[ii["origem_segmento"] == seg].copy()
        
        # Mostramos apenas o NOME do centro para nao embolar os relatórios
        sub["origem_rotulo"] = sub["origem_nome"].fillna(sub["origem_id"])
        
        pv_sub = sub.pivot_table(index="origem_rotulo", columns="mes", values="valor", aggfunc="sum", fill_value=0.0)
        pv_sub = pv_sub.reindex(columns=cols_meses, fill_value=0.0)
        pv_sub["TOTAL"] = pv_sub[cols_limite].sum(axis=1)
        pv_sub["MÉDIA"] = pv_sub["TOTAL"] / max(1, mes_limite)
        pv_sub = pv_sub.sort_values("TOTAL", ascending=False)
        pv_sub.loc[f"TOTAL {seg.upper()}"] = pv_sub.sum(numeric_only=True)
        pv_sub.index.name = "Centro de Custo de Origem"
        
        detalhes_por_seg[seg] = pv_sub
        
    return pv_seg, detalhes_por_seg

def relatorio_total_pivot(pv_dir, pv_seg, mes_limite=12):
    cols_meses = [f"{m:02d}" for m in range(1, 13)] + ["TOTAL", "MÉDIA"]
    df_tot = pd.DataFrame(0.0, index=["1. Custo Direto", "2. Rateio Recebido", "3. Custo Total"], columns=cols_meses)
    
    if not pv_dir.empty and "TOTAL DO CUSTO DIRETO" in pv_dir.index:
        df_tot.loc["1. Custo Direto", pv_dir.columns] = pv_dir.loc["TOTAL DO CUSTO DIRETO"]
        
    if not pv_seg.empty and "TOTAL RATEIO RECEBIDO" in pv_seg.index:
        df_tot.loc["2. Rateio Recebido", pv_seg.columns] = pv_seg.loc["TOTAL RATEIO RECEBIDO"]
        
    df_tot.loc["3. Custo Total"] = df_tot.loc["1. Custo Direto"] + df_tot.loc["2. Rateio Recebido"]
    df_tot.index.name = "Resumo Consolidado"
    return df_tot

def gerar_pdf_relatorio(cad_info, pv_dir, pv_seg, detalhes_seg, pv_tot, ano_sel, mes_limite):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
    except ImportError:
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, leading=18, textColor=colors.HexColor('#0F172A'))
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#475569'))
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=10.5, leading=14, textColor=colors.HexColor('#1E40AF'), spaceBefore=8, spaceAfter=4)
    subsec_style = ParagraphStyle('SubSectionStyle', parent=styles['Heading3'], fontSize=9, leading=12, textColor=colors.HexColor('#0F172A'), spaceBefore=6, spaceAfter=2)
    
    # AJUSTE FINO: Estilo da fonte corrigido para ficar idêntico ao restante da tabela (sem negrito e cor preta)
    cell_style = ParagraphStyle(
        'CellStyle', 
        parent=styles['Normal'], 
        fontSize=7, 
        leading=8, 
        fontName='Helvetica', 
        textColor=colors.black
    )

    elements = []
    elements.append(Paragraph(f"<b>RELATÓRIO GERENCIAL CONSOLIDADO DE CUSTOS — {ano_sel}</b>", title_style))
    elements.append(Paragraph(
        f"<b>Centro de Custo:</b> {cad_info['cc_nome']} ({cad_info['cc_id']}) | "
        f"<b>Classificação:</b> {cad_info['classificacao']} | "
        f"<b>Segmento:</b> {cad_info['segmento']} | "
        f"<b>Acumulado até Mês:</b> {mes_limite:02d}",
        sub_style
    ))
    elements.append(Spacer(1, 8))

    def fmt_pdf_val(v):
        if pd.isna(v) or v == 0: return "-"
        n = round(float(v))
        return f"{abs(n):,.0f}".replace(",", ".")

    def criar_tabela_pdf(df_tabela, wrap_index=False):
        header = [str(df_tabela.index.name) if df_tabela.index.name else ""] + [f"{m:02d}" for m in range(1, 13)] + ["TOTAL", "MÉDIA"]
        table_data = [header]
        
        for idx, row in df_tabela.iterrows():
            idx_str = str(idx)
            
            # Aplica o ParagraphStyle normal (sem negrito) apenas para nomes longos
            if wrap_index and len(idx_str) > 30 and not idx_str.startswith("TOTAL"):
                idx_display = Paragraph(idx_str, cell_style)
            else:
                idx_display = idx_str
                
            r = [idx_display] + [fmt_pdf_val(row[col]) for col in [f"{m:02d}" for m in range(1, 13)] + ["TOTAL", "MÉDIA"]]
            table_data.append(r)
            
        t = Table(table_data, colWidths=[135] + [43]*12 + [58, 54])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Garante alinhamento vertical para textos quebrados
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E2E8F0')),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ]))
        return t

    # 1. Custo Direto
    elements.append(Paragraph(f"1. Evolução do Custo Direto (em R$ - Acumulado até Mês {mes_limite:02d})", section_style))
    if not pv_dir.empty:
        elements.append(criar_tabela_pdf(pv_dir, wrap_index=True))

    # 2. Custo Indireto - Resumo
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"2. Resumo das Origens do Custo Indireto por Segmento (em R$)", section_style))
    if not pv_seg.empty:
        elements.append(criar_tabela_pdf(pv_seg))
        
    # 3. Custo Total
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"3. Custo Total do Centro (Direto + Indireto em R$)", section_style))
    if not pv_tot.empty:
        t_tot = criar_tabela_pdf(pv_tot)
        t_tot.setStyle(TableStyle([('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#DBEAFE'))])) 
        elements.append(t_tot)

    # 4. Detalhamento
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"4. Detalhamento por Centro de Custo de Origem", section_style))
    for seg_nome, pv_sub in detalhes_seg.items():
        elements.append(Paragraph(f"<b>Origem: Segmento {seg_nome}</b>", subsec_style))
        t_sub = criar_tabela_pdf(pv_sub, wrap_index=True)
        t_sub.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')), ('FONTSIZE', (0,0), (-1,-1), 6.5)]))
        elements.append(t_sub)
        elements.append(Spacer(1, 4))

    doc.build(elements)
    return buffer.getvalue()
