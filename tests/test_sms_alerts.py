"""Unit tests for app/services/sms_alerts.py's orchestration logic
(cooldowns, severity gating) with every DB/Twilio-touching helper mocked --
no real Postgres or Twilio needed, matching this project's existing split
between pure-logic tests and integration testing (see alert_engine's own
test file). db_conn is never touched directly: every function that would
query it is monkeypatched instead.
"""
import datetime
from unittest.mock import patch

from app.services import sms_alerts


def test_format_alert_message_contains_zone_and_severity():
    msg = sms_alerts.format_alert_message("Ranipool", "high")
    assert "HIGH" in msg
    assert "Ranipool" in msg


def test_trigger_zone_alert_skips_within_cooldown():
    recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    with patch.object(sms_alerts, "get_last_alert_time_by_channel", return_value=recent):
        result = sms_alerts.trigger_zone_alert(db=None, zone_id="z1", zone_name="Ranipool", severity="high")
    assert result["skipped"] is True
    assert "Cooldown" in result["reason"]


def test_trigger_zone_alert_skips_with_no_subscribers():
    with patch.object(sms_alerts, "get_last_alert_time_by_channel", return_value=None), \
         patch.object(sms_alerts, "get_subscribers_for_zone", return_value=[]):
        result = sms_alerts.trigger_zone_alert(db=None, zone_id="z1", zone_name="Ranipool", severity="high")
    assert result["skipped"] is True
    assert "subscribers" in result["reason"]


def test_trigger_zone_alert_sends_to_all_subscribers():
    with patch.object(sms_alerts, "get_last_alert_time_by_channel", return_value=None), \
         patch.object(sms_alerts, "get_subscribers_for_zone", return_value=["+911", "+912"]), \
         patch.object(sms_alerts, "send_sms", side_effect=lambda to, msg: {"to": to, "success": True, "sid": "SM1"}), \
         patch.object(sms_alerts, "log_alert_sent") as mock_log:
        result = sms_alerts.trigger_zone_alert(db=None, zone_id="z1", zone_name="Ranipool", severity="high")

    assert result == {
        "skipped": False, "attempted": 2, "sent": 2, "failed": 0,
        "results": [
            {"to": "+911", "success": True, "sid": "SM1"},
            {"to": "+912", "success": True, "sid": "SM1"},
        ],
    }
    mock_log.assert_called_once_with(None, "z1", "high", 2, channel="sms")


def test_escalate_critical_alert_never_calls_below_critical_severity():
    with patch.object(sms_alerts, "trigger_zone_alert", return_value={"skipped": True, "reason": "no subscribers"}), \
         patch.object(sms_alerts, "get_authority_contacts") as mock_contacts:
        result = sms_alerts.escalate_critical_alert(db=None, zone_id="z1", zone_name="Ranipool", severity="high")

    assert result["calls"] == {"skipped": True, "reason": "Not critical severity"}
    mock_contacts.assert_not_called()  # never even looks up authorities below critical


def test_escalate_critical_alert_calls_authorities_when_critical():
    with patch.object(sms_alerts, "trigger_zone_alert", return_value={"skipped": True, "reason": "no subscribers"}), \
         patch.object(sms_alerts, "get_last_alert_time_by_channel", return_value=None), \
         patch.object(sms_alerts, "get_authority_contacts", return_value=[{"name": "Officer A", "phone": "+913"}]), \
         patch.object(sms_alerts, "make_alert_call", return_value={"to": "+913", "success": True, "sid": "CA1"}), \
         patch.object(sms_alerts, "log_alert_sent") as mock_log:
        result = sms_alerts.escalate_critical_alert(db=None, zone_id="z1", zone_name="Ranipool", severity="critical")

    assert result["calls"]["skipped"] is False
    assert result["calls"]["called"] == 1
    mock_log.assert_called_once_with(None, "z1", "critical", 1, channel="call")


def test_escalate_critical_alert_respects_send_sms_false():
    """The Broadcast composer passes send_sms=False when the operator didn't
    select the "sms" channel -- calls should still fire on critical severity,
    but no text should go out."""
    with patch.object(sms_alerts, "trigger_zone_alert") as mock_sms, \
         patch.object(sms_alerts, "get_last_alert_time_by_channel", return_value=None), \
         patch.object(sms_alerts, "get_authority_contacts", return_value=[{"name": "Officer A", "phone": "+913"}]), \
         patch.object(sms_alerts, "make_alert_call", return_value={"to": "+913", "success": True, "sid": "CA1"}), \
         patch.object(sms_alerts, "log_alert_sent"):
        result = sms_alerts.escalate_critical_alert(
            db=None, zone_id="z1", zone_name="Ranipool", severity="critical", send_sms=False,
        )

    mock_sms.assert_not_called()
    assert result["sms"] == {"skipped": True, "reason": "sms channel not selected"}
    assert result["calls"]["called"] == 1


def test_send_sms_returns_failure_dict_when_twilio_not_configured():
    with patch.object(sms_alerts, "get_twilio_client", side_effect=RuntimeError("Twilio not configured")):
        result = sms_alerts.send_sms("+911", "test message")
    assert result["success"] is False
    assert "not configured" in result["error"]


def test_make_alert_call_returns_failure_dict_when_twilio_not_configured():
    with patch.object(sms_alerts, "get_twilio_client", side_effect=RuntimeError("Twilio not configured")):
        result = sms_alerts.make_alert_call("+911", "test message")
    assert result["success"] is False
    assert "not configured" in result["error"]
