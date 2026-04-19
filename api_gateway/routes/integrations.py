"""Integration routes for Jira/Azure DevOps connectivity."""

import logging
import os
import base64
from datetime import datetime, timezone
from uuid import uuid4
import httpx

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo/integrations", tags=["integrations"])


# =====================================================================
# Configured Integrations
# =====================================================================

CONFIGURED_INTEGRATIONS = [
    {
        "id": "jira-001",
        "name": "Jira",
        "type": "ISSUE_TRACKER",
        "provider": "atlassian",
        "status": "CONNECTED",
        "connected_at": "2026-03-20T10:00:00Z",
        "config": {
            "base_url": "https://qaplatform.atlassian.net",
            "project_key": "QAP",
            "sync_enabled": True,
            "auto_import": True,
            "webhook_url": "/api/v1/demo/integrations/jira/webhook",
        },
        "stats": {
            "stories_imported": 47,
            "last_sync": "2026-03-25T14:30:00Z",
            "sync_frequency": "Every 15 minutes",
        },
        "icon": "🔷",
    },
    {
        "id": "azdo-001",
        "name": "Azure DevOps",
        "type": "ISSUE_TRACKER",
        "provider": "microsoft",
        "status": "DISCONNECTED",
        "connected_at": None,
        "config": {
            "organization": "qaplatform-org",
            "project": "QA-Platform",
            "sync_enabled": True,
            "auto_import": False,
            "webhook_url": "/api/v1/demo/integrations/azuredevops/webhook",
        },
        "stats": {
            "stories_imported": 23,
            "last_sync": "2026-03-25T12:15:00Z",
            "sync_frequency": "Every 30 minutes",
        },
        "icon": "🔶",
    },
    {
        "id": "selenium-001",
        "name": "Selenium Grid",
        "type": "TEST_RUNNER",
        "provider": "selenium",
        "status": "DISCONNECTED",
        "connected_at": None,
        "config": {
            "hub_url": "http://selenium-hub:4444",
            "browsers": ["chrome", "firefox", "edge"],
            "max_parallel": 5,
        },
        "stats": {
            "tests_executed": 312,
            "last_run": "2026-03-25T15:00:00Z",
        },
        "icon": "🌐",
    },
    {
        "id": "testng-001",
        "name": "TestNG",
        "type": "TEST_FRAMEWORK",
        "provider": "testng",
        "status": "DISCONNECTED",
        "connected_at": None,
        "config": {
            "version": "7.9.0",
            "report_format": "xml",
        },
        "stats": {
            "suites_managed": 8,
        },
        "icon": "🧪",
    },
]


# Simulated Jira issues for import
JIRA_ISSUES = {
    "QAP-101": {
        "key": "QAP-101",
        "summary": "User login with SSO should redirect to dashboard",
        "description": "As a user, I want to log in using Single Sign-On (SSO) so that I can access the dashboard without entering separate credentials. The system should integrate with corporate SAML/OAuth providers and handle token refresh automatically.",
        "type": "Story",
        "status": "Ready for QA",
        "priority": "High",
        "sprint": "Sprint 14",
        "assignee": "Jane Smith",
        "labels": ["authentication", "sso", "security"],
        "created": "2026-03-20T10:30:00Z",
        "acceptance_criteria": [
            "SSO login redirects to corporate IdP",
            "After authentication, user lands on dashboard",
            "Token refresh happens automatically",
            "Failed SSO shows appropriate error message",
        ],
    },
    "QAP-102": {
        "key": "QAP-102",
        "summary": "Shopping cart should persist across browser sessions",
        "description": "As a customer, I want my shopping cart items to persist even after I close the browser so that I can continue shopping later without losing my selections. Cart data should sync between devices when logged in.",
        "type": "Story",
        "status": "In Sprint",
        "priority": "Medium",
        "sprint": "Sprint 14",
        "assignee": "Bob Johnson",
        "labels": ["cart", "persistence", "e-commerce"],
        "created": "2026-03-21T14:00:00Z",
        "acceptance_criteria": [
            "Cart items remain after browser close/reopen",
            "Cart syncs across multiple devices when logged in",
            "Guest cart merges with authenticated cart on login",
            "Cart expiry after 30 days of inactivity",
        ],
    },
    "QAP-103": {
        "key": "QAP-103",
        "summary": "Patient records should display medication history timeline",
        "description": "As a doctor, I want to view a patient's medication history as an interactive timeline so that I can quickly identify patterns, allergies, and potential drug interactions before prescribing new treatments.",
        "type": "Story",
        "status": "Ready for QA",
        "priority": "Critical",
        "sprint": "Sprint 14",
        "assignee": "Dr. Alice Chen",
        "labels": ["healthcare", "patient-records", "timeline"],
        "created": "2026-03-22T09:15:00Z",
        "acceptance_criteria": [
            "Timeline shows all medications with start/end dates",
            "Drug interactions are highlighted with warning icons",
            "Allergies are prominently displayed",
            "Timeline is filterable by date range and medication type",
        ],
    },
    "QAP-104": {
        "key": "QAP-104",
        "summary": "Bank transfer should validate recipient account in real-time",
        "description": "As a bank user, I want the system to validate the recipient's account number and display their name before I confirm a transfer so that I can avoid sending money to wrong accounts.",
        "type": "Story",
        "status": "In Sprint",
        "priority": "High",
        "sprint": "Sprint 14",
        "assignee": "Mike Williams",
        "labels": ["banking", "transfers", "validation"],
        "created": "2026-03-23T11:00:00Z",
        "acceptance_criteria": [
            "Account validation happens within 2 seconds",
            "Recipient name is displayed after validation",
            "Invalid account numbers show clear error message",
            "Transfer is blocked if validation fails",
        ],
    },
}


@router.get("")
async def list_integrations(request: Request):
    """List all configured integrations."""
    logger.info("Listing integrations")
    return {
        "integrations": CONFIGURED_INTEGRATIONS,
        "total": len(CONFIGURED_INTEGRATIONS),
    }


@router.get("/{integration_id}")
async def get_integration(integration_id: str, request: Request):
    """Get details of a specific integration."""
    for integration in CONFIGURED_INTEGRATIONS:
        if integration["id"] == integration_id:
            return integration
    return JSONResponse(
        status_code=404,
        content={"error": "Integration not found"},
    )


@router.post("/jira/import")
async def import_from_jira(request: Request, background_tasks: BackgroundTasks):
    """
    Import a user story from Jira by issue key.
    
    Simulates fetching the issue from Jira and creating a QA job.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON body"},
        )

    issue_key = body.get("issue_key", "").upper().strip()

    if not issue_key:
        return JSONResponse(
            status_code=400,
            content={"error": "issue_key is required"},
        )

    # Look up the Jira issue
    JIRA_URL = os.environ.get("AGENT_JIRA_URL")
    JIRA_USER = os.environ.get("AGENT_JIRA_USER")
    JIRA_TOKEN = os.environ.get("AGENT_JIRA_TOKEN")
    
    issue = None
    
    if JIRA_URL and JIRA_USER and JIRA_TOKEN:
        try:
            auth = base64.b64encode(f"{JIRA_USER}:{JIRA_TOKEN}".encode()).decode()
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{JIRA_URL.rstrip('/')}/rest/api/3/issue/{issue_key}",
                    headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
                    timeout=10.0
                )
                if res.status_code == 200:
                    data = res.json()
                    fields = data.get("fields", {})
                    
                    # Extract description from Atlassian Document Format
                    desc = ""
                    if isinstance(fields.get("description"), dict) and "content" in fields["description"]:
                        for block in fields["description"]["content"]:
                            if block.get("type") == "paragraph" and "content" in block:
                                for text_block in block["content"]:
                                    if "text" in text_block:
                                        desc += text_block["text"] + " "
                    elif isinstance(fields.get("description"), str):
                        desc = fields["description"]
                        
                    issue = {
                        "key": data["key"],
                        "summary": fields.get("summary", ""),
                        "description": desc.strip() or "No description provided",
                        "status": fields.get("status", {}).get("name", "Unknown"),
                        "priority": fields.get("priority", {}).get("name", "Normal"),
                        "labels": fields.get("labels", []),
                        "sprint": "Current Sprint",
                        "acceptance_criteria": []
                    }
                elif res.status_code == 404:
                    logger.warning(f"Jira issue {issue_key} not found via API")
                else:
                    logger.error(f"Jira API error: {res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Failed to fetch issue from Jira API: {e}")
            
    # Fallback to mock data if real API config is missing or failed
    if not issue:
        issue = JIRA_ISSUES.get(issue_key)
        
    if not issue:
        return JSONResponse(
            status_code=404,
            content={
                "error": f"Jira issue {issue_key} not found",
                "available_keys": list(JIRA_ISSUES.keys()),
            },
        )

    # Build the user story from Jira data
    acceptance_text = "\n".join(f"- {ac}" for ac in issue.get("acceptance_criteria", []))
    user_story = f"{issue.get('description', '')}\n\nAcceptance Criteria:\n{acceptance_text}"

    # Create a job from the imported story
    from api_gateway.routes.demo import DEMO_JOBS, _initialize_new_demo_job, _generate_real_tests_task

    job_data = {
        "project_id": body.get("project_id", "demo-project-001"),
        "story_title": f"[{issue_key}] {issue['summary']}",
        "user_story": user_story,
        "priority": {"Critical": "CRITICAL", "High": "HIGH", "Medium": "NORMAL", "Low": "LOW"}.get(
            issue["priority"], "NORMAL"
        ),
        "tags": issue.get("labels", []) + ["jira-import"],
        "environment_target": "STAGING",
    }

    new_job = _initialize_new_demo_job(job_data)
    new_job["source"] = {
        "type": "jira",
        "issue_key": issue_key,
        "issue_url": f"https://qaplatform.atlassian.net/browse/{issue_key}",
        "sprint": issue.get("sprint"),
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }

    DEMO_JOBS.insert(0, new_job)
    
    # Start real AI generation and browser execution in the background
    background_tasks.add_task(_generate_real_tests_task, new_job, job_data)

    logger.info(f"Imported Jira issue {issue_key} as job {new_job['job_id']}")

    return {
        "success": True,
        "job_id": new_job["job_id"],
        "jira_issue": {
            "key": issue_key,
            "summary": issue["summary"],
            "status": issue["status"],
            "priority": issue["priority"],
        },
        "message": f"Successfully imported {issue_key} and created QA job",
        "queued_at": new_job["created_at"],
    }


@router.post("/jira/webhook")
async def jira_webhook(request: Request):
    """
    Receive Jira webhook events.
    
    Handles: issue_created, issue_updated, sprint_started, sprint_closed
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    event_type = body.get("webhookEvent", body.get("event_type", "unknown"))
    logger.info(f"Received Jira webhook: {event_type}")

    return {
        "received": True,
        "event_type": event_type,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Webhook event '{event_type}' processed successfully",
    }


@router.post("/azuredevops/webhook")
async def azuredevops_webhook(request: Request):
    """Receive Azure DevOps webhook events."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    event_type = body.get("eventType", body.get("event_type", "unknown"))
    logger.info(f"Received Azure DevOps webhook: {event_type}")

    return {
        "received": True,
        "event_type": event_type,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Azure DevOps event '{event_type}' processed successfully",
    }


@router.get("/jira/issues")
async def list_jira_issues(request: Request):
    """List available Jira issues for import."""
    JIRA_URL = os.environ.get("AGENT_JIRA_URL")
    JIRA_USER = os.environ.get("AGENT_JIRA_USER")
    JIRA_TOKEN = os.environ.get("AGENT_JIRA_TOKEN")
    
    issues = []
    use_mock_fallback = True  # Only use mock if real Jira is not configured
    
    if JIRA_URL and JIRA_USER and JIRA_TOKEN:
        use_mock_fallback = False  # Real Jira is configured, don't use mock
        try:
            # Get project key from environment, default to SCRUM
            project_key = os.environ.get("AGENT_JIRA_PROJECT_KEY", "SCRUM")
            auth = base64.b64encode(f"{JIRA_USER}:{JIRA_TOKEN}".encode()).decode()
            async with httpx.AsyncClient() as client:
                # Query must be bounded with project filter - Jira Cloud requires this
                jql = f"project = {project_key} order by created DESC"
                res = await client.get(
                    f"{JIRA_URL.rstrip('/')}/rest/api/3/search/jql?jql={jql}&maxResults=10&fields=summary,status,issuetype,priority,labels",
                    headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
                    timeout=10.0
                )
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("issues", []):
                        fields = item.get("fields", {})
                        issues.append({
                            "key": item["key"],
                            "summary": fields.get("summary", ""),
                            "type": fields.get("issuetype", {}).get("name", "Story"),
                            "status": fields.get("status", {}).get("name", "Unknown"),
                            "priority": fields.get("priority", {}).get("name", "Normal"),
                            "sprint": "Current Sprint",
                            "labels": fields.get("labels", [])
                        })
                else:
                    logger.error(f"Jira API list error: {res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Failed to list issues from Jira API: {e}")
            
    # Use mock data if Jira is not configured or if API returned no issues
    if use_mock_fallback or not issues:
        issues = [
            {
                "key": v["key"],
                "summary": v["summary"],
                "type": v["type"],
                "status": v["status"],
                "priority": v["priority"],
                "sprint": v["sprint"],
                "labels": v["labels"],
            }
            for v in JIRA_ISSUES.values()
        ]
        
    return {"issues": issues, "total": len(issues)}
