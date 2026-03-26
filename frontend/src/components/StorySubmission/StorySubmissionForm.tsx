import { useState, FormEvent, ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useJob } from '../../context/JobContext'
import { JobSubmitRequest, JobPriority, EnvironmentTarget } from '../../types/api'
import { validateStorySubmission, ValidationErrors } from '../../utils/validation'
import { showToast } from '../Common/Toast'
import LoadingSpinner from '../Common/LoadingSpinner'

interface StorySubmissionFormProps {
  projectId: string
  onSuccessSubmit?: (jobId: string) => void
}

export default function StorySubmissionForm({ projectId, onSuccessSubmit }: StorySubmissionFormProps) {
  const { submitJob } = useJob()
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    story_title: '',
    user_story: '',
    priority: 'NORMAL' as JobPriority,
    tags: [] as string[],
    environment_target: 'STAGING' as EnvironmentTarget,
  })
  const [tagInput, setTagInput] = useState('')
  const [errors, setErrors] = useState<ValidationErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    // Clear error for this field
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }))
    }
  }

  const handleAddTag = () => {
    const trimmedTag = tagInput.trim()
    if (trimmedTag && !formData.tags.includes(trimmedTag)) {
      if (formData.tags.length < 10) {
        setFormData((prev) => ({ ...prev, tags: [...prev.tags, trimmedTag] }))
        setTagInput('')
        if (errors.tags) {
          setErrors((prev) => ({ ...prev, tags: '' }))
        }
      } else {
        showToast('Maximum 10 tags allowed', 'warning')
      }
    }
  }

  const handleRemoveTag = (tagToRemove: string) => {
    setFormData((prev) => ({
      ...prev,
      tags: prev.tags.filter((tag) => tag !== tagToRemove),
    }))
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    // Validate
    const validationErrors = validateStorySubmission(formData)
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      showToast('Please fix validation errors', 'error')
      return
    }

    setIsSubmitting(true)

    try {
      const payload: JobSubmitRequest = {
        ...formData,
        project_id: projectId,
      }

      const jobId = await submitJob(payload)
      showToast('Job submitted successfully!', 'success')

      // Reset form
      setFormData({
        story_title: '',
        user_story: '',
        priority: 'NORMAL',
        tags: [],
        environment_target: 'STAGING',
      })

      if (onSuccessSubmit) {
        onSuccessSubmit(jobId)
      } else {
        // Navigate to job detail page
        navigate(`/jobs/${jobId}`)
      }
    } catch (error: any) {
      showToast(error.message || 'Failed to submit job', 'error')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white shadow-md rounded-lg p-6 space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Submit User Story</h2>

      {/* Story Title */}
      <div>
        <label htmlFor="story_title" className="block text-sm font-medium text-gray-700 mb-1">
          Story Title <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="story_title"
          name="story_title"
          value={formData.story_title}
          onChange={handleChange}
          className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary ${
            errors.story_title ? 'border-red-500' : 'border-gray-300'
          }`}
          placeholder="Enter a descriptive title (max 120 characters)"
          maxLength={120}
        />
        {errors.story_title && <p className="mt-1 text-sm text-red-600">{errors.story_title}</p>}
        <p className="mt-1 text-xs text-gray-500">{formData.story_title.length}/120 characters</p>
      </div>

      {/* User Story */}
      <div>
        <label htmlFor="user_story" className="block text-sm font-medium text-gray-700 mb-1">
          User Story <span className="text-red-500">*</span>
        </label>
        <textarea
          id="user_story"
          name="user_story"
          value={formData.user_story}
          onChange={handleChange}
          rows={8}
          className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary ${
            errors.user_story ? 'border-red-500' : 'border-gray-300'
          }`}
          placeholder="As a [user], I want to [action] so that [benefit]..."
          maxLength={5000}
        />
        {errors.user_story && <p className="mt-1 text-sm text-red-600">{errors.user_story}</p>}
        <p className="mt-1 text-xs text-gray-500">{formData.user_story.length}/5000 characters</p>
      </div>

      {/* Priority and Environment in a row */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="priority" className="block text-sm font-medium text-gray-700 mb-1">
            Priority
          </label>
          <select
            id="priority"
            name="priority"
            value={formData.priority}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="LOW">Low</option>
            <option value="NORMAL">Normal</option>
            <option value="HIGH">High</option>
            <option value="CRITICAL">Critical</option>
          </select>
        </div>

        <div>
          <label htmlFor="environment_target" className="block text-sm font-medium text-gray-700 mb-1">
            Environment
          </label>
          <select
            id="environment_target"
            name="environment_target"
            value={formData.environment_target}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="DEVELOPMENT">Development</option>
            <option value="STAGING">Staging</option>
            <option value="PRODUCTION">Production</option>
          </select>
        </div>
      </div>

      {/* Tags */}
      <div>
        <label htmlFor="tags" className="block text-sm font-medium text-gray-700 mb-1">
          Tags (max 10)
        </label>
        <div className="flex gap-2 mb-2">
          <input
            type="text"
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleAddTag()
              }
            }}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="Enter tag and press Enter"
            maxLength={32}
          />
          <button
            type="button"
            onClick={handleAddTag}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
          >
            Add
          </button>
        </div>
        {formData.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {formData.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => handleRemoveTag(tag)}
                  className="text-blue-600 hover:text-blue-800 font-bold"
                  aria-label={`Remove ${tag}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        {errors.tags && <p className="mt-1 text-sm text-red-600">{errors.tags}</p>}
      </div>

      {/* Submit Button */}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-6 py-3 bg-primary text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {isSubmitting ? (
            <>
              <LoadingSpinner size="sm" />
              Submitting...
            </>
          ) : (
            'Submit Job'
          )}
        </button>
      </div>
    </form>
  )
}
