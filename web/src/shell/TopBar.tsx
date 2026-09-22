/**
 * The AWS-console style top navigation bar.
 */

import TopNavigation from '@cloudscape-design/components/top-navigation';

interface TopBarProps {
  region: string;
  credentialsOk: boolean;
}

export default function TopBar({ region, credentialsOk }: TopBarProps) {
  return (
    <div id="top-nav">
      <TopNavigation
        identity={{
          href: '#/run',
          title: 'Amazon Bedrock AgentCore',
          logo: undefined,
        }}
        utilities={[
          {
            type: 'menu-dropdown',
            // Deliberately no account id or role name here: this is shown to
            // customers.
            text: credentialsOk ? 'Connected' : 'No credentials',
            description: credentialsOk ? undefined : 'Credentials unavailable',
            iconName: 'user-profile',
            items: [
              {
                id: 'region',
                text: `Region: ${region}`,
                disabled: true,
              },
            ],
          },
        ]}
      />
    </div>
  );
}
