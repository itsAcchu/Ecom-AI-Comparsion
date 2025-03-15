# model/user_account.py
import sqlite3
import uuid
import hashlib
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

class UserAccount:
    def __init__(self, db_path: str = "data/users.db"):
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Create the database and tables if they don't exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
        ''')
        
        # Create user preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            preferred_stores TEXT,
            favorite_categories TEXT,
            price_alerts BOOLEAN DEFAULT 0,
            theme TEXT DEFAULT 'light',
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Create saved products table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            product_id TEXT,
            product_name TEXT,
            product_url TEXT,
            current_price REAL,
            target_price REAL,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Create search history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            query TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username: str, email: str, password: str) -> Dict:
        """Register a new user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if username or email already exists
            cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email))
            if cursor.fetchone():
                conn.close()
                return {"success": False, "message": "Username or email already exists"}
            
            # Generate unique user ID
            user_id = str(uuid.uuid4())
            password_hash = self._hash_password(password)
            
            # Insert user
            cursor.execute(
                "INSERT INTO users (user_id, username, email, password_hash) VALUES (?, ?, ?, ?)",
                (user_id, username, email, password_hash)
            )
            
            # Initialize user preferences
            cursor.execute(
                "INSERT INTO user_preferences (user_id, preferred_stores, favorite_categories, price_alerts, theme) VALUES (?, ?, ?, ?, ?)",
                (user_id, json.dumps(["Amazon", "Flipkart"]), json.dumps([]), 1, "light")
            )
            
            conn.commit()
            conn.close()
            
            return {"success": True, "user_id": user_id, "message": "User registered successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error registering user: {str(e)}"}
    
    def login_user(self, username_or_email: str, password: str) -> Dict:
        """Log in a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check credentials
            cursor.execute(
                "SELECT user_id, username, email FROM users WHERE (username = ? OR email = ?) AND password_hash = ?",
                (username_or_email, username_or_email, self._hash_password(password))
            )
            
            user = cursor.fetchone()
            if not user:
                conn.close()
                return {"success": False, "message": "Invalid credentials"}
            
            user_id, username, email = user
            
            # Update last login time
            cursor.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "user_id": user_id,
                "username": username,
                "email": email,
                "message": "Login successful"
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error during login: {str(e)}"}
    
    def get_user_preferences(self, user_id: str) -> Dict:
        """Get user preferences"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT preferred_stores, favorite_categories, price_alerts, theme FROM user_preferences WHERE user_id = ?", (user_id,))
            prefs = cursor.fetchone()
            
            if not prefs:
                conn.close()
                return {"success": False, "message": "User preferences not found"}
            
            preferred_stores, favorite_categories, price_alerts, theme = prefs
            
            conn.close()
            
            return {
                "success": True,
                "preferences": {
                    "preferred_stores": json.loads(preferred_stores),
                    "favorite_categories": json.loads(favorite_categories),
                    "price_alerts": bool(price_alerts),
                    "theme": theme
                }
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error fetching preferences: {str(e)}"}

    def update_user_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """Update user preferences"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                conn.close()
                return {"success": False, "message": "User not found"}
            
            # Update preferences
            updates = []
            params = []
            
            if "preferred_stores" in preferences:
                updates.append("preferred_stores = ?")
                params.append(json.dumps(preferences["preferred_stores"]))
            
            if "favorite_categories" in preferences:
                updates.append("favorite_categories = ?")
                params.append(json.dumps(preferences["favorite_categories"]))
            
            if "price_alerts" in preferences:
                updates.append("price_alerts = ?")
                params.append(1 if preferences["price_alerts"] else 0)
            
            if "theme" in preferences:
                updates.append("theme = ?")
                params.append(preferences["theme"])
            
            if not updates:
                conn.close()
                return {"success": False, "message": "No preferences to update"}
            
            query = f"UPDATE user_preferences SET {', '.join(updates)} WHERE user_id = ?"
            params.append(user_id)
            
            cursor.execute(query, tuple(params))
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Preferences updated successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error updating preferences: {str(e)}"}
    
    def add_saved_product(self, user_id: str, product_data: Dict) -> Dict:
        """Add a saved product for tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                conn.close()
                return {"success": False, "message": "User not found"}
            
            # Check if product already saved by this user
            cursor.execute(
                "SELECT id FROM saved_products WHERE user_id = ? AND product_id = ?",
                (user_id, product_data.get("product_id", ""))
            )
            
            existing = cursor.fetchone()
            if existing:
                # Update the existing entry
                cursor.execute(
                    """
                    UPDATE saved_products
                    SET product_name = ?, product_url = ?, current_price = ?, target_price = ?
                    WHERE id = ?
                    """,
                    (
                        product_data.get("product_name", ""),
                        product_data.get("product_url", ""),
                        product_data.get("current_price", 0.0),
                        product_data.get("target_price", 0.0),
                        existing[0]
                    )
                )
                product_id = existing[0]
                message = "Product updated successfully"
            else:
                # Insert new product
                cursor.execute(
                    """
                    INSERT INTO saved_products
                    (user_id, product_id, product_name, product_url, current_price, target_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        product_data.get("product_id", ""),
                        product_data.get("product_name", ""),
                        product_data.get("product_url", ""),
                        product_data.get("current_price", 0.0),
                        product_data.get("target_price", 0.0)
                    )
                )
                product_id = cursor.lastrowid
                message = "Product saved successfully"
            
            conn.commit()
            conn.close()
            
            return {"success": True, "product_id": product_id, "message": message}
            
        except Exception as e:
            return {"success": False, "message": f"Error saving product: {str(e)}"}
    
    def get_saved_products(self, user_id: str) -> Dict:
        """Get all saved products for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, product_id, product_name, product_url, current_price, 
                       target_price, date_added
                FROM saved_products
                WHERE user_id = ?
                ORDER BY date_added DESC
                """,
                (user_id,)
            )
            
            rows = cursor.fetchall()
            products = []
            
            for row in rows:
                product = {
                    "id": row["id"],
                    "product_id": row["product_id"],
                    "product_name": row["product_name"],
                    "product_url": row["product_url"],
                    "current_price": row["current_price"],
                    "target_price": row["target_price"],
                    "date_added": row["date_added"]
                }
                products.append(product)
            
            conn.close()
            
            return {"success": True, "products": products}
            
        except Exception as e:
            return {"success": False, "message": f"Error fetching saved products: {str(e)}"}
    
    def remove_saved_product(self, user_id: str, product_id: int) -> Dict:
        """Remove a saved product"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM saved_products WHERE user_id = ? AND id = ?",
                (user_id, product_id)
            )
            
            if cursor.rowcount > 0:
                message = "Product removed successfully"
                success = True
            else:
                message = "Product not found or not owned by this user"
                success = False
            
            conn.commit()
            conn.close()
            
            return {"success": success, "message": message}
            
        except Exception as e:
            return {"success": False, "message": f"Error removing product: {str(e)}"}
    
    def update_product_price(self, product_id: int, new_price: float) -> Dict:
        """Update the current price of a saved product"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE saved_products SET current_price = ? WHERE id = ?",
                (new_price, product_id)
            )
            
            if cursor.rowcount > 0:
                message = "Price updated successfully"
                success = True
            else:
                message = "Product not found"
                success = False
            
            conn.commit()
            conn.close()
            
            return {"success": success, "message": message}
            
        except Exception as e:
            return {"success": False, "message": f"Error updating price: {str(e)}"}
    
    def add_search_history(self, user_id: str, query: str) -> Dict:
        """Add an item to search history"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO search_history (user_id, query) VALUES (?, ?)",
                (user_id, query)
            )
            
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Search history updated"}
            
        except Exception as e:
            return {"success": False, "message": f"Error updating search history: {str(e)}"}
    
    def get_search_history(self, user_id: str, limit: int = 20) -> Dict:
        """Get recent search history for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, query, timestamp 
                FROM search_history 
                WHERE user_id = ? 
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (user_id, limit)
            )
            
            rows = cursor.fetchall()
            history = []
            
            for row in rows:
                item = {
                    "id": row["id"],
                    "query": row["query"],
                    "timestamp": row["timestamp"]
                }
                history.append(item)
            
            conn.close()
            
            return {"success": True, "history": history}
            
        except Exception as e:
            return {"success": False, "message": f"Error fetching search history: {str(e)}"}
    
    def clear_search_history(self, user_id: str) -> Dict:
        """Clear all search history for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM search_history WHERE user_id = ?",
                (user_id,)
            )
            
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Search history cleared successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error clearing search history: {str(e)}"}
    
    def change_password(self, user_id: str, current_password: str, new_password: str) -> Dict:
        """Change user password"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verify current password
            cursor.execute(
                "SELECT password_hash FROM users WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result or result[0] != self._hash_password(current_password):
                conn.close()
                return {"success": False, "message": "Current password is incorrect"}
            
            # Update to new password
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (self._hash_password(new_password), user_id)
            )
            
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Password changed successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error changing password: {str(e)}"}
    
    def update_user_profile(self, user_id: str, data: Dict) -> Dict:
        """Update user profile information"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if "email" in data:
                # Check if email is already in use
                cursor.execute(
                    "SELECT 1 FROM users WHERE email = ? AND user_id != ?",
                    (data["email"], user_id)
                )
                if cursor.fetchone():
                    conn.close()
                    return {"success": False, "message": "Email already in use"}
                
                updates.append("email = ?")
                params.append(data["email"])
            
            if "username" in data:
                # Check if username is already in use
                cursor.execute(
                    "SELECT 1 FROM users WHERE username = ? AND user_id != ?",
                    (data["username"], user_id)
                )
                if cursor.fetchone():
                    conn.close()
                    return {"success": False, "message": "Username already in use"}
                
                updates.append("username = ?")
                params.append(data["username"])
            
            if not updates:
                conn.close()
                return {"success": False, "message": "No data to update"}
            
            query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
            params.append(user_id)
            
            cursor.execute(query, tuple(params))
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Profile updated successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error updating profile: {str(e)}"}
    
    def delete_account(self, user_id: str, password: str) -> Dict:
        """Delete a user account and all associated data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verify password
            cursor.execute(
                "SELECT password_hash FROM users WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if not result or result[0] != self._hash_password(password):
                conn.close()
                return {"success": False, "message": "Incorrect password"}
            
            # Delete user data from all tables
            cursor.execute("DELETE FROM search_history WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM saved_products WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Account deleted successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error deleting account: {str(e)}"}
    
    def get_price_alerts(self, user_id: str) -> Dict:
        """Get products with current price below target price"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get user preference for price alerts
            cursor.execute(
                "SELECT price_alerts FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            pref = cursor.fetchone()
            
            if not pref or not pref["price_alerts"]:
                conn.close()
                return {"success": True, "alerts_enabled": False, "products": []}
            
            # Get products where current price is below target price
            cursor.execute(
                """
                SELECT id, product_id, product_name, product_url, current_price, target_price
                FROM saved_products
                WHERE user_id = ? AND current_price <= target_price AND target_price > 0
                """,
                (user_id,)
            )
            
            rows = cursor.fetchall()
            alerts = []
            
            for row in rows:
                alert = {
                    "id": row["id"],
                    "product_id": row["product_id"],
                    "product_name": row["product_name"],
                    "product_url": row["product_url"],
                    "current_price": row["current_price"],
                    "target_price": row["target_price"],
                    "savings": row["target_price"] - row["current_price"]
                }
                alerts.append(alert)
            
            conn.close()
            
            return {"success": True, "alerts_enabled": True, "products": alerts}
            
        except Exception as e:
            return {"success": False, "message": f"Error fetching price alerts: {str(e)}"}
            
    def get_user_stats(self, user_id: str) -> Dict:
        """Get user statistics and activity summary"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get account creation date and last login
            cursor.execute(
                "SELECT created_at, last_login FROM users WHERE user_id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                conn.close()
                return {"success": False, "message": "User not found"}
            
            created_at, last_login = user_data
            
            # Count saved products
            cursor.execute(
                "SELECT COUNT(*) FROM saved_products WHERE user_id = ?",
                (user_id,)
            )
            saved_products_count = cursor.fetchone()[0]
            
            # Count searches
            cursor.execute(
                "SELECT COUNT(*) FROM search_history WHERE user_id = ?",
                (user_id,)
            )
            search_count = cursor.fetchone()[0]
            
            # Get most recent searches
            cursor.execute(
                """
                SELECT query FROM search_history 
                WHERE user_id = ? 
                ORDER BY timestamp DESC LIMIT 5
                """,
                (user_id,)
            )
            recent_searches = [row[0] for row in cursor.fetchall()]
            
            # Count products with price alerts
            cursor.execute(
                """
                SELECT COUNT(*) FROM saved_products
                WHERE user_id = ? AND target_price > 0
                """,
                (user_id,)
            )
            price_alerts_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "success": True,
                "stats": {
                    "account_age_days": (datetime.now() - datetime.fromisoformat(created_at.replace(' ', 'T'))).days if created_at else 0,
                    "last_login": last_login,
                    "saved_products_count": saved_products_count,
                    "search_count": search_count,
                    "recent_searches": recent_searches,
                    "price_alerts_count": price_alerts_count
                }
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error fetching user stats: {str(e)}"}