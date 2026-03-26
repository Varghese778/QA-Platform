import { Stage } from '../../types/api'
import { formatShortDate, getStatusColor } from '../../utils/format'

interface StageCardProps {
  stage: Stage
}

export default function StageCard({ stage }: StageCardProps) {
  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'COMPLETE':
        return '✓'
      case 'FAILED':
        return '✕'
      case 'RUNNING':
        return '⟳'
      case 'PENDING':
        return '○'
      case 'SKIPPED':
        return '−'
      default:
        return '○'
    }
  }

  const getStatusBadgeClasses = (status: string): string => {
    const color = getStatusColor(status)
    const colorMap = {
      success: 'bg-green-100 text-green-800 border-green-200',
      danger: 'bg-red-100 text-red-800 border-red-200',
      warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      info: 'bg-blue-100 text-blue-800 border-blue-200',
      gray: 'bg-gray-100 text-gray-800 border-gray-200',
      primary: 'bg-blue-100 text-blue-800 border-blue-200',
    }
    return colorMap[color]
  }

  const isRunning = stage.status === 'RUNNING'

  return (
    <div className={`border rounded-lg p-4 ${getStatusBadgeClasses(stage.status)} border`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          <div className={`text-2xl ${isRunning ? 'animate-spin-slow' : ''}`}>
            {getStatusIcon(stage.status)}
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">{stage.name}</h4>
            <div className="mt-1 space-y-1 text-xs text-gray-600">
              {stage.started_at && (
                <div>
                  <span className="font-medium">Started:</span> {formatShortDate(stage.started_at)}
                </div>
              )}
              {stage.completed_at && (
                <div>
                  <span className="font-medium">Completed:</span> {formatShortDate(stage.completed_at)}
                </div>
              )}
              {stage.agent_id && (
                <div>
                  <span className="font-medium">Agent:</span> {stage.agent_id}
                </div>
              )}
            </div>
            {stage.log_snippet && (
              <div className="mt-2 p-2 bg-gray-50 rounded text-xs font-mono text-gray-700 overflow-x-auto">
                {stage.log_snippet}
              </div>
            )}
          </div>
        </div>
        <div>
          <span className={`px-2 py-1 rounded text-xs font-semibold ${getStatusBadgeClasses(stage.status)}`}>
            {stage.status}
          </span>
        </div>
      </div>
    </div>
  )
}
