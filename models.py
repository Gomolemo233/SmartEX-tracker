# models.py
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, user_row):
        self.id = user_row['UserID']
        self.username = user_row['Username']
        self.first_name = user_row['FirstName']
        self.last_name = user_row['LastName']
