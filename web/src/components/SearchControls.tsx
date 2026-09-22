/**
 * Search request controls, shown on the Run page.
 *
 * These live on the main page rather than in the settings drawer because they are
 * part of the demo: every value here is enforced server-side on each search by
 * SearchPolicy, overriding whatever the model asks for. The payload preview shows
 * exactly what goes on the wire.
 */

import { useState } from 'react';

import Alert from '@cloudscape-design/components/alert';
import Badge from '@cloudscape-design/components/badge';
import Box from '@cloudscape-design/components/box';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import DatePicker from '@cloudscape-design/components/date-picker';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import Input from '@cloudscape-design/components/input';
import Select from '@cloudscape-design/components/select';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Textarea from '@cloudscape-design/components/textarea';

import type { Constraints, SearchFilters, SettingsPayload } from '../api/types';

/** Presets for the published-date filter. Value is a day count, or a marker. */
const DATE_PRESETS: { label: string; days: number | 'any' | 'custom' }[] = [
  { label: 'Any time', days: 'any' },
  { label: 'Past 7 days', days: 7 },
  { label: 'Past 30 days', days: 30 },
  { label: 'Past 6 months', days: 182 },
  { label: 'Past 12 months', days: 365 },
  { label: 'Custom range', days: 'custom' },
];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Reduce a pasted URL or host to the bare domain, mirroring config.normalize_domain. */
function normalizeDomain(value: string): string {
  let text = value.trim().replace(/,+$/, '').trim();
  if (!text) return '';
  if (text.includes('//')) text = text.split('//')[1];
  text = text.split('/')[0].split('?')[0];
  if (text.includes(':')) text = text.split(':')[0];
  text = text.trim().toLowerCase().replace(/\.+$/, '');
  return text.startsWith('www.') ? text.slice(4) : text;
}

function parseDomains(raw: string, cap: number): string[] {
  const out: string[] = [];
  for (const token of raw.split(/[\s,]+/)) {
    const domain = normalizeDomain(token);
    if (domain && !out.includes(domain)) out.push(domain);
  }
  return out.slice(0, cap);
}

/** Build the filters payload locally so the preview matches what the server sends. */
function buildFilters(settings: SettingsPayload): SearchFilters {
  const filters: SearchFilters = {};
  const domainFilter: { include?: string[]; exclude?: string[] } = {};
  if (settings.domainInclude.length) domainFilter.include = settings.domainInclude;
  if (settings.domainExclude.length) domainFilter.exclude = settings.domainExclude;
  if (Object.keys(domainFilter).length) filters.domainFilter = domainFilter;

  const dateFilter: { from?: string; to?: string } = {};
  if (settings.publishedFrom) dateFilter.from = settings.publishedFrom;
  if (settings.publishedTo) dateFilter.to = settings.publishedTo;
  if (Object.keys(dateFilter).length) filters.publishedDateFilter = dateFilter;

  return filters;
}

interface SearchControlsProps {
  constraints: Constraints;
  settings: SettingsPayload;
  disabled?: boolean;
  onChange: (patch: Partial<SettingsPayload>) => void;
}

export default function SearchControls({
  constraints,
  settings,
  disabled = false,
  onChange,
}: SearchControlsProps) {
  const [includeText, setIncludeText] = useState(settings.domainInclude.join('\n'));
  const [excludeText, setExcludeText] = useState(settings.domainExclude.join('\n'));
  const [preset, setPreset] = useState<string>(
    settings.publishedFrom ? 'Custom range' : 'Any time',
  );

  const applyPreset = (label: string) => {
    setPreset(label);
    const match = DATE_PRESETS.find((p) => p.label === label);
    if (!match) return;
    if (match.days === 'any') {
      onChange({ publishedFrom: null, publishedTo: null });
    } else if (match.days === 'custom') {
      onChange({ publishedFrom: isoDaysAgo(30), publishedTo: todayIso() });
    } else {
      onChange({ publishedFrom: isoDaysAgo(match.days), publishedTo: todayIso() });
    }
  };

  const filters = buildFilters(settings);
  const filtersActive = Object.keys(filters).length > 0;
  const overlap = settings.domainInclude.filter((d) =>
    settings.domainExclude.includes(d),
  );
  const rangeInverted =
    !!settings.publishedFrom &&
    !!settings.publishedTo &&
    settings.publishedFrom > settings.publishedTo;

  return (
    <Container
      header={
        <Header
          variant="h2"
          description="Applied to Option 2 and enforced on every search, overriding whatever the model asks for."
          actions={
            filtersActive ? (
              <Badge color="blue">filters active</Badge>
            ) : (
              <Badge color="grey">no filters</Badge>
            )
          }
        >
          Search controls
        </Header>
      }
    >
      <SpaceBetween size="l">
        <ColumnLayout columns={3}>
          <FormField
            label="Results per search"
            description={`Range ${constraints.maxResultsRange[0]}-${constraints.maxResultsRange[1]}.`}
            constraintText="Per search, not per run. The model may search several times, so the total number of unique sources can be a multiple of this."
          >
            <Input
              type="number"
              disabled={disabled}
              value={String(settings.maxResults)}
              onChange={({ detail }) => {
                const [lo, hi] = constraints.maxResultsRange;
                const parsed = Number.parseInt(detail.value, 10);
                if (Number.isNaN(parsed)) return;
                onChange({ maxResults: Math.max(lo, Math.min(parsed, hi)) });
              }}
            />
          </FormField>

          <FormField
            label="Published date"
            description="Bounds are inclusive, web results only."
          >
            <Select
              disabled={disabled}
              selectedOption={{ label: preset, value: preset }}
              options={DATE_PRESETS.map((p) => ({ label: p.label, value: p.label }))}
              onChange={({ detail }) =>
                applyPreset(detail.selectedOption.value ?? 'Any time')
              }
            />
          </FormField>

          {preset === 'Custom range' ? (
            <ColumnLayout columns={2}>
              <FormField label="From">
                <DatePicker
                  disabled={disabled}
                  value={settings.publishedFrom ?? ''}
                  placeholder="YYYY/MM/DD"
                  onChange={({ detail }) =>
                    onChange({ publishedFrom: detail.value || null })
                  }
                />
              </FormField>
              <FormField label="To">
                <DatePicker
                  disabled={disabled}
                  value={settings.publishedTo ?? ''}
                  placeholder="YYYY/MM/DD"
                  onChange={({ detail }) => onChange({ publishedTo: detail.value || null })}
                />
              </FormField>
            </ColumnLayout>
          ) : (
            <Box variant="small" color="text-body-secondary" padding={{ top: 'xxl' }}>
              {settings.publishedFrom
                ? `From ${settings.publishedFrom} to ${settings.publishedTo}`
                : 'No date restriction.'}
            </Box>
          )}
        </ColumnLayout>

        <ColumnLayout columns={2}>
          <FormField
            label="Only these domains (include)"
            description="Results come back only from these. A root domain also matches subdomains."
            constraintText={`URLs or hosts, one per line. Up to ${constraints.maxDomainsPerList}.`}
          >
            <Textarea
              disabled={disabled}
              value={includeText}
              rows={3}
              placeholder={'python.org\ndocs.aws.amazon.com'}
              onChange={({ detail }) => {
                setIncludeText(detail.value);
                onChange({
                  domainInclude: parseDomains(
                    detail.value,
                    constraints.maxDomainsPerList,
                  ),
                });
              }}
            />
          </FormField>

          <FormField
            label="Never these domains (exclude)"
            description="Results from these are dropped. Exclude wins over include."
            constraintText="Leave both empty to search the whole index."
          >
            <Textarea
              disabled={disabled}
              value={excludeText}
              rows={3}
              placeholder={'reddit.com\nquora.com'}
              onChange={({ detail }) => {
                setExcludeText(detail.value);
                onChange({
                  domainExclude: parseDomains(
                    detail.value,
                    constraints.maxDomainsPerList,
                  ),
                });
              }}
            />
          </FormField>
        </ColumnLayout>

        {overlap.length > 0 && (
          <Alert type="warning">
            In both lists, so they return nothing: {overlap.join(', ')}
          </Alert>
        )}

        {rangeInverted && (
          <Alert type="warning">
            &lsquo;From&rsquo; is after &lsquo;To&rsquo;, so nothing will match.
          </Alert>
        )}

        <ExpandableSection
          headerText="Filters sent with each search"
          variant="footer"
          defaultExpanded={filtersActive}
        >
          {filtersActive ? (
            <div className="payload-scroll">
              <pre>{JSON.stringify(filters, null, 2)}</pre>
            </div>
          ) : (
            <StatusIndicator type="info">
              No filters: the full index, any publication date.
            </StatusIndicator>
          )}
        </ExpandableSection>
      </SpaceBetween>
    </Container>
  );
}
