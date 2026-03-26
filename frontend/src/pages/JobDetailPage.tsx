import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useJob } from '../context/JobContext'
import { TestCase, ExecutionReport } from '../types/api'
import { showToast } from '../components/Common/Toast'
import DashboardLayout from '../components/Layout/DashboardLayout'
import PipelineStatusPanel from '../components/PipelineStatus/PipelineStatusPanel'
import TestSuiteViewer from '../components/TestSuite/TestSuiteViewer'
import ExecutionReportViewer from '../components/ExecutionReport/ExecutionReportViewer'
import RegressionPanel from '../components/RegressionPanel/RegressionPanel'
import LoadingSpinner from '../components/Common/LoadingSpinner'

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { jobs, fetchJobDetail, fetchJobTests, fetchJobReport, cancelJob } = useJob()

  const [testCases, setTestCases] = useState<TestCase[]>([])
  const [report, setReport] = useState<ExecutionReport | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingTests, setIsLoadingTests] = useState(false)
  const [isLoadingReport, setIsLoadingReport] = useState(false)
  const [activeTab, setActiveTab] = useState<'pipeline' | 'tests' | 'report' | 'regressions'>('pipeline')

  const job = jobId ? jobs.get(jobId) : null

  // Fetch job details on mount
  useEffect(() => {
    const loadJobDetail = async () => {
      if (!jobId) return

      setIsLoading(true)
      try {
        await fetchJobDetail(jobId)
      } catch (error: any) {
        showToast(error.message || 'Failed to load job details', 'error')
        navigate('/dashboard')
      } finally {
        setIsLoading(false)
      }
    }

    loadJobDetail()
  }, [jobId])

  // Fetch tests when switching to tests tab
  useEffect(() => {
    if (activeTab === 'tests' && jobId && testCases.length === 0) {
      loadTests()
    }
  }, [activeTab, jobId])

  // Fetch report when switching to report tab
  useEffect(() => {
    if (activeTab === 'report' && jobId && !report && job?.report_ready) {
      loadReport()
    }
  }, [activeTab, jobId, job?.report_ready])

  const loadTests = async () => {
    if (!jobId) return

    setIsLoadingTests(true)
    try {
      const tests = await fetchJobTests(jobId)
      setTestCases(tests)
    } catch (error: any) {
      showToast(error.message || 'Failed to load tests', 'error')
    } finally {
      setIsLoadingTests(false)
    }
  }

  const loadReport = async () => {
    if (!jobId) return

    setIsLoadingReport(true)
    try {
      const reportData = await fetchJobReport(jobId)
      setReport(reportData)
    } catch (error: any) {
      if (error.code === 'REPORT_NOT_READY') {
        showToast('Report is not ready yet. Please wait...', 'warning')
      } else {
        showToast(error.message || 'Failed to load report', 'error')
      }
    } finally {
      setIsLoadingReport(false)
    }
  }

  const handleCancelJob = async () => {
    if (!jobId) return

    const confirmed = window.confirm('Are you sure you want to cancel this job?')
    if (!confirmed) return

    try {
      await cancelJob(jobId)
      showToast('Job cancelled successfully', 'success')
    } catch (error: any) {
      showToast(error.message || 'Failed to cancel job', 'error')
    }
  }

  if (isLoading || !job) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <button
              onClick={() => navigate('/dashboard')}
              className="text-primary hover:text-blue-700 text-sm font-medium mb-2 flex items-center gap-1"
            >
              ← Back to Dashboard
            </button>
            <h1 className="text-3xl font-bold text-gray-900">{job.story_title}</h1>
            <p className="text-gray-600 mt-2">{job.user_story}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              {job.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
          {(job.status === 'QUEUED' || job.status === 'PROCESSING') && (
            <button
              onClick={handleCancelJob}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors font-medium"
            >
              Cancel Job
            </button>
          )}
        </div>

        {/* Tabs */}
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <div className="flex border-b border-gray-200">
            <button
              onClick={() => setActiveTab('pipeline')}
              className={`flex-1 px-6 py-3 font-medium transition-colors ${
                activeTab === 'pipeline'
                  ? 'bg-primary text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Pipeline Status
            </button>
            <button
              onClick={() => setActiveTab('tests')}
              className={`flex-1 px-6 py-3 font-medium transition-colors ${
                activeTab === 'tests'
                  ? 'bg-primary text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Test Suite
            </button>
            <button
              onClick={() => setActiveTab('report')}
              disabled={!job.report_ready}
              className={`flex-1 px-6 py-3 font-medium transition-colors ${
                activeTab === 'report'
                  ? 'bg-primary text-white'
                  : job.report_ready
                  ? 'bg-white text-gray-700 hover:bg-gray-50'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              Execution Report
              {!job.report_ready && <span className="ml-2 text-xs">(Not Ready)</span>}
            </button>
            <button
              onClick={() => setActiveTab('regressions')}
              className={`flex-1 px-6 py-3 font-medium transition-colors ${
                activeTab === 'regressions'
                  ? 'bg-primary text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              📉 Regressions & Insights
            </button>
          </div>

          <div className="p-6">
            {/* Pipeline Tab */}
            {activeTab === 'pipeline' && (
              <PipelineStatusPanel jobId={job.job_id} jobRecord={job} />
            )}

            {/* Tests Tab */}
            {activeTab === 'tests' && (
              <>
                {isLoadingTests ? (
                  <div className="flex items-center justify-center py-12">
                    <LoadingSpinner size="md" />
                  </div>
                ) : (
                  <TestSuiteViewer
                    jobId={job.job_id}
                    testCases={testCases}
                    onFilterChange={() => {}}
                  />
                )}
              </>
            )}

            {/* Report Tab */}
            {activeTab === 'report' && (
              <>
                {isLoadingReport ? (
                  <div className="flex items-center justify-center py-12">
                    <LoadingSpinner size="md" />
                  </div>
                ) : report ? (
                  <ExecutionReportViewer jobId={job.job_id} report={report} />
                ) : (
                  <div className="text-center py-12">
                    <div className="text-gray-400 text-5xl mb-4">📊</div>
                    <h3 className="text-lg font-semibold text-gray-700">Report Not Available</h3>
                    <p className="text-sm text-gray-500 mt-2">
                      The execution report is not ready yet. Please check back later.
                    </p>
                  </div>
                )}
              </>
            )}

            {/* Regressions & Insights Tab */}
            {activeTab === 'regressions' && (
              <RegressionPanel jobId={job.job_id} />
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
