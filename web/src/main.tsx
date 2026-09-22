import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// Cloudscape global styles must be imported once, before any component renders.
import '@cloudscape-design/global-styles/index.css';

import App from './App';
import './styles.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Root element #root is missing from index.html');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
