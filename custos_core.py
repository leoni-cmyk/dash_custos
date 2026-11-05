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
    # Estilo especial para nomes longos na tabela (Word-wrap)
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=6.5, leading=7.5, fontName='Helvetica-Bold', textColor=colors.HexColor('#334155'))

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
            # Quebra automática do nome se for muito longo
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
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Garante alinhamento vertical correto para textos quebrados
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
