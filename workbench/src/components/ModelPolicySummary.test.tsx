import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Trace } from '../types'
import { ModelPolicySummary } from './ModelPolicySummary'

describe('ModelPolicySummary', () => {
  it('renders partial route recommendations without crashing', () => {
    const trace = {
      completion: {
        route_decision: {
          selected_route: 'continuity',
          model_recommendation: {
            current_selected_model: 'qwen3:14b',
            observational_only: true,
            model_selection_changed: false,
          },
        },
      },
    } as Trace

    render(<ModelPolicySummary trace={trace} />)

    expect(screen.getByText('continuity')).toBeInTheDocument()
    expect(screen.getByText('qwen3:14b')).toBeInTheDocument()
    expect(screen.getAllByText('not specified')).toHaveLength(3)
    expect(screen.getByText('No latency note for this route.')).toBeInTheDocument()
    expect(screen.getByText('No recommendation evidence path for this route.')).toBeInTheDocument()
  })
})
