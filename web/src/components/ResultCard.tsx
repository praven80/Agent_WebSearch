/**
 * One column of the side-by-side comparison: verdict, metrics, answer, sources and
 * the execution trace.
 */

import Alert from '@cloudscape-design/components/alert';
import Badge from '@cloudscape-design/components/badge';
import Box from '@cloudscape-design/components/box';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import Header from '@cloudscape-design/components/header';
import Link from '@cloudscape-design/components/link';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import type { ModeInfo, RunResult } from '../api/types';
import Markdown from './Markdown';

function money(value: number): string {
  if (value <= 0) return '-';
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(3)}`;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <Box variant="awsui-key-label">{label}</Box>
      <Box variant="p" fontWeight="bold">
        {value}
      </Box>
    </div>
  );
}

function Verdict({ result, mode }: { result: RunResult; mode: ModeInfo }) {
  if (!result.ok) {
    return (
      <Alert type="error" header="Run failed">
        {result.error}
      </Alert>
    );
  }
  if (result.grounded) {
    return (
      <Alert type="success">
        Grounded in {result.citations.length} live source
        {result.citations.length === 1 ? '' : 's'} retrieved during this run.
      </Alert>
    );
  }
  // Nothing retrieved. Why that happened matters: for the option with no
  // retrieval it is the point of the option, and for the option with retrieval
  // available it is usually the model deciding it already knew the answer. Only
  // a search that ran and came back empty is a genuine miss.
  if (!mode.offersSearch) {
    return (
      <Alert type="warning">
        Not grounded: this option has no retrieval, so no claim here can be traced
        to a source.
      </Alert>
    );
  }
  if (result.toolCalls.length === 0) {
    return (
      <Alert type="info">
        The model chose not to search: it judged the answer to be settled knowledge
        and answered directly, so nothing here is grounded. The connector was
        available and cost nothing. Ask about something recent to see it used.
      </Alert>
    );
  }
  return (
    <Alert type="warning">
      Searched, but nothing usable came back, so no claim here can be traced to a
      source. Check the trace for the query the model chose and any active filters.
    </Alert>
  );
}

function Sources({ result, mode }: { result: RunResult; mode: ModeInfo }) {
  if (result.citations.length === 0) {
    let reason = 'this option retrieved nothing.';
    if (mode.offersSearch) {
      reason =
        result.toolCalls.length === 0
          ? 'the model answered from training data and did not search.'
          : 'the search ran but returned nothing usable.';
    }
    return (
      <Box variant="small" color="text-body-secondary">
        No sources: {reason}
      </Box>
    );
  }
  // Spell out the arithmetic when there was more than one search. The per-search
  // cap is set in the search controls, so a run that searched three times can
  // return roughly three times that many sources, which otherwise looks like the
  // cap being ignored.
  const heading =
    result.metrics.searchQueries > 1
      ? `Sources (${result.citations.length} unique, across ${result.metrics.searchQueries} searches)`
      : `Sources (${result.citations.length})`;

  return (
    <ExpandableSection headerText={heading} variant="footer">
      <SpaceBetween size="m">
        {result.citations.map((citation, index) => (
          <div key={`${citation.url}-${index}`}>
            <Box variant="strong">
              {index + 1}.{' '}
              {citation.url ? (
                <Link href={citation.url} external externalIconAriaLabel="Opens in a new tab">
                  {citation.displayTitle}
                </Link>
              ) : (
                citation.displayTitle
              )}
            </Box>
            {(citation.domain || citation.publishedDate) && (
              <Box variant="small" color="text-body-secondary">
                {[citation.domain, citation.publishedDate].filter(Boolean).join(' · ')}
              </Box>
            )}
            {citation.snippet && (
              <Box variant="small" color="text-body-secondary">
                {citation.snippet}
              </Box>
            )}
          </div>
        ))}
      </SpaceBetween>
    </ExpandableSection>
  );
}

function Trace({ result }: { result: RunResult }) {
  return (
    <ExpandableSection headerText="Execution trace" variant="footer">
      <SpaceBetween size="m">
        {result.trace.length > 0 && (
          <div>
            <Box variant="awsui-key-label">Setup</Box>
            <ul>
              {result.trace.map((line, index) => (
                <li key={index}>
                  <Box variant="small">{line}</Box>
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.toolCalls.length === 0 ? (
          <Box variant="small" color="text-body-secondary">
            No tool calls: the model answered directly.
          </Box>
        ) : (
          <SpaceBetween size="l">
            <Box variant="awsui-key-label">
              Tool calls ({result.toolCalls.length})
            </Box>
            {result.toolCalls.map((call, index) => (
              <SpaceBetween size="xs" key={`${call.name}-${index}`}>
                <Box variant="strong">
                  {index + 1}. <code>{call.name}</code>{' '}
                  <Badge color="grey">{call.durationSeconds.toFixed(2)}s</Badge>{' '}
                  {call.error ? (
                    <StatusIndicator type="error">{call.error}</StatusIndicator>
                  ) : (
                    <Box variant="small" display="inline">
                      {call.resultSummary}
                    </Box>
                  )}
                </Box>

                <Box variant="awsui-key-label">Arguments the model chose</Box>
                <div className="payload-scroll">
                  <pre>{JSON.stringify(call.arguments, null, 2)}</pre>
                </div>

                {call.rawResult && (
                  <>
                    <Box variant="awsui-key-label">
                      Tool result sent to the model: complete payload,{' '}
                      {call.rawResultChars.toLocaleString()} characters
                    </Box>
                    <div className="payload-scroll">
                      <pre>{call.rawResult}</pre>
                    </div>
                  </>
                )}
              </SpaceBetween>
            ))}
          </SpaceBetween>
        )}
      </SpaceBetween>
    </ExpandableSection>
  );
}

interface ResultCardProps {
  mode: ModeInfo;
  result: RunResult | null;
  running: boolean;
  error: string | null;
}

export default function ResultCard({ mode, result, running, error }: ResultCardProps) {
  return (
    <Container
      header={
        <Header
          variant="h3"
          description={mode.tagline}
          info={
            mode.ready ? undefined : (
              <StatusIndicator type="stopped">Not ready</StatusIndicator>
            )
          }
        >
          {mode.icon} {mode.title}
        </Header>
      }
    >
      <SpaceBetween size="m">
        {running && (
          <Box textAlign="center" padding="l">
            <SpaceBetween size="s" alignItems="center">
              <Spinner size="large" />
              <Box variant="small" color="text-body-secondary">
                Running…
              </Box>
            </SpaceBetween>
          </Box>
        )}

        {!running && error && (
          <Alert type="error" header="Could not run this option">
            {error}
          </Alert>
        )}

        {!running && !error && !result && (
          <SpaceBetween size="m">
            <StatusIndicator type="pending">Not run yet</StatusIndicator>
            <ExpandableSection
              headerText="Explanation: what this option does and why"
              variant="footer"
            >
              <ul>
                {mode.explanation.map((point, index) => (
                  <li key={index}>
                    <Box variant="small">{point}</Box>
                  </li>
                ))}
              </ul>
            </ExpandableSection>
          </SpaceBetween>
        )}

        {!running && result && (
          <>
            <Verdict result={result} mode={mode} />

            <ColumnLayout columns={3} variant="text-grid">
              <Metric label="Latency" value={`${result.metrics.latencySeconds.toFixed(1)}s`} />
              <Metric label="Tokens" value={result.metrics.totalTokens.toLocaleString()} />
              <Metric label="Est. cost" value={money(result.metrics.totalCostUsd)} />
              <Metric label="Searches" value={result.metrics.searchQueries} />
              <Metric label="Sources" value={result.citations.length} />
              <Metric label="Model cycles" value={result.metrics.modelCycles} />
            </ColumnLayout>

            {result.metrics.searchCostUsd > 0 && (
              <Box variant="small" color="text-body-secondary">
                Model {money(result.metrics.modelCostUsd)} + search{' '}
                {money(result.metrics.searchCostUsd)} ({result.metrics.searchQueries} ×
                $0.007)
              </Box>
            )}

            {result.answer && (
              <div>
                <Box variant="awsui-key-label">Answer</Box>
                <Markdown>{result.answer}</Markdown>
              </div>
            )}

            <Sources result={result} mode={mode} />
            <Trace result={result} />
            <ExpandableSection
              headerText="Explanation: what this option does and why"
              variant="footer"
            >
              <ul>
                {mode.explanation.map((point, index) => (
                  <li key={index}>
                    <Box variant="small">{point}</Box>
                  </li>
                ))}
              </ul>
            </ExpandableSection>
          </>
        )}
      </SpaceBetween>
    </Container>
  );
}
