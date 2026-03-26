import { TestCase } from '../../types/api'
import { getStatusColor } from '../../utils/format'

interface TestCaseCardProps {
  testCase: TestCase
  expanded: boolean
  onToggle: () => void
}

export default function TestCaseCard({ testCase, expanded, onToggle }: TestCaseCardProps) {
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

  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'PASS':
        return '✓'
      case 'FAIL':
        return '✕'
      case 'SKIP':
        return '−'
      case 'PENDING':
        return '○'
      default:
        return '?'
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3 flex-1">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-lg font-bold ${getStatusBadgeClasses(testCase.status)}`}>
            {getStatusIcon(testCase.status)}
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">{testCase.title}</h4>
            {testCase.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {testCase.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {testCase.execution_time && (
            <span className="text-xs text-gray-500 font-mono">
              {testCase.execution_time}ms
            </span>
          )}
          <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${getStatusBadgeClasses(testCase.status)}`}>
            {testCase.status}
          </span>
          <span className="text-gray-400 text-xl">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Details (collapsible) */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-200 bg-gray-50 space-y-4">
          {/* Preconditions */}
          {testCase.preconditions.length > 0 && (
            <div>
              <h5 className="font-semibold text-gray-700 mb-2">Preconditions:</h5>
              <ul className="list-disc list-inside space-y-1 text-sm text-gray-600">
                {testCase.preconditions.map((precondition, idx) => (
                  <li key={idx}>{precondition}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Steps */}
          <div>
            <h5 className="font-semibold text-gray-700 mb-2">Steps:</h5>
            <ol className="space-y-2">
              {testCase.steps.map((step) => (
                <li key={step.step_number} className="flex gap-2 text-sm">
                  <span className="font-semibold text-gray-500 min-w-[2rem]">
                    {step.step_number}.
                  </span>
                  <div className="flex-1">
                    <div className="text-gray-900">{step.action}</div>
                    <div className="text-gray-600 italic mt-1">
                      Expected: {step.expected_result}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          {/* Expected Result */}
          <div>
            <h5 className="font-semibold text-gray-700 mb-2">Final Expected Result:</h5>
            <p className="text-sm text-gray-600">{testCase.expected_result}</p>
          </div>

          {/* Failure Reason (if failed) */}
          {(testCase.status === 'FAIL' || testCase.error_trace) && (
            <div className="bg-red-50 border-l-4 border-red-400 p-3 rounded">
              <h5 className="font-semibold text-red-800 mb-1">Execution Error:</h5>
              <p className="text-sm text-red-700 font-mono whitespace-pre-wrap">
                {testCase.error_trace || testCase.failure_reason}
              </p>
            </div>
          )}

          {/* Screenshot Evidence */}
          {testCase.screenshot && (
            <div className="mt-4">
              <h5 className="font-semibold text-gray-700 mb-2">Execution Evidence:</h5>
              <div className="border border-gray-300 rounded-lg overflow-hidden bg-white">
                <img 
                  src={`data:image/png;base64,${testCase.screenshot}`} 
                  alt="Test Execution Screenshot" 
                  className="w-full h-auto max-h-[500px] object-contain cursor-zoom-in"
                  onClick={(e) => {
                    const img = e.currentTarget;
                    if (img.style.maxHeight === 'none') {
                      img.style.maxHeight = '500px';
                    } else {
                      img.style.maxHeight = 'none';
                    }
                  }}
                />
              </div>
              <p className="text-[10px] text-gray-400 mt-1 uppercase tracking-widest text-center">
                Real-time Playwright Capture
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
