import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { CarbonCalculator } from './CarbonCalculator';

describe('CarbonCalculator', () => {
  it('renders a worksheet-style emissions calculator with live totals', async () => {
    const user = userEvent.setup();
    render(<CarbonCalculator />);

    expect(screen.getByText('Carbon calculator')).toBeInTheDocument();
    expect(screen.getByText('Diesel generator fuel')).toBeInTheDocument();
    expect(screen.getByText('Company pool vehicle fuel usage / emission factor quarterly breakdown')).toBeInTheDocument();
    expect(screen.getByText('Quarter total')).toBeInTheDocument();
    expect(screen.getByText('1,758.61')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Diesel generator fuel activity data'), '100');

    expect(screen.getByText('268 kgCO2')).toBeInTheDocument();
  });
});
