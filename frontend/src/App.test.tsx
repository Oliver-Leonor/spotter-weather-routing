import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App shell', () => {
  it('renders the product name and an empty state before analysis', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /StormRoute/i })).toBeInTheDocument()
    expect(screen.getByText(/Weather-Aware Trip Planning/i)).toBeInTheDocument()
    expect(screen.getByText(/Plan a trip to see routes/i)).toBeInTheDocument()
  })
})
