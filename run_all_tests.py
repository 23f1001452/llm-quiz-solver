#!/usr/bin/env python3
"""
run_all_tests.py - Automated comprehensive testing
Run this before deployment to verify all requirements
"""

import asyncio
import httpx
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Configuration
LOCAL_URL = "http://localhost:8000"
PRODUCTION_URL = os.getenv("PRODUCTION_URL", "")  # Set this after deployment
EMAIL = os.getenv("STUDENT_EMAIL")
SECRET = os.getenv("SECRET_KEY")

# Test results
results = {
    "critical": {},
    "important": {},
    "optional": {}
}

# Colors
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_test(name):
    print(f"{Colors.YELLOW}Testing: {name}{Colors.RESET}")

def print_pass(message):
    print(f"{Colors.GREEN}✅ PASS: {message}{Colors.RESET}")

def print_fail(message):
    print(f"{Colors.RED}❌ FAIL: {message}{Colors.RESET}")

def print_skip(message):
    print(f"{Colors.YELLOW}⏭️  SKIP: {message}{Colors.RESET}")


async def test_health_check(base_url, test_type):
    """Test health check endpoint"""
    print_test("Health Check")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "running":
                    print_pass(f"Health check works: {data}")
                    return True
            print_fail(f"Unexpected response: {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Connection failed: {str(e)}")
        return False


async def test_invalid_json(base_url, test_type):
    """Test invalid JSON returns 400"""
    print_test("Invalid JSON (should return 400)")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/quiz",
                headers={"Content-Type": "application/json"},
                content="this is not json"
            )
            if response.status_code == 400:
                print_pass("Correctly returned 400 for invalid JSON")
                return True
            print_fail(f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Test failed: {str(e)}")
        return False


async def test_invalid_credentials(base_url, test_type):
    """Test invalid credentials return 403"""
    print_test("Invalid Credentials (should return 403)")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/quiz",
                json={
                    "email": "wrong@example.com",
                    "secret": "wrong-secret",
                    "url": "https://example.com/quiz"
                }
            )
            if response.status_code == 403:
                print_pass("Correctly returned 403 for invalid credentials")
                return True
            print_fail(f"Expected 403, got {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Test failed: {str(e)}")
        return False


async def test_demo_quiz(base_url, test_type):
    """Test with official demo quiz"""
    print_test("Official Demo Quiz")
    
    if not EMAIL or not SECRET:
        print_skip("EMAIL or SECRET not configured")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{base_url}/quiz",
                json={
                    "email": EMAIL,
                    "secret": SECRET,
                    "url": "https://tds-llm-analysis.s-anand.net/demo"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    print_pass(f"Demo quiz completed: {data.get('message')}")
                    return True
                else:
                    print_fail(f"Quiz failed: {data}")
                    return False
            else:
                print_fail(f"HTTP {response.status_code}: {response.text[:200]}")
                return False
                
    except httpx.TimeoutException:
        print_fail("Request timed out (>180s)")
        return False
    except Exception as e:
        print_fail(f"Test failed: {str(e)}")
        return False


def test_prompt_lengths():
    """Test prompt lengths"""
    print_test("Prompt Length Requirements")
    
    system_prompt = input("Enter your system prompt: ").strip()
    user_prompt = input("Enter your user prompt: ").strip()
    
    system_len = len(system_prompt)
    user_len = len(user_prompt)
    
    system_ok = system_len <= 100
    user_ok = user_len <= 100
    
    if system_ok:
        print_pass(f"System prompt: {system_len} chars ≤ 100")
    else:
        print_fail(f"System prompt: {system_len} chars > 100 (TOO LONG!)")
    
    if user_ok:
        print_pass(f"User prompt: {user_len} chars ≤ 100")
    else:
        print_fail(f"User prompt: {user_len} chars > 100 (TOO LONG!)")
    
    return system_ok and user_ok


def test_repository_files():
    """Test repository files exist"""
    print_test("Repository Files")
    
    required_files = {
        "LICENSE": "MIT License file",
        "README.md": "Documentation",
        "requirements.txt": "Dependencies",
        "main.py": "Main application",
        ".gitignore": "Git ignore rules"
    }
    
    all_exist = True
    for file, desc in required_files.items():
        if os.path.exists(file):
            print_pass(f"{file} exists ({desc})")
        else:
            print_fail(f"{file} missing! ({desc})")
            all_exist = False
    
    # Check .env is NOT tracked
    import subprocess
    try:
        result = subprocess.run(
            ["git", "ls-files", ".env"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            print_fail(".env is tracked by git! (SECURITY ISSUE)")
            all_exist = False
        else:
            print_pass(".env is not tracked (good!)")
    except:
        print_skip("Could not check git tracking")
    
    return all_exist


async def run_local_tests():
    """Run tests against local server"""
    print_header("LOCAL TESTS (http://localhost:8000)")
    
    print("⚠️  Make sure local server is running: uvicorn main:app --reload\n")
    input("Press Enter when ready...")
    
    results["critical"]["local_health"] = await test_health_check(LOCAL_URL, "local")
    results["critical"]["local_invalid_json"] = await test_invalid_json(LOCAL_URL, "local")
    results["critical"]["local_invalid_creds"] = await test_invalid_credentials(LOCAL_URL, "local")
    
    # Optional: demo quiz on local (skip if not set up)
    print("\n")
    test_demo = input("Test with demo quiz locally? (y/n): ").lower() == 'y'
    if test_demo:
        results["optional"]["local_demo"] = await test_demo_quiz(LOCAL_URL, "local")


async def run_production_tests():
    """Run tests against production server"""
    
    if not PRODUCTION_URL:
        prod_url = input("\nEnter your production URL (e.g., https://your-app.onrender.com): ").strip()
        if not prod_url:
            print_skip("No production URL provided, skipping production tests")
            return
    else:
        prod_url = PRODUCTION_URL
    
    print_header(f"PRODUCTION TESTS ({prod_url})")
    
    results["critical"]["prod_health"] = await test_health_check(prod_url, "production")
    results["important"]["prod_invalid_json"] = await test_invalid_json(prod_url, "production")
    results["important"]["prod_invalid_creds"] = await test_invalid_credentials(prod_url, "production")
    
    print("\n")
    test_demo = input("Test with official demo quiz? (y/n): ").lower() == 'y'
    if test_demo:
        results["critical"]["prod_demo"] = await test_demo_quiz(prod_url, "production")


def run_manual_tests():
    """Run tests that require manual input"""
    print_header("MANUAL TESTS")
    
    # Prompt lengths
    results["critical"]["prompt_lengths"] = test_prompt_lengths()
    
    print("\n")
    
    # Repository files
    results["important"]["repo_files"] = test_repository_files()


def print_summary():
    """Print test results summary"""
    print_header("TEST RESULTS SUMMARY")
    
    def count_results(category):
        passed = sum(1 for v in results[category].values() if v is True)
        failed = sum(1 for v in results[category].values() if v is False)
        skipped = sum(1 for v in results[category].values() if v is None)
        total = len(results[category])
        return passed, failed, skipped, total
    
    # Critical tests
    print(f"\n{Colors.RED}CRITICAL TESTS (Must Pass){Colors.RESET}")
    passed, failed, skipped, total = count_results("critical")
    for name, result in results["critical"].items():
        status = "✅" if result else ("⏭️ " if result is None else "❌")
        print(f"  {status} {name}")
    print(f"  Result: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    
    # Important tests
    print(f"\n{Colors.YELLOW}IMPORTANT TESTS (Should Pass){Colors.RESET}")
    passed, failed, skipped, total = count_results("important")
    for name, result in results["important"].items():
        status = "✅" if result else ("⏭️ " if result is None else "❌")
        print(f"  {status} {name}")
    print(f"  Result: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    
    # Optional tests
    if results["optional"]:
        print(f"\n{Colors.BLUE}OPTIONAL TESTS (Nice to Have){Colors.RESET}")
        passed, failed, skipped, total = count_results("optional")
        for name, result in results["optional"].items():
            status = "✅" if result else ("⏭️ " if result is None else "❌")
            print(f"  {status} {name}")
        print(f"  Result: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    
    # Overall assessment
    critical_passed, critical_failed, _, critical_total = count_results("critical")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    if critical_passed == critical_total:
        print(f"{Colors.GREEN}🎉 ALL CRITICAL TESTS PASSED! You're ready for deployment.{Colors.RESET}")
    elif critical_passed >= critical_total * 0.8:
        print(f"{Colors.YELLOW}⚠️  Most critical tests passed. Fix failures before submitting.{Colors.RESET}")
    else:
        print(f"{Colors.RED}❌ Multiple critical tests failed. Review and fix before deployment.{Colors.RESET}")
    
    print(f"\n{Colors.BLUE}Next Steps:{Colors.RESET}")
    if critical_failed > 0:
        print(f"  1. Fix all failing critical tests")
        print(f"  2. Re-run this script")
    else:
        print(f"  1. Deploy to Render")
        print(f"  2. Run production tests")
        print(f"  3. Submit Google Form")
    print()


async def main():
    """Main test runner"""
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}  LLM Quiz Solver - Comprehensive Test Suite{Colors.RESET}")
    print(f"{Colors.BLUE}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    # Run test phases
    await run_local_tests()
    
    print("\n")
    test_production = input("Run production tests? (y/n): ").lower() == 'y'
    if test_production:
        await run_production_tests()
    
    print("\n")
    run_manual_tests()
    
    # Print summary
    print_summary()
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(f"test_results_{timestamp}.txt", "w") as f:
        f.write("LLM Quiz Solver Test Results\n")
        f.write(f"Date: {datetime.now()}\n\n")
        f.write(f"Critical Tests: {results['critical']}\n")
        f.write(f"Important Tests: {results['important']}\n")
        f.write(f"Optional Tests: {results['optional']}\n")
    
    print(f"\nResults saved to: test_results_{timestamp}.txt")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Testing interrupted by user{Colors.RESET}")
        sys.exit(1)