import { ReportSummary as ReportSummaryType } from '../../types/api'

interface ReportSummaryProps {
  summary: ReportSummaryType
}

export default function ReportSummary({ summary }: ReportSummaryProps) {
  const passRate = summary.total_tests > 0
    ? Math.round((summary.passed / summary.total_tests) * 100)
    : 0

  const getStatusColor = (value: number, total: number): string => {
    const rate = (value / total) * 100
    if (rate === 100) return 'text-green-600'
    if (rate >= 80) return 'text-blue-600'
    if (rate >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {/* Total Tests */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div className="text-sm text-gray-500 mb-1">Total Tests</div>
        <div className="text-3xl font-bold text-gray-900">{summary.total_tests}</div>
      </div>

      {/* Passed */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <div className="text-sm text-green-700 mb-1">Passed</div>
        <div className="text-3xl font-bold text-green-600">{summary.passed}</div>
        <div className="text-xs text-green-600 mt-1">
          {summary.total_tests > 0
            ? Math.round((summary.passed / summary.total_tests) * 100)
            : 0}%
        </div>
      </div>

      {/* Failed */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="text-sm text-red-700 mb-1">Failed</div>
        <div className="text-3xl font-bold text-red-600">{summary.failed}</div>
        <div className="text-xs text-red-600 mt-1">
          {summary.total_tests > 0
            ? Math.round((summary.failed / summary.total_tests) * 100)
            : 0}%
        </div>
      </div>

      {/* Skipped */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div className="text-sm text-gray-500 mb-1">Skipped</div>
        <div className="text-3xl font-bold text-gray-600">{summary.skipped}</div>
        <div className="text-xs text-gray-600 mt-1">
          {summary.total_tests > 0
            ? Math.round((summary.skipped / summary.total_tests) * 100)
            : 0}%
        </div>
      </div>

      {/* Pass Rate Bar */}
      <div className="col-span-2 md:col-span-4 bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-gray-700">Pass Rate</span>
          <span className={`text-2xl font-bold ${getStatusColor(summary.passed, summary.total_tests)}`}>
            {passRate}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
          <div className="flex h-full">
            <div
              className="bg-green-500"
              style={{ width: `${(summary.passed / summary.total_tests) * 100}%` }}
            ></div>
            <div
              className="bg-red-500"
              style={{ width: `${(summary.failed / summary.total_tests) * 100}%` }}
            ></div>
            <div
              className="bg-gray-400"
              style={{ width: `${(summary.skipped / summary.total_tests) * 100}%` }}
            ></div>
          </div>
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>Passed: {summary.passed}</span>
          <span>Failed: {summary.failed}</span>
          <span>Skipped: {summary.skipped}</span>
        </div>
      </div>

      {/* Coverage */}
      <div className="col-span-2 md:col-span-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-blue-700">Test Coverage</span>
          <span className="text-2xl font-bold text-blue-600">{summary.coverage_percent}%</span>
        </div>
        <div className="w-full bg-blue-200 rounded-full h-3">
          <div
            className="bg-blue-600 h-3 rounded-full"
            style={{ width: `${summary.coverage_percent}%` }}
          ></div>
        </div>
      </div>
    </div>
  )
}
