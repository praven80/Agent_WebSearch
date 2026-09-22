/**
 * The AppLayout tools drawer: environment setup only.
 *
 * The search request parameters deliberately live on the Run page instead, in
 * SearchControls, because they are part of the demo rather than one-time config
 * and were too easy to miss inside a collapsed drawer.
 */

import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import FormField from '@cloudscape-design/components/form-field';
import HelpPanel from '@cloudscape-design/components/help-panel';
import Input from '@cloudscape-design/components/input';
import Select from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';

import type { Bootstrap, Readiness, SettingsPayload } from '../api/types';

interface SettingsPanelProps {
  bootstrap: Bootstrap;
  settings: SettingsPayload;
  readiness: Readiness | null;
  onChange: (patch: Partial<SettingsPayload>) => void;
}

export default function SettingsPanel({
  bootstrap,
  settings,
  readiness,
  onChange,
}: SettingsPanelProps) {
  const { constraints, modelOptions } = bootstrap;

  const gatewayRegion = readiness?.gateway.region;
  const regionUnsupported =
    readiness?.gateway.configured && readiness.gateway.regionSupported === false;

  return (
    <HelpPanel header={<h2>Environment</h2>}>
      <SpaceBetween size="l">
        <FormField
          label="Bedrock model"
          description="Used identically by both options, so the comparison isolates search."
        >
          <Select
            selectedOption={{
              label:
                modelOptions.find((m) => m.id === settings.modelId)?.label ??
                settings.modelId,
              value: settings.modelId,
              description: settings.modelId,
            }}
            options={modelOptions.map((m) => ({
              label: m.label,
              value: m.id,
              description: m.id,
            }))}
            onChange={({ detail }) =>
              onChange({ modelId: detail.selectedOption.value ?? settings.modelId })
            }
          />
        </FormField>

        <FormField
          label="AgentCore Gateway URL"
          description="The GatewayUrl output from infra/deploy.sh. Required for Option 2."
          errorText={
            settings.gatewayUrl && !readiness?.gateway.configured
              ? 'Not an AgentCore Gateway endpoint.'
              : undefined
          }
        >
          <Input
            value={settings.gatewayUrl}
            placeholder="https://<id>.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
            onChange={({ detail }) => onChange({ gatewayUrl: detail.value })}
          />
        </FormField>

        {regionUnsupported && (
          <Alert type="warning" header="Region not supported">
            This Gateway is in {gatewayRegion}. Web Search is available in{' '}
            {constraints.webSearchRegions.join(', ')}.
          </Alert>
        )}

        <Box variant="small" color="text-body-secondary">
          Results per search and the domain and published-date filters are on the Run
          page, under Search controls.
        </Box>

        <Box variant="small" color="text-body-secondary">
          Filters require connector version 1.2.0 or later. Cost figures in the app are
          estimates from list pricing, not a bill.
        </Box>
      </SpaceBetween>
    </HelpPanel>
  );
}
