"""
PDF export for claim logs.

Renders ClaimLog objects to printable PDF documents suitable for insurance filing.
Uses ReportLab for PDF generation.
"""

from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from datetime import datetime
from claim_log_service import ClaimLog


def export_claim_log_to_pdf(claim_log: ClaimLog) -> bytes:
    """Export a claim log to PDF bytes.
    
    Generates a clean, readable PDF document from a ClaimLog object.
    The PDF includes:
    - Title and metadata (route ID, generation timestamp)
    - Narrative summary
    - Table of hazard events (time, type, severity, location, notes)
    - Weather snapshot summary
    - Key metrics
    
    Args:
        claim_log: ClaimLog object to export
        
    Returns:
        PDF file as bytes (can be written to file or returned as HTTP response)
        
    Example:
        >>> from claim_log_service import ClaimLog, HazardEvent, WeatherSnapshot
        >>> # Create a claim log (see claim_log_service for examples)
        >>> pdf_bytes = export_claim_log_to_pdf(claim_log)
        >>> with open("claim.pdf", "wb") as f:
        ...     f.write(pdf_bytes)
    """
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Routecast Claim Log",
    )
    
    # Container for PDF elements
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=HexColor("#1E88E5"),
        spaceAfter=12,
        alignment=0,  # Left align
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=HexColor("#333333"),
        spaceAfter=10,
        spaceBefore=10,
    )
    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=10,
        textColor=HexColor("#555555"),
        spaceAfter=6,
    )
    
    # Title
    story.append(Paragraph("Routecast Claim Log", title_style))
    
    # Metadata section
    metadata = [
        f"<b>Route ID:</b> {claim_log.route_id}",
        f"<b>Generated:</b> {claim_log.generated_at}",
        f"<b>Schema Version:</b> {claim_log.schema_version}",
    ]
    for line in metadata:
        story.append(Paragraph(line, normal_style))
    
    story.append(Spacer(1, 0.2 * inch))
    
    # Narrative section
    story.append(Paragraph("Incident Summary", heading_style))
    story.append(Paragraph(claim_log.narrative, normal_style))
    
    story.append(Spacer(1, 0.15 * inch))
    
    # Hazard events table
    if claim_log.hazards:
        story.append(Paragraph("Hazard Events", heading_style))
        
        # Build table data
        table_data = [
            ["Time", "Type", "Severity", "Location", "Notes"],
        ]
        
        for hazard in claim_log.hazards:
            # Parse timestamp for cleaner display
            try:
                dt = datetime.fromisoformat(hazard.timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except:
                time_str = hazard.timestamp
            
            # Format location
            lat, lon = hazard.location
            location_str = f"{lat:.2f}, {lon:.2f}"
            
            # Notes may be empty
            notes_str = hazard.notes or ""
            
            table_data.append([
                time_str,
                hazard.type,
                hazard.severity,
                location_str,
                notes_str,
            ])
        
        # Create table with styling
        table = Table(table_data, colWidths=[1.3 * inch, 1 * inch, 0.9 * inch, 1.2 * inch, 1.4 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1E88E5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), HexColor("#FAFAFA")),
            ("GRID", (0, 0), (-1, -1), 1, HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F5F5F5")]),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.15 * inch))
    
    # Totals section
    story.append(Paragraph("Summary", heading_style))
    
    totals_text = f"<b>Total Events:</b> {claim_log.totals['total_events']}<br/>"
    
    if claim_log.totals["by_type"]:
        totals_text += "<b>By Type:</b> " + ", ".join(
            f"{t}({c})" for t, c in sorted(claim_log.totals["by_type"].items())
        ) + "<br/>"
    
    if claim_log.totals["by_severity"]:
        totals_text += "<b>By Severity:</b> " + ", ".join(
            f"{s}({c})" for s, c in sorted(claim_log.totals["by_severity"].items())
        )
    
    story.append(Paragraph(totals_text, normal_style))
    story.append(Spacer(1, 0.15 * inch))
    
    # Weather snapshot section
    story.append(Paragraph("Weather Conditions", heading_style))
    
    weather_text = f"<b>Summary:</b> {claim_log.weather_snapshot.summary}<br/>"
    weather_text += f"<b>Source:</b> {claim_log.weather_snapshot.source}<br/>"
    
    start_time, end_time = claim_log.weather_snapshot.time_range
    weather_text += f"<b>Observation Period:</b> {start_time} to {end_time}<br/>"
    
    # Key metrics
    metrics = claim_log.weather_snapshot.key_metrics
    if metrics:
        weather_text += "<b>Key Metrics:</b><br/>"
        for key, value in sorted(metrics.items()):
            if key != "alerts":
                weather_text += f"&nbsp;&nbsp;{key}: {value}<br/>"
        
        # Alerts if present
        if "alerts" in metrics and metrics["alerts"]:
            weather_text += f"&nbsp;&nbsp;Alerts: {', '.join(metrics['alerts'])}<br/>"
    
    story.append(Paragraph(weather_text, normal_style))
    
    # Footer
    story.append(Spacer(1, 0.25 * inch))
    footer_text = "This claim log was generated by Routecast and is provided for documentation purposes."
    story.append(Paragraph(footer_text, ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=HexColor("#999999"),
        alignment=1,  # Center align
    )))
    
    # Build PDF
    doc.build(story)
    
    # Get bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
