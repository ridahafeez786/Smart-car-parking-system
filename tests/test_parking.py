import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError
from backend.parking import ConfirmedPlate, ParkingStore, present


class ParkingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "parking.sqlite3"
        self.store = ParkingStore(self.path)
        self.start = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)

    def test_summary_counts_active_and_closed_separately(self):
        self.assertEqual(self.store.summary(), {"active_count": 0, "closed_count": 0, "total_amount_minor": 0})
        first = self.store.enter("TEST001", self.start)
        self.store.enter("TEST002", self.start)
        self.store.exit(first["id"], first["plate"], self.start + timedelta(minutes=90))
        self.assertEqual(self.store.summary(), {"active_count": 1, "closed_count": 1, "total_amount_minor": 20000})

    def test_confirmation_and_normalization(self):
        self.assertEqual(ConfirmedPlate(plate="tn 99-f 2378", confirmed=True).plate, "TN99F2378")
        for body in ({"plate": "TN99F2378"}, {"plate": "TN99F2378", "confirmed": False},
                     {"plate": "!!!", "confirmed": True}):
            with self.assertRaises(ValidationError):
                ConfirmedPlate(**body)

    def test_duplicate_entry_and_persistence(self):
        row = self.store.enter("TN99F2378", self.start)
        with self.assertRaises(HTTPException) as caught:
            self.store.enter("TN99F2378", self.start)
        self.assertEqual(caught.exception.status_code, 409)
        reopened = ParkingStore(self.path)
        self.assertEqual(reopened.list_sessions(True)[0]["id"], row["id"])

    def test_fee_boundaries_and_entry_rate_snapshot(self):
        for index, (duration, charge) in enumerate([
            (timedelta(0), 10000), (timedelta(hours=1), 10000),
            (timedelta(hours=1, microseconds=1), 20000), (timedelta(hours=2), 20000)
        ]):
            plate = f"TEST{index}"
            row = self.store.enter(plate, self.start)
            other = ParkingStore(self.path, hourly_rate_minor=50000)
            closed = other.exit(row["id"], plate, self.start + duration)
            self.assertEqual(closed["amount_minor"], charge)

    def test_exit_retries_preserve_receipt_and_new_visit(self):
        row = self.store.enter("TN99F2378", self.start)
        closed = self.store.exit(row["id"], row["plate"], self.start + timedelta(minutes=2))
        second = self.store.enter(row["plate"], self.start + timedelta(hours=1))
        retry = self.store.exit(row["id"], row["plate"], self.start + timedelta(days=1))
        self.assertEqual(closed, retry)
        self.assertEqual(self.store.list_sessions(True)[0]["id"], second["id"])
        self.assertEqual(len(self.store.list_sessions(False)), 1)
        self.assertEqual(present(self.store.receipt(row["id"]))["amount"], "100.00")

    def test_bad_exit_and_active_receipt_do_not_close_session(self):
        row = self.store.enter("TN99F2378", self.start)
        for action in [
            lambda: self.store.exit(row["id"], "WRONG123", self.start),
            lambda: self.store.exit(row["id"], row["plate"], self.start - timedelta(seconds=1)),
            lambda: self.store.receipt(row["id"]),
        ]:
            with self.assertRaises(HTTPException):
                action()
        self.assertEqual(len(self.store.list_sessions(True)), 1)


if __name__ == "__main__":
    unittest.main()
