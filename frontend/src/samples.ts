import type { TriageRequest } from './types'

// One representative sample per category — pulled from the synthetic fixture
// scenarios so the demo lands on an obvious-correct triage result.

export type Sample = TriageRequest & { label: string }

export const SAMPLES: Sample[] = [
  {
    label: 'Login — 2FA lockout (urgent)',
    subject: "Locked out after enabling 2FA — recovery codes don't work",
    body:
      "I enabled 2FA last week and now I'm locked out. The recovery codes I saved also " +
      'return invalid. This is blocking my whole team (75 people on the Pro plan). ' +
      'Need this resolved today. Account: acct_8c4f.',
  },
  {
    label: 'Billing — duplicate charge (high)',
    subject: 'Charged twice for Pro plan in March',
    body:
      'We were charged $1,299 on March 28 and again on March 30 for the same Pro billing ' +
      'period. Account acct_2b91, 50 seats. Please refund the duplicate and confirm ' +
      "there isn't an underlying billing-system issue.",
  },
  {
    label: 'Integration — webhook not firing (high)',
    subject: 'Webhook not firing for payment.failed events',
    body:
      "Webhook subscriptions for payment.failed aren't firing. Verified the endpoint is " +
      'reachable (returns 200 to curl). Last successful delivery was 12 hours ago. ' +
      'Pro plan, account acct_7a3e.',
  },
  {
    label: 'Feature — bulk CSV export (low/normal)',
    subject: 'Bulk export to CSV from the analytics view',
    body:
      'We need bulk CSV export from the analytics view. Right now we have to export ' +
      "individual records one at a time, which doesn't scale past a few hundred. " +
      'Pro plan, account acct_d508. Happy to share our use case in detail.',
  },
  {
    label: 'Bug — dashboard double-count (urgent)',
    subject: 'Dashboard totals double-count merged tickets',
    body:
      'Repro: 1) open the dashboard, 2) apply any tag filter, 3) compare the totals ' +
      'header to the actual count of cards. Totals are exactly 2× the count. We ' +
      'checked — the doubled rows are tickets that were merged. Chrome 120 on ' +
      'macOS 14.3, Enterprise, account acct_19fa.',
  },
]
