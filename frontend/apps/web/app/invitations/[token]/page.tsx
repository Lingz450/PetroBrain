import type { Metadata } from 'next';

import { InvitationClient } from './InvitationClient';

export const metadata: Metadata = {
  title: 'Accept invitation - PetroBrain',
  description: 'Accept a PetroBrain company workspace invitation.',
};

export default function InvitationPage({ params }: { params: { token: string } }) {
  return <InvitationClient token={params.token} />;
}
