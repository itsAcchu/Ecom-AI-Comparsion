# model/price_tracker.py
import requests
from bs4 import BeautifulSoup
import random
import time
import re
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import matplotlib.pyplot as plt
import pandas as pd

class PriceTracker:
    def __init__(self, db_path: str = "data/prices.db"):
        self.db_path = db_path
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        ]
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Create the database and tables if they don't exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create products table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            platform TEXT NOT NULL,
            url TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            last_updated TIMESTAMP
        )
        ''')
        
        # Create price history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            price REAL NOT NULL,
            discount_percentage REAL,
            original_price REAL,
            availability TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        )
        ''')
        
        # Create price alerts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            target_price REAL NOT NULL,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_random_headers(self) -> Dict:
        """Get random headers for web requests"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _extract_amazon_price(self, url: str) -> Dict:
        """Extract price information from Amazon product page"""
        try:
            headers = self._get_random_headers()
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to fetch page: {response.status_code}"
                }
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract product name
            product_name_element = soup.select_one("span#productTitle")
            product_name = product_name_element.text.strip() if product_name_element else "Unknown Product"
            
            # Extract product ID
            product_id = None
            product_id_match = re.search(r'/dp/([A-Z0-9]{10})', url)
            if product_id_match:
                product_id = product_id_match.group(1)
                
            # Extract brand
            brand_element = soup.select_one("a#bylineInfo, a#brand")
            brand = None
            if brand_element:
                brand_text = brand_element.text.strip()
                brand_match = re.search(r'Brand: (.*)|Visit the (.*) Store', brand_text)
                if brand_match:
                    brand = brand_match.group(1) or brand_match.group(2)
            
            # Extract current price
            price = None
            price_element = soup.select_one("span.a-price .a-offscreen")
            if price_element:
                price_text = price_element.text.strip()
                price_match = re.search(r'₹\s*([\d,]+\.?\d*)|₹([\d,]+\.?\d*)', price_text)
                if price_match:
                    price_str = price_match.group(1) or price_match.group(2)
                    price = float(price_str.replace(',', ''))
            
            # Extract original price
            original_price = None
            original_price_element = soup.select_one("span.a-price.a-text-price .a-offscreen")
            if original_price_element:
                original_price_text = original_price_element.text.strip()
                original_price_match = re.search(r'₹\s*([\d,]+\.?\d*)|₹([\d,]+\.?\d*)', original_price_text)
                if original_price_match:
                    original_price_str = original_price_match.group(1) or original_price_match.group(2)
                    original_price = float(original_price_str.replace(',', ''))
            
            # Calculate discount percentage
            discount_percentage = None
            if price and original_price and original_price > price:
                discount_percentage = round(((original_price - price) / original_price) * 100, 2)
            
            # Check availability
            availability = "In Stock"
            availability_element = soup.select_one("#availability span")
            if availability_element:
                availability_text = availability_element.text.strip().lower()
                if "out of stock" in availability_text:
                    availability = "Out of Stock"
                elif "in stock" not in availability_text:
                    availability = "Unknown"
            
            # Extract category
            category = None
            breadcrumb_elements = soup.select("#wayfinding-breadcrumbs_feature_div ul li:not(.a-breadcrumb-divider)")
            if breadcrumb_elements and len(breadcrumb_elements) > 0:
                category = breadcrumb_elements[-1].text.strip()
            
            return {
                "success": True,
                "product_id": product_id,
                "name": product_name,
                "platform": "Amazon",
                "url": url,
                "price": price,
                "original_price": original_price,
                "discount_percentage": discount_percentage,
                "availability": availability,
                "category": category,
                "brand": brand
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error extracting Amazon price: {str(e)}"
            }
    
    def _extract_flipkart_price(self, url: str) -> Dict:
        """Extract price information from Flipkart product page"""
        try:
            headers = self._get_random_headers()
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to fetch page: {response.status_code}"
                }
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract product name
            product_name_element = soup.select_one("span.B_NuCI")
            product_name = product_name_element.text.strip() if product_name_element else "Unknown Product"
            
            # Extract product ID
            product_id = None
            product_id_match = re.search(r'/p/itm([a-zA-Z0-9]+)', url)
            if product_id_match:
                product_id = product_id_match.group(1)
            
            # Extract brand
            brand = None
            # Try to extract from the product name
            if product_name:
                brand_match = re.match(r'^([A-Za-z0-9\-\s]+)', product_name)
                if brand_match:
                    brand = brand_match.group(1).strip()
            
            # Extract current price
            price = None
            price_element = soup.select_one("div._30jeq3._16Jk6d")
            if price_element:
                price_text = price_element.text.strip()
                price_match = re.search(r'₹([\d,]+)', price_text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            # Extract original price
            original_price = None
            original_price_element = soup.select_one("div._3I9_wc._2p6lqe")
            if original_price_element:
                original_price_text = original_price_element.text.strip()
                original_price_match = re.search(r'₹([\d,]+)', original_price_text)
                if original_price_match:
                    original_price = float(original_price_match.group(1).replace(',', ''))
            
            # Calculate discount percentage
            discount_percentage = None
            discount_element = soup.select_one("div._3Ay6Sb._31Dcoz")
            if discount_element:
                discount_text = discount_element.text.strip()
                discount_match = re.search(r'(\d+)%', discount_text)
                if discount_match:
                    discount_percentage = float(discount_match.group(1))
            elif price and original_price and original_price > price:
                discount_percentage = round(((original_price - price) / original_price) * 100, 2)
            
            # Check availability
            availability = "In Stock"
            out_of_stock_element = soup.select_one("div._16FRp0")
            if out_of_stock_element and "out of stock" in out_of_stock_element.text.lower():
                availability = "Out of Stock"
            
            # Extract category
            category = None
            breadcrumb_elements = soup.select("div._36fx1h._6t1WkM._3HqJxg div._2whKao")
            if breadcrumb_elements and len(breadcrumb_elements) > 0:
                category = breadcrumb_elements[-1].text.strip()
            
            return {
                "success": True,
                "product_id": product_id,
                "name": product_name,
                "platform": "Flipkart",
                "url": url,
                "price": price,
                "original_price": original_price,
                "discount_percentage": discount_percentage,
                "availability": availability,
                "category": category,
                "brand": brand
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error extracting Flipkart price: {str(e)}"
            }
    
    def _extract_snapdeal_price(self, url: str) -> Dict:
        """Extract price information from Snapdeal product page"""
        try:
            headers = self._get_random_headers()
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to fetch page: {response.status_code}"
                }
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract product name
            product_name_element = soup.select_one("h1.pdp-e-i-head")
            product_name = product_name_element.text.strip() if product_name_element else "Unknown Product"
            
            # Extract product ID
            product_id = None
            product_id_match = re.search(r'/product/(\d+)', url)
            if product_id_match:
                product_id = product_id_match.group(1)
            
            # Extract brand
            brand = None
            brand_element = soup.select_one("div.pdp-e-brand-logo-top span.pdp-e-brand-logo-name")
            if brand_element:
                brand = brand_element.text.strip()
            
            # Extract current price
            price = None
            price_element = soup.select_one("span.payBlkBig")
            if price_element:
                price_text = price_element.text.strip()
                price_match = re.search(r'Rs\.\s*([\d,]+)', price_text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            # Extract original price
            original_price = None
            original_price_element = soup.select_one("div.pdpCutPrice")
            if original_price_element:
                original_price_text = original_price_element.text.strip()
                original_price_match = re.search(r'Rs\.\s*([\d,]+)', original_price_text)
                if original_price_match:
                    original_price = float(original_price_match.group(1).replace(',', ''))
            
            # Calculate discount percentage
            discount_percentage = None
            discount_element = soup.select_one("div.pdpDiscount span")
            if discount_element:
                discount_text = discount_element.text.strip()
                discount_match = re.search(r'(\d+)%', discount_text)
                if discount_match:
                    discount_percentage = float(discount_match.group(1))
            elif price and original_price and original_price > price:
                discount_percentage = round(((original_price - price) / original_price) * 100, 2)
            
            # Check availability
            availability = "In Stock"
            out_of_stock_element = soup.select_one("div.notifyMe-soldout")
            if out_of_stock_element:
                availability = "Out of Stock"
            
            # Extract category
            category = None
            breadcrumb_elements = soup.select("div.bread-crumb a")
            if breadcrumb_elements and len(breadcrumb_elements) > 0:
                category = breadcrumb_elements[-1].text.strip()
            
            return {
                "success": True,
                "product_id": product_id,
                "name": product_name,
                "platform": "Snapdeal",
                "url": url,
                "price": price,
                "original_price": original_price,
                "discount_percentage": discount_percentage,
                "availability": availability,
                "category": category,
                "brand": brand
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error extracting Snapdeal price: {str(e)}"
            }
    
    def track_product(self, url: str) -> Dict:
        """Track a product from a supported e-commerce platform"""
        if "amazon" in url.lower():
            result = self._extract_amazon_price(url)
        elif "flipkart" in url.lower():
            result = self._extract_flipkart_price(url)
        elif "snapdeal" in url.lower():
            result = self._extract_snapdeal_price(url)
        else:
            return {
                "success": False,
                "message": "Unsupported platform. Currently supports Amazon, Flipkart, and Snapdeal."
            }
        
        if result["success"]:
            self._save_product_data(result)
        
        return result
    
    def _save_product_data(self, data: Dict) -> None:
        """Save product data to the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # First, check if product already exists
            cursor.execute(
                "SELECT product_id FROM products WHERE product_id = ?", 
                (data["product_id"],)
            )
            existing = cursor.fetchone()
            
            # Update or insert product information
            if existing:
                cursor.execute(
                    """
                    UPDATE products 
                    SET name = ?, platform = ?, url = ?, category = ?, brand = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE product_id = ?
                    """,
                    (data["name"], data["platform"], data["url"], 
                     data.get("category"), data.get("brand"), data["product_id"])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO products (product_id, name, platform, url, category, brand, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (data["product_id"], data["name"], data["platform"], data["url"], 
                     data.get("category"), data.get("brand"))
                )
            
            # Save price history
            cursor.execute(
                """
                INSERT INTO price_history (product_id, price, discount_percentage, original_price, availability)
                VALUES (?, ?, ?, ?, ?)
                """,
                (data["product_id"], data.get("price"), data.get("discount_percentage"), 
                 data.get("original_price"), data.get("availability"))
            )
            
            # Check for price alerts
            if data.get("price") is not None:
                cursor.execute(
                    """
                    SELECT a.id, a.user_id, a.target_price, p.name
                    FROM price_alerts a
                    JOIN products p ON a.product_id = p.product_id
                    WHERE a.product_id = ? AND a.active = 1 AND a.target_price >= ?
                    """,
                    (data["product_id"], data.get("price"))
                )
                
                triggered_alerts = cursor.fetchall()
                for alert in triggered_alerts:
                    # Mark alert as inactive
                    cursor.execute(
                        "UPDATE price_alerts SET active = 0 WHERE id = ?",
                        (alert[0],)
                    )
                    # In a real application, you would notify the user here
                    print(f"ALERT: Price of {alert[3]} dropped to {data.get('price')} below target of {alert[2]} for user {alert[1]}")
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving product data: {str(e)}")
    
    def get_product_history(self, product_id: str, days: int = 30) -> Dict:
        """Get price history for a product over specified number of days"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            cursor = conn.cursor()
            
            # Get product details
            cursor.execute(
                """
                SELECT * FROM products WHERE product_id = ?
                """,
                (product_id,)
            )
            product = cursor.fetchone()
            
            if not product:
                return {
                    "success": False,
                    "message": f"Product with ID {product_id} not found"
                }
            
            # Get price history for the specified time period
            cursor.execute(
                """
                SELECT price, discount_percentage, original_price, availability, timestamp
                FROM price_history
                WHERE product_id = ? AND timestamp >= datetime('now', ?)
                ORDER BY timestamp ASC
                """,
                (product_id, f'-{days} days')
            )
            
            history = cursor.fetchall()
            
            result = {
                "success": True,
                "product": dict(product),
                "history": [dict(record) for record in history]
            }
            
            conn.close()
            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"Error retrieving product history: {str(e)}"
            }
    
    def set_price_alert(self, user_id: str, product_id: str, target_price: float) -> Dict:
        """Set a price alert for a product"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if product exists
            cursor.execute(
                "SELECT product_id FROM products WHERE product_id = ?", 
                (product_id,)
            )
            if not cursor.fetchone():
                conn.close()
                return {
                    "success": False,
                    "message": f"Product with ID {product_id} not found"
                }
            
            # Create a new alert
            cursor.execute(
                """
                INSERT INTO price_alerts (user_id, product_id, target_price, active)
                VALUES (?, ?, ?, 1)
                """,
                (user_id, product_id, target_price)
            )
            
            alert_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "message": "Price alert set successfully",
                "alert_id": alert_id
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error setting price alert: {str(e)}"
            }
    
    def delete_price_alert(self, alert_id: int) -> Dict:
        """Delete a price alert"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM price_alerts WHERE id = ?",
                (alert_id,)
            )
            
            if cursor.rowcount > 0:
                result = {
                    "success": True,
                    "message": f"Alert with ID {alert_id} deleted successfully"
                }
            else:
                result = {
                    "success": False,
                    "message": f"Alert with ID {alert_id} not found"
                }
            
            conn.commit()
            conn.close()
            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"Error deleting price alert: {str(e)}"
            }
    
    def get_user_alerts(self, user_id: str) -> Dict:
        """Get all active price alerts for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT a.id, a.product_id, a.target_price, a.created_at,
                       p.name, p.platform, p.url
                FROM price_alerts a
                JOIN products p ON a.product_id = p.product_id
                WHERE a.user_id = ? AND a.active = 1
                """,
                (user_id,)
            )
            
            alerts = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return {
                "success": True,
                "alerts": alerts
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting user alerts: {str(e)}"
            }
    
    def generate_price_chart(self, product_id: str, days: int = 30) -> str:
        """Generate and save a price chart for a product"""
        try:
            # Get product history data
            history_data = self.get_product_history(product_id, days)
            
            if not history_data["success"]:
                return None
            
            # Extract data for chart
            product_name = history_data["product"]["name"]
            dates = []
            prices = []
            
            for record in history_data["history"]:
                timestamp = datetime.strptime(record["timestamp"], "%Y-%m-%d %H:%M:%S")
                dates.append(timestamp)
                prices.append(record["price"])
            
            # Create DataFrame for easier manipulation
            df = pd.DataFrame({
                'date': dates,
                'price': prices
            })
            
            # Create the chart
            plt.figure(figsize=(12, 6))
            plt.plot(df['date'], df['price'], marker='o', linestyle='-', color='blue')
            plt.title(f"Price History for {product_name}")
            plt.xlabel("Date")
            plt.ylabel("Price (₹)")
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Create charts directory if it doesn't exist
            os.makedirs("data/charts", exist_ok=True)
            
            # Save the chart
            chart_path = f"data/charts/{product_id}_{datetime.now().strftime('%Y%m%d')}.png"
            plt.savefig(chart_path)
            plt.close()
            
            return chart_path
        except Exception as e:
            print(f"Error generating price chart: {str(e)}")
            return None
    
    def batch_track_products(self, urls: List[str]) -> Dict:
        """Track multiple products at once"""
        results = {
            "success": [],
            "failed": []
        }
        
        for url in urls:
            result = self.track_product(url)
            if result["success"]:
                results["success"].append({
                    "url": url,
                    "product_id": result["product_id"],
                    "name": result["name"],
                    "price": result.get("price")
                })
            else:
                results["failed"].append({
                    "url": url,
                    "message": result.get("message", "Unknown error")
                })
        
        return {
            "success": True,
            "total": len(urls),
            "successful": len(results["success"]),
            "failed": len(results["failed"]),
            "results": results
        }
    
    def find_price_drops(self, threshold_percentage: float = 5.0, days: int = 7) -> List[Dict]:
        """Find products with significant price drops within a given period"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get products with recent price drops
            cursor.execute(
                """
                SELECT p.product_id, p.name, p.platform, p.url,
                       h1.price as current_price, 
                       h2.price as previous_price,
                       ((h2.price - h1.price) / h2.price * 100) as price_drop_percentage
                FROM products p
                JOIN price_history h1 ON p.product_id = h1.product_id
                JOIN (
                    SELECT product_id, MAX(timestamp) as max_timestamp
                    FROM price_history
                    GROUP BY product_id
                ) latest ON p.product_id = latest.product_id AND h1.timestamp = latest.max_timestamp
                JOIN price_history h2 ON p.product_id = h2.product_id
                JOIN (
                    SELECT product_id, MAX(timestamp) as prev_timestamp
                    FROM price_history
                    WHERE timestamp <= datetime('now', ?)
                    GROUP BY product_id
                ) previous ON p.product_id = previous.product_id AND h2.timestamp = previous.prev_timestamp
                WHERE ((h2.price - h1.price) / h2.price * 100) >= ?
                ORDER BY price_drop_percentage DESC
                """,
                (f'-{days} days', threshold_percentage)
            )
            
            drops = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return drops
        except Exception as e:
            print(f"Error finding price drops: {str(e)}")
            return []
    
    def get_product_recommendations(self, product_id: str) -> List[Dict]:
        """Get product recommendations based on category and brand"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get category and brand of the target product
            cursor.execute(
                """
                SELECT category, brand FROM products WHERE product_id = ?
                """,
                (product_id,)
            )
            product_info = cursor.fetchone()
            
            if not product_info:
                conn.close()
                return []
            
            category = product_info["category"]
            brand = product_info["brand"]
            
            # Find similar products by category and brand
            cursor.execute(
                """
                SELECT p.product_id, p.name, p.platform, p.url, p.category, p.brand,
                       h.price
                FROM products p
                JOIN (
                    SELECT product_id, MAX(timestamp) as max_timestamp
                    FROM price_history
                    GROUP BY product_id
                ) latest ON p.product_id = latest.product_id
                JOIN price_history h ON p.product_id = h.product_id AND h.timestamp = latest.max_timestamp
                WHERE p.product_id != ? AND (p.category = ? OR p.brand = ?)
                ORDER BY 
                    CASE WHEN p.category = ? AND p.brand = ? THEN 1
                         WHEN p.brand = ? THEN 2
                         WHEN p.category = ? THEN 3
                         ELSE 4
                    END,
                    h.price ASC
                LIMIT 5
                """,
                (product_id, category, brand, category, brand, brand, category)
            )
            
            recommendations = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return recommendations
        except Exception as e:
            print(f"Error getting product recommendations: {str(e)}")
            return []