import { ExecutionReport } from '../../types/api'
import { formatDuration } from '../../utils/format'
import { jobService } from '../../services/jobService'
import { showToast } from '../Common/Toast'
import ReportSummary from './ReportSummary'
import FailureDetails from './FailureDetails'

interface ExecutionReportViewerProps {
  jobId: string
  report: ExecutionReport
}

export default function ExecutionReportViewer({ jobId, report }: ExecutionReportViewerProps) {
  const handleExportPDF = async () => {
    try {
      await jobService.downloadExport(jobId, 'pdf')
      showToast('Report exported as PDF', 'success')
    } catch (error: any) {
      showToast(error.message || 'Failed to export PDF', 'error')
    }
  }

  const handleExportCSV = async () => {
    try {
      await jobService.downloadExport(jobId, 'csv')
      showToast('Report exported as CSV', 'success')
    } catch (error: any) {
      showToast(error.message || 'Failed to export CSV', 'error')
    }
  }

  return (
    <div className="bg-white shadow-md rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Execution Report</h2>
        <div className="flex gap-2">
          <button
            onClick={handleExportPDF}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm font-medium"
          >
            Export PDF
          </button>
          <button
            onClick={handleExportCSV}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm font-medium"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Summary */}
      <ReportSummary summary={report.summary} />

      {/* Failures */}
      {report.failures.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Failures ({report.failures.length})</h3>
          <FailureDetails failures={report.failures} />
        </div>
      )}

      {/* Metadata */}
      <div className="border-t border-gray-200 pt-4 text-sm text-gray-600">
        <div>
          <span className="font-medium">Report Generated:</span>{' '}
          {new Date(report.generated_at).toLocaleString()}
        </div>
        <div className="mt-1">
          <span className="font-medium">Execution Duration:</span>{' '}
          {formatDuration(report.summary.duration_ms)}
        </div>
      </div>
    </div>
  )
}
