'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import type { Route } from 'next';

import { BackLink, Logo } from '@petrobrain/ui';
import { AuthGate } from '../chat/components/AuthGate';
import { useChatStore } from '@/lib/chat/store';
import { createTask, deleteTask, listTasks, taskAction, updateTask } from '@/lib/tasks/api';
import type { PetroTask, TaskCreateInput, TaskUpdateInput } from '@/lib/tasks/types';

const CATEGORIES = [
  'emissions_reporting', 'ghg_inventory', 'nuprc_reporting', 'ogmp_2_reporting',
  'ldar_inspection', 'flare_monitoring', 'ptw_expiry', 'permit_renewal',
  'hse_audit', 'hse_training', 'incident_follow_up', 'audit_action',
  'weekly_production_report', 'monthly_management_report', 'research_digest',
];

const EMPTY: TaskCreateInput = {
  title: '', description: '', category: 'compliance_calendar', priority: 'medium',
  recurrence_type: 'none', assigned_to_team: '', due_date: '',
  timezone: 'Africa/Lagos', status: 'active', compliance_critical: true,
  safety_critical: false, reminder_channels: ['in_app'],
};

export function TasksClient() {
  const token = useChatStore((s) => s.token);
  const principal = useChatStore((s) => s.principal);
  const baseUrl = useChatStore((s) => s.apiBaseUrl);
  const hydrated = useChatStore((s) => s.hasHydrated);
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('all');
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<PetroTask | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PetroTask | null>(null);
  const [draft, setDraft] = useState<TaskCreateInput>(EMPTY);
  const auth = { baseUrl, token: token ?? '' };

  const query = useQuery({
    queryKey: ['tasks', filter],
    queryFn: ({ signal }) => listTasks({ ...auth, signal }, filter === 'mine' ? '?assigned_to_me=true' : ''),
    enabled: Boolean(token),
  });

  const create = useMutation({
    mutationFn: (input: TaskCreateInput) => createTask(auth, input),
    onSuccess: () => {
      setCreating(false);
      setDraft(EMPTY);
      void queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const update = useMutation({
    mutationFn: ({ id, input }: { id: string; input: TaskUpdateInput }) => updateTask(auth, id, input),
    onSuccess: () => {
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const destroy = useMutation({
    mutationFn: (id: string) => deleteTask(auth, id),
    onSuccess: () => {
      setDeleteTarget(null);
      void queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const action = useMutation({
    mutationFn: ({ id, act }: { id: string; act: 'complete' | 'pause' | 'resume' }) =>
      taskAction(auth, id, act),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  });

  if (!hydrated) return <main className="grid min-h-screen place-items-center"><Logo size={40} glow /></main>;
  if (!token || !principal) return <AuthGate />;
  const tasks = (query.data?.tasks ?? []).filter((task) => matchesFilter(task, filter));

  return (
    <main className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <header className="border-b border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-950">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Link href={'/chat' as Route} legacyBehavior passHref>
              <BackLink label="Back to Chat" />
            </Link>
            <div className="hidden sm:block h-5 w-px bg-neutral-200 dark:bg-neutral-700" />
            <div>
              <h1 className="text-lg font-semibold sm:text-xl">Tasks</h1>
              <p className="hidden text-xs text-neutral-500 sm:block">Compliance and operations reminders</p>
            </div>
          </div>
          <button
            onClick={() => setCreating(true)}
            className="rounded-full bg-primary-600 px-3 py-2 text-xs font-semibold text-white sm:px-4 sm:text-sm"
          >
            Create task
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-6">
        <div className="mb-5 flex flex-wrap gap-2 overflow-x-auto pb-1">
          {(['all', 'mine', 'overdue', 'compliance', 'emissions', 'hse', 'digests'] as const).map((value) => (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium capitalize ${
                filter === value
                  ? 'bg-primary-600 text-white'
                  : 'bg-white text-neutral-600 ring-1 ring-neutral-200 dark:bg-neutral-900 dark:text-neutral-300 dark:ring-neutral-800'
              }`}
            >
              {value}
            </button>
          ))}
        </div>

        {query.isLoading ? <p className="text-sm text-neutral-500">Loading tasks...</p> : null}
        {query.error ? <p role="alert" className="text-sm text-red-600">{query.error.message}</p> : null}

        <section className="grid gap-3 sm:grid-cols-2">
          {tasks.map((task) => (
            <TaskRow
              key={task.task_id}
              task={task}
              busy={action.isPending}
              onAction={(act) => action.mutate({ id: task.task_id, act })}
              onEdit={() => setEditing(task)}
              onDelete={() => setDeleteTarget(task)}
            />
          ))}
        </section>

        {!query.isLoading && tasks.length === 0 ? (
          <p className="rounded-xl border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500 dark:border-neutral-700">
            No matching PetroBrain tasks.
          </p>
        ) : null}
      </div>

      {creating ? (
        <TaskFormModal
          mode="create"
          draft={EMPTY}
          busy={create.isPending}
          error={create.error?.message}
          onClose={() => { setCreating(false); setDraft(EMPTY); }}
          onSubmit={(data) => create.mutate(data)}
        />
      ) : null}

      {editing ? (
        <TaskFormModal
          mode="edit"
          draft={{
            title: editing.title,
            description: editing.description ?? '',
            category: editing.category,
            priority: editing.priority,
            recurrence_type: editing.recurrence_type,
            assigned_to_team: editing.assigned_to_team ?? '',
            due_date: editing.due_date ? editing.due_date.slice(0, 16) : '',
            timezone: 'Africa/Lagos',
            status: 'active',
            compliance_critical: editing.compliance_critical,
            safety_critical: editing.safety_critical,
            reminder_channels: ['in_app'],
          }}
          busy={update.isPending}
          error={update.error?.message}
          onClose={() => setEditing(null)}
          onSubmit={(data) =>
            update.mutate({
              id: editing.task_id,
              input: {
                title: data.title,
                description: data.description,
                category: data.category,
                priority: data.priority,
                recurrence_type: data.recurrence_type,
                assigned_to_team: data.assigned_to_team,
                due_date: data.due_date || undefined,
              },
            })
          }
        />
      ) : null}

      {deleteTarget ? (
        <DeleteConfirmModal
          task={deleteTarget}
          busy={destroy.isPending}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => destroy.mutate(deleteTarget.task_id)}
        />
      ) : null}
    </main>
  );
}

function TaskRow({
  task,
  busy,
  onAction,
  onEdit,
  onDelete,
}: {
  task: PetroTask;
  busy: boolean;
  onAction: (action: 'complete' | 'pause' | 'resume') => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-primary-700">
            {task.category.replace(/_/g, ' ')}
          </p>
          <h2 className="mt-1 font-semibold leading-snug">{task.title}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className="rounded-full bg-neutral-100 px-2 py-1 text-[10px] font-semibold uppercase dark:bg-neutral-800">
            {task.status}
          </span>
          <button
            type="button"
            onClick={onEdit}
            aria-label="Edit task"
            title="Edit task"
            className="flex h-7 w-7 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-500 transition hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:border-primary-600 dark:hover:bg-primary-900/20 dark:hover:text-primary-300"
          >
            <svg width="13" height="13" viewBox="0 0 20 20" fill="none" aria-hidden>
              <path d="M13.5 3.5l3 3L6 17H3v-3L13.5 3.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          </button>
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete task"
            title="Delete task"
            className="flex h-7 w-7 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-500 transition hover:border-red-300 hover:bg-red-50 hover:text-red-600 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:border-red-700 dark:hover:bg-red-900/20 dark:hover:text-red-400"
          >
            <svg width="13" height="13" viewBox="0 0 20 20" fill="none" aria-hidden>
              <path d="M5 7h10M8 7V5h4v2M9 10v4m2-4v4M6 7l1 9h6l1-9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div><dt className="text-neutral-500">Team</dt><dd>{task.assigned_to_team || 'Unassigned'}</dd></div>
        <div><dt className="text-neutral-500">Recurrence</dt><dd className="capitalize">{task.recurrence_type}</dd></div>
        <div><dt className="text-neutral-500">Next due</dt><dd>{formatDate(task.next_run_at ?? task.due_date)}</dd></div>
        <div><dt className="text-neutral-500">Priority</dt><dd className="capitalize">{task.priority}</dd></div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-2">
        {task.status === 'paused' ? (
          <Action label="Resume" disabled={busy} onClick={() => onAction('resume')} />
        ) : (
          <Action label="Pause" disabled={busy || task.status === 'completed'} onClick={() => onAction('pause')} />
        )}
        <Action label="Complete" disabled={busy || task.status === 'completed'} onClick={() => onAction('complete')} />
      </div>
    </article>
  );
}

function Action({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="rounded-full border border-neutral-200 px-3 py-1.5 text-xs font-semibold disabled:opacity-40 dark:border-neutral-700"
    >
      {label}
    </button>
  );
}

function TaskFormModal({
  mode,
  draft: initialDraft,
  busy,
  error,
  onClose,
  onSubmit,
}: {
  mode: 'create' | 'edit';
  draft: TaskCreateInput;
  busy: boolean;
  error?: string | undefined;
  onClose: () => void;
  onSubmit: (data: TaskCreateInput) => void;
}) {
  const [draft, setDraft] = useState<TaskCreateInput>(initialDraft);
  const inputClass =
    'h-10 w-full rounded-xl border border-neutral-200 bg-white px-3 text-sm text-neutral-900 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-200 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-100 dark:focus:ring-primary-900';

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <form
        onSubmit={(e) => { e.preventDefault(); onSubmit(draft); }}
        className="w-full max-w-lg space-y-4 rounded-2xl bg-white p-5 shadow-xl dark:bg-neutral-900 sm:p-6"
      >
        <h2 className="text-lg font-semibold">{mode === 'create' ? 'Create PetroBrain task' : 'Edit task'}</h2>

        <Field label="Title">
          <input title="Title" required value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className={inputClass} />
        </Field>

        <Field label="Description">
          <textarea
            title="Description"
            value={draft.description ?? ''}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
            rows={2}
            className={`${inputClass} h-auto py-2`}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Category">
            <select title="Category" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} className={inputClass}>
              {CATEGORIES.map((item) => (
                <option key={item} value={item}>{item.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </Field>

          <Field label="Priority">
            <select
              title="Priority"
              value={draft.priority}
              onChange={(e) => setDraft({ ...draft, priority: e.target.value as TaskCreateInput['priority'] })}
              className={inputClass}
            >
              {(['low', 'medium', 'high', 'critical'] as const).map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </Field>

          <Field label="Assigned team">
            <input
              title="Assigned team"
              value={draft.assigned_to_team ?? ''}
              onChange={(e) => setDraft({ ...draft, assigned_to_team: e.target.value })}
              className={inputClass}
            />
          </Field>

          <Field label="Recurrence">
            <select title="Recurrence" value={draft.recurrence_type} onChange={(e) => setDraft({ ...draft, recurrence_type: e.target.value })} className={inputClass}>
              {['none', 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </Field>

          <Field label="Due date">
            <input
              title="Due date"
              type="datetime-local"
              value={draft.due_date ?? ''}
              onChange={(e) => setDraft({ ...draft, due_date: e.target.value })}
              className={inputClass}
            />
          </Field>
        </div>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        {mode === 'create' ? (
          <p className="text-xs text-neutral-500">This saves an in-app PetroBrain task. Email and calendar delivery are not enabled.</p>
        ) : null}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-full border border-neutral-200 px-4 py-2 text-sm dark:border-neutral-700">
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy || !draft.title.trim()}
            className="rounded-full bg-primary-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {mode === 'create' ? 'Create' : 'Save changes'}
          </button>
        </div>
      </form>
    </div>
  );
}

function DeleteConfirmModal({
  task,
  busy,
  onCancel,
  onConfirm,
}: {
  task: PetroTask;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow-xl dark:bg-neutral-900">
        <h2 className="text-lg font-semibold">Delete task?</h2>
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          <strong>&ldquo;{task.title}&rdquo;</strong> will be permanently removed. This cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-neutral-200 px-4 py-2 text-sm dark:border-neutral-700"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className="rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1 text-xs font-medium text-neutral-600 dark:text-neutral-300">
      <span>{label}</span>
      {children}
    </label>
  );
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not set';
}

function matchesFilter(task: PetroTask, filter: string) {
  if (filter === 'overdue') {
    return Boolean(task.next_run_at && new Date(task.next_run_at) < new Date() && !['completed', 'cancelled'].includes(task.status));
  }
  if (filter === 'compliance') return task.compliance_critical;
  if (filter === 'emissions') return /emissions|ghg|ogmp|ldar|flare/.test(task.category);
  if (filter === 'hse') return /hse|ptw|incident|permit/.test(task.category);
  if (filter === 'digests') return task.category === 'research_digest';
  return true;
}
