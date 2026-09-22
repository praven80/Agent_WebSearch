/**
 * Architecture page: one tab per option, each with the diagram and the
 * show-and-tell detail beneath it.
 */

import { useEffect, useState } from 'react';

import Alert from '@cloudscape-design/components/alert';
import Box from '@cloudscape-design/components/box';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import Link from '@cloudscape-design/components/link';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import Table from '@cloudscape-design/components/table';
import Tabs from '@cloudscape-design/components/tabs';

import { ApiError, api } from '../api/client';
import type { ArchitectureOption, SettingsPayload } from '../api/types';

function Diagram({ svg, title }: { svg: string; title: string }) {
  // The SVG is generated server-side by demo/architecture.py, which escapes the
  // dynamic values it interpolates (model id, region, tool name). Rendering it
  // directly keeps it crisp and scalable at projector sizes.
  return (
    <div
      className="arch-diagram"
      role="img"
      aria-label={`Architecture diagram for ${title}`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul>
      {items.map((item, index) => (
        <li key={index}>
          <Box variant="p">{item}</Box>
        </li>
      ))}
    </ul>
  );
}

function OptionDetail({ option }: { option: ArchitectureOption }) {
  return (
    <SpaceBetween size="l">
      <Container>
        <Diagram svg={option.diagramSvg} title={option.title} />
      </Container>

      <Box variant="p">{option.summary}</Box>

      <Table
        variant="embedded"
        header={<Header variant="h3">Components</Header>}
        items={option.components}
        columnDefinitions={[
          { id: 'component', header: 'Component', cell: (c) => c.component },
          { id: 'operatedBy', header: 'Operated by', cell: (c) => c.operatedBy },
          {
            id: 'responsibility',
            header: 'Responsibility',
            cell: (c) => c.responsibility,
          },
        ]}
      />

      <Container header={<Header variant="h3">Request flow</Header>}>
        <ol>
          {option.requestFlow.map((step, index) => (
            <li key={index}>
              <Box variant="p">{step}</Box>
            </li>
          ))}
        </ol>
      </Container>

      <ColumnLayout columns={2}>
        <Container header={<Header variant="h3">You own</Header>}>
          <BulletList items={option.youOwn} />
        </Container>
        <Container header={<Header variant="h3">AWS owns</Header>}>
          <BulletList items={option.awsOwns} />
        </Container>
      </ColumnLayout>

      <ColumnLayout columns={2}>
        <Container header={<Header variant="h3">Security posture</Header>}>
          <SpaceBetween size="s">
            {option.security.map((row) => (
              <div key={row.name}>
                <Box variant="awsui-key-label">{row.name}</Box>
                <Box variant="p">{row.value}</Box>
              </div>
            ))}
          </SpaceBetween>
        </Container>
        <Container header={<Header variant="h3">Cost model</Header>}>
          <SpaceBetween size="s">
            {option.cost.map((row) => (
              <div key={row.name}>
                <Box variant="awsui-key-label">{row.name}</Box>
                <Box variant="p">{row.value}</Box>
              </div>
            ))}
          </SpaceBetween>
        </Container>
      </ColumnLayout>

      <Container
        header={
          <Header variant="h3" description={option.codeCaption}>
            Code
          </Header>
        }
      >
        <div className="payload-scroll">
          <pre>{option.code}</pre>
        </div>
      </Container>

      {option.iam && (
        <Container
          header={
            <Header
              variant="h3"
              description="Two actions, and no bedrock:InvokeModel. The InvokeWebSearch resource ARN is owned by AWS: the account segment is literally 'aws'."
            >
              Gateway service role: outbound permissions
            </Header>
          }
        >
          <div className="payload-scroll">
            <pre>{option.iam}</pre>
          </div>
        </Container>
      )}

      {option.links.length > 0 && (
        <Container header={<Header variant="h3">Reference</Header>}>
          <SpaceBetween size="xs">
            {option.links.map((link) => (
              <Link
                key={link.url}
                href={link.url}
                external
                externalIconAriaLabel="Opens in a new tab"
              >
                {link.label}
              </Link>
            ))}
          </SpaceBetween>
        </Container>
      )}
    </SpaceBetween>
  );
}

export default function ArchitecturePage({ settings }: { settings: SettingsPayload }) {
  const [options, setOptions] = useState<ArchitectureOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .architecture(settings, controller.signal)
      .then((data) => {
        setOptions(data.options);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(caught instanceof ApiError ? caught.message : String(caught));
      });
    return () => controller.abort();
    // Diagrams embed the model id and region, so refetch when those change.
  }, [settings.modelId, settings.gatewayUrl]);

  if (error) {
    return (
      <Alert type="error" header="Could not load the architecture detail">
        {error}
      </Alert>
    );
  }

  if (!options) {
    return (
      <Box textAlign="center" padding="xxl">
        <Spinner size="large" />
      </Box>
    );
  }

  return (
    <SpaceBetween size="l">
      <Box variant="p">
        One diagram per option, with the components, the request flow, the trust
        boundaries, and who owns what. Note that both options share the same
        right-hand side: the difference is entirely on the left.
      </Box>
      <Tabs
        tabs={options.map((option) => ({
          id: option.key,
          label: option.title,
          content: <OptionDetail option={option} />,
        }))}
      />
    </SpaceBetween>
  );
}
