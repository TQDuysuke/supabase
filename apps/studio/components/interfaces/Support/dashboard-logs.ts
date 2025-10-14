import * as Sentry from '@sentry/nextjs'

import { SupportCategories } from '@supabase/shared-types/out/constants'
import { getBreadcrumbSnapshot, getMirroredBreadcrumbs } from 'lib/breadcrumbs'
import { uuidv4 } from 'lib/helpers'
import { sanitizeArrayOfObjects } from 'lib/sanitize'
import { createSupportStorageClient } from './support-storage-client'
import type { ExtendedSupportCategories } from './Support.constants'
import { NO_PROJECT_MARKER } from './SupportForm.utils'

export type DashboardBreadcrumb = Sentry.Breadcrumb

const DASHBOARD_LOG_BUCKET = 'dashboard-logs'
const SIGNED_URL_EXPIRY = 10 * 365 * 24 * 60 * 60

export const DASHBOARD_LOG_CATEGORIES: ExtendedSupportCategories[] = [
  SupportCategories.DASHBOARD_BUG,
]

export const getSanitizedBreadcrumbs = (): unknown[] => {
  const breadcrumbs = getBreadcrumbSnapshot() ?? getMirroredBreadcrumbs()
  return sanitizeArrayOfObjects(breadcrumbs)
}

export const uploadDashboardLog = async (
  projectRef: string | null | undefined
): Promise<string | undefined> => {
  const sanitized = getSanitizedBreadcrumbs()
  if (sanitized.length === 0) return undefined

  try {
    const supportStorageClient = createSupportStorageClient()
    const basePath = projectRef && projectRef.length > 0 ? projectRef : NO_PROJECT_MARKER
    const objectKey = `${basePath}/${Date.now()}-${uuidv4()}.json`
    const body = new Blob([JSON.stringify(sanitized, null, 2)], {
      type: 'application/json',
    })

    const { error: uploadError } = await supportStorageClient.storage
      .from(DASHBOARD_LOG_BUCKET)
      .upload(objectKey, body, {
        cacheControl: '3600',
        contentType: 'application/json',
        upsert: false,
      })

    if (uploadError) {
      console.error(
        '[SupportForm] Failed to upload dashboard log to support storage bucket',
        uploadError
      )
      return undefined
    }

    const { data: signedUrls, error: signedUrlError } = await supportStorageClient.storage
      .from(DASHBOARD_LOG_BUCKET)
      .createSignedUrls([objectKey], SIGNED_URL_EXPIRY)

    if (signedUrlError) {
      console.error('[SupportForm] Failed to generate signed URL for dashboard log', signedUrlError)
      return undefined
    }

    return signedUrls?.[0]?.signedUrl
  } catch (error) {
    console.error('[SupportForm] Unexpected error uploading dashboard log', error)
    return undefined
  }
}
