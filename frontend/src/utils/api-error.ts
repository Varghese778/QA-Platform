import { AxiosError } from 'axios'
import { ApiErrorResponse } from '../types/api'

export class ApiError extends Error {
  public code: string
  public details?: Array<{ field: string; message: string }>
  public requestId: string
  public timestamp: string

  constructor(
    code: string,
    message: string,
    requestId = 'unknown',
    timestamp = new Date().toISOString(),
    details?: Array<{ field: string; message: string }>
  ) {
    super(message)
    this.code = code
    this.requestId = requestId
    this.timestamp = timestamp
    this.details = details
    this.name = 'ApiError'
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function parseApiError(error: unknown): ApiError {
  if (isApiError(error)) {
    return error
  }

  const axiosError = error as AxiosError<ApiErrorResponse>

  if (axiosError.response?.data) {
    const data = axiosError.response.data
    return new ApiError(
      data.error_code || 'UNKNOWN_ERROR',
      data.message || 'An error occurred',
      data.request_id || 'unknown',
      data.timestamp || new Date().toISOString(),
      data.details
    )
  }

  if (axiosError.message === 'Network Error') {
    return new ApiError(
      'NETWORK_ERROR',
      'Failed to connect to the server. Please check your connection.'
    )
  }

  if (axiosError.code === 'ECONNABORTED') {
    return new ApiError(
      'REQUEST_TIMEOUT',
      'Request timed out. Please try again.'
    )
  }

  return new ApiError(
    'UNKNOWN_ERROR',
    error instanceof Error ? error.message : 'An unknown error occurred'
  )
}

export function getErrorMessage(error: unknown): string {
  const apiError = parseApiError(error)
  return apiError.message
}

export function getFieldErrors(error: unknown): Record<string, string> {
  const apiError = parseApiError(error)
  if (!apiError.details) return {}

  return apiError.details.reduce(
    (acc, detail) => {
      acc[detail.field] = detail.message
      return acc
    },
    {} as Record<string, string>
  )
}
