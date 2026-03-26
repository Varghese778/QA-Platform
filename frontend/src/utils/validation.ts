export interface ValidationErrors {
  [field: string]: string
}

export function validateStoryTitle(title: string): string | null {
  if (!title || title.trim().length === 0) {
    return 'Story title is required'
  }
  if (title.length < 1) {
    return 'Story title must be at least 1 character'
  }
  if (title.length > 120) {
    return 'Story title must be at most 120 characters'
  }
  return null
}

export function validateUserStory(story: string): string | null {
  if (!story || story.trim().length === 0) {
    return 'User story is required'
  }
  if (story.length < 20) {
    return 'User story must be at least 20 characters'
  }
  if (story.length > 5000) {
    return 'User story must be at most 5000 characters'
  }
  return null
}

export function validateTags(tags: string[]): string | null {
  if (!Array.isArray(tags)) {
    return 'Tags must be an array'
  }
  if (tags.length > 10) {
    return 'Maximum 10 tags allowed'
  }
  for (const tag of tags) {
    if (typeof tag !== 'string') {
      return 'Each tag must be a string'
    }
    if (tag.length > 32) {
      return `Tag "${tag}" must be at most 32 characters`
    }
    if (tag.trim().length === 0) {
      return 'Tags cannot be empty'
    }
  }
  return null
}

export function validateFiles(files: File[]): string | null {
  if (!Array.isArray(files)) {
    return 'Files must be an array'
  }
  if (files.length > 5) {
    return 'Maximum 5 files allowed'
  }

  const allowedTypes = ['.pdf', '.md', '.txt', '.png', '.jpg', '.jpeg']
  const maxSizeBytes = 10 * 1024 * 1024 // 10MB

  for (const file of files) {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!allowedTypes.includes(ext)) {
      return `File type "${ext}" not allowed. Allowed types: ${allowedTypes.join(', ')}`
    }
    if (file.size > maxSizeBytes) {
      return `File "${file.name}" is too large. Maximum 10MB allowed`
    }
  }
  return null
}

export function validateStorySubmission(data: {
  story_title: string
  user_story: string
  tags: string[]
  context_files?: File[]
}): ValidationErrors {
  const errors: ValidationErrors = {}

  const titleError = validateStoryTitle(data.story_title)
  if (titleError) errors.story_title = titleError

  const storyError = validateUserStory(data.user_story)
  if (storyError) errors.user_story = storyError

  const tagsError = validateTags(data.tags)
  if (tagsError) errors.tags = tagsError

  if (data.context_files && data.context_files.length > 0) {
    const filesError = validateFiles(data.context_files)
    if (filesError) errors.context_files = filesError
  }

  return errors
}
