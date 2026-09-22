/**
 * Application shell: AWS-console layout, readiness banner, and page routing.
 */

import { useState } from 'react';

import Alert from '@cloudscape-design/components/alert';
import AppLayout from '@cloudscape-design/components/app-layout';
import Box from '@cloudscape-design/components/box';
import BreadcrumbGroup from '@cloudscape-design/components/breadcrumb-group';
import ContentLayout from '@cloudscape-design/components/content-layout';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import StatusIndicator from '@cloudscape-design/components/status-indicator';

import SettingsPanel from './components/SettingsPanel';
import ArchitecturePage from './pages/ArchitecturePage';
import ComparisonPage from './pages/ComparisonPage';
import RunPage from './pages/RunPage';
import SideNav from './shell/SideNav';
import TopBar from './shell/TopBar';
import { PAGE_TITLES, useHashPage } from './shell/navigation';
import { useDemoState } from './state/useDemoState';

const PAGE_DESCRIPTIONS: Record<string, string> = {
  run: 'The same question and the same model, with and without the managed Web Search connector on an AgentCore Gateway.',
  architecture:
    'How each option is wired, who operates each component, and where the trust boundaries fall.',
  comparison:
    'Every dimension that differs between answering from training data and grounding in the Amazon web index.',
};

export default function App() {
  const [page, navigate] = useHashPage();
  const [navOpen, setNavOpen] = useState(true);
  // The drawer holds environment setup only. It starts closed so the Run page gets
  // the full width; the search controls a presenter actually touches are on the
  // page itself.
  const [toolsOpen, setToolsOpen] = useState(false);
  const {
    loading,
    loadError,
    bootstrap,
    settings,
    readiness,
    readinessPending,
    updateSettings,
  } = useDemoState();

  const credentialsOk = readiness?.credentials.ok ?? false;
  const region = readiness?.settings.awsRegion ?? bootstrap?.settings.awsRegion ?? '-';

  const notReadyModes = (readiness?.modes ?? []).filter((mode) => !mode.ready);

  const content = () => {
    if (loading) {
      return (
        <Box textAlign="center" padding="xxl">
          <SpaceBetween size="s" alignItems="center">
            <Spinner size="large" />
            <Box variant="p">Loading configuration…</Box>
          </SpaceBetween>
        </Box>
      );
    }

    if (loadError && !bootstrap) {
      return (
        <Alert type="error" header="Cannot reach the demo backend">
          <SpaceBetween size="s">
            <Box variant="p">{loadError}</Box>
            <Box variant="p">
              Start it with:{' '}
              <code>.venv/bin/uvicorn api.main:app --reload --port 8000</code>
            </Box>
          </SpaceBetween>
        </Alert>
      );
    }

    if (!bootstrap || !settings) {
      return null;
    }

    if (page === 'architecture') {
      return <ArchitecturePage settings={settings} />;
    }
    if (page === 'comparison') {
      return <ComparisonPage regions={bootstrap.constraints.webSearchRegions} />;
    }
    return (
      <RunPage
        bootstrap={bootstrap}
        settings={settings}
        modes={readiness?.modes ?? []}
        filtersSummary={readiness?.settings.filtersSummary ?? 'none'}
        filtersActive={readiness?.settings.filtersActive ?? false}
        onSettingsChange={updateSettings}
      />
    );
  };

  return (
    <>
      <TopBar region={region} credentialsOk={credentialsOk} />
      <AppLayout
        headerSelector="#top-nav"
        navigationOpen={navOpen}
        onNavigationChange={({ detail }) => setNavOpen(detail.open)}
        navigation={<SideNav page={page} onNavigate={navigate} />}
        toolsOpen={toolsOpen}
        onToolsChange={({ detail }) => setToolsOpen(detail.open)}
        toolsHide={!bootstrap || !settings}
        tools={
          bootstrap && settings ? (
            <SettingsPanel
              bootstrap={bootstrap}
              settings={settings}
              readiness={readiness}
              onChange={updateSettings}
            />
          ) : undefined
        }
        breadcrumbs={
          <BreadcrumbGroup
            items={[
              { text: 'Amazon Bedrock AgentCore', href: '#/run' },
              { text: 'Web Search demo', href: '#/run' },
              { text: PAGE_TITLES[page], href: `#/${page}` },
            ]}
            onFollow={(event) => {
              event.preventDefault();
              const target = event.detail.href.replace(/^#\//, '');
              if (target) navigate(target as typeof page);
            }}
          />
        }
        content={
          <ContentLayout
            header={
              <SpaceBetween size="m">
                <Header
                  variant="h1"
                  description={PAGE_DESCRIPTIONS[page]}
                  actions={
                    readinessPending ? (
                      <StatusIndicator type="loading">Checking readiness</StatusIndicator>
                    ) : credentialsOk ? (
                      <StatusIndicator type="success">Connected</StatusIndicator>
                    ) : (
                      <StatusIndicator type="warning">No AWS credentials</StatusIndicator>
                    )
                  }
                >
                  Web Search on Amazon Bedrock AgentCore
                </Header>

                {!loading && !credentialsOk && readiness && (
                  <Alert type="warning" header="AWS credentials are not usable">
                    <SpaceBetween size="xs">
                      <Box variant="p">{readiness.credentials.message}</Box>
                      <Box variant="p">
                        Export credentials in the shell running the API and restart it.
                      </Box>
                    </SpaceBetween>
                  </Alert>
                )}

                {!loading && credentialsOk && notReadyModes.length > 0 && (
                  <Alert type="info" header="Some options are not ready">
                    <ul>
                      {notReadyModes.map((mode) => (
                        <li key={mode.key}>
                          <Box variant="p">
                            {mode.title} ({mode.readyReason})
                          </Box>
                        </li>
                      ))}
                    </ul>
                  </Alert>
                )}

                {loadError && bootstrap && (
                  <Alert type="error" header="Backend request failed">
                    {loadError}
                  </Alert>
                )}
              </SpaceBetween>
            }
          >
            {content()}
          </ContentLayout>
        }
      />
    </>
  );
}
