import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from service import RoomReserve,BookingError

class BookingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.db'
        self.api=RoomReserve(self.path)
        self.admin=self.api.create_user(None,'admin01','password123','admin')
        self.teacher=self.api.create_user(self.admin,'instructor01','password123','instructor')
        self.teacher2=self.api.create_user(self.admin,'instructor02','password123','instructor')
        self.room=self.api.add_room(self.admin,'LAB-101','Computer Lab','Laboratory',30)
        self.day=(date.today()+timedelta(days=5)).isoformat()
    def tearDown(self):self.tmp.cleanup()
    def request(self,user=None,start='09:00',end='10:00',attendees=20):
        return self.api.request(user or self.teacher,self.room,self.day,start,end,'Programming class',attendees)
    def test_bootstrap_and_auth(self):
        self.assertEqual(self.api.login('admin01','password123')['role'],'admin')
        with self.assertRaises(BookingError):self.api.login('admin01','incorrect')
        with self.assertRaises(BookingError):self.api.create_user(None,'thirduser','password123','instructor')
    def test_permissions(self):
        with self.assertRaises(BookingError):self.api.add_room(self.teacher,'A12','New Room','Classroom',20)
        with self.assertRaises(BookingError):self.api.create_user(self.teacher,'newuser','password123','instructor')
        bid=self.request()
        with self.assertRaises(BookingError):self.api.review(self.teacher,bid,True)
    def test_pending_and_approval_conflict(self):
        a=self.request();b=self.request(self.teacher2,'09:30','10:30')
        self.assertEqual(len(self.api.available(self.day,'09:30','09:45')),1)
        self.api.review(self.admin,a,True)
        self.assertEqual(self.api.available(self.day,'09:30','09:45'),[])
        with self.assertRaises(BookingError):self.api.review(self.admin,b,True)
        self.assertEqual(len(self.api.reservations(self.admin,status='Pending')),1)
    def test_adjacent_reservations_allowed(self):
        a=self.request();self.api.review(self.admin,a,True)
        b=self.request(self.teacher2,'10:00','11:00');self.api.review(self.admin,b,True)
        self.assertEqual(len(self.api.reservations(public=True,day=self.day)),2)
    def test_limits_and_invalid_times(self):
        for start,end in [('10:00','10:00'),('12:00','11:00'),('9am','10:00')]:
            with self.subTest(start=start),self.assertRaises(BookingError):self.request(start=start,end=end)
        with self.assertRaises(BookingError):self.request(attendees=31)
        with self.assertRaises(BookingError):self.api.request(self.teacher,self.room,'2021-01-01','09:00','10:00','Lecture',10)
    def test_public_privacy_and_ownership(self):
        a=self.request();self.assertEqual(self.api.reservations(public=True),[])
        self.assertEqual(self.api.reservations(self.teacher2),[])
        with self.assertRaises(BookingError):self.api.cancel(self.teacher2,a)
        self.api.review(self.admin,a,True)
        self.assertEqual(len(self.api.reservations(public=True)),1)
        self.api.cancel(self.teacher,a)
        self.assertEqual(self.api.reservations(public=True),[])
    def test_disabled_room_and_rejected_request(self):
        a=self.request();self.api.set_room_active(self.admin,self.room,False)
        with self.assertRaises(BookingError):self.api.review(self.admin,a,True)
        with self.assertRaises(BookingError):self.request()
        self.api.review(self.admin,a,False,'Unavailable')
        self.assertEqual(self.api.reservations(self.admin)[0]['review_note'],'Unavailable')
    def test_persistence_and_search(self):
        a=self.request();self.api.review(self.admin,a,True)
        later=RoomReserve(self.path)
        self.assertEqual(len(later.reservations(public=True,day=self.day,room_id=self.room)),1)
        self.assertEqual(len(later.available(self.day,'10:00','11:00',category='Laboratory')),1)
        self.assertEqual(later.available(self.day,'09:00','09:30',category='Classroom'),[])
    def test_duplicate_room_and_validation(self):
        with self.assertRaises(BookingError):self.api.add_room(self.admin,'lab-101','Duplicate','Lab',30)
        with self.assertRaises(BookingError):self.api.add_room(self.admin,'ROOM2','Extra','Classroom',0)
        with self.assertRaises(BookingError):self.api.request(self.teacher,self.room,self.day,'08:00','09:00','',10)
    def test_edit_room_and_capacity_protection(self):
        self.api.edit_room(self.admin,self.room,'LAB-201','Advanced Lab','Laboratory',45)
        self.assertEqual(self.api.rooms()[0]['code'],'LAB-201')
        bid=self.request(attendees=40)
        self.api.review(self.admin,bid,True)
        with self.assertRaises(BookingError):
            self.api.edit_room(self.admin,self.room,'LAB-201','Advanced Lab','Laboratory',20)
        with self.assertRaises(BookingError):
            self.api.edit_room(self.teacher,self.room,'LAB-201','Advanced Lab','Laboratory',50)

    def test_cancel_frees_room(self):
        a=self.request();self.api.review(self.admin,a,True)
        self.api.cancel(self.admin,a)
        self.assertEqual(len(self.api.available(self.day,'09:00','10:00')),1)

if __name__=='__main__':unittest.main()
