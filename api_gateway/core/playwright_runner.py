import asyncio
import base64
import time
from playwright.async_api import async_playwright

async def execute_test(test_json: dict, target_url: str) -> dict:
    """
    Executes a test suite JSON against a target URL using Playwright.
    Returns a dictionary with status, execution time, and a base64 screenshot.
    """
    start_time = time.time()
    screenshot_b64 = None
    error_msg = None
    status = "PASS"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 1280, 'height': 720})
            page = await context.new_page()
            
            # Navigate to the target
            await page.goto(target_url, wait_until="networkidle")
            
            # Execute steps
            steps = test_json.get("test_cases", [{}])[0].get("steps", [])
            if not steps:
                # Fallback to general steps if nested structure differs
                steps = test_json.get("steps", [])

            for step in steps:
                action = step.get("action", "").lower()
                target = step.get("target", "")
                value = step.get("value", "")
                
                try:
                    if action == "input" or action == "type":
                        await page.fill(target, value)
                    elif action == "click":
                        await page.click(target)
                    elif action == "verify" or action == "assert":
                        # Check if element is visible
                        is_visible = await page.is_visible(target, timeout=5000)
                        if not is_visible:
                            raise Exception(f"Element {target} not found for verification")
                    
                    # Small wait for stability
                    await asyncio.sleep(0.5)
                except Exception as e:
                    status = "FAIL"
                    error_msg = f"Step failed: {action} on {target}. Error: {str(e)}"
                    break
            
            # Capture evidence
            screenshot_bytes = await page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            await browser.close()
            
    except Exception as e:
        status = "FAIL"
        error_msg = f"Browser execution failed: {str(e)}"
    
    end_time = time.time()
    execution_time_ms = int((end_time - start_time) * 1000)
    
    return {
        "status": status,
        "execution_time_ms": execution_time_ms,
        "error_message": error_msg,
        "screenshot_base64": screenshot_b64
    }
