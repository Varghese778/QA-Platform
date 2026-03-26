import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import DashboardLayout from '../components/Layout/DashboardLayout'
import LoadingSpinner from '../components/Common/LoadingSpinner'
import { showToast } from '../components/Common/Toast'
import { integrationService, Integration, JiraIssue } from '../services/integrationService'
import { projectService } from '../services/projectService'

export default function IntegrationsPage() {
  const navigate = useNavigate()
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [jiraIssues, setJiraIssues] = useState<JiraIssue[]>([])
  const [loading, setLoading] = useState(true)
  const [importingKey, setImportingKey] = useState<string | null>(null)
  const [manualKey, setManualKey] = useState('')
  const [showJiraPanel, setShowJiraPanel] = useState(false)
  const [projects, setProjects] = useState<any[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string>('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [integrationsData, issuesData, projectsList] = await Promise.all([
        integrationService.listIntegrations(),
        integrationService.listJiraIssues(),
        projectService.listProjects()
      ])
      setIntegrations(integrationsData)
      setJiraIssues(issuesData)
      setProjects(projectsList)
      if (projectsList.length > 0) {
        setSelectedProjectId(projectsList[0].project_id)
      }
    } catch (error: any) {
      showToast('Failed to load integrations', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async (issueKey: string) => {
    if (!selectedProjectId) {
      showToast('Please select a target project', 'error');
      return;
    }
    setImportingKey(issueKey)
    try {
      const result = await integrationService.importFromJira(issueKey, selectedProjectId)
      showToast(`✅ ${result.message}`, 'success')
      // Navigate to the new job
      setTimeout(() => navigate(`/jobs/${result.job_id}`), 1000)
    } catch (error: any) {
      showToast(`Failed to import: ${error?.response?.data?.error || error.message}`, 'error')
    } finally {
      setImportingKey(null)
    }
  }

  const handleManualImport = async () => {
    if (!manualKey.trim()) return
    await handleImport(manualKey.trim().toUpperCase())
    setManualKey('')
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      </DashboardLayout>
    )
  }

  const statusColor = (s: string) =>
    s === 'CONNECTED' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'

  const priorityColor = (p: string) => {
    const map: Record<string, string> = {
      Critical: 'bg-red-100 text-red-800',
      High: 'bg-orange-100 text-orange-800',
      Medium: 'bg-yellow-100 text-yellow-800',
      Low: 'bg-blue-100 text-blue-800',
    }
    return map[p] || 'bg-gray-100 text-gray-800'
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">🔗 Integrations</h1>
          <p className="text-gray-600 mt-1">
            Connected enterprise tools and DevOps integrations
          </p>
        </div>

        {/* Connected Integrations Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {integrations.map((integration) => (
            <div
              key={integration.id}
              className="bg-white shadow-md rounded-lg p-5 border border-gray-100 hover:shadow-lg transition-shadow"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-3xl">{integration.icon}</span>
                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${statusColor(integration.status)}`}>
                  {integration.status}
                </span>
              </div>
              <h3 className="font-bold text-lg text-gray-900">{integration.name}</h3>
              <p className="text-sm text-gray-500 capitalize">{integration.type.replace('_', ' ').toLowerCase()}</p>

              {/* Stats */}
              <div className="mt-3 space-y-1 text-xs text-gray-500">
                {integration.stats.stories_imported !== undefined && (
                  <div>📥 {integration.stats.stories_imported} stories imported</div>
                )}
                {integration.stats.tests_executed !== undefined && (
                  <div>🧪 {integration.stats.tests_executed} tests executed</div>
                )}
                {integration.stats.suites_managed !== undefined && (
                  <div>📦 {integration.stats.suites_managed} suites managed</div>
                )}
                {integration.stats.last_sync && (
                  <div>🔄 Last sync: {new Date(integration.stats.last_sync).toLocaleString()}</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Jira Import Section */}
        <div className="bg-white shadow-md rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">🔷 Import from Jira</h2>
              <p className="text-gray-600 text-sm mt-1">
                Import user stories directly from Jira and auto-generate QA test suites
              </p>
            </div>
            <button
              onClick={() => setShowJiraPanel(!showJiraPanel)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              {showJiraPanel ? 'Hide Issues' : 'Browse Jira Issues'}
            </button>
          </div>

          {/* Project Selection */}
          <div className="mb-6 bg-blue-50 p-4 rounded-lg border border-blue-100">
            <label className="block text-sm font-semibold text-blue-900 mb-2">Target Project for Import</label>
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="w-full xl:w-1/2 px-3 py-2 border border-blue-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="" disabled>Select a project...</option>
              {projects.map(p => (
                <option key={p.project_id} value={p.project_id}>{p.name}</option>
              ))}
            </select>
          </div>

          {/* Manual Import */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              value={manualKey}
              onChange={(e) => setManualKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleManualImport()}
              placeholder="Enter Jira issue key (e.g., QAP-101)"
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleManualImport}
              disabled={!manualKey.trim() || importingKey !== null}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {importingKey ? 'Importing...' : 'Import'}
            </button>
          </div>

          {/* Jira Issues Browser */}
          {showJiraPanel && (
            <div className="space-y-3 border-t pt-4">
              <h3 className="font-semibold text-gray-700 text-sm uppercase tracking-wide">
                Available Issues in Jira
              </h3>
              {jiraIssues.map((issue) => (
                <div
                  key={issue.key}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-mono text-blue-600 font-bold">
                          {issue.key}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${priorityColor(issue.priority)}`}>
                          {issue.priority}
                        </span>
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                          {issue.type}
                        </span>
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                          {issue.status}
                        </span>
                      </div>
                      <p className="font-medium text-gray-900">{issue.summary}</p>
                      <div className="flex gap-1 mt-2">
                        {issue.labels.map((label) => (
                          <span
                            key={label}
                            className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs"
                          >
                            {label}
                          </span>
                        ))}
                      </div>
                    </div>
                    <button
                      onClick={() => handleImport(issue.key)}
                      disabled={importingKey !== null}
                      className="ml-4 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 transition-colors text-sm font-medium whitespace-nowrap"
                    >
                      {importingKey === issue.key ? '⏳ Importing...' : '📥 Import & Generate Tests'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Webhook Configuration */}
        <div className="bg-white shadow-md rounded-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">⚡ Webhook Configuration</h2>
          <p className="text-gray-600 text-sm mb-4">
            Configure webhooks to automatically import user stories when they're created or moved to "Ready for QA" in your issue tracker.
          </p>
          <div className="space-y-3">
            <div className="bg-gray-50 rounded-lg p-4 border">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-gray-900">Jira Webhook</span>
                  <p className="text-xs text-gray-500 mt-1">Triggers on: issue_created, issue_updated, sprint_started</p>
                </div>
                <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-semibold">ACTIVE</span>
              </div>
              <code className="block mt-2 text-xs bg-gray-100 p-2 rounded text-gray-700 font-mono break-all">
                POST {window.location.origin}/api/v1/demo/integrations/jira/webhook
              </code>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 border">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-gray-900">Azure DevOps Webhook</span>
                  <p className="text-xs text-gray-500 mt-1">Triggers on: workitem.created, workitem.updated</p>
                </div>
                <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-semibold">ACTIVE</span>
              </div>
              <code className="block mt-2 text-xs bg-gray-100 p-2 rounded text-gray-700 font-mono break-all">
                POST {window.location.origin}/api/v1/demo/integrations/azuredevops/webhook
              </code>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
