import { useState } from 'react'
import { TestCase } from '../../types/api'
import { getStatusColor} from '../../utils/format'
import TestCaseCard from './TestCaseCard'

interface TestSuiteViewerProps {
  jobId: string
  testCases: TestCase[]
  onFilterChange?: (filter: string | null) => void
}

export default function TestSuiteViewer({ jobId, testCases, onFilterChange }: TestSuiteViewerProps) {
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [filterTag, setFilterTag] = useState<string | null>(null)
  const [expandedTests, setExpandedTests] = useState<Set<string>>(new Set())

  const filteredTests = testCases.filter((test) => {
    if (filterStatus && test.status !== filterStatus) return false
    if (filterTag && !test.tags.includes(filterTag)) return false
    return true
  })

  const allTags = Array.from(new Set(testCases.flatMap((test) => test.tags)))

  const toggleExpand = (testId: string) => {
    const newExpanded = new Set(expandedTests)
    if (newExpanded.has(testId)) {
      newExpanded.delete(testId)
    } else {
      newExpanded.add(testId)
    }
    setExpandedTests(newExpanded)
  }

  const handleFilterStatusChange = (status: string | null) => {
    setFilterStatus(status)
    if (onFilterChange) {
      onFilterChange(status)
    }
  }

  const getStatusCount = (status: string): number => {
    return testCases.filter((t) => t.status === status).length
  }

  return (
    <div className="bg-white shadow-md rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Test Suite</h2>
        <div className="text-sm text-gray-500">
          {filteredTests.length} of {testCases.length} tests
        </div>
      </div>

      {/* Status Filter */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => handleFilterStatusChange(null)}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            filterStatus === null
              ? 'bg-primary text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          All ({testCases.length})
        </button>
        <button
          onClick={() => handleFilterStatusChange('PASS')}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            filterStatus === 'PASS'
              ? 'bg-green-600 text-white'
              : 'bg-green-100 text-green-800 hover:bg-green-200'
          }`}
        >
          Passed ({getStatusCount('PASS')})
        </button>
        <button
          onClick={() => handleFilterStatusChange('FAIL')}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            filterStatus === 'FAIL'
              ? 'bg-red-600 text-white'
              : 'bg-red-100 text-red-800 hover:bg-red-200'
          }`}
        >
          Failed ({getStatusCount('FAIL')})
        </button>
        <button
          onClick={() => handleFilterStatusChange('SKIP')}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            filterStatus === 'SKIP'
              ? 'bg-gray-600 text-white'
              : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
          }`}
        >
          Skipped ({getStatusCount('SKIP')})
        </button>
        <button
          onClick={() => handleFilterStatusChange('PENDING')}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            filterStatus === 'PENDING'
              ? 'bg-yellow-600 text-white'
              : 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200'
          }`}
        >
          Pending ({getStatusCount('PENDING')})
        </button>
      </div>

      {/* Tag Filter */}
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm font-medium text-gray-700">Filter by tag:</span>
          <button
            onClick={() => setFilterTag(null)}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              filterTag === null
                ? 'bg-primary text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            All
          </button>
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setFilterTag(tag)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                filterTag === tag
                  ? 'bg-primary text-white'
                  : 'bg-blue-100 text-blue-800 hover:bg-blue-200'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* Test Cases */}
      <div className="space-y-3">
        {filteredTests.length > 0 ? (
          filteredTests.map((test) => (
            <TestCaseCard
              key={test.test_id}
              testCase={test}
              expanded={expandedTests.has(test.test_id)}
              onToggle={() => toggleExpand(test.test_id)}
            />
          ))
        ) : (
          <div className="text-center py-12">
            <div className="text-gray-400 text-5xl mb-4">📝</div>
            {testCases.length === 0 ? (
              <>
                <h3 className="text-lg font-semibold text-gray-700">No Tests Generated</h3>
                <p className="text-sm text-gray-500 mt-2">
                  The test generation pipeline has not produced any test cases yet.
                  <br />
                  Consider revising your user story for better results.
                </p>
              </>
            ) : (
              <>
                <h3 className="text-lg font-semibold text-gray-700">No Matching Tests</h3>
                <p className="text-sm text-gray-500 mt-2">
                  Try adjusting your filters to see more tests.
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
