"use client";

import * as React from "react";
import { Key, Save, Check, RefreshCw, Eye, EyeOff } from "@/components/icons";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TestConnection } from "./test-connection";
import { useToast } from "@/components/ui/toast";
import type { ProviderKey } from "@/lib/types";

interface ProviderDefinition {
  id: string;
  name: string;
  category: "streaming" | "ai" | "transcription";
  fields: Array<{ key_name: string; label: string; placeholder: string }>;
}

const PROVIDERS: ProviderDefinition[] = [
  {
    id: "twitch",
    name: "Twitch",
    category: "streaming",
    fields: [
      { key_name: "TWITCH_CLIENT_ID", label: "Client ID", placeholder: "e.g. uo6dgg42ep7e8..." },
      { key_name: "TWITCH_CLIENT_SECRET", label: "Client Secret", placeholder: "••••••••••••" },
    ],
  },
  {
    id: "kick",
    name: "Kick",
    category: "streaming",
    fields: [
      { key_name: "KICK_APP_ID", label: "App ID", placeholder: "e.g. app_12345..." },
      { key_name: "KICK_API_KEY", label: "API Key", placeholder: "••••••••••••" },
    ],
  },
  {
    id: "youtube",
    name: "YouTube / Google Cloud",
    category: "streaming",
    fields: [
      { key_name: "GOOGLE_CLIENT_ID", label: "Google Client ID", placeholder: "••••••••••••.apps.googleusercontent.com" },
      { key_name: "GOOGLE_CLIENT_SECRET", label: "Client Secret", placeholder: "••••••••••••" },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic Claude",
    category: "ai",
    fields: [
      { key_name: "ANTHROPIC_API_KEY", label: "API Key", placeholder: "sk-ant-api03-••••••••••••" },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    category: "ai",
    fields: [
      { key_name: "OPENAI_API_KEY", label: "API Key", placeholder: "sk-proj-••••••••••••" },
    ],
  },
  {
    id: "gemini",
    name: "Google Gemini",
    category: "ai",
    fields: [
      { key_name: "GEMINI_API_KEY", label: "API Key", placeholder: "AIzaSy••••••••••••" },
    ],
  },
  {
    id: "deepgram",
    name: "Deepgram (Audio / Speech-to-Text)",
    category: "transcription",
    fields: [
      { key_name: "DEEPGRAM_API_KEY", label: "API Key", placeholder: "••••••••••••" },
    ],
  },
];

interface ApiKeyFormProps {
  storedKeys: ProviderKey[];
  onSaveKey: (provider: string, keyName: string, value: string) => Promise<any>;
}

export function ApiKeyForm({ storedKeys, onSaveKey }: ApiKeyFormProps) {
  const { toast } = useToast();
  const [formData, setFormData] = React.useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = React.useState<string | null>(null);

  // Map of stored keys by key_name
  const storedKeyMap = React.useMemo(() => {
    const map = new Map<string, ProviderKey>();
    storedKeys.forEach((k) => map.set(k.key_name, k));
    return map;
  }, [storedKeys]);

  const handleInputChange = (keyName: string, val: string) => {
    setFormData((prev) => ({ ...prev, [keyName]: val }));
  };

  const handleSaveField = async (provider: string, keyName: string) => {
    const value = formData[keyName];
    if (!value || !value.trim()) return;

    setSavingKey(keyName);
    try {
      await onSaveKey(provider, keyName, value.trim());
      // Clear input since backend now has it stored and masked
      setFormData((prev) => ({ ...prev, [keyName]: "" }));
      toast({
        title: "Key Encrypted & Saved",
        message: `${keyName} updated successfully.`,
        type: "success",
      });
    } catch (err: any) {
      toast({
        title: "Failed to Save Key",
        message: err.message || "An error occurred",
        type: "error",
      });
    } finally {
      setSavingKey(null);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {PROVIDERS.map((prov) => {
        // Check if provider has stored keys
        const providerKeys = storedKeys.filter((k) => k.provider === prov.id);
        const isConfigured = providerKeys.length > 0;

        return (
          <Card key={prov.id} className="border-border bg-surface flex flex-col justify-between">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Key className="h-4 w-4 text-accent" />
                  {prov.name}
                </CardTitle>
                <Badge variant={isConfigured ? "success" : "secondary"} className="text-[10px]">
                  {isConfigured ? "Configured" : "Not Set"}
                </Badge>
              </div>
              <CardDescription className="capitalize">
                {prov.category} provider credentials
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {prov.fields.map((field) => {
                const stored = storedKeyMap.get(field.key_name);
                const currentInputValue = formData[field.key_name] || "";
                const isSaving = savingKey === field.key_name;

                return (
                  <div key={field.key_name} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label htmlFor={field.key_name} className="text-xs">
                        {field.label}
                      </Label>
                      {stored && (
                        <span className="text-[11px] font-mono text-muted-foreground">
                          Current: {stored.masked_value}
                        </span>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <Input
                        id={field.key_name}
                        type="password"
                        placeholder={stored ? "Enter new value to update" : field.placeholder}
                        value={currentInputValue}
                        onChange={(e) => handleInputChange(field.key_name, e.target.value)}
                        className="text-xs font-mono"
                      />
                      <Button
                        type="button"
                        variant="default"
                        size="sm"
                        disabled={!currentInputValue.trim() || isSaving}
                        isLoading={isSaving}
                        onClick={() => handleSaveField(prov.id, field.key_name)}
                        className="shrink-0 text-xs gap-1"
                      >
                        <Save className="h-3.5 w-3.5" />
                        Save
                      </Button>
                    </div>
                  </div>
                );
              })}

              {/* Provider Connection Test Button if at least one key is stored */}
              {providerKeys.length > 0 && (
                <div className="pt-2 border-t border-border/50 flex justify-end">
                  <TestConnection keyId={providerKeys[0].id} />
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
