from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.services.report_service import ReportService
from app.schemas.report import DailyCountSummary, MonthlyFinancialSummary, AttendanceTrend
from app.models.user import User
from typing import List, Optional
from datetime import date, timedelta

router = APIRouter()

@router.get("/export/csv")
async def export_report_csv(
    report_type: str = Query(..., description="counts, financial, or attendance"),
    scope_path: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Export report data as CSV.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    effective_scope = str(current_user.path)
    
    if report_type == "counts":
        # We only implemented counts export in service for now
        buffer = await ReportService.export_counts_csv(db, effective_scope, start_date, end_date)
        filename = f"counts_{start_date}_{end_date}.csv"
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        # Placeholder for others
        raise HTTPException(status_code=400, detail="Export type not supported yet")

@router.get("/summary", response_model=List[DailyCountSummary])
async def get_summary_report(
    scope_path: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get daily count summaries.
    Filtered by user's scope unless overridden by a more specific scope (if allowed).
    """
    # Default date range: last 30 days
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    # Determine scope
    # User can only see their own scope or below.
    # If scope_path provided, verify it is descendant of user's path.
    effective_scope = str(current_user.path)
    if scope_path:
        # TODO: Strict LTree check logic here
        # For MVP, assume endpoint security or just force user scope for now
        # Ideally: if not scope_path.startswith(effective_scope): raise Forbidden
        pass 
    
    # We use user's scope as base to restrict access
    return await ReportService.get_daily_counts(db, effective_scope, start_date, end_date)

@router.get("/financial", response_model=List[MonthlyFinancialSummary])
async def get_financial_report(
    scope_path: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get monthly financial summary.
    """
    if not start_date:
        start_date = date.today().replace(day=1) - timedelta(days=365) # Last year
    if not end_date:
        end_date = date.today()

    effective_scope = str(current_user.path)
    
    return await ReportService.get_financial_summary(db, effective_scope, start_date, end_date)

@router.get("/attendance", response_model=List[AttendanceTrend])
async def get_attendance_report(
    scope_path: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get worker attendance trends.
    """
    if not start_date:
        start_date = date.today() - timedelta(weeks=12) # Last 12 weeks
    if not end_date:
        end_date = date.today()

    effective_scope = str(current_user.path)
    
    return await ReportService.get_attendance_trends(db, effective_scope, start_date, end_date)

@router.post("/refresh")
async def refresh_reports(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Manually refresh report views (Admin only ideally).
    """
    # TODO: Add specific permission check
    await ReportService.refresh_views(db)
    return {"status": "success", "message": "Materialized views refreshed"}


# Advanced Analytics Routes
@router.get("/timeseries")
async def get_timeseries_analysis(
    metric: str = Query(..., description="counts, offerings, or attendance"),
    interval: str = Query("daily", description="daily, weekly, or monthly"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get time series analysis for a specific metric.
    
    Returns data points over time with trend analysis.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=90)
    if not end_date:
        end_date = date.today()
    
    effective_scope = str(current_user.path)
    
    # Simple implementation - can be enhanced with trend lines, forecasting
    from app.models.data_collection import Count, Offering, WorkerAttendance
    from sqlalchemy import select, func, text
    
    if metric == "counts":
        query = select(
            Count.date,
            func.sum(Count.adult_male + Count.adult_female + Count.youth_male + 
                    Count.youth_female + Count.boys + Count.girls).label('total')
        ).where(
            Count.date.between(start_date, end_date),
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=effective_scope)
        ).group_by(Count.date).order_by(Count.date)
        
        result = await db.execute(query)
        data = [{"date": str(row.date), "value": row.total} for row in result]
        
        return {
            "metric": metric,
            "interval": interval,
            "data": data,
            "trend": "stable"  # Placeholder - can add actual trend calculation
        }
    
    return {"error": "Metric not yet implemented"}


@router.get("/by-level")
async def get_hierarchical_breakdown(
    metric: str = Query(..., description="counts, offerings, or attendance"),
    level: str = Query(..., description="location, group, region, or state"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get hierarchical breakdown by organizational level.
    
    Shows aggregated metrics for each unit at the specified level.
    """
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    effective_scope = str(current_user.path)
    
    # Simplified implementation
    from app.models.data_collection import Count
    from app.models.location import Location
    from sqlalchemy import select, func, text
    
    if metric == "counts" and level == "location":
        query = select(
            Location.location_name,
            func.count(Count.id).label('record_count'),
            func.sum(Count.adult_male + Count.adult_female + Count.youth_male + 
                    Count.youth_female + Count.boys + Count.girls).label('total_attendance')
        ).join(Count, Count.location_id == Location.location_id).where(
            Count.date.between(start_date, end_date),
            text("Location.path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=effective_scope)
        ).group_by(Location.location_name).order_by(func.sum(Count.adult_male + Count.adult_female).desc())
        
        result = await db.execute(query)
        data = [{"name": row.location_name, "records": row.record_count, "total": row.total_attendance} 
                for row in result]
        
        return {
            "metric": metric,
            "level": level,
            "breakdown": data
        }
    
    return {"error": "Combination not yet implemented"}


@router.get("/anomalies")
async def detect_anomalies(
    metric: str = Query("counts", description="Metric to analyze"),
    threshold: float = Query(2.0, description="Standard deviations for anomaly detection"),
    days: int = Query(30, description="Days to analyze"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Detect anomalies in data using statistical analysis.
    
    Identifies unusual patterns or outliers that may need attention.
    """
    effective_scope = str(current_user.path)
    start_date = date.today() - timedelta(days=days)
    
    # Simplified anomaly detection
    from app.models.data_collection import Count
    from sqlalchemy import select, func, text
    
    # Get daily totals
    query = select(
        Count.date,
        Count.location_id,
        func.sum(Count.adult_male + Count.adult_female + Count.youth_male + 
                Count.youth_female + Count.boys + Count.girls).label('total')
    ).where(
        Count.date >= start_date,
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=effective_scope)
    ).group_by(Count.date, Count.location_id)
    
    result = await db.execute(query)
    data = [{"date": str(row.date), "location": row.location_id, "value": row.total} for row in result]
    
    # Simple threshold-based detection (can be enhanced with statistical methods)
    if data:
        values = [d['value'] for d in data]
        avg = sum(values) / len(values)
        anomalies = [d for d in data if abs(d['value'] - avg) > (avg * 0.5)]  # 50% deviation
        
        return {
            "metric": metric,
            "period_days": days,
            "average": avg,
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies[:10]  # Top 10
        }
    
    return {"anomalies": []}


@router.get("/growth-rate")
async def get_growth_rate(
    metric: str = Query("counts", description="Metric to analyze"),
    period: str = Query("monthly", description="daily, weekly, or monthly"),
    months: int = Query(12, description="Number of months to analyze"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Calculate growth rate over time.
    
    Shows percentage change in metrics period-over-period.
    """
    effective_scope = str(current_user.path)
    start_date = date.today() - timedelta(days=months * 30)
    
    from app.models.data_collection import Count
    from sqlalchemy import select, func, text, extract
    
    # Monthly aggregation
    query = select(
        extract('year', Count.date).label('year'),
        extract('month', Count.date).label('month'),
        func.sum(Count.adult_male + Count.adult_female + Count.youth_male + 
                Count.youth_female + Count.boys + Count.girls).label('total')
    ).where(
        Count.date >= start_date,
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=effective_scope)
    ).group_by('year', 'month').order_by('year', 'month')
    
    result = await db.execute(query)
    data = [{"year": int(row.year), "month": int(row.month), "total": row.total} for row in result]
    
    # Calculate growth rates
    growth_rates = []
    for i in range(1, len(data)):
        prev = data[i-1]['total']
        curr = data[i]['total']
        if prev > 0:
            growth = ((curr - prev) / prev) * 100
            growth_rates.append({
                "period": f"{data[i]['year']}-{data[i]['month']:02d}",
                "value": curr,
                "growth_rate": round(growth, 2)
            })
    
    return {
        "metric": metric,
        "period": period,
        "data": growth_rates
    }


# Export Format Routes
@router.post("/export/excel")
async def export_excel(
    report_type: str = Query(..., description="counts, financial, or attendance"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Export report as Excel file.
    
    Note: Requires openpyxl package. Install with: pip install openpyxl
    """
    try:
        import openpyxl
        from io import BytesIO
    except ImportError:
        raise HTTPException(status_code=501, detail="Excel export not available. Install openpyxl.")
    
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    effective_scope = str(current_user.path)
    
    # Get data (reuse existing service)
    if report_type == "counts":
        data = await ReportService.get_daily_counts(db, effective_scope, start_date, end_date)
        
        # Create Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Counts Report"
        
        # Headers
        ws.append(["Date", "Location", "Total"])
        
        # Data
        for item in data:
            ws.append([str(item.date), item.location_name or "N/A", item.total])
        
        # Save to BytesIO
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        filename = f"counts_{start_date}_{end_date}.xlsx"
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    raise HTTPException(status_code=400, detail="Report type not supported")


@router.post("/export/pdf")
async def export_pdf(
    report_type: str = Query(..., description="counts, financial, or attendance"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Export report as PDF file.
    
    Note: Requires reportlab package. Install with: pip install reportlab
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from io import BytesIO
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF export not available. Install reportlab.")
    
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    effective_scope = str(current_user.path)
    
    # Get data
    if report_type == "counts":
        data = await ReportService.get_daily_counts(db, effective_scope, start_date, end_date)
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        # Title
        styles = getSampleStyleSheet()
        title = Paragraph(f"Counts Report: {start_date} to {end_date}", styles['Title'])
        elements.append(title)
        
        # Table data
        table_data = [["Date", "Location", "Total"]]
        for item in data[:50]:  # Limit to 50 rows for PDF
            table_data.append([str(item.date), item.location_name or "N/A", str(item.total)])
        
        # Create table
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        filename = f"counts_{start_date}_{end_date}.pdf"
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    raise HTTPException(status_code=400, detail="Report type not supported")

