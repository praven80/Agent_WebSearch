/**
 * Side-by-side page: the dimension-by-dimension table and the closing points.
 */

import { useEffect, useState } from 'react';

import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import Link from '@cloudscape-design/components/link';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import Table from '@cloudscape-design/components/table';

import { ApiError, api } from '../api/client';
import type { Comparison } from '../api/types';

const DOC_LINKS = [
  {
    label: 'Web Search Tool: AgentCore Developer Guide',
    url: 'https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html',
  },
  {
    label: 'Introducing Web Search on Amazon Bedrock AgentCore: AWS ML Blog',
    url: 'https://aws.amazon.com/blogs/machine-learning/introducing-web-search-on-amazon-bedrock-agentcore/',
  },
];

export default function ComparisonPage({ regions }: { regions: string[] }) {
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .comparison(controller.signal)
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof ApiError ? caught.message : String(caught));
      });
    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <Alert type="error" header="Could not load the comparison">
        {error}
      </Alert>
    );
  }

  if (!data) {
    return (
      <Box textAlign="center" padding="xxl">
        <Spinner size="large" />
      </Box>
    );
  }

  return (
    <SpaceBetween size="l">
      <Table
        variant="container"
        header={
          <Header variant="h2" counter={`(${data.rows.length})`}>
            The two options, dimension by dimension
          </Header>
        }
        items={data.rows}
        columnDefinitions={[
          {
            id: 'dimension',
            header: 'Dimension',
            cell: (row) => <Box variant="strong">{row.dimension}</Box>,
            width: 260,
          },
          { id: 'noSearch', header: '1. No web search', cell: (row) => row.noSearch },
          {
            id: 'withAgentCore',
            header: '2. Web search with AgentCore',
            cell: (row) => row.withAgentCore,
          },
        ]}
      />

      <Container header={<Header variant="h2">What to take away</Header>}>
        <ul>
          {data.closingPoints.map((point, index) => (
            <li key={index}>
              <Box variant="p">{point}</Box>
            </li>
          ))}
        </ul>
      </Container>

      <Container header={<Header variant="h2">Reference</Header>}>
        <SpaceBetween size="s">
          {DOC_LINKS.map((link) => (
            <Link
              key={link.url}
              href={link.url}
              external
              externalIconAriaLabel="Opens in a new tab"
            >
              {link.label}
            </Link>
          ))}
          <Box variant="small" color="text-body-secondary">
            Web Search is available in {regions.join(', ')}. Search results must be
            displayed with their source citations, and may not be used to build a
            competing index.
          </Box>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
