"""Opt-in regression against the running demo API and real MySQL timestamp precision.

ATTENDANCE_API_URL=http://127.0.0.1:8000 python -m unittest discover -s tests
The temporary account is removed in tearDown, even if assertions fail.
"""
import os
import secrets
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import delete
from config import Settings
from database import make_engine, make_sessions
from models import AuthSession, Student

@unittest.skipUnless(os.getenv('ATTENDANCE_API_URL'), 'Set ATTENDANCE_API_URL to run the live MySQL regression.')
class MySQLSessionTests(unittest.TestCase):
    def setUp(self):
        self.client = httpx.Client(base_url=os.environ['ATTENDANCE_API_URL'], timeout=10)
        if not self.client.get('/config').json().get('demo_mode'):
            self.client.close()
            self.skipTest('Integration account creation is restricted to a demo API.')
        self.student_id = 'QA' + secrets.token_hex(4).upper()
        self.password = secrets.token_urlsafe(24)
        response = self.client.post('/register', json={'student_id':self.student_id,'name':'Session Regression',
            'email':self.student_id.lower()+'@example.test','password':self.password,'group_id':1})
        self.assertEqual(response.status_code,201,response.text)

    def tearDown(self):
        self.client.close()
        if hasattr(self,'student_id'):
            engine = make_engine(Settings())
            with make_sessions(engine).begin() as db:
                db.execute(delete(AuthSession).where(AuthSession.student_id==self.student_id))
                db.execute(delete(Student).where(Student.student_id==self.student_id))
            engine.dispose()

    def test_logout_revocation_is_visible_immediately(self):
        # Multiple real round trips exercise subsecond MySQL DATETIME rounding.
        for _ in range(4):
            login = self.client.post('/login',json={'student_id':self.student_id,'password':self.password})
            self.assertEqual(login.status_code,200,login.text)
            self.client.headers['Authorization']='Bearer '+login.json()['access_token']
            self.assertEqual(self.client.get('/me').status_code,200)
            self.assertEqual(self.client.post('/logout').status_code,200)
            self.assertEqual(self.client.get('/me').status_code,401, 'A revoked token was still accepted immediately after logout.')
