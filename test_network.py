"""
Network connectivity diagnostic script
Test if the container can reach OpenAI API
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_basic_connectivity():
    """Test basic internet connectivity"""
    print("=" * 60)
    print("NETWORK CONNECTIVITY DIAGNOSTICS")
    print("=" * 60)
    
    # Test 1: DNS Resolution
    print("\n1. Testing DNS resolution...")
    try:
        import socket
        ip = socket.gethostbyname("api.openai.com")
        print(f"   ✓ DNS works: api.openai.com -> {ip}")
    except Exception as e:
        print(f"   ✗ DNS failed: {e}")
        return False
    
    # Test 2: HTTPS Connection
    print("\n2. Testing HTTPS connection...")
    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            response = client.get("https://api.openai.com/v1/models")
            print(f"   ✓ HTTPS connection works: Status {response.status_code}")
    except Exception as e:
        print(f"   ✗ HTTPS connection failed: {type(e).__name__} - {e}")
        return False
    
    # Test 3: OpenAI API Authentication
    print("\n3. Testing OpenAI API authentication...")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("   ✗ OPENAI_API_KEY not found in environment")
        return False
    
    print(f"   API Key found: {api_key[:20]}...")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=30.0, max_retries=2)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        print(f"   ✓ OpenAI API works: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"   ✗ OpenAI API failed: {type(e).__name__}")
        print(f"   Error details: {e}")
        return False

def test_proxy_settings():
    """Check if proxy settings are interfering"""
    print("\n4. Checking proxy settings...")
    
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    
    if http_proxy or https_proxy:
        print(f"   ! HTTP_PROXY: {http_proxy}")
        print(f"   ! HTTPS_PROXY: {https_proxy}")
        print("   These proxy settings might be blocking OpenAI API")
    else:
        print("   ✓ No proxy settings detected")

def suggest_solutions():
    """Suggest solutions based on diagnostics"""
    print("\n" + "=" * 60)
    print("SUGGESTED SOLUTIONS")
    print("=" * 60)
    print("""
1. **Container Network Issue**: If running in Docker/container:
   - Ensure container has internet access
   - Check firewall rules
   - Try: docker run --network host

2. **Corporate Firewall**: If behind corporate firewall:
   - OpenAI API (api.openai.com) might be blocked
   - Contact IT to whitelist api.openai.com
   - Consider using a proxy with authentication

3. **API Key Issue**: 
   - Verify API key is valid at https://platform.openai.com/api-keys
   - Check if API key has usage limits or is expired

4. **Temporary Workaround**:
   - Use a different AI provider (Azure OpenAI, Anthropic, etc.)
   - Run the application outside the container
   - Use a VPN if available
""")

if __name__ == "__main__":
    success = test_basic_connectivity()
    test_proxy_settings()
    
    if not success:
        suggest_solutions()
        sys.exit(1)
    else:
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED - Network connectivity is working!")
        print("=" * 60)
        sys.exit(0)
