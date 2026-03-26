export type JobPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL'
export type JobStatus = 'QUEUED' | 'PROCESSING' | 'COMPLETE' | 'FAILED' | 'CANCELLED'
export type StageStatus = 'PENDING' | 'RUNNING' | 'COMPLETE' | 'FAILED' | 'SKIPPED'
export type TestStatus = 'PASS' | 'FAIL' | 'SKIP' | 'PENDING'
export type EnvironmentTarget = 'DEVELOPMENT' | 'STAGING' | 'PRODUCTION'

export interface User {
  id: string
  email: string
  name: string
  roles: Record<string, string>
}

export interface Stage {
  stage_id: string
  name: string
  status: StageStatus
  started_at?: string
  completed_at?: string
  agent_id?: string
  log_snippet?: string
}

export interface JobRecord {
  job_id: string
  story_title: string
  user_story: string
  project_id: string
  priority: JobPriority
  tags: string[]
  status: JobStatus
  stages: Stage[]
  created_at: string
  updated_at: string
  report_ready: boolean
  environment_target: EnvironmentTarget
}

export interface TestStep {
  step_number: number
  action: string
  expected_result: string
}

export interface TestCase {
  test_id: string
  title: string
  preconditions: string[]
  steps: TestStep[]
  expected_result: string
  tags: string[]
  status: TestStatus
  failure_reason?: string
  screenshot?: string // Base64 screenshot
  execution_time?: number // ms
  error_trace?: string
}

export interface ReportSummary {
  total_tests: number
  passed: number
  failed: number
  skipped: number
  duration_ms: number
  coverage_percent: number
}

export interface Failure {
  test_id: string
  test_name: string
  error_type: string
  error_message: string
  stack_trace?: string
}

export interface ExecutionReport {
  job_id: string
  summary: ReportSummary
  failures: Failure[]
  generated_at: string
}

export interface JobSubmitRequest {
  story_title: string
  user_story: string
  project_id: string
  priority: JobPriority
  tags: string[]
  environment_target: EnvironmentTarget
}

export interface JobSubmitResponse {
  job_id: string
  queued_at: string
  estimated_completion_seconds?: number
}

export interface JobListResponse {
  jobs: JobRecord[]
  total: number
  page: number
  page_size: number
}

export interface JobTestsResponse {
  tests: TestCase[]
  total: number
  page: number
  page_size: number
}

export interface ProjectItem {
  project_id: string
  name: string
  description?: string
}

export interface ProjectListResponse {
  projects: ProjectItem[]
}

export interface StatusUpdate {
  message_type: 'status_update' | 'error' | 'heartbeat' | 'connected'
  payload: Record<string, any>
  timestamp: string
}

export interface ApiErrorResponse {
  error_code: string
  message: string
  details?: Array<{ field: string; message: string }>
  request_id: string
  timestamp: string
}
