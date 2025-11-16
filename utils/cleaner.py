import re
from selenium.webdriver.common.by import By

def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # Remove special characters except basic punctuation
    text = re.sub(r'[^\w\s,.!?\'"-]', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def clean_post_data(post: dict) -> dict:
    """Clean all text fields in a post dictionary"""
    cleaned = post.copy()
    
    if "content" in cleaned:
        cleaned["content"] = clean_text(cleaned["content"])
    
    if "username" in cleaned:
        cleaned["username"] = clean_text(cleaned["username"])
    
    return cleaned