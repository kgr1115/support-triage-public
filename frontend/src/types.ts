// TypeScript shapes mirror the backend's Pydantic models in app/main.py and
// app/schemas.py. Keep these in sync if the backend contract changes.

export type Priority = 'urgent' | 'high' | 'normal' | 'low'

export type Category =
  | 'login_issue'
  | 'billing_dispute'
  | 'integration_setup'
  | 'feature_request'
  | 'bug_report'

export type Sentiment = 'positive' | 'neutral' | 'negative' | 'frustrated'

export type Classification = {
  priority: Priority
  category: Category
  sentiment: Sentiment
}

export type RetrievedItem = {
  id: string
  title: string
  score: number
}

export type DraftedResponse = {
  ticket_id: string
  retrieved_kb_ids: string[]
  response: string
  cited_kb_ids: string[]
}

export type TriageResponse = {
  classification: Classification
  retrieved_kb: RetrievedItem[]
  drafted_response: DraftedResponse
  suggested_macros: RetrievedItem[]
}

export type TriageRequest = {
  subject: string
  body: string
}
