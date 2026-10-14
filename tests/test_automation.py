import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from backend.parking import ParkingStore


def detection(plate='ABC123', score=.99):
    return [{'confidence':.95, 'ocr':{'normalized_text':plate, 'confidence':score}}]


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'parking.db'
        self.store=ParkingStore(self.path)
        self.start=datetime(2026,10,13,tzinfo=timezone.utc)

    def scan(self, seconds, detections=None, source='camera', event=None):
        return self.store.auto_scan(detection() if detections is None else detections,
            event or str(uuid4()),source,'station',self.start+timedelta(seconds=seconds))

    def test_upload_toggle_and_exact_retry(self):
        first=self.scan(0,source='upload',event='one')
        self.assertEqual(first['action'],'entry')
        self.assertEqual(self.scan(1,detection('XYZ456'),source='upload')['action'],'entry')
        last=self.scan(61,source='upload',event='two')
        self.assertEqual(last['action'],'exit')
        self.assertEqual(last['session']['amount_minor'],2000)
        self.assertEqual(self.scan(100,source='upload',event='one'),first)
        self.assertEqual(self.scan(100,source='upload',event='two'),last)
        self.assertEqual(len(self.store.list_sessions(True)),1)
        self.assertEqual(self.scan(120,source='upload')['action'],'entry')

    def test_camera_hold_then_remove_and_reappear(self):
        for second in [0,1]: self.assertEqual(self.scan(second)['status'],'stabilizing')
        self.assertEqual(self.scan(2)['action'],'entry')
        for second in range(3,9): self.assertEqual(self.scan(second)['status'],'already_seen')
        self.assertEqual(self.scan(9,[])['status'],'rearming')
        self.assertEqual(self.scan(10,[])['status'],'rearming')
        self.assertEqual(self.scan(12,[])['status'],'ready')
        self.scan(13);self.scan(14)
        self.assertEqual(self.scan(15)['action'],'exit')
        self.assertEqual(self.store.summary()['closed_count'],1)

    def test_uncertain_multiple_and_brief_blanks_do_not_rearm(self):
        for sec in [0,1,2]:self.scan(sec)
        for sec in [3,4,5]:self.assertEqual(self.scan(sec,detection(score=.2))['status'],'uncertain')
        for sec in [6,7,8]:self.assertEqual(self.scan(sec,detection()+detection('XYZ123'))['status'],'multiple')
        self.scan(9,[]);self.scan(10,[])
        self.assertEqual(self.scan(11)['status'],'already_seen')
        self.assertEqual(self.store.summary()['closed_count'],0)

    def test_different_plate_can_enter_and_gate_survives_restart(self):
        for sec in [0,1,2]:self.scan(sec)
        for sec in [3,4]:self.scan(sec,detection('XYZ456'))
        self.assertEqual(self.scan(5,detection('XYZ456'))['action'],'entry')
        self.store=ParkingStore(self.path)
        self.assertEqual(self.scan(6)['status'],'already_seen')
        self.assertEqual(self.store.summary()['active_count'],2)

    def test_frame_retry_is_not_another_vote_and_flicker_resets(self):
        first=self.scan(0,event='same')
        self.assertEqual(self.scan(1,event='same'),first)
        self.assertEqual(self.scan(2,event='same'),first)
        self.scan(3,detection('XYZ456'));self.scan(4)
        self.assertEqual(self.scan(5)['status'],'stabilizing')
        self.assertEqual(self.scan(6)['action'],'entry')

    def test_uncertain_upload_does_not_write(self):
        for det in [[],detection(score=.2),detection('ABCD'),detection()+detection('XYZ456')]:
            self.assertNotIn('action',self.scan(0,det,source='upload'))
        self.assertEqual(self.store.summary()['active_count'],0)

    def test_readable_plate_ignores_unreadable_background_upload(self):
        mixed = detection('TN21AT8349') + detection('', score=0)
        first = self.scan(0,mixed,source='upload',event='mixed-entry')
        self.assertEqual(first['action'],'entry')
        self.assertEqual(self.store.list_sessions(True)[0]['plate'],'TN21AT8349')
        self.assertEqual(self.scan(1,mixed,source='upload',event='mixed-entry'),first)
        self.assertEqual(self.scan(61,mixed,source='upload')['action'],'exit')
        self.assertEqual(self.store.summary()['active_count'],0)

    def test_readable_plate_with_background_camera_stability_and_hold(self):
        mixed = detection() + detection('BAD123',score=.2)
        self.assertEqual(self.scan(0,mixed)['status'],'stabilizing')
        self.assertEqual(self.scan(1,list(reversed(mixed)))['status'],'stabilizing')
        self.assertEqual(self.scan(2,mixed)['action'],'entry')
        for sec in (3,4,5):self.assertEqual(self.scan(sec,mixed)['status'],'already_seen')
        self.assertEqual(self.store.summary()['active_count'],1)
        self.assertEqual(self.store.summary()['closed_count'],0)

    def test_duplicate_boxes_for_one_plate_record_only_once(self):
        self.assertEqual(self.scan(0,detection()+detection(),source='upload')['action'],'entry')
        self.assertEqual(self.store.summary()['active_count'],1)

    def test_legacy_hourly_migration(self):
        path=Path(self.temp.name)/'legacy.db'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY, plate TEXT NOT NULL, entry_time TEXT NOT NULL, exit_time TEXT, hourly_rate_minor INTEGER NOT NULL, currency TEXT DEFAULT "PKR", duration_seconds INTEGER, billed_hours INTEGER, amount_minor INTEGER)')
            db.execute('INSERT INTO sessions(id,plate,entry_time,hourly_rate_minor) VALUES (?,?,?,?)',('old','OLD123',self.start.isoformat(),10000))
        db.close()
        store=ParkingStore(path)
        old=store.exit('old','OLD123',self.start+timedelta(minutes=61))
        self.assertEqual(old['amount_minor'],20000)
        self.assertEqual(old['rate_unit'],'hour')
        self.assertEqual(store.enter('NEW123',self.start)['unit_rate_minor'],1000)

if __name__=='__main__':unittest.main()
