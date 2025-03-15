# model/review_analyzer.py
import re
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from collections import Counter
import streamlit as st
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import pandas as pd
import random
import time
from typing import Dict, List, Any, Tuple

class ReviewAnalyzer:
    def __init__(self):
        # Download necessary NLTK data
        try:
            nltk.data.find('vader_lexicon')
        except LookupError:
            nltk.download('vader_lexicon')
        
        try:
            nltk.data.find('punkt')
        except LookupError:
            nltk.download('punkt')
        
        try:
            nltk.data.find('stopwords')
        except LookupError:
            nltk.download('stopwords')
        
        self.sia = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words('english'))
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
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
    
    def _extract_amazon_reviews(self, product_url: str, num_reviews: int = 10) -> List[Dict]:
        """Extract reviews from Amazon product page"""
        reviews = []
        
        try:
            # Check if the URL is a product page
            if '/dp/' not in product_url:
                return reviews
            
            # Convert to review page URL
            product_id = re.search(r'/dp/([^/]+)', product_url).group(1)
            reviews_url = f"https://www.amazon.in/product-reviews/{product_id}"
            
            headers = self._get_random_headers()
            response = requests.get(reviews_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find review cards
                review_elements = soup.select("div.review")
                
                for element in review_elements[:num_reviews]:
                    try:
                        # Extract review rating
                        rating_element = element.select_one("i.review-rating")
                        rating = 0
                        if rating_element:
                            rating_text = rating_element.text.strip()
                            rating_match = re.search(r'(\d+\.\d+|\d+)', rating_text)
                            if rating_match:
                                rating = float(rating_match.group(1))
                        
                        # Extract review title
                        title_element = element.select_one("a.review-title, span.review-title")
                        title = title_element.text.strip() if title_element else ""
                        
                        # Extract review content
                        content_element = element.select_one("span.review-text")
                        content = content_element.text.strip() if content_element else ""
                        
                        # Extract reviewer name
                        name_element = element.select_one("span.a-profile-name")
                        reviewer = name_element.text.strip() if name_element else "Anonymous"
                        
                        # Extract review date
                        date_element = element.select_one("span.review-date")
                        date = date_element.text.strip() if date_element else ""
                        
                        reviews.append({
                            'rating': rating,
                            'title': title,
                            'content': content,
                            'reviewer': reviewer,
                            'date': date,
                            'source': 'Amazon'
                        })
                    except Exception as e:
                        print(f"Error extracting review: {e}")
                        continue
        except Exception as e:
            print(f"Error fetching Amazon reviews: {e}")
        
        return reviews
    
    def _extract_snapdeal_reviews(self, product_url: str, num_reviews: int = 10) -> List[Dict]:
        """Extract reviews from Snapdeal product page"""
        reviews = []
        
        try:
            headers = self._get_random_headers()
            response = requests.get(product_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find review section
                review_elements = soup.select("div.user-review")
                
                for element in review_elements[:num_reviews]:
                    try:
                        # Extract review rating
                        rating_element = element.select_one("div.rating")
                        rating = 0
                        if rating_element:
                            rating_text = rating_element.get('style', '')
                            rating_match = re.search(r'width:\s*(\d+)%', rating_text)
                            if rating_match:
                                rating = float(rating_match.group(1)) / 20  # Convert percentage to 5-star scale
                        
                        # Extract review title
                        title_element = element.select_one("div.user-review-title")
                        title = title_element.text.strip() if title_element else ""
                        
                        # Extract review content
                        content_element = element.select_one("div.user-review-text")
                        content = content_element.text.strip() if content_element else ""
                        
                        # Extract reviewer name
                        name_element = element.select_one("div.user-review-userInfo")
                        reviewer = name_element.text.strip() if name_element else "Anonymous"
                        
                        # Extract review date
                        date_element = element.select_one("div.user-review-date")
                        date = date_element.text.strip() if date_element else ""
                        
                        reviews.append({
                            'rating': rating,
                            'title': title,
                            'content': content,
                            'reviewer': reviewer,
                            'date': date,
                            'source': 'Snapdeal'
                        })
                    except Exception as e:
                        print(f"Error extracting review: {e}")
                        continue
        except Exception as e:
            print(f"Error fetching Snapdeal reviews: {e}")
        
        return reviews
    
    def _extract_flipkart_reviews(self, product_url: str, num_reviews: int = 10) -> List[Dict]:
        """Extract reviews from Flipkart product page"""
        reviews = []
        
        try:
            # Check if the URL is a product page
            if '/p/' not in product_url:
                return reviews
            
            headers = self._get_random_headers()
            response = requests.get(product_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find review section
                review_elements = soup.select("div._1AtVbE")
                
                for element in review_elements[:num_reviews]:
                    try:
                        # Extract review rating
                        rating_element = element.select_one("div._3LWZlK")
                        rating = 0
                        if rating_element:
                            rating_text = rating_element.text.strip()
                            rating_match = re.search(r'(\d+\.\d+|\d+)', rating_text)
                            if rating_match:
                                rating = float(rating_match.group(1))
                        
                        # Extract review title
                        title_element = element.select_one("p._2-N8zT")
                        title = title_element.text.strip() if title_element else ""
                        
                        # Extract review content
                        content_element = element.select_one("div.t-ZTKy")
                        content = content_element.text.strip() if content_element else ""
                        
                        # Extract reviewer name
                        name_element = element.select_one("p._2sc7ZR")
                        reviewer = name_element.text.strip() if name_element else "Anonymous"
                        
                        # Extract review date
                        date_element = element.select_one("p._2sc7ZR")
                        date = date_element.text.strip() if date_element else ""
                        
                        reviews.append({
                            'rating': rating,
                            'title': title,
                            'content': content,
                            'reviewer': reviewer,
                            'date': date,
                            'source': 'Flipkart'
                        })
                    except Exception as e:
                        print(f"Error extracting review: {e}")
                        continue
        except Exception as e:
            print(f"Error fetching Flipkart reviews: {e}")
        
        return reviews
    
    def fetch_reviews(self, product_url: str, source: str = None, num_reviews: int = 10) -> List[Dict]:
        """Fetch reviews from a product page"""
        reviews = []
        
        # Add a small delay to avoid being blocked
        time.sleep(1)
        
        if source is None:
            # Determine source from URL
            if 'amazon' in product_url:
                source = 'amazon'
            elif 'snapdeal' in product_url:
                source = 'snapdeal'
            elif 'flipkart' in product_url:
                source = 'flipkart'
            else:
                return reviews
        
        # Extract reviews based on the source
        if source.lower() == 'amazon':
            reviews = self._extract_amazon_reviews(product_url, num_reviews)
        elif source.lower() == 'snapdeal':
            reviews = self._extract_snapdeal_reviews(product_url, num_reviews)
        elif source.lower() == 'flipkart':
            reviews = self._extract_flipkart_reviews(product_url, num_reviews)
        
        return reviews
    
    def analyze_reviews(self, reviews: List[Dict]) -> Dict:
        """Analyze a list of reviews and return insights"""
        if not reviews:
            return {
                'average_rating': 0,
                'sentiment_scores': {},
                'sentiment_distribution': {},
                'common_words': [],
                'pros_cons': {
                    'pros': [],
                    'cons': []
                },
                'review_count': 0
            }
        
        # Calculate average rating
        ratings = [review['rating'] for review in reviews if 'rating' in review and review['rating']]
        average_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Perform sentiment analysis
        sentiment_scores = {}
        sentiment_distribution = {'positive': 0, 'neutral': 0, 'negative': 0}
        
        for review in reviews:
            if 'content' in review and review['content']:
                score = self.sia.polarity_scores(review['content'])
                sentiment_scores[review.get('reviewer', 'Anonymous')] = score
                
                # Classify sentiment
                compound = score['compound']
                if compound >= 0.05:
                    sentiment_distribution['positive'] += 1
                elif compound <= -0.05:
                    sentiment_distribution['negative'] += 1
                else:
                    sentiment_distribution['neutral'] += 1
        
        # Calculate sentiment distribution percentages
        total_reviews = len(reviews)
        for key in sentiment_distribution:
            sentiment_distribution[key] = (sentiment_distribution[key] / total_reviews) * 100 if total_reviews else 0
        
        # Extract common words
        all_words = []
        for review in reviews:
            if 'content' in review and review['content']:
                words = word_tokenize(review['content'].lower())
                # Filter out stop words and punctuation
                filtered_words = [word for word in words if word.isalpha() and word not in self.stop_words and len(word) > 2]
                all_words.extend(filtered_words)
        
        # Get most common words
        word_counts = Counter(all_words)
        common_words = word_counts.most_common(20)
        
        # Extract pros and cons
        pros = []
        cons = []
        
        for review in reviews:
            if 'content' in review and review['content']:
                score = self.sia.polarity_scores(review['content'])
                
                # Extract key phrases
                sentences = review['content'].split('.')
                for sentence in sentences:
                    if len(sentence.strip()) < 5:  # Skip very short sentences
                        continue
                    
                    sentence_score = self.sia.polarity_scores(sentence)
                    
                    # Clean and prepare the sentence
                    clean_sentence = re.sub(r'[^\w\s]', '', sentence).strip()
                    if len(clean_sentence) < 5:  # Skip very short sentences
                        continue
                    
                    # Add to pros or cons based on sentiment
                    if sentence_score['compound'] >= 0.4 and clean_sentence not in pros:
                        pros.append(clean_sentence)
                    elif sentence_score['compound'] <= -0.4 and clean_sentence not in cons:
                        cons.append(clean_sentence)
        
        # Limit pros and cons to top 5 each
        pros = pros[:5]
        cons = cons[:5]
        
        return {
            'average_rating': average_rating,
            'sentiment_scores': sentiment_scores,
            'sentiment_distribution': sentiment_distribution,
            'common_words': common_words,
            'pros_cons': {
                'pros': pros,
                'cons': cons
            },
            'review_count': total_reviews
        }
    
    def plot_sentiment_distribution(self, sentiment_distribution: Dict) -> plt.Figure:
        """Plot sentiment distribution as a pie chart"""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        labels = []
        sizes = []
        colors = ['#4CAF50', '#FFC107', '#F44336']  # Green, Yellow, Red
        
        for label, percentage in sentiment_distribution.items():
            labels.append(f"{label.capitalize()} ({percentage:.1f}%)")
            sizes.append(percentage)
        
        ax.pie