import { useEffect, useState } from 'react'
import { JobRecord, Stage, StatusUpdate } from '../../types/api'
import { useWebSocket } from '../../context/WebSocketContext'
import { useJob } from '../../context/JobContext'
import { formatShortDate, formatDuration, getStatusColor } from '../../utils/format'
import StageCard from './StageCard'

interface PipelineStatusPanelProps {
  jobId: string
  jobRecord: JobRecord
}

export default function PipelineStatusPanel({ jobId, jobRecord }: PipelineStatusPanelProps) {
  const { subscribe } = useWebSocket()
  const { updateJobInCache } = useJob()
  const [timeoutWarning, setTimeoutWarning] = useState(false)

  useEffect(() => {
    // Subscribe to WebSocket updates for this job
    const unsubscribe = subscribe(jobId, (message: StatusUpdate) => {
      if (message.message_type === 'status_update') {
        const payload = message.payload

        // Update job in cache
        if (payload.status) {
          updateJobInCache(jobId, {
            status: payload.status,
            stages: payload.stages || jobRecord.stages,
          })
        }
      }
    })

    return () => {
      unsubscribe()
    }
  }, [jobId, subscribe, updateJobInCache])

  useEffect(() => {
    // Check for timeout warning (job stuck > 15 minutes)
    if (jobRecord.status === 'PROCESSING') {
      const createdAt = new Date(jobRecord.created_at).getTime()
      const now = Date.now()
      const elapsedMs = now - createdAt

      if (elapsedMs > 15 * 60 * 1000) {
        setTimeoutWarning(true)
      }
    } else {
      setTimeoutWarning(false)
    }
  }, [jobRecord.status, jobRecord.created_at])

  const getStatusBadgeClasses = (status: string): string => {
    const color = getStatusColor(status)
    const colorMap = {
      success: 'bg-green-100 text-green-800 border-green-300',
      danger: 'bg-red-100 text-red-800 border-red-300',
      warning: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      info: 'bg-blue-100 text-blue-800 border-blue-300',
      gray: 'bg-gray-100 text-gray-800 border-gray-300',
      primary: 'bg-blue-100 text-blue-800 border-blue-300',
    }
    return colorMap[color]
  }

  const getProgressPercentage = (): number => {
    const totalStages = jobRecord.stages.length
    if (totalStages === 0) return 0

    const completedStages = jobRecord.stages.filter(
      (s) => s.status === 'COMPLETE' || s.status === 'FAILED' || s.status === 'SKIPPED'
    ).length

    return Math.round((completedStages / totalStages) * 100)
  }

  return (
    <div className="bg-white shadow-md rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Pipeline Status</h2>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${getStatusBadgeClasses(jobRecord.status)}`}>
            {jobRecord.status}
          </span>
        </div>
      </div>

      {/* Timeout Warning */}
      {timeoutWarning && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded">
          <div className="flex items-center">
            <span className="text-yellow-600 text-xl mr-3">⚠</span>
            <div>
              <p className="font-semibold text-yellow-800">Job Timeout Warning</p>
              <p className="text-sm text-yellow-700">
                This job has been processing for over 15 minutes. Consider canceling and contacting support.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-gray-700">Overall Progress</span>
          <span className="text-sm font-medium text-gray-700">{getProgressPercentage()}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="bg-primary h-3 rounded-full transition-all duration-500"
            style={{ width: `${getProgressPercentage()}%` }}
          ></div>
        </div>
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4 text-sm border-t border-gray-200 pt-4">
        <div>
          <span className="text-gray-500">Created:</span>
          <span className="ml-2 font-medium">{formatShortDate(jobRecord.created_at)}</span>
        </div>
        <div>
          <span className="text-gray-500">Last Updated:</span>
          <span className="ml-2 font-medium">{formatShortDate(jobRecord.updated_at)}</span>
        </div>
        <div>
          <span className="text-gray-500">Priority:</span>
          <span className="ml-2 font-medium">{jobRecord.priority}</span>
        </div>
        <div>
          <span className="text-gray-500">Environment:</span>
          <span className="ml-2 font-medium">{jobRecord.environment_target}</span>
        </div>
      </div>

      {/* Stages */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">Pipeline Stages</h3>
        {jobRecord.stages.length > 0 ? (
          jobRecord.stages.map((stage) => <StageCard key={stage.stage_id} stage={stage} />)
        ) : (
          <p className="text-gray-500 text-sm">No stages available yet.</p>
        )}
      </div>
    </div>
  )
}
