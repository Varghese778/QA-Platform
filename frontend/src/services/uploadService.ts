import axios from 'axios'
import { getToken } from './apiClient'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api/v1'

export interface UploadResponse {
  file_ids: string[]
  upload_errors: Array<{ file_name: string; error: string }>
}

export const uploadService = {
  /**
   * Upload files to the server
   */
  uploadFiles: async (files: File[]): Promise<UploadResponse> => {
    const formData = new FormData()
    files.forEach((file) => {
      formData.append('files', file)
    })

    const token = getToken()
    const headers: Record<string, string> = {}
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await axios.post<UploadResponse>(
      `${baseURL}/uploads`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...headers,
        },
        timeout: 60000, // 60 seconds for file upload
      }
    )

    return response.data
  },
}
