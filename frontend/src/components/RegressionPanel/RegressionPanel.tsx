import { useState, useEffect } from 'react'
import { apiClient } from '../../services/apiClient'
import LoadingSpinner from '../Common/LoadingSpinner'

interface RegressionItem {
  test_name: string
  test_id: string
  previous_status: string
  current_status: string
  severity: string
  first_seen: string
  regression_type: string
  details: string
  recommended_action: string
  affected_component: string
  history: Array<{ sprint: string; status: string }>
}

interface Improvement {
  test_name: string
  previous_status: string
  current_status: string
  details: string
}

interface LearningSource {
  source_type: string
  source_id: string
  description: string
  influence: string
  confidence: number
  sprint: string
}

interface RegressionPanelProps {
  jobId: string
}

export default function RegressionPanel({ jobId }: RegressionPanelProps) {
  const [regressionData, setRegressionData] = useState<any>(null)
  const [insightsData, setInsightsData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [activeSection, setActiveSection] = useState<'regressions' | 'insights'>('regressions')

  useEffect(() => {
    loadData()
  }, [jobId])

  const loadData = async () => {
    try {
      const [regRes, insRes] = await Promise.all([
        apiClient.get(`/demo/jobs/${jobId}/regressions`),
        apiClient.get(`/demo/jobs/${jobId}/insights`),
      ])
      setRegressionData(regRes.data)
      setInsightsData(insRes.data)
    } catch (error) {
      console.error('Failed to load regression/insights data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  if (!regressionData || !insightsData) {
    return (
      <div className="text-center py-12">
        <div className="text-gray-400 text-5xl mb-4">📊</div>
        <h3 className="text-lg font-semibold text-gray-700">Analysis Not Available</h3>
      </div>
    )
  }

  const summary = regressionData.analysis_summary
  const healthColor = summary.overall_health === 'WARNING'
    ? 'bg-yellow-100 text-yellow-800'
    : summary.overall_health === 'CRITICAL'
    ? 'bg-red-100 text-red-800'
    : 'bg-green-100 text-green-800'

  const severityColor = (s: string) => {
    const map: Record<string, string> = {
      HIGH: 'bg-red-100 text-red-800',
      MEDIUM: 'bg-yellow-100 text-yellow-800',
      LOW: 'bg-blue-100 text-blue-800',
    }
    return map[s] || 'bg-gray-100 text-gray-800'
  }

  const sourceIcon = (type: string) => {
    const map: Record<string, string> = {
      PAST_DEFECT: '🐛',
      HISTORICAL_TEST_RESULT: '📋',
      REGRESSION_PATTERN: '📉',
      KNOWLEDGE_GRAPH: '🧠',
      COVERAGE_GAP: '🔍',
    }
    return map[type] || '📌'
  }

  return (
    <div className="space-y-6">
      {/* Section Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveSection('regressions')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeSection === 'regressions'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          📉 Regression Analysis
        </button>
        <button
          onClick={() => setActiveSection('insights')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            activeSection === 'insights'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          🧠 AI Learning Insights
        </button>
      </div>

      {activeSection === 'regressions' && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-gray-900">{summary.total_tests_compared}</div>
              <div className="text-xs text-gray-500">Tests Compared</div>
            </div>
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-600">{summary.regressions_detected}</div>
              <div className="text-xs text-gray-500">Regressions</div>
            </div>
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-600">{summary.improvements_detected}</div>
              <div className="text-xs text-gray-500">Improvements</div>
            </div>
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-gray-600">{summary.stable_tests}</div>
              <div className="text-xs text-gray-500">Stable</div>
            </div>
            <div className="bg-white border rounded-lg p-3 text-center">
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${healthColor}`}>
                {summary.overall_health}
              </span>
              <div className="text-xs text-gray-500 mt-1">Health</div>
            </div>
          </div>

          {/* Sprint Trend */}
          <div className="bg-white border rounded-lg p-4">
            <h3 className="font-semibold text-gray-900 mb-3">📊 Sprint Trend ({summary.baseline_sprint} → {summary.current_sprint})</h3>
            <div className="grid grid-cols-4 gap-2">
              {Object.entries(regressionData.trend).map(([sprint, data]: [string, any]) => (
                <div key={sprint} className="text-center">
                  <div className="text-xs font-medium text-gray-500 mb-1">{sprint}</div>
                  <div className="bg-gray-50 rounded-lg p-2">
                    <div className="flex justify-center gap-1 text-xs">
                      <span className="text-green-600 font-bold">{data.passed}✓</span>
                      <span className="text-red-600 font-bold">{data.failed}✗</span>
                    </div>
                    <div className="mt-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500 rounded-full"
                        style={{ width: `${(data.passed / data.total) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Regressions */}
          {regressionData.regressions.length > 0 && (
            <div>
              <h3 className="font-semibold text-red-700 mb-3">🔴 Regressions Detected</h3>
              <div className="space-y-3">
                {regressionData.regressions.map((reg: RegressionItem) => (
                  <div key={reg.test_id} className="border-l-4 border-red-500 bg-red-50 rounded-r-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-gray-900">{reg.test_name}</span>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityColor(reg.severity)}`}>
                            {reg.severity}
                          </span>
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                            {reg.regression_type}
                          </span>
                        </div>
                        <p className="text-sm text-gray-700 mt-1">{reg.details}</p>
                        <div className="mt-2 flex items-center gap-1 text-xs">
                          <span className="text-green-600 font-bold">PASS</span>
                          <span>→</span>
                          <span className="text-red-600 font-bold">FAIL</span>
                          <span className="text-gray-400 ml-2">| Component: {reg.affected_component}</span>
                        </div>
                        <div className="mt-2 bg-white rounded px-3 py-2 text-xs text-gray-600">
                          <strong>Recommended:</strong> {reg.recommended_action}
                        </div>
                      </div>
                    </div>
                    {/* History */}
                    <div className="mt-3 flex gap-1">
                      {reg.history.map((h, i) => (
                        <div key={i} className="text-center">
                          <div className="text-[10px] text-gray-400">{h.sprint.replace('Sprint ', 'S')}</div>
                          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                            h.status === 'PASS' ? 'bg-green-100 text-green-700'
                            : h.status === 'FAIL' ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-400'
                          }`}>
                            {h.status === 'PASS' ? '✓' : h.status === 'FAIL' ? '✗' : '–'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Improvements */}
          {regressionData.improvements.length > 0 && (
            <div>
              <h3 className="font-semibold text-green-700 mb-3">🟢 Improvements</h3>
              <div className="space-y-2">
                {regressionData.improvements.map((imp: Improvement, i: number) => (
                  <div key={i} className="border-l-4 border-green-500 bg-green-50 rounded-r-lg p-3">
                    <div className="font-medium text-gray-900 text-sm">{imp.test_name}</div>
                    <div className="text-xs text-gray-600 mt-1">{imp.details}</div>
                    <div className="flex items-center gap-1 text-xs mt-1">
                      <span className="text-red-600 font-bold">FAIL</span>
                      <span>→</span>
                      <span className="text-green-600 font-bold">PASS</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {activeSection === 'insights' && (
        <>
          {/* Learning Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-blue-600">{insightsData.learning_summary.historical_runs_analyzed}</div>
              <div className="text-xs text-gray-500">Runs Analyzed</div>
            </div>
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-orange-600">{insightsData.learning_summary.defects_consulted}</div>
              <div className="text-xs text-gray-500">Defects Consulted</div>
            </div>
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-purple-600">{insightsData.learning_summary.knowledge_base_queries}</div>
              <div className="text-xs text-gray-500">KB Queries</div>
            </div>
            <div className="bg-white border rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-600">{(insightsData.learning_summary.context_relevance_score * 100).toFixed(0)}%</div>
              <div className="text-xs text-gray-500">Relevance Score</div>
            </div>
          </div>

          {/* AI Agent Notes */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <span className="text-2xl">🤖</span>
              <div>
                <h4 className="font-semibold text-blue-900 mb-1">AI Agent Analysis</h4>
                <p className="text-sm text-blue-800">{insightsData.ai_agent_notes}</p>
              </div>
            </div>
          </div>

          {/* Learning Sources */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-3">📚 Knowledge Sources Used</h3>
            <div className="space-y-2">
              {insightsData.learning_sources.map((source: LearningSource, i: number) => (
                <div key={i} className="bg-white border rounded-lg p-4 hover:shadow-sm transition-shadow">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">{sourceIcon(source.source_type)}</span>
                        <span className="font-mono text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                          {source.source_id}
                        </span>
                        <span className="text-xs text-gray-400">{source.sprint}</span>
                      </div>
                      <p className="text-sm font-medium text-gray-900">{source.description}</p>
                      <p className="text-xs text-gray-600 mt-1">
                        <strong>Influence:</strong> {source.influence}
                      </p>
                    </div>
                    <div className="ml-4 text-right">
                      <div className="text-sm font-bold text-green-600">{(source.confidence * 100).toFixed(0)}%</div>
                      <div className="text-[10px] text-gray-400">confidence</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
