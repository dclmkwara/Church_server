"""Opt-in live F4 rendered-page/export reconciliation on the local clone only."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest
from bs4 import BeautifulSoup
from openpyxl import load_workbook
from sqlalchemy import create_engine, text

MARKER = "F4_TEST:f4-v1"
pytestmark = pytest.mark.skipif(
    not all(os.getenv(name) for name in ("F4_DATABASE_URL", "F4_BASE_URL", "F4_SCOPE_PATHS"))
    or not (os.getenv("F4_COOKIE_STATE") or (os.getenv("F4_TEST_EMAIL") and os.getenv("F4_TEST_PASSWORD"))),
    reason="requires explicit local F4 clone, running app and authenticated browser state",
)


def _configuration():
    db = urlparse(os.environ["F4_DATABASE_URL"])
    app = urlparse(os.environ["F4_BASE_URL"])
    assert db.hostname in {"127.0.0.1", "localhost", "::1"}
    assert db.path.lstrip("/") == "dclm_slice_f"
    assert app.hostname in {"127.0.0.1", "localhost", "::1"}
    if os.getenv("F4_TEST_EMAIL") and os.getenv("F4_TEST_PASSWORD"):
        with httpx.Client(base_url=os.environ["F4_BASE_URL"], follow_redirects=True, timeout=30) as login:
            response = login.post("/login", data={
                "email": os.environ["F4_TEST_EMAIL"],
                "password": os.environ["F4_TEST_PASSWORD"],
                "next": "/dashboard",
            })
            assert response.status_code == 200 and response.url.path == "/dashboard", "local test account sign-in failed"
            return dict(login.cookies)
    state = json.loads(Path(os.environ["F4_COOKIE_STATE"]).read_text(encoding="utf-8"))
    return {c["name"]: c["value"] for c in state.get("cookies", [])}


def _sql(connection, scope: str, start: date, end: date) -> dict:
    params = {"scope": scope, "start": start, "end": end}
    count_rows = connection.execute(text("""
      WITH accepted AS (
        SELECT c.*, coalesce(nullif(c.program_scope_path,''),c.path) report_path
        FROM counts c WHERE c.status='approved' AND c.is_deleted IS NOT TRUE AND c.program_type_id=1
          AND c.date::date BETWEEN :start AND :end
      ), effective AS (
        SELECT l.* FROM accepted l WHERE lower(coalesce(l.program_level,'local')) IN ('local','location')
          AND (l.path=:scope OR l.path LIKE :scope || '.%')
          AND NOT EXISTS (SELECT 1 FROM accepted x WHERE lower(x.program_level) IN ('group','region','state')
            AND x.date::date=l.date::date AND l.path LIKE x.report_path || '.%')
        UNION ALL
        SELECT x.* FROM accepted x WHERE lower(coalesce(x.program_level,'')) IN ('group','region','state')
          AND (x.report_path=:scope OR x.report_path LIKE :scope || '.%')
      )
      SELECT date::date d, sum(adult_male) am, sum(adult_female) af, sum(youth_male) ym,
        sum(youth_female) yf, sum(boys) cm, sum(girls) cf, sum(total) total
      FROM effective GROUP BY 1
    """), params).mappings().all()
    offering_rows = connection.execute(text("""
      SELECT status,fund_type,coalesce(sum(amount),0) amount,count(*) n FROM offerings
      WHERE is_deleted IS NOT TRUE AND date::date BETWEEN :start AND :end
        AND (path=:scope OR path LIKE :scope || '.%')
      GROUP BY status,fund_type
    """), params).mappings().all()
    offerings = {
        "approved_amount": sum(r["amount"] for r in offering_rows if r["status"] == "approved"),
        "approved_records": sum(r["n"] for r in offering_rows if r["status"] == "approved"),
        "pending_amount": sum(r["amount"] for r in offering_rows if r["status"] in {"pending", "corrected"}),
        "pending_records": sum(r["n"] for r in offering_rows if r["status"] in {"pending", "corrected"}),
        "funds": {r["fund_type"]: float(r["amount"]) for r in offering_rows if r["status"] == "approved"},
    }
    offering_correction = connection.execute(text("""
      SELECT a.before_values->>'date' before_date,a.after_values->>'date' after_date,count(*) n
      FROM offering_audits a JOIN offerings o ON o.id=a.offering_id
      WHERE o.note LIKE :marker AND a.action='corrected'
      GROUP BY a.before_values->>'date',a.after_values->>'date'
    """), {"marker": f"%{MARKER}%"}).mappings().all()
    worker_sql = text("""
      WITH s AS (
        SELECT date::date d, coalesce(nullif(program_scope_path,''),path::text) p,
          expected_workers_count n, expected_worker_ids ids
        FROM worker_attendance_submissions WHERE is_deleted IS NOT TRUE AND program_type_id=:worker_type
          AND date::date BETWEEN :start AND :end AND (path::text=:scope OR path::text LIKE :scope || '.%')
      ), roster AS (
        SELECT d,p,bool_or(ids IS NOT NULL) snapshot,max(n) legacy,count(DISTINCT j.id) snap_n
        FROM s LEFT JOIN LATERAL jsonb_array_elements_text(coalesce(ids,'[]'::jsonb)) j(id) ON true GROUP BY d,p
      ), present AS (
        SELECT date::date d,coalesce(nullif(program_scope_path,''),path::text) p,
          count(DISTINCT worker_id) FILTER(WHERE lower(status)='present') n,
          count(DISTINCT worker_id) FILTER(WHERE lower(status)='late') late_n
        FROM worker_attendance WHERE is_deleted IS NOT TRUE AND program_type_id=:worker_type
          AND date::date BETWEEN :start AND :end AND (path::text=:scope OR path::text LIKE :scope || '.%') GROUP BY 1,2
      )
      SELECT coalesce(sum(CASE WHEN r.snapshot THEN r.snap_n ELSE r.legacy END),0) expected,
        coalesce(sum(p.n),0) present,coalesce(sum(p.late_n),0) late,count(*) meetings
      FROM roster r LEFT JOIN present p USING(d,p)
    """)
    workers = connection.execute(worker_sql, {**params, "worker_type": 19}).mappings().one()
    leaders = connection.execute(worker_sql, {**params, "worker_type": 17}).mappings().one()
    fellowship = connection.execute(text("""
      WITH scoped AS (SELECT fellowship_id FROM fellowships
        WHERE path::text=:scope OR path::text LIKE :scope || '.%'),
      latest_attendance AS (
        SELECT DISTINCT ON (fa.fellowship_id) fa.fellowship_id,fa.total
        FROM fellowship_attendance fa JOIN scoped s USING(fellowship_id)
        WHERE fa.is_deleted IS NOT TRUE ORDER BY fa.fellowship_id,fa.date DESC,fa.created_at DESC
      ), latest_offering AS (
        SELECT DISTINCT ON (fo.fellowship_id) fo.fellowship_id,fo.amount
        FROM fellowship_offerings fo JOIN scoped s USING(fellowship_id)
        WHERE fo.is_deleted IS NOT TRUE ORDER BY fo.fellowship_id,fo.date DESC,fo.created_at DESC
      )
      SELECT coalesce((SELECT avg(total) FROM latest_attendance),0) avg_attendance,
        coalesce((SELECT sum(amount) FROM latest_offering),0) latest_offering,
        coalesce((SELECT sum(total) FROM latest_attendance),0) attendance_sum
    """), {"scope": scope}).mappings().one()
    records = connection.execute(text("""
      SELECT lower(record_type) t,count(*) n FROM records WHERE is_deleted IS NOT TRUE
        AND lower(record_type) IN ('newcomer','convert') AND date::date BETWEEN :start AND :end
        AND (path=:scope OR path LIKE :scope || '.%') GROUP BY 1
    """), params).mappings().all()
    event = connection.execute(text("""
      SELECT coalesce(sum(c.total),0) FROM counts c JOIN program_events e ON e.id=c.event_id
      WHERE e.title LIKE :marker AND e.is_deleted IS NOT TRUE AND e.approval_status='approved'
        AND c.is_deleted IS NOT TRUE AND c.status='approved'
        AND (c.program_scope_path=:scope OR c.program_scope_path LIKE :scope || '.%')
    """), {"scope": scope, "marker": f"%{MARKER}%"}).scalar_one()
    return {
        "counts": {r["d"].isoformat(): dict(adult_male=r["am"],adult_female=r["af"],youth_male=r["ym"],
          youth_female=r["yf"],children_male=r["cm"],children_female=r["cf"],total=r["total"]) for r in count_rows},
        "offerings": offerings, "offering_correction": [dict(r) for r in offering_correction],
        "workers": dict(workers), "leaders": dict(leaders), "fellowship": dict(fellowship),
        "records": {r["t"]:r["n"] for r in records}, "event": event,
    }


def _table_column_sum(html: str, column_name: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.select("table"):
        headers = [cell.get_text(" ", strip=True).casefold() for cell in table.select("thead th")]
        if column_name.casefold() not in headers:
            continue
        index = headers.index(column_name.casefold())
        return sum(int(re.sub(r"[^0-9]", "", row.select("td")[index].get_text(" ", strip=True)) or 0)
                   for row in table.select("tbody tr") if len(row.select("td")) > index)
    raise AssertionError(f"Rendered table column not found: {column_name}")


def _dashboard_metric(html: str, label_prefix: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select(".analytics-metric"):
        label = card.select_one(".analytics-kicker")
        value = card.select_one(".analytics-value")
        if label and value and label.get_text(" ", strip=True).startswith(label_prefix):
            return value.get_text(" ", strip=True)
    raise AssertionError(f"Dashboard metric was not rendered: {label_prefix}")


def _summary_value(html: str, label: str) -> str:
    text_content = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    match = re.search(re.escape(label) + r"\s+([\d,.]+%?)\s+", text_content)
    if not match:
        raise AssertionError(f"Rendered summary metric was not found: {label}")
    return match.group(1)


def _record_counts(html: str) -> dict[str, int]:
    soup = BeautifulSoup(html, "html.parser")
    counts = {"Newcomer": 0, "Convert": 0}
    aggregate = soup.get_text(" ", strip=True)
    newcomer_total = re.search(r"Newcomers\s+(\d+)\s+Count in this scope", aggregate)
    convert_total = re.search(r"Converts\s+(\d+)\s+Count in this scope", aggregate)
    if newcomer_total and convert_total:
        return {"Newcomer": int(newcomer_total.group(1)), "Convert": int(convert_total.group(1))}
    for table in soup.select("table"):
        table_rows = table.select("tr")
        headers = [cell.get_text(" ", strip=True).casefold() for cell in table_rows[0].select("th,td")] if table_rows else []
        if not {"type", "follow-up"}.issubset(set(headers)):
            continue
        type_index = headers.index("type")
        for row in table_rows[1:]:
            cells = row.select("td")
            if len(cells) <= type_index:
                continue
            typ = cells[type_index].get_text(" ", strip=True).title()
            if typ in counts:
                counts[typ] += 1
        break
    return counts


def test_rendered_pages_and_exports_match_independent_f4_sql():
    cookies = _configuration()
    raw_url = os.environ["F4_DATABASE_URL"]
    engine = create_engine(raw_url.replace("postgresql://", "postgresql+psycopg2://", 1))
    scopes = [v.strip() for v in os.environ["F4_SCOPE_PATHS"].split(",") if v.strip()]
    assert len(scopes) == 4
    today = datetime.now(ZoneInfo("Africa/Lagos")).date()
    sunday = today
    sunday -= timedelta(days=(sunday.weekday()+1)%7)
    start = sunday - timedelta(weeks=3)
    try:
        with engine.connect() as db, httpx.Client(base_url=os.environ["F4_BASE_URL"],cookies=cookies,
                follow_redirects=True,timeout=120) as client:
            campaign = db.execute(text("select id::text from program_campaigns where campaign_code=:m"),{"m":MARKER}).scalar_one()
            for scope in scopes:
                metrics = _sql(db,scope,start,today)
                q={"scope_path":scope,"include_pending":"false","date_from":start.isoformat(),"date_to":today.isoformat()}
                pages={}
                routes={
                  "finance":("/church-data/finance/content",{}),
                  "saturday":("/church-data/meetings/workers-saturday",{}),
                  "tuesday":("/church-data/meetings/leaders-tuesday",{}),
                  "fellowship":("/fellowship/content",{}),
                  "newcomers":("/church-data/newcomers/content",{}),
                  "retreat":("/church-data/programs/analytics/retreat",{"campaign_id":campaign}),
                  "crusade":("/church-data/programs/analytics/crusade",{}),
                  "dashboard":("/dashboard",{}),
                }
                for name,(route,extra) in routes.items():
                    response=client.get(route,params={**q,**extra})
                    assert response.status_code==200,(scope,name,response.status_code)
                    pages[name]=response.text
                row=metrics["counts"].get(sunday.isoformat())
                assert row is not None, (scope, metrics["counts"])
                panel_response=client.get("/dashboard/panels",params={**q,"weeks":4})
                assert panel_response.status_code==200
                panel_html=panel_response.text
                assert _dashboard_metric(pages["dashboard"],"Latest Sunday population").replace(",","")==str(row["total"])
                if scope == "org.234.KW.ILR.ILE":
                    assert "Reported 0" in BeautifulSoup(panel_html,"html.parser").get_text(" ",strip=True)
                assert str(row["total"]) in BeautifulSoup(panel_html,"html.parser").get_text(" ",strip=True).replace(",","")
                assert int(_summary_value(pages["saturday"], "Present workers")) == int(metrics["workers"]["present"])
                assert _table_column_sum(pages["saturday"], "Expected roster places") == int(metrics["workers"]["expected"])
                sat_rate = 0 if not metrics["workers"]["expected"] else round(
                    ((int(metrics["workers"]["present"]) + int(metrics["workers"]["late"])) / int(metrics["workers"]["expected"])) * 100, 1
                )
                assert int(_summary_value(pages["saturday"], "Late workers")) == int(metrics["workers"]["late"])
                assert _summary_value(pages["saturday"], "Attendance rate") == f"{sat_rate:.1f}%"
                assert int(_summary_value(pages["tuesday"], "Present workers")) == int(metrics["leaders"]["present"])
                assert _table_column_sum(pages["tuesday"], "Expected roster places") == int(metrics["leaders"]["expected"])
                leaders_rate = 0 if not metrics["leaders"]["expected"] else round(
                    ((int(metrics["leaders"]["present"]) + int(metrics["leaders"]["late"])) / int(metrics["leaders"]["expected"])) * 100, 1
                )
                assert int(_summary_value(pages["tuesday"], "Late workers")) == int(metrics["leaders"]["late"])
                assert _summary_value(pages["tuesday"], "Attendance rate") == f"{leaders_rate:.1f}%"
                fellowship_text = BeautifulSoup(pages["fellowship"], "html.parser").get_text(" ", strip=True).replace(",", "")
                assert str(int(metrics["fellowship"]["avg_attendance"])) in fellowship_text
                assert f"{metrics['fellowship']['latest_offering']:,.0f}" in BeautifulSoup(pages["fellowship"], "html.parser").get_text(" ", strip=True)
                retreat_text = BeautifulSoup(pages["retreat"], "html.parser").get_text(" ", strip=True).replace(",","")
                if int(metrics["event"]):
                    assert str(metrics["event"]) in retreat_text
                else:
                    assert "130" not in retreat_text, (scope, "region retreat count leaked below reporting scope")
                assert "Crusade" in BeautifulSoup(pages["crusade"], "html.parser").get_text(" ", strip=True)
                finance_text = BeautifulSoup(pages["finance"], "html.parser").get_text(" ", strip=True)
                finance_value = re.search(r"Approved in selected period\s+N([\d,]+)", finance_text)
                pending_value = re.search(r"Awaiting review\s+N([\d,]+)", finance_text)
                assert finance_value and int(finance_value.group(1).replace(",", "")) == int(metrics["offerings"]["approved_amount"])
                assert pending_value and int(pending_value.group(1).replace(",", "")) == int(metrics["offerings"]["pending_amount"])
                assert _dashboard_metric(pages["dashboard"],"Approved offerings").replace("₦","").replace(",","").replace(".00","") == str(int(metrics["offerings"]["approved_amount"]))
                assert _dashboard_metric(pages["dashboard"],"Newcomers")==str(metrics["records"].get("newcomer",0))
                assert _dashboard_metric(pages["dashboard"],"Converts")==str(metrics["records"].get("convert",0))
                assert _record_counts(pages["newcomers"]) == {
                    "Newcomer": metrics["records"].get("newcomer",0),
                    "Convert": metrics["records"].get("convert",0),
                }
                # Pastor report Excel and CSV are fetched over HTTP and parsed.
                export_params={"period":"recent","scope_path":scope,"include_pending":"false",
                               "campaign_id":campaign,"event_mode":"retreat"}
                x=client.get("/dashboard/pastor-report/export.xlsx",params=export_params)
                assert x.status_code==200
                wb=load_workbook(io.BytesIO(x.content),read_only=True,data_only=True)
                data=list(wb["Counts by category"].values)
                hdr=[str(v or "").upper() for v in data[0]]
                er=next(r for r in data[1:] if str(r[0])==sunday.isoformat() and str(r[2])==scope)
                assert int(er[hdr.index("TOTAL")] or 0)==row["total"]
                for key,label in (("adult_male","ADULT MALE"),("adult_female","ADULT FEMALE"),
                    ("youth_male","YOUTH MALE"),("youth_female","YOUTH FEMALE"),
                    ("children_male","CHILDREN MALE"),("children_female","CHILDREN FEMALE")):
                    assert int(er[hdr.index(label)] or 0)==row[key]
                offer_rows=list(wb["Offerings summary"].values)
                oh=[str(v or "").casefold() for v in offer_rows[0]]
                approved_offerings=[r for r in offer_rows[1:] if len(r)>max(oh.index("status"),oh.index("amount")) and str(r[oh.index("status")]).casefold()=="approved"]
                pending_offerings=[r for r in offer_rows[1:] if len(r)>max(oh.index("status"),oh.index("amount")) and str(r[oh.index("status")]).casefold() in {"pending","corrected"}]
                assert sum(float(r[oh.index("amount")] or 0) for r in approved_offerings)==float(metrics["offerings"]["approved_amount"])
                assert sum(float(r[oh.index("amount")] or 0) for r in pending_offerings)==float(metrics["offerings"]["pending_amount"])
                fund_totals = {}
                for row_data in approved_offerings:
                    fund = str(row_data[oh.index("fund type")]).casefold()
                    fund_totals[fund] = fund_totals.get(fund, 0) + float(row_data[oh.index("amount")] or 0)
                assert fund_totals == metrics["offerings"]["funds"]
                assert len(metrics["offering_correction"]) == 1
                assert "2026-10-31" in metrics["offering_correction"][0]["before_date"]
                assert "2026-11-01" in metrics["offering_correction"][0]["after_date"]
                hcf_rows=list(wb["House Caring Fellowship"].values)
                hcf_header=[str(v or "").casefold() for v in hcf_rows[0]]
                hcf_day=next((r for r in hcf_rows[1:] if str(r[0])==sunday.isoformat()),None)
                if hcf_day and metrics["fellowship"]["attendance_sum"]:
                    assert int(hcf_day[hcf_header.index("reported total")] or 0)==int(metrics["fellowship"]["attendance_sum"])
                event_rows=list(wb["Retreat Crusade"].values)
                event_header=[str(v or "").casefold() for v in event_rows[0]]
                marker_event=next((r for r in event_rows[1:] if MARKER in str(r[0])),None)
                assert marker_event is not None
                assert int(marker_event[event_header.index("population")] or 0)==int(metrics["event"])
                csv_resp=client.get("/dashboard/pastor-report/export.csv",params=export_params)
                assert csv_resp.status_code==200
                with zipfile.ZipFile(io.BytesIO(csv_resp.content)) as z:
                    csv_data=list(csv.reader(io.StringIO(z.read("counts_by_category.csv").decode("utf-8-sig"))))
                    offer_csv=list(csv.DictReader(io.StringIO(z.read("offerings_summary.csv").decode("utf-8-sig"))))
                    fellowship_csv=list(csv.DictReader(io.StringIO(z.read("house_caring_fellowship.csv").decode("utf-8-sig"))))
                    event_csv=list(csv.DictReader(io.StringIO(z.read("retreat_crusade.csv").decode("utf-8-sig"))))
                ch=[v.upper() for v in csv_data[0]]
                cr=next(r for r in csv_data[1:] if r[ch.index("SUNDAY")]==sunday.isoformat()
                        and r[ch.index("SCOPE PATH")]==scope)
                assert int(cr[ch.index("TOTAL")] or 0)==row["total"]
                assert _dashboard_metric(pages["dashboard"],"Newcomers")==str(metrics["records"].get("newcomer",0))
                assert sum(float(r.get("Amount") or 0) for r in offer_csv if str(r.get("Status", "")).casefold()=="approved") == float(metrics["offerings"]["approved_amount"])
                assert sum(float(r.get("Amount") or 0) for r in offer_csv if str(r.get("Status", "")).casefold() in {"pending","corrected"}) == float(metrics["offerings"]["pending_amount"])
                fellowship_export = next((r for r in fellowship_csv if str(r.get("Date"))==sunday.isoformat()), None)
                if fellowship_export and metrics["fellowship"]["attendance_sum"]:
                    assert int(fellowship_export["Reported total"] or 0)==int(metrics["fellowship"]["attendance_sum"])
                event_export = next((r for r in event_csv if MARKER in str(r.get("Campaign", ""))), None)
                assert event_export is not None
                assert int(event_export.get("Population") or 0)==int(metrics["event"])
                # Rendered dashboard card has the same Sunday total where in period.
                if row["total"] is not None:
                    assert str(row["total"]) in BeautifulSoup(pages["dashboard"], "html.parser").get_text(" ", strip=True).replace(",","")
    finally:
        engine.dispose()
