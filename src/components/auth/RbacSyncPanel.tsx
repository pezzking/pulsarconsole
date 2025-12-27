import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  Plus,
  Minus,
  Edit3,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Eye,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import {
  useRbacDiff,
  useRbacSyncPreview,
  useRbacSync,
  type SyncDiffResponse,
} from '@/api/hooks';
import { ConfirmDialog } from '@/components/shared';

interface RbacSyncPanelProps {
  tenant: string;
  namespace: string;
}

type SyncDirection = 'console_to_pulsar' | 'pulsar_to_console';

export default function RbacSyncPanel({
  tenant,
  namespace,
}: RbacSyncPanelProps) {
  const { data: diff, isLoading: diffLoading, refetch: refetchDiff } = useRbacDiff(tenant, namespace);
  const [direction, setDirection] = useState<SyncDirection>('console_to_pulsar');
  const [showPreview, setShowPreview] = useState(false);

  const {
    data: preview,
    isLoading: previewLoading,
  } = useRbacSyncPreview(tenant, namespace, showPreview ? direction : undefined);

  const syncMutation = useRbacSync();
  const [confirmSync, setConfirmSync] = useState(false);

  const handleSync = async () => {
    try {
      const result = await syncMutation.mutateAsync({
        tenant,
        namespace,
        direction,
        dry_run: false,
      });

      if (result.success) {
        toast.success(`Sync completed: ${result.changes_applied} changes applied`);
      } else {
        toast.error(`Sync failed: ${result.errors?.join(', ')}`);
      }
      setConfirmSync(false);
      refetchDiff();
    } catch {
      toast.error('Failed to synchronize RBAC');
    }
  };

  const renderDiffSection = (
    title: string,
    data: Record<string, string[]> | undefined,
    variant: 'add' | 'remove' | 'neutral'
  ) => {
    if (!data || Object.keys(data).length === 0) return null;

    const iconClass =
      variant === 'add'
        ? 'text-green-500'
        : variant === 'remove'
        ? 'text-red-500'
        : 'text-muted-foreground';

    const Icon = variant === 'add' ? Plus : variant === 'remove' ? Minus : Edit3;

    return (
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
        {Object.entries(data).map(([role, actions]) => (
          <div
            key={role}
            className="p-3 bg-white/5 rounded-lg flex items-center gap-3"
          >
            <Icon className={cn('w-4 h-4', iconClass)} />
            <div className="flex-1">
              <p className="font-medium text-sm">{role}</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {actions.map((action) => (
                  <span
                    key={action}
                    className="px-2 py-0.5 text-xs bg-white/10 rounded-full"
                  >
                    {action}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl border border-white/10 overflow-hidden"
    >
      {/* Header */}
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <RefreshCw className="text-primary" size={20} />
              RBAC Synchronization
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Sync permissions between Console and Pulsar for {tenant}/{namespace}
            </p>
          </div>
          <button
            onClick={() => refetchDiff()}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            title="Refresh diff"
          >
            <RefreshCw
              size={18}
              className={cn(diffLoading && 'animate-spin')}
            />
          </button>
        </div>

        {/* Direction Selector */}
        <div className="mt-4 flex gap-2">
          <button
            onClick={() => {
              setDirection('console_to_pulsar');
              setShowPreview(false);
            }}
            className={cn(
              'flex-1 px-4 py-3 rounded-lg border transition-colors flex items-center justify-center gap-2',
              direction === 'console_to_pulsar'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-white/5 border-white/10 hover:bg-white/10'
            )}
          >
            Console
            <ArrowRight size={16} />
            Pulsar
          </button>
          <button
            onClick={() => {
              setDirection('pulsar_to_console');
              setShowPreview(false);
            }}
            className={cn(
              'flex-1 px-4 py-3 rounded-lg border transition-colors flex items-center justify-center gap-2',
              direction === 'pulsar_to_console'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-white/5 border-white/10 hover:bg-white/10'
            )}
          >
            Pulsar
            <ArrowLeft size={16} />
            Console
          </button>
        </div>
      </div>

      {/* Diff View */}
      <div className="p-6">
        {diffLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : diff ? (
          <div className="space-y-6">
            {/* Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-white/5 rounded-lg text-center">
                <p className="text-2xl font-bold">{diff.total_console}</p>
                <p className="text-xs text-muted-foreground">Console Roles</p>
              </div>
              <div className="p-4 bg-white/5 rounded-lg text-center">
                <p className="text-2xl font-bold">{diff.total_pulsar}</p>
                <p className="text-xs text-muted-foreground">Pulsar Roles</p>
              </div>
              <div className="p-4 bg-green-500/10 rounded-lg text-center">
                <p className="text-2xl font-bold text-green-500">
                  {Object.keys(diff.same || {}).length}
                </p>
                <p className="text-xs text-muted-foreground">In Sync</p>
              </div>
              <div className="p-4 bg-yellow-500/10 rounded-lg text-center">
                <p className="text-2xl font-bold text-yellow-500">
                  {Object.keys(diff.only_in_console || {}).length +
                    Object.keys(diff.only_in_pulsar || {}).length +
                    Object.keys(diff.different || {}).length}
                </p>
                <p className="text-xs text-muted-foreground">Differences</p>
              </div>
            </div>

            {/* Detailed Diff */}
            <div className="space-y-4">
              {renderDiffSection(
                'Only in Console',
                diff.only_in_console,
                direction === 'console_to_pulsar' ? 'add' : 'remove'
              )}
              {renderDiffSection(
                'Only in Pulsar',
                diff.only_in_pulsar,
                direction === 'pulsar_to_console' ? 'add' : 'remove'
              )}
              {diff.different && Object.keys(diff.different).length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">
                    Different Permissions
                  </h4>
                  {Object.entries(diff.different).map(([role, perms]) => (
                    <div
                      key={role}
                      className="p-3 bg-white/5 rounded-lg"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <Edit3 className="w-4 h-4 text-yellow-500" />
                        <p className="font-medium text-sm">{role}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">
                            Console:
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {(perms as { console: string[]; pulsar: string[] }).console.map((a) => (
                              <span
                                key={a}
                                className="px-2 py-0.5 text-xs bg-blue-500/10 text-blue-400 rounded-full"
                              >
                                {a}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">
                            Pulsar:
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {(perms as { console: string[]; pulsar: string[] }).pulsar.map((a) => (
                              <span
                                key={a}
                                className="px-2 py-0.5 text-xs bg-purple-500/10 text-purple-400 rounded-full"
                              >
                                {a}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* No differences */}
              {Object.keys(diff.only_in_console || {}).length === 0 &&
                Object.keys(diff.only_in_pulsar || {}).length === 0 &&
                Object.keys(diff.different || {}).length === 0 && (
                  <div className="text-center py-8">
                    <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                    <p className="text-green-500 font-medium">
                      Console and Pulsar are in sync
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      No synchronization needed
                    </p>
                  </div>
                )}
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <XCircle className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-muted-foreground">Could not load diff</p>
          </div>
        )}
      </div>

      {/* Actions */}
      {diff &&
        (Object.keys(diff.only_in_console || {}).length > 0 ||
          Object.keys(diff.only_in_pulsar || {}).length > 0 ||
          Object.keys(diff.different || {}).length > 0) && (
          <div className="p-6 border-t border-white/10 flex gap-3">
            <button
              onClick={() => setShowPreview(!showPreview)}
              className="flex-1 px-4 py-2 border border-white/10 rounded-lg hover:bg-white/5 transition-colors flex items-center justify-center gap-2"
            >
              <Eye size={18} />
              {showPreview ? 'Hide Preview' : 'Preview Changes'}
            </button>
            <button
              onClick={() => setConfirmSync(true)}
              disabled={syncMutation.isPending}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {syncMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw size={18} />
              )}
              Sync Now
            </button>
          </div>
        )}

      {/* Preview Panel */}
      {showPreview && preview && (
        <div className="p-6 border-t border-white/10 bg-white/5">
          <h4 className="font-medium mb-4 flex items-center gap-2">
            <Eye size={18} className="text-primary" />
            Preview: {preview.changes?.length || 0} changes
          </h4>

          {previewLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
            </div>
          ) : (
            <div className="space-y-2">
              {preview.changes?.map((change, i) => (
                <div
                  key={i}
                  className="p-3 bg-white/5 rounded-lg flex items-center gap-3"
                >
                  {change.action === 'add' && (
                    <Plus className="w-4 h-4 text-green-500" />
                  )}
                  {change.action === 'remove' && (
                    <Minus className="w-4 h-4 text-red-500" />
                  )}
                  {change.action === 'update' && (
                    <Edit3 className="w-4 h-4 text-yellow-500" />
                  )}
                  <div className="flex-1">
                    <span className="font-medium text-sm capitalize">
                      {change.action}
                    </span>{' '}
                    <span className="text-sm text-muted-foreground">
                      role <code className="text-primary">{change.role}</code>
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {change.permissions.map((p) => (
                      <span
                        key={p}
                        className="px-2 py-0.5 text-xs bg-white/10 rounded-full"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              ))}

              {preview.warnings?.map((w, i) => (
                <div
                  key={`warn-${i}`}
                  className="p-3 bg-yellow-500/10 rounded-lg flex items-center gap-2 text-yellow-500 text-sm"
                >
                  <AlertTriangle size={16} />
                  {w}
                </div>
              ))}

              {preview.changes?.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No changes to apply
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Sync Confirmation */}
      <ConfirmDialog
        open={confirmSync}
        onOpenChange={setConfirmSync}
        title="Confirm Synchronization"
        description={`This will sync permissions from ${
          direction === 'console_to_pulsar' ? 'Console to Pulsar' : 'Pulsar to Console'
        }. Changes in the destination will be overwritten.`}
        confirmLabel="Sync"
        onConfirm={handleSync}
        variant="warning"
        loading={syncMutation.isPending}
      />
    </motion.div>
  );
}
