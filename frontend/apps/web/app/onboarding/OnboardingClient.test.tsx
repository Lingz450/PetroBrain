import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useChatStore } from '@/lib/chat/store';
import { OnboardingClient } from './OnboardingClient';

const { replace, saveIndividual } = vi.hoisted(() => ({
  replace: vi.fn(),
  saveIndividual: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/onboarding/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/onboarding/api')>('@/lib/onboarding/api');
  return {
    ...actual,
    getOnboardingStatus: vi.fn().mockResolvedValue({
      account_type: 'individual',
      onboarding_status: 'in_progress',
      current_step: 'profile',
      answers: {},
      tenant_id: 'individual-a',
      workspace_name: 'Personal workspace',
    }),
    getOnboardingOptions: vi.fn().mockResolvedValue({
      account_types: ['individual', 'company'],
      focus_areas: ['Upstream', 'Emissions / ESG / MRV'],
      use_cases: ['Research oil and gas topics'],
      regions: ['Nigeria', 'Global'],
      company_types: [],
      company_sizes: [],
      regulator_focus: [],
      asset_types: [],
      roles: [],
    }),
    saveIndividual,
    completeOnboarding: vi.fn().mockResolvedValue({ recommended_destination: '/chat' }),
  };
});

describe('OnboardingClient', () => {
  beforeEach(() => {
    replace.mockClear();
    saveIndividual.mockReset();
    saveIndividual.mockResolvedValue({});
    useChatStore.setState({
      token: 'token',
      principal: {
        tenantId: 'individual-a',
        userId: 'user-a',
        role: 'tenant_owner',
        allowedAssets: ['*'],
      },
      apiBaseUrl: 'http://api.test',
      hasHydrated: true,
    });
  });

  it('saves required individual details and advances to focus areas', async () => {
    render(<OnboardingClient />);
    await screen.findByRole('heading', { name: 'Tell us about your work' });

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Ada Okafor' } });
    fireEvent.change(screen.getByLabelText(/^country/i), { target: { value: 'Nigeria' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save and continue' }));

    await waitFor(() => expect(saveIndividual).toHaveBeenCalled());
    expect(await screen.findByRole('heading', {
      name: 'What area of oil and gas do you work with most?',
    })).toBeInTheDocument();
  });
});
