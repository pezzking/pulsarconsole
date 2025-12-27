import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  RefreshCw,
  Settings,
  FolderOpen,
  ChevronRight,
  Loader2,
  AlertTriangle,
  Save,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  usePulsarAuthStatus,
  usePulsarAuthValidation,
  useBrokerConfig,
  useUpdateBrokerConfig,
  useDeleteBrokerConfig,
  useTenants,
  useNamespaces,
} from '@/api/hooks';
import AuthStatusCard from '@/components/auth/AuthStatusCard';
import PermissionEditor from '@/components/auth/PermissionEditor';
import RbacSyncPanel from '@/components/auth/RbacSyncPanel';
import { ConfirmDialog } from '@/components/shared';
import { cn } from '@/lib/utils';

type TabType = 'status' | 'permissions' | 'sync' | 'config';

export default function PulsarAuthPage() {
  const [activeTab, setActiveTab] = useState<TabType>('status');
  const [selectedTenant, setSelectedTenant] = useState<string>('');
  const [selectedNamespace, setSelectedNamespace] = useState<string>('');
  const [editingConfig, setEditingConfig] = useState<string | null>(null);
  const [newConfigValue, setNewConfigValue] = useState('');
  const [deleteConfigConfirm, setDeleteConfigConfirm] = useState<string | null>(null);

  // Auth status queries
  const {
    data: authStatus,
    isLoading: statusLoading,
    refetch: refetchStatus,
  } = usePulsarAuthStatus();

  const {
    data: validation,
    isLoading: validationLoading,
    refetch: refetchValidation,
  } = usePulsarAuthValidation();

  // Broker config
  const { data: brokerConfig, isLoading: configLoading } = useBrokerConfig();
  const updateConfig = useUpdateBrokerConfig();
  const deleteConfig = useDeleteBrokerConfig();

  // Tenant/namespace selection for permissions
  const { data: tenants } = useTenants({ useCache: true });
  const { data: namespaces } = useNamespaces(selectedTenant, true);

  const handleUpdateConfig = async (configName: string) => {
    if (!newConfigValue.trim()) {
      toast.error('Value is required');
      return;
    }

    try {
      await updateConfig.mutateAsync({
        configName,
        value: newConfigValue,
      });
      toast.success(`Updated ${configName}`);
      setEditingConfig(null);
      setNewConfigValue('');
    } catch {
      toast.error(`Failed to update ${configName}`);
    }
  };

  const handleDeleteConfig = async () => {
    if (!deleteConfigConfirm) return;

    try {
      await deleteConfig.mutateAsync(deleteConfigConfirm);
      toast.success(`Deleted ${deleteConfigConfirm}`);
      setDeleteConfigConfirm(null);
    } catch {
      toast.error(`Failed to delete ${deleteConfigConfirm}`);
    }
  };

  const tabs: { id: TabType; label: string; icon: typeof Shield }[] = [
    { id: 'status', label: 'Status', icon: Shield },
    { id: 'permissions', label: 'Permissions', icon: FolderOpen },
    { id: 'sync', label: 'RBAC Sync', icon: RefreshCw },
    { id: 'config', label: 'Broker Config', icon: Settings },
  ];

  // Filter auth-related config keys
  const authConfigKeys = brokerConfig
    ? Object.entries(brokerConfig).filter(
        ([key]) =>
          key.toLowerCase().includes('auth') ||
          key.toLowerCase().includes('super') ||
          key.toLowerCase().includes('token') ||
          key.toLowerCase().includes('tls')
      )
    : [];

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Shield className="text-primary" />
            Pulsar Authentication
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage authentication, authorization, and permissions
          </p>
        </div>
        <button
          onClick={() => {
            refetchStatus();
            refetchValidation();
          }}
          className="p-2 hover:bg-white/10 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw
            size={20}
            className={cn(
              (statusLoading || validationLoading) && 'animate-spin'
            )}
          />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/10 pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2 rounded-t-lg transition-colors flex items-center gap-2',
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-white/5 text-muted-foreground'
            )}
          >
            <tab.icon size={18} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
      >
        {/* Status Tab */}
        {activeTab === 'status' && (
          <AuthStatusCard
            status={authStatus}
            validation={validation}
            isLoading={statusLoading}
            isValidating={validationLoading}
          />
        )}

        {/* Permissions Tab */}
        {activeTab === 'permissions' && (
          <div className="space-y-6">
            {/* Namespace Selector */}
            <div className="glass rounded-xl p-6 border border-white/10">
              <h3 className="text-lg font-semibold mb-4">Select Namespace</h3>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium mb-2">
                    Tenant
                  </label>
                  <select
                    value={selectedTenant}
                    onChange={(e) => {
                      setSelectedTenant(e.target.value);
                      setSelectedNamespace('');
                    }}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">Select tenant...</option>
                    {tenants?.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end">
                  <ChevronRight className="w-6 h-6 text-muted-foreground mb-3" />
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium mb-2">
                    Namespace
                  </label>
                  <select
                    value={selectedNamespace}
                    onChange={(e) => setSelectedNamespace(e.target.value)}
                    disabled={!selectedTenant}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                  >
                    <option value="">Select namespace...</option>
                    {namespaces?.map((ns) => (
                      <option key={ns.namespace} value={ns.namespace}>
                        {ns.namespace}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Permission Editor */}
            {selectedTenant && selectedNamespace ? (
              <PermissionEditor
                tenant={selectedTenant}
                namespace={selectedNamespace}
              />
            ) : (
              <div className="glass rounded-xl p-8 text-center border border-white/10">
                <FolderOpen className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-muted-foreground">
                  Select a tenant and namespace to manage permissions
                </p>
              </div>
            )}
          </div>
        )}

        {/* RBAC Sync Tab */}
        {activeTab === 'sync' && (
          <div className="space-y-6">
            {/* Namespace Selector */}
            <div className="glass rounded-xl p-6 border border-white/10">
              <h3 className="text-lg font-semibold mb-4">Select Namespace</h3>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium mb-2">
                    Tenant
                  </label>
                  <select
                    value={selectedTenant}
                    onChange={(e) => {
                      setSelectedTenant(e.target.value);
                      setSelectedNamespace('');
                    }}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">Select tenant...</option>
                    {tenants?.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end">
                  <ChevronRight className="w-6 h-6 text-muted-foreground mb-3" />
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium mb-2">
                    Namespace
                  </label>
                  <select
                    value={selectedNamespace}
                    onChange={(e) => setSelectedNamespace(e.target.value)}
                    disabled={!selectedTenant}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                  >
                    <option value="">Select namespace...</option>
                    {namespaces?.map((ns) => (
                      <option key={ns.namespace} value={ns.namespace}>
                        {ns.namespace}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* RBAC Sync Panel */}
            {selectedTenant && selectedNamespace ? (
              <RbacSyncPanel
                tenant={selectedTenant}
                namespace={selectedNamespace}
              />
            ) : (
              <div className="glass rounded-xl p-8 text-center border border-white/10">
                <RefreshCw className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-muted-foreground">
                  Select a tenant and namespace to sync RBAC
                </p>
              </div>
            )}
          </div>
        )}

        {/* Broker Config Tab */}
        {activeTab === 'config' && (
          <div className="space-y-6">
            {/* Warning */}
            <div className="p-4 bg-yellow-500/10 rounded-xl flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5" />
              <div>
                <p className="font-medium text-yellow-500">
                  Caution: Broker Configuration
                </p>
                <p className="text-sm text-yellow-400 mt-1">
                  Modifying broker configuration can affect cluster behavior.
                  Some changes require a broker restart to take effect.
                </p>
              </div>
            </div>

            {/* Config List */}
            <div className="glass rounded-xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10">
                <h3 className="font-semibold">Auth-Related Configuration</h3>
                <p className="text-sm text-muted-foreground">
                  Dynamic broker configuration values
                </p>
              </div>

              {configLoading ? (
                <div className="p-8 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : authConfigKeys.length > 0 ? (
                <div className="divide-y divide-white/10">
                  {authConfigKeys.map(([key, value]) => (
                    <div
                      key={key}
                      className="p-4 flex items-center gap-4 hover:bg-white/5"
                    >
                      <div className="flex-1 min-w-0">
                        <code className="text-sm text-primary">{key}</code>
                        {editingConfig === key ? (
                          <input
                            type="text"
                            value={newConfigValue}
                            onChange={(e) => setNewConfigValue(e.target.value)}
                            className="w-full mt-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                            placeholder="New value..."
                            autoFocus
                          />
                        ) : (
                          <p className="text-sm text-muted-foreground truncate mt-1">
                            {value || '(empty)'}
                          </p>
                        )}
                      </div>
                      {editingConfig === key ? (
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setEditingConfig(null);
                              setNewConfigValue('');
                            }}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                          >
                            <ChevronRight
                              size={18}
                              className="rotate-90 text-muted-foreground"
                            />
                          </button>
                          <button
                            onClick={() => handleUpdateConfig(key)}
                            disabled={updateConfig.isPending}
                            className="p-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                          >
                            {updateConfig.isPending ? (
                              <Loader2 size={18} className="animate-spin" />
                            ) : (
                              <Save size={18} />
                            )}
                          </button>
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setEditingConfig(key);
                              setNewConfigValue(value);
                            }}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                            title="Edit"
                          >
                            <Settings size={18} />
                          </button>
                          <button
                            onClick={() => setDeleteConfigConfirm(key)}
                            className="p-2 hover:bg-destructive/10 text-muted-foreground hover:text-destructive rounded-lg transition-colors"
                            title="Delete"
                          >
                            <Trash2 size={18} />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center">
                  <Settings className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-muted-foreground">
                    No auth-related configuration found
                  </p>
                </div>
              )}
            </div>

            {/* All Config (expandable) */}
            {brokerConfig && Object.keys(brokerConfig).length > 0 && (
              <details className="glass rounded-xl border border-white/10 overflow-hidden">
                <summary className="p-4 cursor-pointer hover:bg-white/5 font-medium">
                  All Dynamic Configuration ({Object.keys(brokerConfig).length}{' '}
                  keys)
                </summary>
                <div className="p-4 border-t border-white/10 max-h-96 overflow-auto">
                  <pre className="text-xs text-muted-foreground">
                    {JSON.stringify(brokerConfig, null, 2)}
                  </pre>
                </div>
              </details>
            )}
          </div>
        )}
      </motion.div>

      {/* Delete Config Confirmation */}
      <ConfirmDialog
        open={!!deleteConfigConfirm}
        onOpenChange={(open) => !open && setDeleteConfigConfirm(null)}
        title="Delete Configuration"
        description={`Are you sure you want to delete "${deleteConfigConfirm}"? This will reset the setting to its default value.`}
        confirmLabel="Delete"
        onConfirm={handleDeleteConfig}
        variant="danger"
        loading={deleteConfig.isPending}
      />
    </div>
  );
}
