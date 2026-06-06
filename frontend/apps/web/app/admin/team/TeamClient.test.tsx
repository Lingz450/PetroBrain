import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useChatStore } from '@/lib/chat/store';
import { TeamClient } from './TeamClient';

vi.mock('@/lib/onboarding/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/onboarding/api')>('@/lib/onboarding/api');
  return {
    ...actual,
    listMembers: vi.fn().mockResolvedValue({
      members: [{
        id: 'owner',
        email: 'owner@example.com',
        role: 'tenant_owner',
        status: 'active',
      }],
    }),
    listInvitations: vi.fn().mockResolvedValue({
      invitations: [{
        invitation_id: 'invite-1',
        tenant_id: 'tenant-a',
        email: 'engineer@example.com',
        role: 'engineer',
        status: 'pending',
        invited_by_user_id: 'owner',
        expires_at: '2030-01-01T00:00:00Z',
        created_at: '2029-01-01T00:00:00Z',
      }],
    }),
  };
});

describe('TeamClient', () => {
  beforeEach(() => {
    useChatStore.setState({
      token: 'token',
      principal: {
        tenantId: 'tenant-a',
        userId: 'owner',
        role: 'tenant_owner',
        allowedAssets: ['*'],
      },
      apiBaseUrl: 'http://api.test',
      hasHydrated: true,
    });
  });

  it('renders members, invitations, and the role selector', async () => {
    render(<TeamClient />);
    expect(await screen.findByText('owner@example.com')).toBeInTheDocument();
    expect(await screen.findByText('engineer@example.com')).toBeInTheDocument();
    expect(screen.getByLabelText('Role')).toBeInTheDocument();
  });
});
