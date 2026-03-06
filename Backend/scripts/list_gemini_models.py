"""
List Available Gemini Models
This will show which models your API key can access
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import google.generativeai as genai
    from app.core.config import settings
    
    print("\n" + "="*60)
    print("📋 CHECKING AVAILABLE GEMINI MODELS")
    print("="*60)
    
    # Configure API
    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    print("\nAvailable models:")
    print("-" * 60)
    
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"✅ {model.name}")
            print(f"   Display name: {model.display_name}")
            print(f"   Description: {model.description[:80]}...")
            print()
    
    print("="*60)
    print("\nℹ️  Use one of these model names in your .env file")
    print("   Example: GEMINI_MODEL_ID=models/gemini-pro")
    print("="*60)
    
except ImportError:
    print("❌ google-generativeai not installed")
    print("   Run: pip install google-generativeai")
except Exception as e:
    print(f"❌ Error: {e}")
