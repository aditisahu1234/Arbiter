import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App'
import Dashboard from './pages/Dashboard'
import Markets from './pages/Markets'
import AssetDetail from './pages/AssetDetail'
import Screener from './pages/Screener'
import StrategyLab from './pages/StrategyLab'
import Backtest from './pages/Backtest'
import RiskAnalytics from './pages/RiskAnalytics'
import CAPMFF3 from './pages/CAPMFF3'
import Observability from './pages/Observability'

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'markets', element: <Markets /> },
      { path: 'asset/:symbol', element: <AssetDetail /> },
      { path: 'screener', element: <Screener /> },
      { path: 'strategy', element: <StrategyLab /> },
      { path: 'backtest', element: <Backtest /> },
      { path: 'risk', element: <RiskAnalytics /> },
      { path: 'capm-ff3', element: <CAPMFF3 /> },
      { path: 'observability', element: <Observability /> },
    ],
  },
])

export default function Router() {
  return <RouterProvider router={router} />
}
