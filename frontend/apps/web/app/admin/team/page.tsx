import type { Metadata } from 'next';

import { TeamClient } from './TeamClient';

export const metadata: Metadata = {
  title: 'Team - PetroBrain',
  description: 'Manage PetroBrain company members and invitations.',
};

export default function TeamPage() {
  return <TeamClient />;
}
