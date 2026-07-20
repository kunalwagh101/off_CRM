from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "sales.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )


def _create(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "lead_name": "Asha Mehta",
        "company": "Acme Climate",
        "email": "asha@example.com",
        "source": "LinkedIn",
        "setter_name": "Sam Setter",
        "closer_name": "Cora Closer",
    }
    payload.update(overrides)
    response = client.post("/api/v1/sales/leads", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_sales_kanban_is_single_source_of_truth_with_leak_flags(tmp_path: Path) -> None:
    old = datetime.now(timezone.utc) - timedelta(days=20)
    with TestClient(create_app(_settings(tmp_path))) as client:
        lead = _create(
            client,
            date_created=old.isoformat(),
            first_contact_at=(old + timedelta(minutes=15)).isoformat(),
            date_meeting_booked=(old + timedelta(days=1)).isoformat(),
            meeting_at=(old + timedelta(days=7)).isoformat(),
            last_touch_at=old.isoformat(),
            deposit_amount=250,
            deposit_received_at=old.isoformat(),
            total_deal_value=1500,
            commission_percent=12,
        )
        assert lead["earnings"] == 180
        assert set(lead["leak_flags"]) == {"booking_lag", "deposit_unpaid"}

        moved = client.post(
            f"/api/v1/sales/leads/{lead['id']}/move",
            json={
                "lead_status": "follow_up_ongoing",
                "expected_revision": lead["revision"],
            },
        )
        assert moved.status_code == 200
        moved_lead = moved.json()
        assert moved_lead["follow_up_aging"] is True
        assert "follow_up_aging" in moved_lead["leak_flags"]

        stale = client.patch(
            f"/api/v1/sales/leads/{lead['id']}",
            json={"notes": "stale overwrite", "expected_revision": lead["revision"]},
        )
        assert stale.status_code == 409

        missing_reason = client.post(
            f"/api/v1/sales/leads/{lead['id']}/move",
            json={
                "lead_status": "lost",
                "expected_revision": moved_lead["revision"],
            },
        )
        assert missing_reason.status_code == 422
        assert "Loss reason" in missing_reason.json()["detail"]

        lost = client.patch(
            f"/api/v1/sales/leads/{lead['id']}",
            json={
                "lead_status": "lost",
                "loss_reason": "price",
                "expected_revision": moved_lead["revision"],
            },
        )
        assert lost.status_code == 200
        assert lost.json()["loss_reason_label"] == "Price"

        board = client.get("/api/v1/sales/board").json()
        assert board["total"] == 1
        assert next(item for item in board["columns"] if item["status"] == "lost")["count"] == 1
        events = client.get(f"/api/v1/sales/leads/{lead['id']}/events").json()
        assert events["total"] == 3


def test_sales_dashboard_calculates_setter_closer_and_money_metrics(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        won = _create(
            client,
            lead_name="Won Lead",
            lead_status="won",
            date_created="2026-01-01T09:00:00Z",
            first_contact_at="2026-01-01T09:10:00Z",
            date_meeting_booked="2026-01-02T09:00:00Z",
            meeting_at="2026-01-05T09:00:00Z",
            meeting_status="show",
            offer_made=True,
            sale_type="one_call",
            deposit_amount=200,
            deposit_received_at="2026-01-05T09:00:00Z",
            total_deal_value=1000,
            cash_collected=1000,
            date_paid_in_full="2026-01-10T09:00:00Z",
            refund_clawback_amount=100,
            commission_percent=10,
        )
        assert won["earnings"] == 90
        _create(
            client,
            lead_name="Lost Lead",
            lead_status="lost",
            loss_reason="price",
            date_created="2026-01-03T09:00:00Z",
            first_contact_at="2026-01-03T09:30:00Z",
            date_meeting_booked="2026-01-04T09:00:00Z",
            meeting_at="2026-01-10T09:00:00Z",
            meeting_status="no_show",
        )
        activity = client.post(
            "/api/v1/sales/activity",
            json={
                "activity_date": "2026-01-02",
                "setter_name": "Sam Setter",
                "dials_dms_sent": 100,
                "conversations": 20,
                "declines": 3,
            },
        )
        assert activity.status_code == 200
        goal = client.patch(
            "/api/v1/sales/goals/2026-01",
            json={"revenue_goal": 5000, "cash_goal": 4000, "currency": "USD"},
        )
        assert goal.status_code == 200

        response = client.get(
            "/api/v1/sales/dashboard?start_date=2026-01-01&end_date=2026-01-31"
        )
        assert response.status_code == 200, response.text
        dashboard = response.json()
        setter = dashboard["setter_summary"]
        assert setter["dials_dms_sent"] == 100
        assert setter["conversations_to_booked_rate"] == 10
        assert setter["speed_to_lead_minutes"] == 20
        assert setter["booking_lag_days"] == 4.5
        assert setter["calls_scheduled"] == 2
        assert setter["calls_taken"] == 1
        assert setter["no_shows"] == 1
        closer = dashboard["closer_summary"]
        assert closer["offer_rate"] == 100
        assert closer["close_rate"] == 100
        assert closer["close_rate_on_offers"] == 100
        assert closer["average_deal_size"] == 1000
        assert closer["revenue_per_call"] == 1000
        money = dashboard["money"]
        assert money["revenue_generated"] == 1000
        assert money["cash_collected"] == 1000
        assert money["refunds_clawbacks"] == 100
        assert money["net_revenue"] == 900
        assert money["commissions_total"] == 90
        assert money["goal_completion_percent"] == 20
        assert money["deposit_to_paid_in_full_rate"] == 100
        assert money["average_days_to_collect"] == 5
        price = next(item for item in dashboard["loss_reasons"] if item["reason"] == "price")
        assert price["count"] == 1
        assert price["percent"] == 100


def test_projection_supports_manual_scenarios_and_current_month_revenue(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    with TestClient(create_app(_settings(tmp_path))) as client:
        _create(
            client,
            lead_name="Current Win",
            lead_status="won",
            meeting_status="show",
            offer_made=True,
            sale_type="follow_up",
            total_deal_value=1000,
            cash_collected=600,
            date_created=now.isoformat(),
        )
        projection = client.post(
            "/api/v1/sales/projection",
            json={
                "forecast_month": month,
                "meetings_scheduled": 10,
                "show_up_rate": 80,
                "offer_rate": 50,
                "close_rate": 25,
                "average_deal_size": 2000,
                "cash_collection_rate": 60,
            },
        )
        assert projection.status_code == 200, projection.text
        body = projection.json()
        expected = next(item for item in body["scenarios"] if item["name"] == "expected")
        worst = next(item for item in body["scenarios"] if item["name"] == "worst")
        best = next(item for item in body["scenarios"] if item["name"] == "best")
        assert body["current_revenue"] == 1000
        assert body["current_cash"] == 600
        assert expected["projected_sales"] == 1
        assert expected["incremental_revenue"] == 2000
        assert expected["end_of_month_revenue"] == 3000
        assert worst["end_of_month_revenue"] < expected["end_of_month_revenue"]
        assert best["end_of_month_revenue"] > expected["end_of_month_revenue"]


@pytest.mark.parametrize("month", ["2026-13", "Jan-2026", ""])
def test_invalid_goal_month_is_rejected(tmp_path: Path, month: str) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.patch(
            f"/api/v1/sales/goals/{month}",
            json={"revenue_goal": 1000, "cash_goal": 0, "currency": "USD"},
        )
        assert response.status_code in {404, 422}
