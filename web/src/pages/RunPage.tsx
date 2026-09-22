/**
 * Run page: ask one question, run both options, compare side by side.
 *
 * Both options are fired in parallel so each column renders as soon as it lands.
 */

import { useCallback, useState } from 'react';

import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Checkbox from '@cloudscape-design/components/checkbox';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import Form from '@cloudscape-design/components/form';
import FormField from '@cloudscape-design/components/form-field';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Table from '@cloudscape-design/components/table';
import Textarea from '@cloudscape-design/components/textarea';

import { ApiError, api } from '../api/client';
import type { Bootstrap, ModeInfo, RunResult, SettingsPayload } from '../api/types';
import ResultCard from '../components/ResultCard';
import SearchControls from '../components/SearchControls';

interface RunPageProps {
  bootstrap: Bootstrap;
  settings: SettingsPayload;
  modes: ModeInfo[];
  filtersSummary: string;
  filtersActive: boolean;
  onSettingsChange: (patch: Partial<SettingsPayload>) => void;
}

export default function RunPage({
  bootstrap,
  settings,
  modes,
  filtersSummary,
  filtersActive,
  onSettingsChange,
}: RunPageProps) {
  const [question, setQuestion] = useState(bootstrap.sampleQuestions[0] ?? '');
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, RunResult>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [ranQuestion, setRanQuestion] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  // Default to every ready option, but let an explicit choice stick.
  const isSelected = (mode: ModeInfo) => selected[mode.key] ?? mode.ready;

  const anyRunning = Object.values(running).some(Boolean);

  const runAll = useCallback(async () => {
    const trimmed = question.trim();
    if (!trimmed) {
      setFormError('Enter a question first.');
      return;
    }
    const chosen = modes.filter((mode) => isSelected(mode) && mode.ready);
    if (chosen.length === 0) {
      setFormError('Select at least one option that is ready to run.');
      return;
    }

    setFormError(null);
    setRanQuestion(trimmed);
    setResults({});
    setErrors({});
    setRunning(Object.fromEntries(chosen.map((m) => [m.key, true])));

    // Parallel: the columns are independent, and the demo should not wait for the
    // slower option before showing the faster one.
    await Promise.all(
      chosen.map(async (mode) => {
        try {
          const response = await api.run(mode.key, trimmed, settings);
          setResults((current) => ({ ...current, [mode.key]: response.result }));
        } catch (error: unknown) {
          setErrors((current) => ({
            ...current,
            [mode.key]: error instanceof ApiError ? error.message : String(error),
          }));
        } finally {
          setRunning((current) => ({ ...current, [mode.key]: false }));
        }
      }),
    );
  }, [question, modes, settings, selected]);

  const hasOutput =
    Object.keys(results).length > 0 ||
    Object.keys(errors).length > 0 ||
    anyRunning;

  const summaryRows = modes
    .filter((mode) => results[mode.key])
    .map((mode) => {
      const result = results[mode.key];
      return {
        option: `${mode.number}. ${mode.label}`,
        grounded: result.grounded ? 'Yes' : 'No',
        sources: result.citations.length,
        searches: result.metrics.searchQueries,
        latency: `${result.metrics.latencySeconds.toFixed(1)}s`,
        tokens: result.metrics.totalTokens.toLocaleString(),
        cost:
          result.metrics.totalCostUsd > 0
            ? `$${result.metrics.totalCostUsd.toFixed(4)}`
            : '-',
      };
    });

  return (
    <SpaceBetween size="l">
      <Container
        header={
          <Header
            variant="h2"
            description="Ask one question and watch the same model answer it with and without the managed Web Search tool. Nothing changes between the columns except whether the tool is attached."
          >
            Question
          </Header>
        }
      >
        <Form
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button
                variant="primary"
                loading={anyRunning}
                onClick={runAll}
                data-testid="run-comparison"
              >
                Run comparison
              </Button>
            </SpaceBetween>
          }
          errorText={formError}
        >
          <SpaceBetween size="m">
            <FormField
              label="Question"
              description={`Web Search accepts queries up to ${bootstrap.constraints.maxQueryChars} characters; the model shortens long questions into a query itself. The model also decides whether to search at all, so ask about something recent or changing. Settled facts get answered from training data and Option 2 will show no sources.`}
            >
              <Textarea
                value={question}
                rows={3}
                onChange={({ detail }) => setQuestion(detail.value)}
              />
            </FormField>

            <FormField
              label="Sample questions"
              description="Each of these has an answer that changes faster than a training run."
            >
              <SpaceBetween direction="horizontal" size="xs">
                {bootstrap.sampleQuestions.map((sample, index) => (
                  <Button
                    key={index}
                    onClick={() => setQuestion(sample)}
                    disabled={anyRunning}
                  >
                    {sample.length > 40 ? `${sample.slice(0, 38)}…` : sample}
                  </Button>
                ))}
              </SpaceBetween>
            </FormField>

            <FormField label="Options to run">
              <SpaceBetween size="xs">
                {modes.map((mode) => (
                  <Checkbox
                    key={mode.key}
                    checked={isSelected(mode)}
                    disabled={!mode.ready || anyRunning}
                    onChange={({ detail }) =>
                      setSelected((current) => ({
                        ...current,
                        [mode.key]: detail.checked,
                      }))
                    }
                  >
                    {mode.icon} {mode.title}{' '}
                    <Box variant="small" color="text-body-secondary" display="inline">
                      ({mode.readyReason})
                    </Box>
                  </Checkbox>
                ))}
              </SpaceBetween>
            </FormField>

            {filtersActive && (
              <Alert type="info">Search filters in effect: {filtersSummary}</Alert>
            )}
          </SpaceBetween>
        </Form>
      </Container>

      <SearchControls
        constraints={bootstrap.constraints}
        settings={settings}
        disabled={anyRunning}
        onChange={onSettingsChange}
      />

      {hasOutput && (
        <Container
          header={
            <Header variant="h2" description={ranQuestion}>
              Results
            </Header>
          }
        >
          <SpaceBetween size="l">
            <ColumnLayout columns={modes.length === 1 ? 1 : 2}>
              {modes.map((mode) => (
                <ResultCard
                  key={mode.key}
                  mode={mode}
                  result={results[mode.key] ?? null}
                  running={running[mode.key] ?? false}
                  error={errors[mode.key] ?? null}
                />
              ))}
            </ColumnLayout>

            {summaryRows.length > 0 && (
              <Table
                variant="embedded"
                header={<Header variant="h3">This run, side by side</Header>}
                items={summaryRows}
                columnDefinitions={[
                  { id: 'option', header: 'Option', cell: (r) => r.option },
                  { id: 'grounded', header: 'Grounded', cell: (r) => r.grounded },
                  { id: 'sources', header: 'Sources', cell: (r) => r.sources },
                  { id: 'searches', header: 'Searches', cell: (r) => r.searches },
                  { id: 'latency', header: 'Latency', cell: (r) => r.latency },
                  { id: 'tokens', header: 'Tokens', cell: (r) => r.tokens },
                  { id: 'cost', header: 'Est. cost', cell: (r) => r.cost },
                ]}
              />
            )}
          </SpaceBetween>
        </Container>
      )}

      {!hasOutput && (
        <Container header={<Header variant="h2">Options</Header>}>
          <ColumnLayout columns={modes.length === 1 ? 1 : 2}>
            {modes.map((mode) => (
              <ResultCard
                key={mode.key}
                mode={mode}
                result={null}
                running={false}
                error={null}
              />
            ))}
          </ColumnLayout>
        </Container>
      )}
    </SpaceBetween>
  );
}
