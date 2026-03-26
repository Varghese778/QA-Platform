import React, { createContext, useContext, useState, ReactNode } from 'react'
import {
  JobRecord,
  JobSubmitRequest,
  TestCase,
  ExecutionReport,
} from '../types/api'
import { jobService } from '../services/jobService'

interface JobContextType {
  jobs: Map<string, JobRecord>
  selectedJobId: string | null
  jobsLoading: boolean
  jobsError: string | null
  submitJob: (payload: JobSubmitRequest) => Promise<string>
  fetchJobs: (projectId: string, page?: number, pageSize?: number, status?: string) => Promise<void>
  fetchJobDetail: (jobId: string) => Promise<JobRecord>
  fetchJobTests: (jobId: string, page?: number, pageSize?: number, statusFilter?: string) => Promise<TestCase[]>
  fetchJobReport: (jobId: string) => Promise<ExecutionReport>
  cancelJob: (jobId: string) => Promise<void>
  deleteJob: (jobId: string) => Promise<void>
  selectJob: (jobId: string | null) => void
  updateJobInCache: (jobId: string, updates: Partial<JobRecord>) => void
  clearError: () => void
}

const JobContext = createContext<JobContextType | undefined>(undefined)

export function JobProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Map<string, JobRecord>>(new Map())
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [jobsLoading, setJobsLoading] = useState(false)
  const [jobsError, setJobsError] = useState<string | null>(null)

  const submitJob = async (payload: JobSubmitRequest): Promise<string> => {
    setJobsError(null)
    try {
      const jobId = await jobService.submitJob(payload)
      return jobId
    } catch (error: any) {
      setJobsError(error.message || 'Failed to submit job')
      throw error
    }
  }

  const fetchJobs = async (
    projectId: string,
    page: number = 1,
    pageSize: number = 20,
    status?: string
  ): Promise<void> => {
    setJobsLoading(true)
    setJobsError(null)

    try {
      const response = await jobService.listJobs(projectId, page, pageSize, status)
      const newJobs = new Map(jobs)
      response.jobs.forEach((job) => {
        newJobs.set(job.job_id, job)
      })
      setJobs(newJobs)
    } catch (error: any) {
      setJobsError(error.message || 'Failed to fetch jobs')
    } finally {
      setJobsLoading(false)
    }
  }

  const fetchJobDetail = async (jobId: string): Promise<JobRecord> => {
    setJobsError(null)
    try {
      const job = await jobService.getJob(jobId)
      const newJobs = new Map(jobs)
      newJobs.set(jobId, job)
      setJobs(newJobs)
      return job
    } catch (error: any) {
      setJobsError(error.message || 'Failed to fetch job details')
      throw error
    }
  }

  const fetchJobTests = async (
    jobId: string,
    page: number = 1,
    pageSize: number = 20,
    statusFilter?: string
  ): Promise<TestCase[]> => {
    setJobsError(null)
    try {
      const response = await jobService.getJobTests(jobId, page, pageSize, statusFilter)
      return response.tests
    } catch (error: any) {
      setJobsError(error.message || 'Failed to fetch job tests')
      throw error
    }
  }

  const fetchJobReport = async (jobId: string): Promise<ExecutionReport> => {
    setJobsError(null)
    try {
      const report = await jobService.getJobReport(jobId)
      return report
    } catch (error: any) {
      setJobsError(error.message || 'Failed to fetch job report')
      throw error
    }
  }

  const cancelJob = async (jobId: string): Promise<void> => {
    setJobsError(null)
    try {
      await jobService.cancelJob(jobId)
      // Update local cache
      const job = jobs.get(jobId)
      if (job) {
        updateJobInCache(jobId, { status: 'CANCELLED' })
      }
    } catch (error: any) {
      setJobsError(error.message || 'Failed to cancel job')
      throw error
    }
  }

  const deleteJob = async (jobId: string): Promise<void> => {
    setJobsError(null)
    try {
      await jobService.deleteJob(jobId)
      const newJobs = new Map(jobs)
      newJobs.delete(jobId)
      setJobs(newJobs)
    } catch (error: any) {
      setJobsError(error.message || 'Failed to delete job')
      throw error
    }
  }

  const selectJob = (jobId: string | null): void => {
    setSelectedJobId(jobId)
  }

  const updateJobInCache = (jobId: string, updates: Partial<JobRecord>): void => {
    const job = jobs.get(jobId)
    if (job) {
      const updatedJob = { ...job, ...updates, updated_at: new Date().toISOString() }
      const newJobs = new Map(jobs)
      newJobs.set(jobId, updatedJob)
      setJobs(newJobs)
    }
  }

  const clearError = (): void => {
    setJobsError(null)
  }

  const value: JobContextType = {
    jobs,
    selectedJobId,
    jobsLoading,
    jobsError,
    submitJob,
    fetchJobs,
    fetchJobDetail,
    fetchJobTests,
    fetchJobReport,
    cancelJob,
    deleteJob,
    selectJob,
    updateJobInCache,
    clearError,
  }

  return <JobContext.Provider value={value}>{children}</JobContext.Provider>
}

export function useJob(): JobContextType {
  const context = useContext(JobContext)
  if (context === undefined) {
    throw new Error('useJob must be used within a JobProvider')
  }
  return context
}
