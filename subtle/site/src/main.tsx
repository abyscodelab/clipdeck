import {createRoot} from 'react-dom/client';
import App from './App';
import './styles.css';
import {initAnalytics, trackScrollDepth} from './analytics';

createRoot(document.getElementById('root')!).render(<App />);
initAnalytics();
trackScrollDepth();
