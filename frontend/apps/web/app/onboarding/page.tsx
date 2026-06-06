import type { Metadata } from 'next';
import { Suspense } from 'react';

import { OnboardingClient } from './OnboardingClient';

export const metadata: Metadata = {
  title: 'Set up your workspace - PetroBrain',
  description: 'Configure your PetroBrain oil and gas workspace.',
};

export default function OnboardingPage() {
  return (
    <Suspense fallback={<main className="grid min-h-screen place-items-center text-sm text-neutral-500">Preparing onboarding...</main>}>
      <OnboardingClient />
    </Suspense>
  );
}
