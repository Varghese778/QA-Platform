import { apiClient, getToken } from './apiClient'
import {
  JobRecord,
  JobSubmitRequest,
  JobSubmitResponse,
  JobListResponse,
  JobTestsResponse,
  ExecutionReport,
  TestCase,
} from '../types/api'

// Check if user is in demo mode
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

export const jobService = {
  /**
   * Submit a new job (user story)
   */
  submitJob: async (data: JobSubmitRequest): Promise<string> => {
    const endpoint = isDemoMode() ? '/demo/jobs' : '/jobs'
    const response = await apiClient.post<JobSubmitResponse>(endpoint, data)
    return response.data.job_id
  },

  /**
   * Get list of jobs for a project
   */
  listJobs: async (
    projectId: string,
    page: number = 1,
    pageSize: number = 20,
    status?: string
  ): Promise<JobListResponse> => {
    const params: Record<string, any> = {
      project_id: projectId,
      page,
      page_size: pageSize,
    }
    if (status) {
      params.status = status
    }
    const endpoint = isDemoMode() ? '/demo/jobs' : '/jobs'
    const response = await apiClient.get<JobListResponse>(endpoint, { params })
    return response.data
  },

  /**
   * Get detailed job information
   */
  getJob: async (jobId: string): Promise<JobRecord> => {
    const endpoint = isDemoMode() ? `/demo/jobs/${jobId}` : `/jobs/${jobId}`
    const response = await apiClient.get<JobRecord>(endpoint)
    return response.data
  },

  /**
   * Get test cases for a job
   */
  getJobTests: async (
    jobId: string,
    page: number = 1,
    pageSize: number = 20,
    statusFilter?: string
  ): Promise<JobTestsResponse> => {
    const params: Record<string, any> = {
      page,
      page_size: pageSize,
    }
    if (statusFilter) {
      params.filter_status = statusFilter
    }
    const endpoint = isDemoMode()
      ? `/demo/jobs/${jobId}/tests`
      : `/jobs/${jobId}/tests`
    const response = await apiClient.get<JobTestsResponse>(
      endpoint,
      { params }
    )
    return response.data
  },

  /**
   * Get execution report for a job
   */
  getJobReport: async (jobId: string): Promise<ExecutionReport> => {
    const endpoint = isDemoMode()
      ? `/demo/jobs/${jobId}/report`
      : `/jobs/${jobId}/report`
    const response = await apiClient.get<ExecutionReport>(endpoint)
    return response.data
  },

  /**
   * Export job report as PDF or CSV
   */
  exportJob: async (jobId: string, format: 'pdf' | 'csv'): Promise<Blob> => {
    const endpoint = isDemoMode()
      ? `/demo/jobs/${jobId}/export`
      : `/jobs/${jobId}/export`
    const response = await apiClient.get(endpoint, {
      params: { format },
      responseType: 'blob',
    })
    return response.data
  },

  /**
   * Cancel a job
   */
  cancelJob: async (jobId: string): Promise<void> => {
    const endpoint = isDemoMode()
      ? `/demo/jobs/${jobId}`
      : `/jobs/${jobId}`
    await apiClient.delete(endpoint)
  },

  /**
   * Hard Delete a job
   */
  deleteJob: async (jobId: string): Promise<void> => {
    const endpoint = isDemoMode()
      ? `/demo/jobs/${jobId}?hard=true`
      : `/jobs/${jobId}` // Assuming real endpoints implement delete similarly, though demo specifically asked for UI cleanup
    await apiClient.delete(endpoint)
  },

  /**
   * Download exported file
   */
  downloadExport: async (jobId: string, format: 'pdf' | 'csv'): Promise<void> => {
    const blob = await jobService.exportJob(jobId, format)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `job-${jobId}-report.${format}`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  },
}
