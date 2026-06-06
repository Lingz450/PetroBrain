import type { Metadata } from 'next';

import { AccountTypeClient } from './AccountTypeClient';

export const metadata: Metadata = {
  title: 'Choose account type - PetroBrain',
  description: 'Choose an individual or company PetroBrain workspace.',
};

export default function AccountTypePage() {
  return <AccountTypeClient />;
}
