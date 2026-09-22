/**
 * Console-style left navigation.
 */

import SideNavigation from '@cloudscape-design/components/side-navigation';

import { PAGE_TITLES, type PageId } from './navigation';

interface SideNavProps {
  page: PageId;
  onNavigate: (page: PageId) => void;
}

export default function SideNav({ page, onNavigate }: SideNavProps) {
  return (
    <SideNavigation
      activeHref={`#/${page}`}
      header={{ href: '#/run', text: 'Web Search' }}
      onFollow={(event) => {
        // Cloudscape navigates by href; intercept so the hash drives our own
        // lightweight routing without a full page load.
        if (event.detail.external) {
          return;
        }
        event.preventDefault();
        const next = event.detail.href.replace(/^#\//, '') as PageId;
        onNavigate(next);
      }}
      items={[
        { type: 'link', text: PAGE_TITLES.run, href: '#/run' },
        { type: 'link', text: PAGE_TITLES.architecture, href: '#/architecture' },
        { type: 'link', text: PAGE_TITLES.comparison, href: '#/comparison' },
        { type: 'divider' },
        {
          type: 'link',
          text: 'Web Search Tool docs',
          href: 'https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html',
          external: true,
          externalIconAriaLabel: 'Opens in a new tab',
        },
        {
          type: 'link',
          text: 'Launch blog post',
          href: 'https://aws.amazon.com/blogs/machine-learning/introducing-web-search-on-amazon-bedrock-agentcore/',
          external: true,
          externalIconAriaLabel: 'Opens in a new tab',
        },
      ]}
    />
  );
}
