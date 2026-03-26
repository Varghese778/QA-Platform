import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useJob } from '../context/JobContext'
import { projectService } from '../services/projectService'
import { ProjectItem } from '../types/api'
import { formatShortDate, getStatusColor } from '../utils/format'
import { showToast } from '../components/Common/Toast'
import DashboardLayout from '../components/Layout/DashboardLayout'
import StorySubmissionForm from '../components/StorySubmission/StorySubmissionForm'
import LoadingSpinner from '../components/Common/LoadingSpinner'

export default function DashboardPage() {
  const { user } = useAuth()
  const { jobs, fetchJobs, jobsLoading, deleteJob } = useJob()
  const navigate = useNavigate()

  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [showSubmissionForm, setShowSubmissionForm] = useState(false)
  const [isLoadingProjects, setIsLoadingProjects] = useState(true)

  // Fetch projects on mount
  useEffect(() => {
    const loadProjects = async () => {
      try {
        const projectList = await projectService.listProjects()
        setProjects(projectList)
        if (projectList.length > 0) {
          setSelectedProjectId(projectList[0].project_id)
        }
      } catch (error: any) {
        console.error('Failed to load projects:', error)
        showToast(`Failed to load projects: ${error.message || error}`, 'error')
        // Still continue to show projects list even if there's an error
      } finally {
        setIsLoadingProjects(false)
      }
    }

    loadProjects()
  }, [])

  // Fetch jobs when project is selected
  useEffect(() => {
    if (selectedProjectId) {
      fetchJobs(selectedProjectId)
    }
  }, [selectedProjectId])

  const getStatusBadgeClasses = (status: string): string => {
    const color = getStatusColor(status)
    const colorMap = {
      success: 'bg-green-100 text-green-800',
      danger: 'bg-red-100 text-red-800',
      warning: 'bg-yellow-100 text-yellow-800',
      info: 'bg-blue-100 text-blue-800',
      gray: 'bg-gray-100 text-gray-800',
      primary: 'bg-blue-100 text-blue-800',
    }
    return colorMap[color]
  }

  const jobList = Array.from(jobs.values()).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )

  if (isLoadingProjects) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      </DashboardLayout>
    )
  }

  if (projects.length === 0) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <div className="text-gray-400 text-6xl mb-4">📁</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">No Projects Found</h2>
          <p className="text-gray-600">
            You don't have access to any projects. Contact your administrator.
          </p>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600 mt-1">Welcome back, {user?.name}!</p>
          </div>
          <button
            onClick={() => setShowSubmissionForm(!showSubmissionForm)}
            className="px-6 py-3 bg-primary text-white rounded-md hover:bg-blue-700 transition-colors font-medium"
          >
            {showSubmissionForm ? 'Hide Form' : '+ New Job'}
          </button>
        </div>

        {/* Project Selector */}
        <div className="bg-white shadow-md rounded-lg p-4">
          <label htmlFor="project-select" className="block text-sm font-medium text-gray-700 mb-2">
            Select Project
          </label>
          <select
            id="project-select"
            value={selectedProjectId || ''}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {projects.map((project) => (
              <option key={project.project_id} value={project.project_id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>

        {/* Story Submission Form */}
        {showSubmissionForm && selectedProjectId && (
          <div className="animate-fadeIn">
            <StorySubmissionForm
              projectId={selectedProjectId}
              onSuccessSubmit={(jobId) => {
                setShowSubmissionForm(false)
                navigate(`/jobs/${jobId}`)
              }}
            />
          </div>
        )}

        {/* Debug: Show if form should be visible but isn't rendering */}
        {showSubmissionForm && !selectedProjectId && (
          <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-4 text-yellow-800">
            ⚠️ Form hidden: No project selected
          </div>
        )}

        {/* Job List */}
        <div className="bg-white shadow-md rounded-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Recent Jobs</h2>

          {jobsLoading ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size="md" />
            </div>
          ) : jobList.length > 0 ? (
            <div className="space-y-3">
              {jobList.map((job) => (
                <div
                  key={job.job_id}
                  onClick={() => navigate(`/jobs/${job.job_id}`)}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer transition-colors group"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 mb-1">{job.story_title}</h3>
                      <p className="text-sm text-gray-600 line-clamp-2 mb-2">{job.user_story}</p>
                      <div className="flex flex-wrap gap-2 items-center text-xs text-gray-500">
                        <span>Created: {formatShortDate(job.created_at)}</span>
                        <span>•</span>
                        <span>Priority: {job.priority}</span>
                        <span>•</span>
                        <span>Env: {job.environment_target}</span>
                        {job.tags.length > 0 && (
                          <>
                            <span>•</span>
                            <span>Tags: {job.tags.slice(0, 3).join(', ')}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end space-y-2 ml-4">
                      <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getStatusBadgeClasses(job.status)}`}>
                        {job.status}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          if (window.confirm('Delete this job?')) {
                            deleteJob(job.job_id)
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 text-xs font-semibold px-2 py-1 border border-red-200 rounded transition-opacity"
                        title="Delete Job"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="text-gray-400 text-5xl mb-4">📋</div>
              <h3 className="text-lg font-semibold text-gray-700">No Jobs Yet</h3>
              <p className="text-sm text-gray-500 mt-2">
                Click the "New Job" button above to submit your first user story.
              </p>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
