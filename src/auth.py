"""
Admin Authentication for Keil's Service Deli
Username/Password with Role Selection (Joey or Michael)
"""

import hashlib
from typing import Optional


# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "6wtUzguuYNwQ_bMabqpd"

# Available roles after admin login
ADMIN_ROLES = ["Michael", "Steve", "Joey"]


class AuthManager:
    def __init__(self, data_dir=None):
        self.admin_username = ADMIN_USERNAME
        self.admin_password_hash = self._hash_password(ADMIN_PASSWORD)
    
    def _hash_password(self, password: str) -> str:
        """Simple password hashing"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """
        Authenticate with username and password.
        Returns admin info if credentials match, None otherwise.
        """
        if username == self.admin_username:
            if self._hash_password(password) == self.admin_password_hash:
                return {
                    'id': 'ADMIN',
                    'name': 'Admin',
                    'role': 'admin',
                    'authenticated': True
                }
        return None
    
    def get_available_roles(self) -> list:
        """Get list of available roles to select"""
        return ADMIN_ROLES
    
    def select_role(self, role: str) -> Optional[dict]:
        """Select a role after admin authentication"""
        if role in ADMIN_ROLES:
            return {
                'id': f'ROLE_{role.upper()}',
                'name': role,
                'role': 'manager',  # Joey, Michael, and Steve have manager access
                'display_role': role
            }
        return None
    
    # Legacy methods for compatibility (not used with new admin system)
    def add_user(self, name: str, password: str, role: str = 'staff') -> bool:
        return False  # Disabled - admin only system
    
    def get_all_users(self) -> list:
        return [{'id': 'ADMIN', 'name': 'Admin', 'role': 'admin'}]
    
    def delete_user(self, user_id: str) -> bool:
        return False  # Disabled - admin only system
