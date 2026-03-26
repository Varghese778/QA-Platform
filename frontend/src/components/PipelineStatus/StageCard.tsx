import { useState } from 'react'
import { Stage } from '../../types/api'
import { formatShortDate, getStatusColor } from '../../utils/format'

interface StageCardProps {
  stage: Stage
}

export default function StageCard({ stage }: StageCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

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
      success: 'bg-green-50 text-green-700 border-green-200',
      danger: 'bg-red-50 text-red-700 border-red-200',
      warning: 'bg-yellow-50 text-yellow-700 border-yellow-200',
      info: 'bg-blue-50 text-blue-700 border-blue-200',
      gray: 'bg-gray-50 text-gray-700 border-gray-200',
      primary: 'bg-blue-50 text-blue-700 border-blue-200',
    }
    return colorMap[color] || colorMap.gray
  }

  const isRunning = stage.status === 'RUNNING'
  const hasDetails = stage.details && stage.details.length > 0

  return (
    <div className={`border rounded-xl transition-all duration-200 ${getStatusBadgeClasses(stage.status)} overflow-hidden`}>
      <div 
        className={`p-4 flex items-start justify-between ${hasDetails ? 'cursor-pointer hover:bg-opacity-80' : ''}`}
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-start gap-4 flex-1">
          <div className={`text-2xl flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full bg-white bg-opacity-50 shadow-sm ${isRunning ? 'animate-spin-slow' : ''}`}>
            {getStatusIcon(stage.status)}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h4 className="font-bold text-gray-900 tracking-tight">{stage.name}</h4>
              {hasDetails && (
                <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 bg-gray-900 bg-opacity-10 rounded text-gray-700">
                  {stage.details?.length} Items
                </span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-gray-600 font-medium">
              {stage.started_at && (
                <div>
                  <span className="opacity-60">Started:</span> {formatShortDate(stage.started_at)}
                </div>
              )}
              {stage.completed_at && (
                <div>
                  <span className="opacity-60">Completed:</span> {formatShortDate(stage.completed_at)}
                </div>
              )}
            </div>
            
            {/* Minimal snippet if not expanded */}
            {stage.log_snippet && !isExpanded && (
              <div className="mt-2 text-xs font-mono text-gray-700 opacity-80 truncate">
                {stage.log_snippet}
              </div>
            )}
          </div>
        </div>
        
        <div className="flex flex-col items-end gap-2">
          <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider shadow-sm border ${getStatusBadgeClasses(stage.status)} bg-white bg-opacity-50`}>
            {stage.status}
          </span>
          {hasDetails && (
            <div className="text-gray-400 mt-1">
              {isExpanded ? '▲' : '▼'}
            </div>
          )}
        </div>
      </div>

      {hasDetails && isExpanded && (
        <div className="px-4 pb-4 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="bg-white bg-opacity-40 rounded-lg p-3 border border-gray-200 border-opacity-50">
            {stage.log_snippet && (
              <div className="mb-3 text-xs font-mono text-gray-800 border-b border-gray-200 border-opacity-30 pb-2">
                {stage.log_snippet}
              </div>
            )}
            <div className="space-y-1.5">
              {stage.details?.map((detail, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs text-gray-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 opacity-60"></span>
                  {detail}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
