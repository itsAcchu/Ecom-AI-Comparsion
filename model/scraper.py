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

class ECommerceComparisonModel:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
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
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-result-item"))
            )
            
            # Find product elements
            product_elements = driver.find_elements(By.CSS_SELECTOR, "div.s-result-item[data-component-type='s-search-result']")
            
            for element in product_elements[:10]:  # Limit to first 10 products
                try:
                    title_element = element.find_element(By.CSS_SELECTOR, "h2 a span")
                    title = title_element.text
                    
                    link_element = element.find_element(By.CSS_SELECTOR, "h2 a")
                    link = link_element.get_attribute("href")
                    
                    # Price might be in different formats
                    try:
                        price_element = element.find_element(By.CSS_SELECTOR, ".a-price .a-offscreen")
                        price_text = price_element.get_attribute("innerHTML")
                    except:
                        try:
                            price_element = element.find_element(By.CSS_SELECTOR, ".a-price-whole")
                            price_text = price_element.text
                        except:
                            price_text = ""
                    
                    try:
                        rating_element = element.find_element(By.CSS_SELECTOR, "i.a-icon-star-small")
                        rating_text = rating_element.get_attribute("aria-label")
                    except:
                        rating_text = ""
                    
                    try:
                        reviews_element = element.find_element(By.CSS_SELECTOR, "span.a-size-base.s-underline-text")
                        reviews_text = reviews_element.text
                    except:
                        reviews_text = ""
                    
                    image_url = ""
                    try:
                        img_element = element.find_element(By.CSS_SELECTOR, "img.s-image")
                        image_url = img_element.get_attribute("src")
                    except:
                        pass
                    
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
                    print(f"Error extracting Amazon product: {e}")
                    continue
            
            driver.quit()
        except Exception as e:
            print(f"Error searching Amazon: {e}")
        
        return products
    
    def search_flipkart(self, query):
        search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
        products = []
        
        try:
            response = requests.get(search_url, headers=self._get_random_headers(), timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find product elements
                product_elements = soup.select("div._1AtVbE")
                
                for element in product_elements[:10]:  # Limit to first 10 products
                    try:
                        title_element = element.select_one("div._4rR01T, a.s1Q9rs")
                        if not title_element:
                            continue
                            
                        title = title_element.text.strip()
                        
                        link_element = element.select_one("a._1fQZEK, a.s1Q9rs")
                        if link_element:
                            link = "https://www.flipkart.com" + link_element.get('href', '')
                        else:
                            continue
                        
                        price_element = element.select_one("div._30jeq3")
                        price_text = price_element.text if price_element else ""
                        
                        rating_element = element.select_one("div._3LWZlK")
                        rating_text = rating_element.text if rating_element else ""
                        
                        reviews_element = element.select_one("span._2_R_DZ, span._13vcmD")
                        reviews_text = reviews_element.text if reviews_element else ""
                        
                        image_element = element.select_one("img._396cs4")
                        image_url = image_element.get('src', '') if image_element else ""
                        
                        products.append({
                            'title': title,
                            'price': self._clean_price(price_text),
                            'rating': self._extract_rating(rating_text),
                            'reviews': self._extract_reviews_count(reviews_text),
                            'link': link,
                            'image': image_url,
                            'source': 'Flipkart',
                            'description': title  # Using title as description for now
                        })
                    except Exception as e:
                        print(f"Error extracting Flipkart product: {e}")
                        continue
        except Exception as e:
            print(f"Error searching Flipkart: {e}")
        
        return products
    
    def search_myntra(self, query):
        search_url = f"https://www.myntra.com/{query.replace(' ', '-')}"
        products = []
        
        try:
            # Using Selenium for Myntra (handles dynamic content)
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.get(search_url)
            
            # Wait for product cards to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.product-base"))
            )
            
            # Find product elements
            product_elements = driver.find_elements(By.CSS_SELECTOR, "li.product-base")
            
            for element in product_elements[:10]:  # Limit to first 10 products
                try:
                    title_element = element.find_element(By.CSS_SELECTOR, "h3.product-brand")
                    title = title_element.text
                    
                    product_name_element = element.find_element(By.CSS_SELECTOR, "h4.product-product")
                    product_name = product_name_element.text
                    
                    full_title = f"{title} {product_name}"
                    
                    link_element = element.find_element(By.CSS_SELECTOR, "a.product-base")
                    link = link_element.get_attribute("href")
                    
                    price_element = element.find_element(By.CSS_SELECTOR, "div.product-price span")
                    price_text = price_element.text
                    
                    # Myntra doesn't show ratings on search page, need to visit product page
                    rating_text = ""
                    reviews_text = ""
                    
                    image_element = element.find_element(By.CSS_SELECTOR, "img.product-image")
                    image_url = image_element.get_attribute("src")
                    
                    products.append({
                        'title': full_title,
                        'price': self._clean_price(price_text),
                        'rating': 0,  # Default to 0 since not available on search page
                        'reviews': 0,  # Default to 0 since not available on search page
                        'link': link,
                        'image': image_url,
                        'source': 'Myntra',
                        'description': full_title  # Using full title as description for now
                    })
                except Exception as e:
                    print(f"Error extracting Myntra product: {e}")
                    continue
            
            driver.quit()
        except Exception as e:
            print(f"Error searching Myntra: {e}")
        
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
    with ThreadPoolExecutor(max_workers=3) as executor:
        amazon_future = executor.submit(self.search_amazon, query)
        flipkart_future = executor.submit(self.search_flipkart, query)
        myntra_future = executor.submit(self.search_myntra, query)
        
        amazon_products = amazon_future.result()
        flipkart_products = flipkart_future.result()
        myntra_products = myntra_future.result()
        
        # Combine all products from different sources
        all_products = amazon_products + flipkart_products + myntra_products
        
        # Process and compare the combined products
        return self.process_and_compare_products(all_products, query)