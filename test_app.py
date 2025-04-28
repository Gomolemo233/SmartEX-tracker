import unittest
from app import app  # Assuming your Flask app is in a file called app.py
from flask import json

class FlaskAppTestCase(unittest.TestCase):
    
    # Set up the test client
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_signup_invalid_email(self):
        # Simulate form data for signup with invalid email
        response = self.app.post('/signup', data={
            'first-name': 'Test',
            'last-name': 'User',
            'username': 'testuser',
            'email': 'invalidemail',
            'password': 'password123',
            'confirm-password': 'password123',
            'account-type': 'personal'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid email format!", response.data.decode())

    def test_signup_password_mismatch(self):
        # Simulate form data with mismatching passwords
        response = self.app.post('/signup', data={
            'first-name': 'Test',
            'last-name': 'User',
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'password123',
            'confirm-password': 'password124',
            'account-type': 'personal'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Passwords do not match!", response.data.decode())

    def test_login_invalid_credentials(self):
        # Test login with invalid credentials
        response = self.app.post('/login', data={
            'username': 'wronguser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid credentials, please try again.", response.data.decode())

    def test_store_teller_token(self):
        # Test storing Teller access token
        token_data = {
            'access_token': 'dummy-access-token'
        }
        response = self.app.post('/store_teller_token', 
                                 data=json.dumps(token_data), 
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Access token stored successfully", response.data.decode())

    def test_dashboard_no_login(self):
        # Test accessing dashboard without being logged in
        response = self.app.get('/dashboard')
        self.assertEqual(response.status_code, 302)  # Should redirect to login page

    def test_dashboard_with_login(self):
        # Test accessing dashboard after logging in (you'd want to mock login here)
        # For simplicity, let's assume a user is already logged in:
        with self.app.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'testuser'
            session['first_name'] = 'Test'
            session['last_name'] = 'User'

        response = self.app.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Welcome, Test User!', response.data.decode())
        
    def test_connect_bank(self):
        # Simulate a GET request to connect the bank (which would show a page with the Teller Connect button)
        response = self.app.get('/connect_bank')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Connect to your bank", response.data.decode())

if __name__ == '__main__':
    unittest.main()
