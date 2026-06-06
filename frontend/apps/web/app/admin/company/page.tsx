import type { Metadata } from 'next';

import { CompanyClient } from './CompanyClient';

export const metadata: Metadata = {
  title: 'Company settings - PetroBrain',
  description: 'Manage your PetroBrain company workspace.',
};

export default function CompanyPage() {
  return <CompanyClient />;
}
