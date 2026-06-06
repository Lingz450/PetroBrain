import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AccountTypeClient } from './AccountTypeClient';

const push = vi.fn();
const back = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, back }),
}));

describe('AccountTypeClient', () => {
  beforeEach(() => {
    push.mockClear();
    back.mockClear();
    sessionStorage.clear();
  });

  it('renders individual and company choices and continues with the selection', () => {
    render(<AccountTypeClient />);

    expect(screen.getByRole('radio', { name: /individual/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /company/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: /company/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

    expect(sessionStorage.getItem('petrobrain-signup-account-type')).toBe('company');
    expect(push).toHaveBeenCalledWith('/signup?account_type=company');
  });
});
