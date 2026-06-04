import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { InventoryHistory } from './InventoryHistory';

describe('InventoryHistory', () => {
  it('shows a user-facing load error without internal config wording', () => {
    render(
      <InventoryHistory
        rows={[]}
        selectedId={null}
        onSelect={vi.fn()}
        isLoading={false}
        isError
      />,
    );

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Could not load inventories');
    expect(alert).not.toHaveTextContent(/API base URL|backend|config/i);
  });
});
