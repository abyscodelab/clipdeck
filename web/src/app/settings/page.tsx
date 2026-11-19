"use client";

import * as React from "react";
import { Settings as SettingsIcon, Key, Sliders, HardDrive, Shield } from "@/components/icons";
import { AppShell } from "@/components/layout/app-shell";
import { ApiKeyForm } from "@/components/settings/api-key-form";
import { DetectorSettings } from "@/components/settings/detector-settings";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import type { ProviderKey, Setting } from "@/lib/types";

export default function SettingsPage() {
  // Fetch encrypted provider keys
  const {
    data: providerKeys = [],
    isLoading: isKeysLoading,
    mutate: mutateKeys,
  } = useApi<ProviderKey[]>(() => api.settings.getKeys(), []);

  // Fetch app settings
  const {
    data: settings = [],
    isLoading: isSettingsLoading,
    mutate: mutateSettings,
  } = useApi<Setting[]>(() => api.settings.get(), []);

  const handleSaveKey = async (provider: string, keyName: string, value: string) => {
    // Check if key already exists
    const existing = providerKeys.find((k) => k.key_name === keyName);
    if (existing) {
      await api.settings.updateKey(existing.id, value);
    } else {
      await api.settings.createKey(provider, keyName, value);
    }
    mutateKeys();
  };

  const handleSaveSettings = async (updatedSettings: Record<string, any>) => {
    await api.settings.update(updatedSettings);
    mutateSettings();
  };

  const isLoading = isKeysLoading || isSettingsLoading;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
            <SettingsIcon className="h-6 w-6 text-accent" />
            System & Provider Settings
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Manage encrypted API credentials, tune detection sensitivity, and set DVR storage caps.
          </p>
        </div>

        {/* Tabbed Navigation */}
        <Tabs defaultValue="providers">
          <TabsList className="grid grid-cols-2 w-full sm:w-80">
            <TabsTrigger value="providers" className="gap-1.5 text-xs font-semibold">
              <Key className="h-3.5 w-3.5 text-accent" />
              API Provider Keys
            </TabsTrigger>
            <TabsTrigger value="detector" className="gap-1.5 text-xs font-semibold">
              <Sliders className="h-3.5 w-3.5 text-accent" />
              Algorithm & DVR
            </TabsTrigger>
          </TabsList>

          {/* Provider Keys Tab */}
          <TabsContent value="providers" className="pt-3">
            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Skeleton className="h-64 w-full rounded-xl" />
                <Skeleton className="h-64 w-full rounded-xl" />
              </div>
            ) : (
              <ApiKeyForm
                storedKeys={providerKeys}
                onSaveKey={handleSaveKey}
              />
            )}
          </TabsContent>

          {/* Detector & General Settings Tab */}
          <TabsContent value="detector" className="pt-3">
            {isLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-72 w-full rounded-xl" />
                <Skeleton className="h-40 w-full rounded-xl" />
              </div>
            ) : (
              <DetectorSettings
                initialSettings={settings}
                onSaveSettings={handleSaveSettings}
              />
            )}
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
