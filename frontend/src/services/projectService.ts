import { apiClient } from './apiClient'
import { ProjectListResponse, ProjectItem } from '../types/api'
import { getToken } from './apiClient'

// Check if user is in demo mode (has a demo token)
const isDemoMode = (): boolean => {
  const token = getToken()
  if (!token) return false

  try {
    // JWT format: header.payload.signature
    const parts = token.split('.')
    if (parts.length !== 3) return false

    // Decode the payload (second part)
    const payload = JSON.parse(atob(parts[1]))

    // Check if the subject contains 'demo'
    return payload.sub?.includes('demo') || false
  } catch (error) {
    // If decoding fails, not a valid JWT or demo token
    return false
  }
}

export const projectService = {
  /**
   * Get list of projects the user has access to
   */
  listProjects: async (): Promise<ProjectItem[]> => {
    const endpoint = isDemoMode() ? '/demo/projects' : '/projects'
    const response = await apiClient.get<ProjectListResponse>(endpoint)
    return response.data.projects
  },

  /**
   * Get a specific project
   */
  getProject: async (projectId: string): Promise<ProjectItem> => {
    const endpoint = isDemoMode() ? `/demo/projects/${projectId}` : `/projects/${projectId}`
    const response = await apiClient.get<ProjectItem>(endpoint)
    return response.data
  },
}
