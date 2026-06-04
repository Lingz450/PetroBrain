import { Providers } from '@/lib/admin-console/Providers';

import { LearningClient } from './LearningClient';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: { id: string };
}

export default function LearningPage({ params }: PageProps) {
  return (
    <Providers>
      <LearningClient tenantId={params.id} />
    </Providers>
  );
}
