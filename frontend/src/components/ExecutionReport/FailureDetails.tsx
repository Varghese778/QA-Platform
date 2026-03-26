import { Failure } from '../../types/api'
import { useState } from 'react'

interface FailureDetailsProps {
  failures: Failure[]
}

export default function FailureDetails({ failures }: FailureDetailsProps) {
  const [expandedFailures, setExpandedFailures] = useState<Set<string>>(new Set())

  const toggleExpand = (testId: string) => {
    const newExpanded = new Set(expandedFailures)
    if (newExpanded.has(testId)) {
      newExpanded.delete(testId)
    } else {
      newExpanded.add(testId)
    }
    setExpandedFailures(newExpanded)
  }

  return (
    <div className="space-y-3">
      {failures.map((failure) => {
        const isExpanded = expandedFailures.has(failure.test_id)

        return (
          <div key={failure.test_id} className="border border-red-200 rounded-lg overflow-hidden bg-red-50">
            {/* Header */}
            <div
              className="flex items-center justify-between p-4 cursor-pointer hover:bg-red-100 transition-colors"
              onClick={() => toggleExpand(failure.test_id)}
            >
              <div className="flex-1">
                <h4 className="font-semibold text-red-900">{failure.test_name}</h4>
                <div className="text-sm text-red-700 mt-1">
                  <span className="font-medium">Error Type:</span> {failure.error_type}
                </div>
              </div>
              <span className="text-red-400 text-xl">{isExpanded ? '▲' : '▼'}</span>
            </div>

            {/* Details (collapsible) */}
            {isExpanded && (
              <div className="px-4 pb-4 border-t border-red-200 space-y-3">
                {/* Error Message */}
                <div>
                  <h5 className="font-semibold text-red-800 mb-2">Error Message:</h5>
                  <div className="p-3 bg-white rounded border border-red-200">
                    <pre className="text-sm text-red-900 whitespace-pre-wrap font-mono">
                      {failure.error_message}
                    </pre>
                  </div>
                </div>

                {/* Stack Trace */}
                {failure.stack_trace && (
                  <div>
                    <h5 className="font-semibold text-red-800 mb-2">Stack Trace:</h5>
                    <div className="p-3 bg-white rounded border border-red-200 overflow-x-auto">
                      <pre className="text-xs text-gray-700 font-mono">
                        {failure.stack_trace}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
