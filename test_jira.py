import os, base64, httpx, asyncio

async def test():
    env = {}
    with open('.env') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                env[k] = v

    JIRA_URL = env.get('AGENT_JIRA_URL')
    JIRA_USER = env.get('AGENT_JIRA_USER').replace('your-', '')
    JIRA_TOKEN = env.get('AGENT_JIRA_TOKEN').replace('your-', '')
    print(f'User: {JIRA_USER}')
    
    auth = base64.b64encode(f'{JIRA_USER}:{JIRA_TOKEN}'.encode()).decode()
    jql = 'project = SCRUM order by created DESC'
    url = f"{JIRA_URL.rstrip('/')}/rest/api/3/search/jql?jql={jql}&maxResults=10&fields=summary,status,issuetype,priority,labels"
    async with httpx.AsyncClient() as client:
        res = await client.get(
            url,
            headers={'Authorization': f'Basic {auth}', 'Accept': 'application/json'}
        )
        print('HTTP', res.status_code)
        
        try:
            print([i['key'] for i in res.json().get('issues', [])])
        except Exception as e:
            print('err', res.text[:100])

asyncio.run(test())
