import { Link, NavLink, Outlet } from 'react-router-dom'
import { useUiStore } from '../../stores/ui'
import styles from './AppShell.module.css'

const NAV_ITEMS = [
  { to: '/folders', label: '收藏夹' },
  { to: '/import', label: '导入' },
  { to: '/tasks', label: '任务' },
  { to: '/items', label: '知识库' },
  { to: '/history', label: '对话历史' },
]

export default function AppShell() {
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useUiStore((s) => s.toggleSidebar)

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.logo}>◆ BiliRag</div>
        <div className={styles.topActions}>
          <button type="button" className={styles.loginBtn}>
            登录
          </button>
          <Link to="/settings" className={styles.settingsBtn} title="设置">
            ⚙
          </Link>
        </div>
      </header>

      <div className={styles.body}>
        <aside className={sidebarCollapsed ? styles.sidebarCollapsed : styles.sidebar}>
          <button type="button" className={styles.toggle} onClick={toggleSidebar}>
            ☰
          </button>
          {!sidebarCollapsed && (
            <nav className={styles.nav}>
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => (isActive ? styles.navItemActive : styles.navItem)}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          )}
        </aside>

        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
