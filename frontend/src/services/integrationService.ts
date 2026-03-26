import { apiClient } from './apiClient'

export interface Integration {
  id: string
  name: string
  type: string
  provider: string
  status: string
  connected_at: string
  config: Record<string, any>
  stats: Record<string, any>
  icon: string
}

export interface JiraIssue {
  key: string
  summary: string
  type: string
  status: string
  priority: string
  sprint: string
  labels: string[]
}

export const integrationService = {
  /**
   * List all configured integrations
   */
  listIntegrations: async (): Promise<Integration[]> => {
    const response = await apiClient.get<{ integrations: Integration[]; total: number }>(
      '/demo/integrations'
    )
    return response.data.integrations
  },

  /**
   * Import a user story from Jira by issue key
   */
  importFromJira: async (
    issueKey: string,
    projectId: string
  ): Promise<{ success: boolean; job_id: string; message: string }> => {
    const response = await apiClient.post('/demo/integrations/jira/import', {
      issue_key: issueKey,
      project_id: projectId,
    })
    return response.data
  },

  /**
   * List available Jira issues for import
   */
  listJiraIssues: async (): Promise<JiraIssue[]> => {
    const response = await apiClient.get<{ issues: JiraIssue[]; total: number }>(
      '/demo/integrations/jira/issues'
    )
    return response.data.issues
  },
}
