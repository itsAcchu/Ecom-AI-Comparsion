# model/coupon_finder.py
import re
import requests
from bs4 import BeautifulSoup
import random
import time
from typing import Dict, List, Tuple
from datetime import datetime

class CouponFinder:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        ]
        # Popular coupon websites in India
        self.coupon_sites = [
            "https://www.grabon.in/amazon-coupons/",
            "https://www.grabon.in/flipkart-coupons/",
            "https://www.grabon.in/snapdeal-coupons/",
            "https://www.coupondunia.in/amazon",
            "https://www.coupondunia.in/flipkart",
            "https://www.coupondunia.in/snapdeal"
        ]
    
    def _get_random_headers(self) -> Dict:
        """Get random headers for web requests"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def fetch_coupons_for_site(self, site_name: str) -> List[Dict]:
        """Fetch coupons for a particular e-commerce site"""
        coupons = []
        site_name = site_name.lower()
        
        # Find matching coupon site URLs
        matching_sites = [site for site in self.coupon_sites if site_name in site.lower()]
        if not matching_sites:
            return coupons
        
        for coupon_site in matching_sites[:2]:  # Limit to 2 sites for efficiency
            try:
                headers = self._get_random_headers()
                response = requests.get(coupon_site, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Different patterns for different coupon sites
                    if "grabon" in coupon_site:
                        coupon_elements = soup.select("div.coupon-item, div.offer-item")
                        for element in coupon_elements[:10]:  # Get first 10 coupons
                            try:
                                code_element = element.select_one("div.coupon-code, span.offer-code")
                                code = code_element.text.strip() if code_element else "No Code Required"
                                
                                desc_element = element.select_one("h3.offer-title, div.offer-desc")
                                description = desc_element.text.strip() if desc_element else ""
                                
                                exp_element = element.select_one("div.expires-on, div.offer-expiry")
                                expiry = exp_element.text.strip() if exp_element else "Unknown"
                                
                                discount_match = re.search(r'(\d+%|\₹\s*\d+)', description)
                                discount_value = discount_match.group(1) if discount_match else "Special Offer"
                                
                                coupons.append({
                                    'code': code,
                                    'description': description,
                                    'expiry': expiry,
                                    'discount_value': discount_value,
                                    'source': 'GrabOn',
                                    'site': site_name
                                })
                            except Exception as e:
                                print(f"Error extracting coupon: {e}")
                                continue
                                
                    elif "coupondunia" in coupon_site:
                        coupon_elements = soup.select("div.coupon_item, div.offercard")
                        for element in coupon_elements[:10]:  # Get first 10 coupons
                            try:
                                code_element = element.select_one("div.coupon_code, span.offcd")
                                code = code_element.text.strip() if code_element else "No Code Required"
                                
                                desc_element = element.select_one("div.title, div.offrdesc")
                                description = desc_element.text.strip() if desc_element else ""
                                
                                exp_element = element.select_one("div.expires, div.offrexp")
                                expiry = exp_element.text.strip() if exp_element else "Unknown"
                                
                                discount_match = re.search(r'(\d+%|\₹\s*\d+)', description)
                                discount_value = discount_match.group(1) if discount_match else "Special Offer"
                                
                                coupons.append({
                                    'code': code,
                                    'description': description,
                                    'expiry': expiry,
                                    'discount_value': discount_value,
                                    'source': 'CouponDunia',
                                    'site': site_name
                                })
                            except Exception as e:
                                print(f"Error extracting coupon: {e}")
                                continue
                
                # Add delay to prevent rate limiting
                time.sleep(2)
                
            except Exception as e:
                print(f"Error fetching coupons from {coupon_site}: {e}")
        
        # Remove duplicates based on code
        unique_coupons = []
        seen_codes = set()
        for coupon in coupons:
            if coupon['code'] not in seen_codes:
                unique_coupons.append(coupon)
                seen_codes.add(coupon['code'])
        
        return unique_coupons

    def fetch_coupons_for_category(self, category: str) -> List[Dict]:
        """Fetch coupons for a particular product category"""
        # This function could use category-specific scraping from coupon sites
        # For now, we'll return a template with placeholder data
        return [
            {
                'code': f"SAVE{category[:3].upper()}20",
                'description': f"20% off on {category} products",
                'expiry': "2025-06-30",
                'discount_value': "20%",
                'source': 'CategorySpecific',
                'site': 'multiple'
            }
        ]
        
    def get_historical_discount_pattern(self, product_id: str, platform: str) -> Dict:
        """
        Get historical discount patterns for a product
        This would ideally use historical data from a database
        For now, we'll return placeholder data
        """
        # In a real implementation, this would query a database of historical prices
        current_month = datetime.now().month
        
        # Create some realistic discount patterns based on current month
        festival_months = [10, 11]  # October, November (Diwali, Black Friday)
        sale_months = [1, 6, 7]     # January (New Year), June-July (End of Season)
        
        if current_month in festival_months:
            peak_discount = random.randint(30, 50)
            avg_discount = random.randint(15, 25)
            recommendation = "Prices likely to drop further as festival season continues"
        elif current_month in sale_months:
            peak_discount = random.randint(20, 40)
            avg_discount = random.randint(10, 20)
            recommendation = "Current sales are ongoing, good time to buy"
        else:
            peak_discount = random.randint(15, 30)
            avg_discount = random.randint(5, 15)
            recommendation = "Consider waiting for upcoming sale season for better discounts"
            
        return {
            'product_id': product_id,
            'platform': platform,
            'peak_discount_percent': peak_discount,
            'average_discount_percent': avg_discount,
            'discount_frequency': f"{random.randint(2, 8)} times per year",
            'best_discount_months': "October, November, January" if platform in ["Amazon", "Flipkart"] else "January, July",
            'recommendation': recommendation
        }