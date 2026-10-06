import { createBrowserRouter, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import FoldersPage from './pages/FoldersPage'
import HistoryPage from './pages/HistoryPage'
import ImportPage from './pages/ImportPage'
import ItemsPage from './pages/ItemsPage'
import SettingsPage from './pages/SettingsPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/folders" replace /> },
      { path: 'folders', element: <FoldersPage /> },
      { path: 'import', element: <ImportPage /> },
      { path: 'items', element: <ItemsPage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
])
