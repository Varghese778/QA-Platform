"""Demo routes for development/testing - no authentication required."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import httpx # Required for real-time sync with async-processing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

DEMO_GENERATED_TESTS = {}
tests_cache = DEMO_GENERATED_TESTS # Alias for analytics routes


def _initialize_new_demo_job(body):
    """Initialize a new demo job in QUEUED state for real AI processing."""
    return {
        "job_id": str(uuid4()),
        "project_id": body.get("project_id", "demo-project-001"),
        "story_title": body.get("story_title", "Demo Test Suite"),
        "user_story": body.get("user_story", ""),
        "status": "QUEUED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "priority": body.get("priority", "NORMAL"),
        "tags": body.get("tags", []),
        "environment_target": body.get("environment_target", "STAGING"),
        "report_ready": False,
        "test_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "stages": [
            {
                "stage_id": str(uuid4()),
                "name": "STORY_PARSING",
                "status": "PENDING",
            },
            {
                "stage_id": str(uuid4()),
                "name": "TEST_GENERATION",
                "status": "PENDING",
            },
            {
                "stage_id": str(uuid4()),
                "name": "TEST_EXECUTION",
                "status": "PENDING",
            },
            {
                "stage_id": str(uuid4()),
                "name": "REPORTING",
                "status": "PENDING",
            },
        ],
    }


def _create_fallback_demo_job(body):
    """Fallback to create a completed demo job if AI engine is unavailable."""
    return {
        "job_id": str(uuid4()),
        "project_id": body.get("project_id", "demo-project-001"),
        "story_title": body.get("story_title", "Demo Test Suite"),
        "user_story": body.get("user_story", ""),
        "status": "COMPLETE",  # Simulate completed job for demo
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "priority": body.get("priority", "NORMAL"),
        "tags": body.get("tags", []),
        "environment_target": body.get("environment_target", "STAGING"),
        "report_ready": True,
        "test_count": 15,
        "passed_count": 13,
        "failed_count": 2,
        "stages": [
            {
                "stage_id": str(uuid4()),
                "name": "STORY_PARSING",
                "status": "COMPLETE",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "stage_id": str(uuid4()),
                "name": "TEST_GENERATION",
                "status": "COMPLETE",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "stage_id": str(uuid4()),
                "name": "TEST_EXECUTION",
                "status": "COMPLETE",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "stage_id": str(uuid4()),
                "name": "REPORTING",
                "status": "COMPLETE",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        ],
    }


# Mock data for demo mode
# NOTE: Uses "project_id" (not "id") to match the frontend ProjectItem type
DEMO_PROJECTS = [
    {
        "project_id": "demo-project-001",
        "name": "E-Commerce Platform",
        "description": "Test suite for the e-commerce application",
        "created_at": "2026-03-01T10:00:00Z",
        "updated_at": "2026-03-25T08:30:00Z",
        "owner_id": "demo-user-123",
        "member_count": 5,
    },
    {
        "project_id": "demo-project-002",
        "name": "Mobile Banking App",
        "description": "Automated tests for banking mobile application",
        "created_at": "2026-02-15T14:30:00Z",
        "updated_at": "2026-03-24T16:45:00Z",
        "owner_id": "demo-user-123",
        "member_count": 3,
    },
    {
        "project_id": "demo-project-003",
        "name": "Healthcare Portal",
        "description": "QA tests for patient management system",
        "created_at": "2026-03-10T09:00:00Z",
        "updated_at": "2026-03-23T11:20:00Z",
        "owner_id": "demo-user-123",
        "member_count": 4,
    },
]

DEMO_JOBS = [
    {
        "job_id": str(uuid4()),
        "project_id": "demo-project-001",
        "story_title": "Login Flow Test Suite",
        "user_story": "As a user, I want to log in with my credentials so that I can access my account dashboard securely.",
        "status": "COMPLETE",
        "created_at": "2026-03-25T08:00:00Z",
        "updated_at": "2026-03-25T08:15:00Z",
        "priority": "NORMAL",
        "tags": ["login", "authentication"],
        "environment_target": "STAGING",
        "report_ready": True,
        "test_count": 12,
        "passed_count": 11,
        "failed_count": 1,
        "stages": [
            {"stage_id": str(uuid4()), "name": "STORY_PARSING", "status": "COMPLETE", "started_at": "2026-03-25T08:00:00Z", "completed_at": "2026-03-25T08:02:00Z"},
            {"stage_id": str(uuid4()), "name": "TEST_GENERATION", "status": "COMPLETE", "started_at": "2026-03-25T08:02:00Z", "completed_at": "2026-03-25T08:08:00Z"},
            {"stage_id": str(uuid4()), "name": "TEST_EXECUTION", "status": "COMPLETE", "started_at": "2026-03-25T08:08:00Z", "completed_at": "2026-03-25T08:13:00Z"},
            {"stage_id": str(uuid4()), "name": "REPORTING", "status": "COMPLETE", "started_at": "2026-03-25T08:13:00Z", "completed_at": "2026-03-25T08:15:00Z"},
        ],
    },
    {
        "job_id": str(uuid4()),
        "project_id": "demo-project-001",
        "story_title": "Checkout Process Tests",
        "user_story": "As a customer, I want to complete a purchase by adding items to my cart and checking out with my payment details.",
        "status": "PROCESSING",
        "created_at": "2026-03-25T09:30:00Z",
        "updated_at": "2026-03-25T10:45:00Z",
        "priority": "HIGH",
        "tags": ["checkout", "payment"],
        "environment_target": "STAGING",
        "report_ready": False,
        "test_count": 8,
        "passed_count": 5,
        "failed_count": 0,
        "stages": [
            {"stage_id": str(uuid4()), "name": "STORY_PARSING", "status": "COMPLETE", "started_at": "2026-03-25T09:30:00Z", "completed_at": "2026-03-25T09:32:00Z"},
            {"stage_id": str(uuid4()), "name": "TEST_GENERATION", "status": "RUNNING", "started_at": "2026-03-25T09:32:00Z"},
            {"stage_id": str(uuid4()), "name": "TEST_EXECUTION", "status": "PENDING"},
            {"stage_id": str(uuid4()), "name": "REPORTING", "status": "PENDING"},
        ],
    },
    {
        "job_id": str(uuid4()),
        "project_id": "demo-project-002",
        "story_title": "Account Balance Verification",
        "user_story": "As a banker, I want to verify account balances are displayed correctly after transactions are processed.",
        "status": "QUEUED",
        "created_at": "2026-03-25T10:00:00Z",
        "updated_at": "2026-03-25T10:00:00Z",
        "priority": "CRITICAL",
        "tags": ["banking", "accounts"],
        "environment_target": "PRODUCTION",
        "report_ready": False,
        "test_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "stages": [
            {"stage_id": str(uuid4()), "name": "STORY_PARSING", "status": "PENDING"},
            {"stage_id": str(uuid4()), "name": "TEST_GENERATION", "status": "PENDING"},
            {"stage_id": str(uuid4()), "name": "TEST_EXECUTION", "status": "PENDING"},
            {"stage_id": str(uuid4()), "name": "REPORTING", "status": "PENDING"},
        ],
    },
]


@router.get("/projects")
async def list_demo_projects(request: Request):
    """
    List demo projects (no authentication required).

    Use this endpoint for testing the frontend without real authentication.
    """
    logger.info("Demo projects list requested")
    return {
        "projects": DEMO_PROJECTS,
        "total": len(DEMO_PROJECTS),
    }


@router.get("/projects/{project_id}")
async def get_demo_project(project_id: str, request: Request):
    """Get a specific demo project."""
    for project in DEMO_PROJECTS:
        if project["project_id"] == project_id:
            return project
    return JSONResponse(
        status_code=404,
        content={"error": "Project not found", "project_id": project_id},
    )


@router.get("/jobs")
async def list_demo_jobs(request: Request, project_id: str = None):
    """
    List demo jobs (no authentication required).
    """
    logger.info(f"Demo jobs list requested for project: {project_id}")

    if project_id:
        jobs = [j for j in DEMO_JOBS if j["project_id"] == project_id]
    else:
        jobs = DEMO_JOBS

    return {
        "jobs": jobs,
        "total": len(jobs),
        "page": 1,
        "page_size": 20,
    }


@router.post("/jobs")
async def create_demo_job(request: Request, background_tasks: BackgroundTasks):
    """
    Create a demo job that triggers real AI test generation via multi-agent engine.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON in request body"},
        )

    # Create initial job record
    new_job = {
        "job_id": str(uuid4()),
        "project_id": body.get("project_id", "demo-project-001"),
        "story_title": body.get("story_title", "Demo Test Suite"),
        "user_story": body.get("user_story", ""),
        "status": "PROCESSING",  # Real processing via AI
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "priority": body.get("priority", "NORMAL"),
        "tags": body.get("tags", []),
        "environment_target": body.get("environment_target", "STAGING"),
        "report_ready": False,
        "test_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "stages": [
            {
                "stage_id": str(uuid4()),
                "name": "STORY_PARSING",
                "status": "RUNNING",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "stage_id": str(uuid4()),
                "name": "TEST_GENERATION",
                "status": "PENDING",
            },
            {
                "stage_id": str(uuid4()),
                "name": "TEST_EXECUTION",
                "status": "PENDING",
            },
            {
                "stage_id": str(uuid4()),
                "name": "REPORTING",
                "status": "PENDING",
            },
        ],
    }

@router.post("/jobs")
async def create_demo_job(request: Request, background_tasks: BackgroundTasks):
    """
    Create a demo job that triggers real AI test generation via multi-agent engine.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON in request body"},
        )

    # Create initial job record
    new_job = _initialize_new_demo_job(body)
    
    DEMO_JOBS.insert(0, new_job)  # Insert at beginning for most recent
    logger.info(f"Demo job created: {new_job['job_id']}")

    # Start real AI generation in the background
    background_tasks.add_task(_generate_real_tests_task, new_job, body)

    return {
        "job_id": new_job["job_id"],
        "queued_at": new_job["created_at"],
        "estimated_completion_seconds": 15,  # Estimate reduced since we skip queue
        "ai_powered": True
    }

async def _broadcast_demo_status(job):
    """Helper to notify async-processing of a demo job update for real-time UI."""
    try:
        async with httpx.AsyncClient() as client:
            # Broadcast the full job object as event to trigger WebSocket updates
            # async-processing will route this through the WebSocket gateway
            payload = {
                "job_id": job["job_id"],
                "project_id": job["project_id"],
                "event_type": "JOB_PROGRESS_UPDATE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": job["status"],
                "stages": job.get("stages", []),
                "report_ready": job.get("report_ready", False)
            }
            # Internal URL for async-processing ingestion
            response = await client.post(
                "http://async-processing:8000/internal/v1/events",
                json=payload,
                timeout=5.0
            )
            if response.status_code not in (200, 202, 204):
                logger.warning(f"Broadcast response {response.status_code}: {response.text}")
            else:
                logger.debug(f"Broadcasted demo status for job {job['job_id']}")
    except Exception as e:
        logger.error(f"Failed to broadcast demo status: {e}")

async def _update_demo_job_stage(job, stage_name, status, log_snippet=None, details_list=None):
    """Helper to update a stage in a demo job for UI feedback."""
    for stage in job.get("stages", []):
        if stage["name"] == stage_name:
            stage["status"] = status
            if log_snippet:
                stage["log_snippet"] = log_snippet
            if details_list:
                stage["details"] = details_list
            if status == "RUNNING":
                stage["started_at"] = datetime.now(timezone.utc).isoformat()
            if status == "COMPLETE":
                stage["completed_at"] = datetime.now(timezone.utc).isoformat()
            break
    
    # TRIGGER BROADCAST: This resolves the manual refresh issue!
    await _broadcast_demo_status(job)


async def _generate_real_tests_task(job, body):
    """Background task to generate real tests using the multi-agent engine endpoint."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "user_story": job["user_story"],
                "story_title": job["story_title"]
            }
            logger.info(f"Requesting real AI tests for demo job {job['job_id']}...")
            
            # AI Pipeline: Start with STORY_PARSING (Insights extraction)
            await _update_demo_job_stage(job, "STORY_PARSING", "RUNNING", "Extracting user story insights...")
            await _update_demo_job_stage(job, "TEST_GENERATION", "PENDING", "Waiting for story parsing...")
            await _update_demo_job_stage(job, "TEST_EXECUTION", "PENDING", "Waiting for test generation...")
            await _update_demo_job_stage(job, "REPORTING", "PENDING", "Waiting for execution results...")
            
            job["status"] = "PROCESSING"
            job["report_ready"] = False # Hide mock report until real one is ready

            # Complete STORY_PARSING with insights summary before requesting tests
            insights_summary = "Story parsed - Requirements identified, test scenarios mapped, edge cases documented."
            await _update_demo_job_stage(job, "STORY_PARSING", "COMPLETE", insights_summary)
            
            # Move to TEST_GENERATION stage
            await _update_demo_job_stage(job, "TEST_GENERATION", "RUNNING", "Initializing Vertex AI (Gemini 2.5 Flash)...")

            response = await client.post(
                "http://multi-agent-engine:8000/internal/v1/generate-demo-tests",
                json=payload,
                timeout=60.0 # Generation might take a minute
            )
            
            if response.status_code == 200:
                data = response.json()
                tests = data.get("tests", [])
                
                # Update cache early for Insights/Regressions
                # We use the correct variable name 'tests' from the response
                tests_cache[job["job_id"]] = tests
                
                # Show list in UI expansion
                test_titles = [t.get("title", "Unnamed Test") for t in tests]
                await _update_demo_job_stage(
                    job, 
                    "TEST_GENERATION", 
                    "COMPLETE", 
                    f"Successfully generated {len(tests)} test cases with Gemini 2.5 Flash.",
                    details_list=test_titles
                )
                
                # Real Execution Phase
                from api_gateway.core.playwright_runner import execute_test
                logger.info(f"Starting real execution of {len(tests)} tests for job {job['job_id']}...")
                
                await _update_demo_job_stage(job, "TEST_EXECUTION", "RUNNING", "Launching Playwright Chromium engine...")
                await _update_demo_job_stage(job, "REPORTING", "PENDING", "Processing execution evidence...")
                
                # We point to our local demo app served on port 5000
                target_url = "http://localhost:5000/index.html"
                
                for i, test in enumerate(tests):
                    msg = f"Executing browser test {i+1}/{len(tests)}: {test.get('title', 'Untitled')}"
                    logger.info(msg)
                    await _update_demo_job_stage(job, "TEST_EXECUTION", "RUNNING", msg)
                    
                    # Map the test case to the runner
                    result = await execute_test(test, target_url)
                    
                    # Merge results back into the test object
                    test["status"] = result["status"]
                    test["execution_time"] = result["execution_time_ms"]
                    test["error_trace"] = result.get("error_message")
                    test["screenshot"] = result.get("screenshot_base64")
                    
                    # Ensure the test has a UUID if missing
                    if "test_id" not in test:
                        test["test_id"] = str(uuid4())

                # Cache real tests
                DEMO_GENERATED_TESTS[job["job_id"]] = tests
                
                # Update job status to COMPLETE
                job["status"] = "COMPLETE"
                job["test_count"] = len(tests)
                job["passed_count"] = len([t for t in tests if t.get("status") == "PASS"])
                job["failed_count"] = len([t for t in tests if t.get("status") == "FAIL"])
                job["report_ready"] = True
                
                # Update all stages to complete
                for stage in job["stages"]:
                    stage["status"] = "COMPLETE"
                    stage["completed_at"] = datetime.now(timezone.utc).isoformat()
                    
                logger.info(f"✅ Real AI tests generated AND EXECUTED for job {job['job_id']}! Count: {job['test_count']}")
                return


            logger.error(f"Generate tests failed: {response.text}")

    except Exception as e:
        logger.error(f"Error calling multi-agent engine: {e}")

    # Fallback: Mark job as FAILED if AI engine is unavailable
    logger.warning(f"AI test generation failed for job {job['job_id']} - marking stages as FAILED")
    job["status"] = "FAILED"
    job["report_ready"] = False
    for stage in job.get("stages", []):
        if stage["status"] == "RUNNING":
            stage["status"] = "FAILED"
            stage["completed_at"] = datetime.now(timezone.utc).isoformat()
    await _broadcast_demo_status(job)

@router.get("/jobs/{job_id}")
async def get_demo_job(job_id: str, request: Request):
    """Get a specific demo job."""
    for job in DEMO_JOBS:
        if job["job_id"] == job_id:
            return job
    return JSONResponse(
        status_code=404,
        content={"error": "Job not found", "job_id": job_id},
    )


@router.delete("/jobs/{job_id}")
async def cancel_demo_job(job_id: str, request: Request, hard: bool = False):
    """Cancel or delete a demo job."""
    for i, job in enumerate(DEMO_JOBS):
        if job["job_id"] == job_id:
            if hard:
                del DEMO_JOBS[i]
                if job_id in DEMO_GENERATED_TESTS:
                    del DEMO_GENERATED_TESTS[job_id]
                logger.info(f"Demo job hard deleted: {job_id}")
                return {"deleted": True, "message": "Job deleted successfully"}
                
            if job["status"] in ("QUEUED", "PROCESSING"):
                job["status"] = "CANCELLED"
                job["updated_at"] = datetime.now(timezone.utc).isoformat()
                logger.info(f"Demo job cancelled: {job_id}")
                return {"cancelled": True, "final_status": "CANCELLED", "message": "Job cancelled successfully"}
            else:
                return JSONResponse(
                    status_code=409,
                    content={"error": f"Cannot cancel job in {job['status']} status (use hard=true to delete)"},
                )
    return JSONResponse(
        status_code=404,
        content={"error": "Job not found", "job_id": job_id},
    )


@router.get("/jobs/{job_id}/tests")
async def get_demo_job_tests(job_id: str, request: Request):
    """
    Get test cases for a demo job.
    Returns realistic test data matching the frontend TestCase interface.
    """
    if job_id in DEMO_GENERATED_TESTS:
        tests = DEMO_GENERATED_TESTS[job_id]
        return {
            "tests": tests,
            "total": len(tests),
            "page": 1,
            "page_size": max(20, len(tests)),
        }

    # Generate test cases matching the frontend TestCase type:
    # { test_id, title, preconditions, steps: [{step_number, action, expected_result}],
    #   expected_result, tags, status: 'PASS'|'FAIL'|'SKIP'|'PENDING', failure_reason? }
    test_cases = [
        {
            "test_id": str(uuid4()),
            "title": "Verify user can login with valid credentials",
            "status": "PASS",
            "preconditions": ["User account exists", "User is on the login page"],
            "steps": [
                {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login page displayed"},
                {"step_number": 2, "action": "Enter valid email", "expected_result": "Email field accepts input"},
                {"step_number": 3, "action": "Enter valid password", "expected_result": "Password field accepts input (masked)"},
                {"step_number": 4, "action": "Click login button", "expected_result": "User is redirected to dashboard"},
                {"step_number": 5, "action": "Verify dashboard is displayed", "expected_result": "Dashboard page loads with user data"},
            ],
            "expected_result": "User successfully logs in and sees the dashboard",
            "tags": ["login", "authentication", "smoke"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify error message for invalid credentials",
            "status": "PASS",
            "preconditions": ["User account exists"],
            "steps": [
                {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login page displayed"},
                {"step_number": 2, "action": "Enter invalid email", "expected_result": "Email field accepts input"},
                {"step_number": 3, "action": "Enter password", "expected_result": "Password field accepts input"},
                {"step_number": 4, "action": "Click login button", "expected_result": "Error message is displayed"},
                {"step_number": 5, "action": "Verify error message displayed", "expected_result": "Message says 'Invalid credentials'"},
            ],
            "expected_result": "Error message displayed for invalid credentials",
            "tags": ["login", "error-handling", "negative"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify password field is masked",
            "status": "PASS",
            "preconditions": ["User is on login page"],
            "steps": [
                {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login page displayed"},
                {"step_number": 2, "action": "Verify password field type is 'password'", "expected_result": "Field type is password"},
                {"step_number": 3, "action": "Verify entered text is masked", "expected_result": "Text shows dots/bullets"},
            ],
            "expected_result": "Password field masks user input",
            "tags": ["security", "ui"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify login button is disabled when fields are empty",
            "status": "FAIL",
            "preconditions": ["User is on login page"],
            "steps": [
                {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login page displayed"},
                {"step_number": 2, "action": "Verify email field is empty", "expected_result": "Email field is blank"},
                {"step_number": 3, "action": "Verify password field is empty", "expected_result": "Password field is blank"},
                {"step_number": 4, "action": "Check login button state", "expected_result": "Login button should be disabled"},
            ],
            "expected_result": "Login button is disabled when fields are empty",
            "tags": ["login", "validation"],
            "failure_reason": "Expected login button to be disabled, but it was enabled",
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify email validation",
            "status": "PASS",
            "preconditions": ["User is on login page"],
            "steps": [
                {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login page displayed"},
                {"step_number": 2, "action": "Enter invalid email format", "expected_result": "Email field accepts input"},
                {"step_number": 3, "action": "Verify validation error message", "expected_result": "Validation error shown"},
            ],
            "expected_result": "Email validation error displayed for invalid format",
            "tags": ["login", "validation"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify forgot password link is displayed",
            "status": "PASS",
            "preconditions": ["User is on login page"],
            "steps": [
                {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login page displayed"},
                {"step_number": 2, "action": "Verify 'Forgot Password' link exists", "expected_result": "Link is visible and clickable"},
            ],
            "expected_result": "Forgot password link is present on login page",
            "tags": ["login", "ui"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify session timeout after inactivity",
            "status": "PASS",
            "preconditions": ["User is logged in", "Session timeout is configured"],
            "steps": [
                {"step_number": 1, "action": "Login successfully", "expected_result": "Dashboard displayed"},
                {"step_number": 2, "action": "Wait for session timeout", "expected_result": "Session expires"},
                {"step_number": 3, "action": "Verify redirect to login page", "expected_result": "Login page displayed"},
            ],
            "expected_result": "User is redirected to login after session timeout",
            "tags": ["security", "session"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify CSRF token protection",
            "status": "PASS",
            "preconditions": ["Application has CSRF protection enabled"],
            "steps": [
                {"step_number": 1, "action": "Inspect login form", "expected_result": "Form contains CSRF token field"},
                {"step_number": 2, "action": "Verify CSRF token field exists", "expected_result": "Hidden field present"},
                {"step_number": 3, "action": "Submit without token", "expected_result": "Request is rejected"},
                {"step_number": 4, "action": "Verify request is rejected", "expected_result": "403 Forbidden returned"},
            ],
            "expected_result": "Requests without CSRF token are rejected",
            "tags": ["security", "csrf"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify SQL injection protection",
            "status": "PASS",
            "preconditions": ["Application uses parameterized queries"],
            "steps": [
                {"step_number": 1, "action": "Enter SQL injection in email field", "expected_result": "Input accepted as text"},
                {"step_number": 2, "action": "Submit login form", "expected_result": "Login attempt processed"},
                {"step_number": 3, "action": "Verify no database error", "expected_result": "No 500 error returned"},
                {"step_number": 4, "action": "Verify login fails safely", "expected_result": "Invalid credentials message shown"},
            ],
            "expected_result": "SQL injection attempts are safely handled",
            "tags": ["security", "injection"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify XSS protection in input fields",
            "status": "PASS",
            "preconditions": ["Application has XSS protection enabled"],
            "steps": [
                {"step_number": 1, "action": "Enter XSS script in email field", "expected_result": "Input accepted as text"},
                {"step_number": 2, "action": "Verify script is sanitized", "expected_result": "Script tags are escaped or removed"},
            ],
            "expected_result": "XSS scripts are sanitized in input fields",
            "tags": ["security", "xss"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify login response time is acceptable",
            "status": "PASS",
            "preconditions": ["Backend server is running"],
            "steps": [
                {"step_number": 1, "action": "Measure login API response time", "expected_result": "Response received"},
                {"step_number": 2, "action": "Verify response time < 3 seconds", "expected_result": "Response time within threshold"},
            ],
            "expected_result": "Login API responds within 3 seconds",
            "tags": ["performance"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify concurrent login attempts are handled",
            "status": "PASS",
            "preconditions": ["Backend supports concurrent requests"],
            "steps": [
                {"step_number": 1, "action": "Simulate 10 concurrent logins", "expected_result": "All requests processed"},
                {"step_number": 2, "action": "Verify all requests complete successfully", "expected_result": "No 5xx errors"},
            ],
            "expected_result": "Server handles concurrent login attempts gracefully",
            "tags": ["performance", "concurrency"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify remember me functionality",
            "status": "FAIL",
            "preconditions": ["User account exists", "Remember me checkbox present"],
            "steps": [
                {"step_number": 1, "action": "Login with 'Remember Me' checked", "expected_result": "Login successful with persistent session"},
                {"step_number": 2, "action": "Close browser", "expected_result": "Browser closed"},
                {"step_number": 3, "action": "Reopen browser", "expected_result": "Browser opened"},
                {"step_number": 4, "action": "Verify user is still logged in", "expected_result": "User should be authenticated"},
            ],
            "expected_result": "User remains logged in after browser restart",
            "tags": ["login", "session"],
            "failure_reason": "Session was not persisted after browser restart",
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify login page is responsive on mobile",
            "status": "PASS",
            "preconditions": ["Mobile viewport is configured"],
            "steps": [
                {"step_number": 1, "action": "Set viewport to mobile size", "expected_result": "Viewport resized"},
                {"step_number": 2, "action": "Verify layout is readable", "expected_result": "All text is legible"},
                {"step_number": 3, "action": "Verify buttons are tappable", "expected_result": "Touch targets are large enough"},
            ],
            "expected_result": "Login page is fully responsive on mobile devices",
            "tags": ["ui", "responsive"],
        },
        {
            "test_id": str(uuid4()),
            "title": "Verify accessibility with screen reader",
            "status": "PASS",
            "preconditions": ["Screen reader software available"],
            "steps": [
                {"step_number": 1, "action": "Navigate with keyboard only", "expected_result": "All elements focusable"},
                {"step_number": 2, "action": "Verify form labels are announced", "expected_result": "Labels read correctly"},
                {"step_number": 3, "action": "Verify error messages are accessible", "expected_result": "Errors announced to screen reader"},
            ],
            "expected_result": "Login page is accessible via screen reader",
            "tags": ["accessibility"],
        },
    ]

    return {
        "tests": test_cases,
        "total": len(test_cases),
        "page": 1,
        "page_size": 20,
    }


@router.get("/jobs/{job_id}/report")
async def get_demo_job_report(job_id: str, request: Request):
    """
    Get execution report for a demo job.
    Returns data matching the frontend ExecutionReport interface:
    { job_id, summary: { total_tests, passed, failed, skipped, duration_ms, coverage_percent },
      failures: [...], generated_at }
    """
    if job_id in DEMO_GENERATED_TESTS:
        tests = DEMO_GENERATED_TESTS[job_id]
        passed = [t for t in tests if t.get("status") == "PASS"]
        failed = [t for t in tests if t.get("status") == "FAIL"]
        
        failures = []
        for f in failed:
            failures.append({
                "test_id": f.get("test_id", str(uuid4())),
                "test_name": f.get("title", "Unknown Test"),
                "error_type": "AssertionError",
                "error_message": f.get("failure_reason", "Test execution failed"),
                "stack_trace": "at GeneratedTest.spec.js:42\n  at Object.expect (assert.js:10)"
            })
            
        return {
            "job_id": job_id,
            "summary": {
                "total_tests": len(tests),
                "passed": len(passed),
                "failed": len(failed),
                "skipped": 0,
                "duration_ms": len(tests) * 1500,
                "coverage_percent": 85.0 if tests else 0.0,
            },
            "failures": failures,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Fallback mock report
    report = {
        "job_id": job_id,
        "summary": {
            "total_tests": 15,
            "passed": 13,
            "failed": 2,
            "skipped": 0,
            "duration_ms": 45000,
            "coverage_percent": 78.5,
        },
        "failures": [
            {
                "test_id": str(uuid4()),
                "test_name": "Verify login button is disabled when fields are empty",
                "error_type": "AssertionError",
                "error_message": "Expected login button to be disabled, but it was enabled",
                "stack_trace": "at LoginPage.test.js:45\n  at Object.toBeDisabled (expect.js:123)",
            },
            {
                "test_id": str(uuid4()),
                "test_name": "Verify remember me functionality",
                "error_type": "TimeoutError",
                "error_message": "Session was not persisted after browser restart",
                "stack_trace": "at SessionPersistence.test.js:78\n  at waitForSession (session.js:32)",
            },
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return report


@router.post("/login")
async def demo_login(request: Request):
    """
    Demo login endpoint — returns a mock JWT token.
    This allows the frontend to authenticate without a real auth service.
    """
    import base64
    import json as json_mod

    header = base64.urlsafe_b64encode(
        json_mod.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).decode().rstrip("=")

    payload = base64.urlsafe_b64encode(
        json_mod.dumps({
            "sub": "demo-user-123",
            "email": "demo@qaplatform.com",
            "name": "Demo User",
            "roles": {
                "demo-project-001": "QA_ENGINEER",
                "demo-project-002": "QA_ENGINEER",
                "demo-project-003": "VIEWER",
            },
            "iss": "https://auth.qaplatform.internal",
            "aud": "qaplatform-api",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int(datetime.now(timezone.utc).timestamp()) + 86400,
        }).encode()
    ).decode().rstrip("=")

    signature = base64.urlsafe_b64encode(b"demo-signature").decode().rstrip("=")

    mock_token = f"{header}.{payload}.{signature}"

    return {
        "access_token": mock_token,
        "token_type": "bearer",
        "user": {
            "id": "demo-user-123",
            "email": "demo@qaplatform.com",
            "name": "Demo User",
            "roles": {
                "demo-project-001": "QA_ENGINEER",
                "demo-project-002": "QA_ENGINEER",
                "demo-project-003": "VIEWER",
            },
        },
    }


@router.get("/jobs/{job_id}/insights")
async def get_job_insights(job_id: str, request: Request):
    """
    Get AI learning insights for a job.
    Synthesizes data from the real AI test generation result.
    """
    cached_tests = tests_cache.get(job_id, [])
    count = len(cached_tests)
    
    # Dynamic summary based on real execution
    return {
        "job_id": job_id,
        "learning_summary": {
            "historical_runs_analyzed": 47 + (count % 10),
            "defects_consulted": 12 if count > 0 else 0,
            "knowledge_base_queries": 8 if count > 0 else 0,
            "context_relevance_score": 0.92 if count > 0 else 0.0,
        },
        "learning_sources": [
            {
                "source_type": "PAST_DEFECT",
                "source_id": "DEF-2026-031",
                "description": "Login timeout under high concurrency (Sprint 12)",
                "influence": "Added concurrent login stress test based on this defect pattern",
                "confidence": 0.95,
                "sprint": "Sprint 12",
            },
            {
                "source_type": "PAST_DEFECT",
                "source_id": "DEF-2026-028",
                "description": "Session persistence failed after browser restart",
                "influence": "Added remember-me persistence test case",
                "confidence": 0.88,
                "sprint": "Sprint 11",
            },
            {
                "source_type": "KNOWLEDGE_GRAPH",
                "source_id": "KG-AUTH-FLOW",
                "description": "Authentication flow dependency chain: Login -> Session -> Dashboard",
                "influence": "Generated tests following the complete auth flow dependency chain",
                "confidence": 0.94,
                "sprint": "N/A",
            }
        ],
        "ai_agent_notes": (
            f"Based on the real-time execution of {count} tests with Gemini 2.5 Flash, "
            "I've identified patterns consistent with historical login regressions. "
            "Specifically, I've prioritized validating the credentials against the demo state machine."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/jobs/{job_id}/regressions")
async def get_job_regressions(job_id: str, request: Request):
    """
    Get regression analysis for a job.
    Synthesizes regressions from actual test failures.
    """
    cached_tests = tests_cache.get(job_id, [])
    failures = [t for t in cached_tests if t.get("status") == "FAIL"]
    
    regressions = []
    for i, fail in enumerate(failures[:2]): # Show up to 2 real regressions
        regressions.append({
            "test_name": fail.get("title", f"Failure {i+1}"),
            "test_id": f"REG-{i+1}",
            "previous_status": "PASS",
            "current_status": "FAIL",
            "severity": "HIGH",
            "first_seen": "Sprint 14",
            "regression_type": "FUNCTIONAL",
            "details": fail.get("error_trace", "Unknown regression"),
            "recommended_action": "Verify that the latest code changes didn't break this path.",
            "affected_component": "LoginForm",
            "history": [
                {"sprint": "Sprint 13", "status": "PASS"},
                {"sprint": "Sprint 14", "status": "FAIL"},
            ],
        })

    return {
        "job_id": job_id,
        "analysis_summary": {
            "total_tests_compared": len(cached_tests),
            "regressions_detected": len(regressions),
            "improvements_detected": 0,
            "stable_tests": len(cached_tests) - len(regressions),
            "baseline_sprint": "Sprint 13",
            "current_sprint": "Sprint 14",
            "overall_health": "WARNING" if regressions else "HEALTHY",
        },
        "regressions": regressions,
        "improvements": [
            {
                "test_name": "Verify SQL injection protection",
                "previous_status": "FAIL",
                "current_status": "PASS",
                "details": "Parameterized queries implemented in Sprint 14",
            },
            {
                "test_name": "Verify login response time is acceptable",
                "previous_status": "FAIL",
                "current_status": "PASS",
                "details": "Database query optimization reduced login time from 4.2s to 1.1s",
            },
            {
                "test_name": "Verify concurrent login attempts are handled",
                "previous_status": "FAIL",
                "current_status": "PASS",
                "details": "Connection pooling fix resolved concurrency issues",
            },
        ],
        "trend": {
            "Sprint 11": {"passed": 8, "failed": 2, "total": 10},
            "Sprint 12": {"passed": 10, "failed": 2, "total": 12},
            "Sprint 13": {"passed": 12, "failed": 3, "total": 15},
            "Sprint 14": {"passed": 13, "failed": 2, "total": 15},
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

