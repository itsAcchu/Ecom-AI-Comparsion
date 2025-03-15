# model/scraper.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from concurrent.futures import ThreadPoolExecutor
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ECommerceComparisonModel:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        ]
        
        # Configure Chrome options for Selenium
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Get weights from session state if available
        if 'weights' in st.session_state:
            self.weights = st.session_state.weights
        else:
            # Default weights
            self.weights = {
                'price': 0.4,
                'ratings': 0.3,
                'reviews': 0.2, 
                'description_relevance': 0.1
            }
    
    def _get_random_headers(self):
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _clean_price(self, price_str):
        if not price_str:
            return None
        # Remove currency symbols and commas
        price = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(price)
        except:
            return None
    
    def _extract_rating(self, rating_str):
        if not rating_str:
            return 0
        # Extract rating value (e.g., "4.5 out of 5" -> 4.5)
        match = re.search(r'(\d+(\.\d+)?)', rating_str)
        if match:
            return float(match.group(1))
        return 0
    
    def _extract_reviews_count(self, reviews_str):
        if not reviews_str:
            return 0
        # Extract number of reviews (e.g., "1,234 reviews" -> 1234)
        match = re.search(r'(\d+[,\d]*)', reviews_str)
        if match:
            return int(match.group(1).replace(',', ''))
        return 0
    
    def search_amazon(self, query):
        search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        products = []
        
        try:
            # Using Selenium for Amazon (handles dynamic content)
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.get(search_url)
            
            # Wait for product cards to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-result-item"))
            )
            
            # Find product elements
            product_elements = driver.find_elements(By.CSS_SELECTOR, "div.s-result-item[data-component-type='s-search-result']")
            
            for element in product_elements[:10]:  # Limit to first 10 products
                try:
                    # Try multiple selectors for title
                    title = ""
                    try:
                        title_element = element.find_element(By.CSS_SELECTOR, "span.a-text-normal")
                        title = title_element.text
                    except:
                        try:
                            title_element = element.find_element(By.CSS_SELECTOR, ".a-size-medium.a-color-base.a-text-normal")
                            title = title_element.text
                        except:
                            try:
                                title_element = element.find_element(By.CSS_SELECTOR, ".a-size-base-plus.a-color-base.a-text-normal")
                                title = title_element.text
                            except:
                                continue  # Skip if no title found
                    
                    # Try multiple selectors for link
                    link = ""
                    try:
                        link_element = element.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")
                        link = link_element.get_attribute("href")
                    except:
                        try:
                            link_element = element.find_element(By.CSS_SELECTOR, ".a-link-normal.s-underline-text.s-underline-link-text")
                            link = link_element.get_attribute("href")
                        except:
                            continue  # Skip if no link found
                    
                    # Price might be in different formats
                    price_text = ""
                    try:
                        price_element = element.find_element(By.CSS_SELECTOR, ".a-price .a-offscreen")
                        price_text = price_element.get_attribute("innerHTML")
                    except:
                        try:
                            price_element = element.find_element(By.CSS_SELECTOR, ".a-price-whole")
                            price_text = price_element.text
                        except:
                            pass  # Price might not be available
                    
                    # Rating and reviews
                    rating_text = ""
                    try:
                        rating_element = element.find_element(By.CSS_SELECTOR, "i.a-icon-star-small, i.a-icon-star")
                        rating_text = rating_element.get_attribute("aria-label")
                    except:
                        pass  # Rating might not be available
                    
                    reviews_text = ""
                    try:
                        reviews_element = element.find_element(By.CSS_SELECTOR, "span.a-size-base.s-underline-text, span.a-size-base")
                        reviews_text = reviews_element.text
                    except:
                        pass  # Reviews might not be available
                    
                    # Image URL
                    image_url = ""
                    try:
                        img_element = element.find_element(By.CSS_SELECTOR, "img.s-image")
                        image_url = img_element.get_attribute("src")
                    except:
                        pass  # Image might not be available
                    
                    # Only add products that have at least title and link
                    if title and link:
                        products.append({
                            'title': title,
                            'price': self._clean_price(price_text),
                            'rating': self._extract_rating(rating_text),
                            'reviews': self._extract_reviews_count(reviews_text),
                            'link': link,
                            'image': image_url,
                            'source': 'Amazon',
                            'description': title  # Using title as description for now
                        })
                except Exception as e:
                    logging.error(f"Error extracting Amazon product: {e}")
                    continue
            
            driver.quit()
        except Exception as e:
            logging.error(f"Error searching Amazon: {e}")
        
        return products
    
    def search_snapdeal(self, query):
        search_url = f"https://www.snapdeal.com/search?keyword={query.replace(' ', '%20')}"
        products = []
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Add a random delay to mimic human behavior
                time.sleep(random.uniform(1, 3))
                
                # Use a random user agent
                headers = self._get_random_headers()
                response = requests.get(search_url, headers=headers, timeout=20)  # Increased timeout
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find product elements
                    product_elements = soup.select("div.product-tuple-listing")
                    
                    for element in product_elements[:10]:  # Limit to first 10 products
                        try:
                            # Title
                            title_element = element.select_one("p.product-title")
                            if not title_element:
                                continue
                            title = title_element.text.strip()
                            
                            # Link
                            link_element = element.select_one("a.dp-widget-link")
                            if link_element:
                                link = link_element.get('href', '')
                            else:
                                continue
                            
                            # Price
                            price_element = element.select_one("span.product-price")
                            price_text = price_element.text if price_element else ""
                            
                            # Rating
                            rating_element = element.select_one("div.filled-stars")
                            rating_text = rating_element.get('style', '') if rating_element else ""
                            if rating_text:
                                rating_text = re.search(r'width:\s*(\d+)%', rating_text)
                                rating_text = float(rating_text.group(1)) / 20 if rating_text else 0
                            else:
                                rating_text = 0
                            
                            # Reviews
                            reviews_element = element.select_one("p.product-rating-count")
                            reviews_text = reviews_element.text if reviews_element else ""
                            
                            # Image
                            image_element = element.select_one("img.product-image")
                            image_url = image_element.get('src', '') if image_element else ""
                            
                            products.append({
                                'title': title,
                                'price': self._clean_price(price_text),
                                'rating': rating_text,
                                'reviews': self._extract_reviews_count(reviews_text),
                                'link': link,
                                'image': image_url,
                                'source': 'Snapdeal',
                                'description': title  # Using title as description for now
                            })
                        except Exception as e:
                            logging.error(f"Error extracting Snapdeal product: {e}")
                            continue
                    break  # Exit retry loop if successful
                else:
                    logging.warning(f"Snapdeal search attempt {attempt + 1} failed with status code {response.status_code}")
            except Exception as e:
                logging.error(f"Error searching Snapdeal (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    logging.error("Max retries reached for Snapdeal search.")
                time.sleep(5)  # Wait before retrying
        
        return products
    
    def process_and_compare_products(self, all_products, query):
        """Process and compare products without performing the search again"""
        if not all_products:
            return {"message": "No products found", "products": []}
        
        # Create a DataFrame for analysis
        df = pd.DataFrame(all_products)
        
        # Handle missing values
        df['price'] = df['price'].fillna(df['price'].mean())
        df['rating'] = df['rating'].fillna(0)
        df['reviews'] = df['reviews'].fillna(0)
        
        # Calculate relevance score based on query using TF-IDF
        vectorizer = TfidfVectorizer()
        try:
            description_vectors = vectorizer.fit_transform(df['description'].fillna(''))
            query_vector = vectorizer.transform([query])
            relevance_scores = cosine_similarity(query_vector, description_vectors)[0]
            df['description_relevance'] = relevance_scores
        except:
            # If TF-IDF fails, assign equal relevance
            df['description_relevance'] = 1.0
        
        # Normalize features
        for feature in ['price', 'rating', 'reviews', 'description_relevance']:
            if feature == 'price':
                # For price, lower is better
                if df[feature].max() != df[feature].min():
                    df[f'{feature}_norm'] = 1 - ((df[feature] - df[feature].min()) / (df[feature].max() - df[feature].min()))
                else:
                    df[f'{feature}_norm'] = 1.0
            else:
                # For other features, higher is better
                if df[feature].max() != df[feature].min():
                    df[f'{feature}_norm'] = (df[feature] - df[feature].min()) / (df[feature].max() - df[feature].min())
                else:
                    df[f'{feature}_norm'] = 1.0
        
        # Calculate weighted score
        df['score'] = (
            df['price_norm'] * self.weights['price'] +
            df['rating_norm'] * self.weights['ratings'] +
            df['reviews_norm'] * self.weights['reviews'] +
            df['description_relevance_norm'] * self.weights['description_relevance']
        )
        
        # Sort by score
        df = df.sort_values('score', ascending=False)
        
        # Add rank and clean up result
        df['rank'] = range(1, len(df) + 1)
        
        # Prepare results
        results = []
        for _, row in df.iterrows():
            results.append({
                'rank': int(row['rank']),
                'title': row['title'],
                'price': row['price'],
                'rating': row['rating'],
                'reviews': int(row['reviews']),
                'score': round(row['score'] * 100, 2),  # Convert to percentage
                'source': row['source'],
                'link': row['link'],
                'image': row['image']
            })
        
        # Get best product from each source
        best_by_source = {}
        for product in results:
            source = product['source']
            if source not in best_by_source:
                best_by_source[source] = product
        
        return {
            "message": f"Found {len(results)} products matching '{query}'",
            "top_results": results[:5],
            "best_by_source": list(best_by_source.values()),
            "all_products": results
        }
    
    def search_and_compare(self, query):
        # Perform searches in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            amazon_future = executor.submit(self.search_amazon, query)
            snapdeal_future = executor.submit(self.search_snapdeal, query)
            
            amazon_products = amazon_future.result()
            snapdeal_products = snapdeal_future.result()
            
            # Combine all products from different sources
            all_products = amazon_products + snapdeal_products
            
            # Process and compare the combined products
            return self.process_and_compare_products(all_products, query)